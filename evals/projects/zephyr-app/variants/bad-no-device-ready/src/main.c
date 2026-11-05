/*
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <app/frame_parser.h>

LOG_MODULE_REGISTER(frame_app, LOG_LEVEL_INF);

static const struct device *const console = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

static const uint8_t demo_frame[] = {FRAME_START, 2U, 0x10U, 0x20U, 0x32U};

int main(void)
{
	struct frame frame;
	int ret;

	ret = frame_parse(demo_frame, sizeof(demo_frame), &frame);
	if (ret < 0) {
		LOG_ERR("parse failed: %d", ret);
		return ret;
	}

	LOG_INF("frame with %u payload bytes on %s", frame.len, console->name);

	return 0;
}
