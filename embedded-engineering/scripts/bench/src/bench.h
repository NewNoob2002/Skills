#ifndef BENCH_H
#define BENCH_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
extern volatile uint32_t g_sink;
extern volatile uint32_t g_reg; /* 模拟外设寄存器 */
#ifdef __cplusplus
}
#endif
#endif /* BENCH_H */
