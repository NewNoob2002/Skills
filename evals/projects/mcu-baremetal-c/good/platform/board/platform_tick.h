/** @file platform_tick.h
 *
 * @brief SysTick 节拍计数（platform 层）。
 */
#ifndef PLATFORM_TICK_H
#define PLATFORM_TICK_H

#include <stdint.h>

uint32_t platform_tick_count(void);

#endif /* PLATFORM_TICK_H */
