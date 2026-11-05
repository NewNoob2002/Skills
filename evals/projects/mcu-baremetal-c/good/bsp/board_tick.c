/** @file board_tick.c
 *
 * @brief 系统节拍计数（bsp 对 platform 的封装）。
 */
#include <stdint.h>

#include "board_tick.h"
#include "platform_tick.h"

uint32_t
board_tick_now (void)
{
    return platform_tick_count();
}

/*** end of file ***/
