/** @file board_led.c
 *
 * @brief 板载 LED 的 gpio_if 实现：写 BSRR 置位或复位引脚。
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "board_led.h"
#include "board_regs.h"

/* 板载 LED 位于 GPIOA 第 5 脚（验证工程虚构的板级连接）。 */
#define BOARD_LED_PIN_MASK (1UL << 5U)
#define BOARD_LED_RESET_SHIFT (16U)

static proj_err_t board_led_write (void * p_ctx, bool b_high);

static gpio_if_t const g_board_led_gpio = {board_led_write, NULL};

gpio_if_t const *
board_led_gpio (void)
{
    return &g_board_led_gpio;
}

static proj_err_t
board_led_write (void * p_ctx, bool b_high)
{
    (void) p_ctx;

    /* BSRR 低 16 位置位、高 16 位复位，单次写入即可，无需读-改-写。 */
    if (b_high)
    {
        BOARD_GPIOA->BSRR = BOARD_LED_PIN_MASK;
    }
    else
    {
        BOARD_GPIOA->BSRR = (BOARD_LED_PIN_MASK << BOARD_LED_RESET_SHIFT);
    }

    return PROJ_ERR_OK;
}

/*** end of file ***/
