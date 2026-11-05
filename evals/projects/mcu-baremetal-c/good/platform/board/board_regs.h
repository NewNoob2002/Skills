/** @file board_regs.h
 *
 * @brief 验证工程用的最小寄存器定义（模拟厂商设备头）。
 *
 * NOTE: 地址与布局是虚构的，只用于静态检查与编译；不对应任何真实芯片。
 */
#ifndef BOARD_REGS_H
#define BOARD_REGS_H

#include <stdint.h>

typedef struct
{
    volatile uint32_t ODR;
    volatile uint32_t BSRR;
} BOARD_GPIO_TypeDef;

#define BOARD_GPIOA ((BOARD_GPIO_TypeDef *)0x48000000UL)

#endif /* BOARD_REGS_H */
