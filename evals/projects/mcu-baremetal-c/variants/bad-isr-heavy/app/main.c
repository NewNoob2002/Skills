/** @file main.c
 *
 * @brief 组合根：把板载 LED 绑定到 ledctl。
 *
 * 本变体把节拍推进放进 app_led_service()，
 * 由 SysTick 中断直接调用（违反 ISR-001）。
 */
#include <stdint.h>

#include "board_led.h"
#include "ledctl.h"

/* LED 半周期：500 个节拍。 */
#define APP_LED_HALF_PERIOD_TICKS (500U)

static ledctl_t g_led;

/* 由 platform/board/vectors.c 的 SysTick 中断调用。 */
void app_led_service (void);

void
app_led_service (void)
{
    (void) ledctl_tick(&g_led);
}

int
main (void)
{
    if (PROJ_ERR_OK !=
        ledctl_init(&g_led, board_led_gpio(), APP_LED_HALF_PERIOD_TICKS))
    {
        for (;;)
        {
            /* 初始化失败：停在安全态，由看门狗复位。 */
        }
    }

    for (;;)
    {
        /* 节拍推进在中断中完成。 */
    }
}

/*** end of file ***/
