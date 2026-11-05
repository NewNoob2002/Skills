/** @file main.c
 *
 * @brief 组合根：把板载 LED 绑定到 ledctl，并按节拍推进。
 */
#include <stdint.h>

#include "board_led.h"
#include "board_tick.h"
#include "ledctl.h"

/* LED 半周期：500 个节拍。 */
#define APP_LED_HALF_PERIOD_TICKS (500U)

static ledctl_t g_led;

int
main (void)
{
    uint32_t last_tick = board_tick_now();

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
        uint32_t const now = board_tick_now();

        /* 无符号差值可以正确处理节拍计数回绕。 */
        while ((uint32_t) (now - last_tick) > 0U)
        {
            last_tick++;
            (void) ledctl_tick(&g_led);
        }
    }
}

/*** end of file ***/
