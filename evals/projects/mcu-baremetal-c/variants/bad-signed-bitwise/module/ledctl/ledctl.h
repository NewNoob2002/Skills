/** @file ledctl.h
 *
 * @brief LED 闪烁控制模块（示例模板）。
 *
 * 职责：根据周期性 tick 翻转 LED，周期可配置。
 * 依赖：interface/gpio_if.h。
 * 线程模型：所有函数只能在同一个任务上下文中调用，不可在 ISR 中调用。
 */

#ifndef LEDCTL_H
#define LEDCTL_H

#include <stdbool.h>
#include <stdint.h>

#include "gpio_if.h"
#include "proj_err.h"

/* 允许的最小与最大半周期，单位为 tick。 */
#define LEDCTL_HALF_PERIOD_MIN_TICKS (1U)
#define LEDCTL_HALF_PERIOD_MAX_TICKS (10000U)

typedef struct
{
    gpio_if_t const * p_gpio;
    uint32_t          half_period_ticks;
    uint32_t          elapsed_ticks;
    bool              b_led_on;
    bool              b_initialized;
} ledctl_t;

/**
 * @brief 初始化 LED 控制实例并把 LED 置为熄灭。
 *
 * @param p_led             实例存储，由调用者分配。
 * @param p_gpio            已绑定的 GPIO 接口，生命周期须长于实例。
 * @param half_period_ticks 亮或灭各持续的 tick 数。
 *
 * @return PROJ_ERR_OK 成功；PROJ_ERR_INVALID_PARAM 参数无效；
 *         或透传 GPIO 写失败的错误码。
 */
proj_err_t ledctl_init (ledctl_t * p_led, gpio_if_t const * p_gpio,
                        uint32_t half_period_ticks);

/**
 * @brief 推进一个 tick，到达半周期时翻转 LED。
 *
 * @param p_led 已初始化的实例。
 *
 * @return PROJ_ERR_OK 成功；PROJ_ERR_INVALID_PARAM 指针为空；
 *         PROJ_ERR_NOT_INITIALIZED 实例未初始化；或透传 GPIO 错误码。
 */
proj_err_t ledctl_tick (ledctl_t * p_led);

/**
 * @brief 判断节拍计数是否为奇数（用于诊断输出）。
 *
 * @param ticks 节拍计数。
 *
 * @return 奇数返回 true。
 */
bool ledctl_is_odd (int32_t ticks);

#endif /* LEDCTL_H */

/*** end of file ***/
