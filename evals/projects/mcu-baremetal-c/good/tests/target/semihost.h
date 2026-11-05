/* ARM semihosting 最小实现：输出字符串与带退出码退出（QEMU 需加 -semihosting）。
 * 操作码见 Arm "Semihosting for AArch32 and AArch64" v2.0：SYS_WRITE0 = 0x04，SYS_EXIT = 0x18。 */
#ifndef SEMIHOST_H
#define SEMIHOST_H

#include <stdint.h>

static inline uint32_t semihost_call(uint32_t op, void const *arg)
{
    register uint32_t r0 __asm__("r0") = op;
    register void const *r1 __asm__("r1") = arg;

    __asm__ volatile("bkpt 0xab" : "+r"(r0) : "r"(r1) : "memory");
    return r0;
}

static inline void semihost_puts(char const *s)
{
    (void)semihost_call(0x04U, s);
}

/* AArch32 的 SYS_EXIT 只传原因码：ADP_Stopped_ApplicationExit（0x20026）表示成功，
 * QEMU 对其他原因码以状态 1 退出。 */
__attribute__((noreturn)) static inline void semihost_exit(int code)
{
    (void)semihost_call(0x18U, (void const *)(code == 0 ? 0x20026UL : 0x20023UL));
    for (;;) {
    }
}

#endif /* SEMIHOST_H */
