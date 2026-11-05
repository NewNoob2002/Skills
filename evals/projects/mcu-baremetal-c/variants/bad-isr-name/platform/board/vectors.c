/** @file vectors.c
 *
 * @brief 向量表固定名的中断入口（platform 层，不受 BARR-C 命名门禁约束）。
 *
 * 缺陷：入口名写成 Systick_Handler（大小写错误），与向量表的 SysTick_Handler 不符，
 * SysTick 异常落到启动文件的弱符号默认处理函数，节拍计数永远不增长。
 */
#include <stdint.h>

#include "platform_tick.h"

static volatile uint32_t s_tick_count = 0U;

void Systick_Handler(void)
{
    s_tick_count++;
}

uint32_t platform_tick_count(void)
{
    /* 32 位对齐读取在 Cortex-M 上是单次访问，且只有 ISR 写入。 */
    return s_tick_count;
}
