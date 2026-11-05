/** @file board_led.h
 *
 * @brief 板载 LED 的 gpio_if 实现。
 */
#ifndef BOARD_LED_H
#define BOARD_LED_H

#include "gpio_if.h"

/**
 * @brief 返回绑定到板载 LED 的 GPIO 接口。
 *
 * @return 指向静态接口实例的指针，生命周期为整个程序。
 */
gpio_if_t const * board_led_gpio (void);

#endif /* BOARD_LED_H */

/*** end of file ***/
