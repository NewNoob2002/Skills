/** @file board_tick.h
 *
 * @brief 系统节拍计数（bsp 对 platform 的封装）。
 */
#ifndef BOARD_TICK_H
#define BOARD_TICK_H

#include <stdint.h>

/**
 * @brief 读取自启动以来的节拍数，计数会回绕。
 *
 * @return 当前节拍计数。
 */
uint32_t board_tick_now (void);

#endif /* BOARD_TICK_H */

/*** end of file ***/
