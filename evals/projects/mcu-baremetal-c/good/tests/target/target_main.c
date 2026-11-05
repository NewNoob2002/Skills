/* 目标级冒烟测试：在 QEMU mps2-an386（Cortex-M4）上运行被测的 ledctl、bsp/board_tick
 * 与 platform/board/vectors.c 中的 SysTick 中断入口。
 *
 * 与 host 单元测试的区别：这里的代码由 arm-none-eabi-gcc 编译链接，节拍来自真实的 SysTick
 * 异常（经向量表分发），能发现向量名不匹配、中断未使能、链接缺符号等 host 上看不到的问题。
 * LED 写入用 fake 记录，不访问 board_regs.h 中虚构的 GPIO 地址。
 * 期望值来自模块规格：初始化写一次熄灭，之后每 HALF_PERIOD 个节拍翻转一次。 */
#include <stdbool.h>
#include <stdint.h>

#include "board_tick.h"
#include "ledctl.h"
#include "semihost.h"

#define HALF_PERIOD    (50U)
#define RUN_TICKS      (200U)
#define EXPECTED_WRITE (1U + RUN_TICKS / HALF_PERIOD)

/* Armv7-M SysTick 寄存器（ARMv7-M ARM B3.3）；mps2-an386 的处理器时钟为 25 MHz。 */
#define SYST_CSR (*(volatile uint32_t *)0xE000E010UL)
#define SYST_RVR (*(volatile uint32_t *)0xE000E014UL)
#define SYST_CVR (*(volatile uint32_t *)0xE000E018UL)
#define SYST_CSR_ENABLE_TICKINT_CLKSRC (0x7UL)
#define SYST_RELOAD_1MS (25000UL - 1UL)

static uint32_t s_writes;
static bool s_level;

static proj_err_t fake_write(void *p_ctx, bool b_high)
{
	(void)p_ctx;
	s_writes++;
	s_level = b_high;
	return PROJ_ERR_OK;
}

static gpio_if_t const s_gpio = {fake_write, 0};
static ledctl_t s_led;

int target_main(void)
{
	SYST_RVR = SYST_RELOAD_1MS;
	SYST_CVR = 0U;
	SYST_CSR = SYST_CSR_ENABLE_TICKINT_CLKSRC;

	if (ledctl_init(&s_led, &s_gpio, HALF_PERIOD) != PROJ_ERR_OK) {
		semihost_puts("FAIL: ledctl_init\n");
		return 1;
	}

	/* 与 app/main.c 相同的推进方式：按节拍差值逐个调用 ledctl_tick。 */
	uint32_t const start = board_tick_now();
	uint32_t last = start;

	while ((uint32_t)(last - start) < RUN_TICKS) {
		uint32_t const now = board_tick_now();

		while ((uint32_t)(now - last) > 0U && (uint32_t)(last - start) < RUN_TICKS) {
			last++;
			(void)ledctl_tick(&s_led);
		}
	}
	SYST_CSR = 0U;

	if (s_writes != EXPECTED_WRITE || s_level != false) {
		semihost_puts("FAIL: unexpected LED write count or final level\n");
		return 1;
	}
	semihost_puts("PASS: target smoke (200 SysTick ticks, 5 LED writes)\n");
	return 0;
}
