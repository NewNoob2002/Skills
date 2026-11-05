/* 目标测试的启动代码与向量表（QEMU mps2-an386）。
 *
 * 中断入口 SysTick_Handler 来自被测的 platform/board/vectors.c；
 * 其余异常进入 fault_handler，通过 semihosting 以失败状态退出，避免仿真挂死。 */
#include <stdint.h>

#include "semihost.h"

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern int      target_main(void);

void Reset_Handler(void);
void fault_handler(void);

/* 弱符号：被测代码没有提供同名函数时由默认处理函数接管（与厂商启动文件的做法一致）。 */
void SysTick_Handler(void) __attribute__((weak, alias("default_handler")));

void default_handler(void)
{
    semihost_puts("FAIL: unexpected interrupt (default_handler)\n");
    semihost_exit(1);
}

void fault_handler(void)
{
    semihost_puts("FAIL: fault exception\n");
    semihost_exit(1);
}

__attribute__((section(".vectors"), used)) static void (*const s_vectors[16])(void) = {
    (void (*)(void))(&_estack),
    Reset_Handler,
    fault_handler, /* NMI */
    fault_handler, /* HardFault */
    fault_handler, /* MemManage */
    fault_handler, /* BusFault */
    fault_handler, /* UsageFault */
    0,
    0,
    0,
    0,
    fault_handler, /* SVCall */
    fault_handler, /* DebugMon */
    0,
    fault_handler, /* PendSV */
    SysTick_Handler,
};

void Reset_Handler(void)
{
    uint32_t const *src = &_sidata;

    for (uint32_t *dst = &_sdata; dst < &_edata; dst++) {
        *dst = *src++;
    }
    for (uint32_t *dst = &_sbss; dst < &_ebss; dst++) {
        *dst = 0U;
    }
    semihost_exit(target_main());
}
