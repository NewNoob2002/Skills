/** @file board_regs.h
 *
 * @brief 验证工程用的最小寄存器定义（模拟厂商设备头）。
 *
 * NOTE: 地址与布局是虚构的，只用于静态检查与编译；不对应任何真实芯片。
 */
#ifndef BOARD_REGS_H
#define BOARD_REGS_H

#include <stdint.h>

#define BOARD_GPIO_RESERVED_WORDS 6U
#define BOARD_GPIO_BYTES 32U

typedef struct
{
    volatile uint32_t ODR;
    volatile uint32_t BSRR;
    volatile uint32_t RESERVED[BOARD_GPIO_RESERVED_WORDS]; /* 显式保留区，防止编译器填充改变寄存器偏移 */
} BOARD_GPIO_TypeDef;

/* C99 没有 _Static_assert：用负数组长度把 sizeof 不符变成编译错误（C-008）。 */
typedef char BoardGpioSizeCheck_t[(sizeof(BOARD_GPIO_TypeDef) == BOARD_GPIO_BYTES) ? 1 : -1];

#define BOARD_GPIOA ((BOARD_GPIO_TypeDef *)0x48000000UL)

#endif /* BOARD_REGS_H */
