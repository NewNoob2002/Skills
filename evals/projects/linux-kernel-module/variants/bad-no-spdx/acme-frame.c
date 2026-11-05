/*
 * ACME frame receiver: platform driver that validates fixed-format frames
 * read from a memory-mapped FIFO.
 *
 * Evaluation sample only: the "acme,frame-rx" device and its register layout
 * are fictional and do not correspond to real hardware.
 */

#include <linux/device.h>
#include <linux/err.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/mod_devicetable.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/types.h>

#define ACME_FRAME_REG_STATUS	0x00
#define ACME_FRAME_REG_DATA	0x04
#define ACME_FRAME_STATUS_READY	BIT(0)

#define ACME_FRAME_SOF		0xa5
#define ACME_FRAME_HDR_LEN	2
#define ACME_FRAME_MAX_PAYLOAD	32

struct acme_frame_priv {
	struct device *dev;
	void __iomem *base;
	spinlock_t lock;	/* protects frames_ok and frames_bad */
	u32 frames_ok;
	u32 frames_bad;
};

/*
 * Frame layout: SOF, payload length, payload, XOR checksum of the payload.
 * Returns the payload length, or -EINVAL for a malformed frame.
 */
static int acme_frame_validate(const u8 *buf, size_t len)
{
	size_t payload_len;
	u8 sum = 0;
	size_t i;

	if (len < ACME_FRAME_HDR_LEN + 1 || buf[0] != ACME_FRAME_SOF)
		return -EINVAL;

	payload_len = buf[1];
	if (payload_len > ACME_FRAME_MAX_PAYLOAD ||
	    len != ACME_FRAME_HDR_LEN + payload_len + 1)
		return -EINVAL;

	for (i = 0; i < payload_len; i++)
		sum ^= buf[ACME_FRAME_HDR_LEN + i];

	if (sum != buf[len - 1])
		return -EINVAL;

	return payload_len;
}

static irqreturn_t acme_frame_irq_thread(int irq, void *data)
{
	struct acme_frame_priv *priv = data;
	u8 buf[ACME_FRAME_HDR_LEN + ACME_FRAME_MAX_PAYLOAD + 1];
	size_t len = 0;
	int ret;

	while (len < sizeof(buf) &&
	       (readl(priv->base + ACME_FRAME_REG_STATUS) & ACME_FRAME_STATUS_READY))
		buf[len++] = readl(priv->base + ACME_FRAME_REG_DATA) & 0xff;

	ret = acme_frame_validate(buf, len);

	spin_lock(&priv->lock);
	if (ret < 0)
		priv->frames_bad++;
	else
		priv->frames_ok++;
	spin_unlock(&priv->lock);

	if (ret < 0)
		dev_dbg(priv->dev, "dropped malformed frame (%zu bytes)\n", len);

	return IRQ_HANDLED;
}

static int acme_frame_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct acme_frame_priv *priv;
	int irq;
	int ret;

	priv = devm_kzalloc(dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	priv->dev = dev;
	spin_lock_init(&priv->lock);

	priv->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(priv->base))
		return PTR_ERR(priv->base);

	irq = platform_get_irq(pdev, 0);
	if (irq < 0)
		return irq;

	ret = devm_request_threaded_irq(dev, irq, NULL, acme_frame_irq_thread,
					IRQF_ONESHOT, dev_name(dev), priv);
	if (ret)
		return dev_err_probe(dev, ret, "failed to request irq %d\n", irq);

	platform_set_drvdata(pdev, priv);
	return 0;
}

static const struct of_device_id acme_frame_of_match[] = {
	{ .compatible = "acme,frame-rx" },
	{ }
};
MODULE_DEVICE_TABLE(of, acme_frame_of_match);

static struct platform_driver acme_frame_driver = {
	.probe = acme_frame_probe,
	.driver = {
		.name = "acme-frame",
		.of_match_table = acme_frame_of_match,
	},
};
module_platform_driver(acme_frame_driver);

MODULE_DESCRIPTION("ACME frame receiver (evaluation sample)");
MODULE_LICENSE("GPL");
