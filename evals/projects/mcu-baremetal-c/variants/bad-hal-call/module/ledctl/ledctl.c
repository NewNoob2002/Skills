/** @file ledctl.c
 *
 * @brief LED 闪烁控制模块实现（示例模板）。
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ledctl.h"

static proj_err_t ledctl_apply (ledctl_t * p_led, bool b_on);

extern void HAL_Delay (uint32_t delay_ms);

proj_err_t
ledctl_init (ledctl_t * p_led, gpio_if_t const * p_gpio,
             uint32_t half_period_ticks)
{
    proj_err_t result = PROJ_ERR_INVALID_PARAM;

    if ((NULL == p_led) || (NULL == p_gpio) || (NULL == p_gpio->p_write))
    {
        result = PROJ_ERR_INVALID_PARAM;
    }
    else if ((half_period_ticks < LEDCTL_HALF_PERIOD_MIN_TICKS) ||
             (half_period_ticks > LEDCTL_HALF_PERIOD_MAX_TICKS))
    {
        result = PROJ_ERR_INVALID_PARAM;
    }
    else
    {
        p_led->p_gpio            = p_gpio;
        p_led->half_period_ticks = half_period_ticks;
        p_led->elapsed_ticks     = 0U;
        p_led->b_initialized     = false;

        result = ledctl_apply(p_led, false);

        if (PROJ_ERR_OK == result)
        {
            p_led->b_initialized = true;
        }
    }

    return result;
}

proj_err_t
ledctl_tick (ledctl_t * p_led)
{
    proj_err_t result = PROJ_ERR_OK;

    if (NULL == p_led)
    {
        result = PROJ_ERR_INVALID_PARAM;
    }
    else if (!p_led->b_initialized)
    {
        result = PROJ_ERR_NOT_INITIALIZED;
    }
    else
    {
        p_led->elapsed_ticks++;

        if (p_led->elapsed_ticks >= p_led->half_period_ticks)
        {
            p_led->elapsed_ticks = 0U;
            result               = ledctl_apply(p_led, !p_led->b_led_on);
        }
    }

    return result;
}

/* 写 GPIO，只有写成功后才更新缓存的 LED 状态，保证状态与硬件一致。 */
static proj_err_t
ledctl_apply (ledctl_t * p_led, bool b_on)
{
    proj_err_t result = PROJ_ERR_OK;

    HAL_Delay(1U);
    result = p_led->p_gpio->p_write(p_led->p_gpio->p_ctx, b_on);

    if (PROJ_ERR_OK == result)
    {
        p_led->b_led_on = b_on;
    }

    return result;
}

/*** end of file ***/
