/** @file vectors.c
 *
 * @brief 向量表固定名的中断入口（platform 层，不受 BARR-C 命名门禁约束）。
 *
 * 只做事件捕获：SysTick 中断只把节拍计数加一，业务处理在主循环中进行。
 */
#include <stdint.h>

#include "platform_tick.h"

static volatile uint32_t s_tick_count = 0U;

extern void app_led_service(void);

void SysTick_Handler(void)
{
    s_tick_count++;
    /* 在中断里推进业务状态并忙等，违反“ISR 只捕获事件” */
    app_led_service();
    for (volatile uint32_t spin = 0U; spin < 10000U; spin++)
    {
    }
}

uint32_t platform_tick_count(void)
{
    /* 32 位对齐读取在 Cortex-M 上是单次访问，且只有 ISR 写入。 */
    return s_tick_count;
}
