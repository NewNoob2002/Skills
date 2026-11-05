/* 仅用于模板编译检查：CMSIS-Core cmsis_compiler.h 中几个内联函数的最小替身。真实项目使用 CMSIS。 */
#ifndef CMSIS_COMPILER_STUB_H
#define CMSIS_COMPILER_STUB_H
#include <stdint.h>
static inline uint32_t __get_PRIMASK(void) { uint32_t r; __asm volatile("mrs %0, primask" : "=r"(r)); return r; }
static inline void __set_PRIMASK(uint32_t v) { __asm volatile("msr primask, %0" : : "r"(v) : "memory"); }
static inline void __disable_irq(void) { __asm volatile("cpsid i" : : : "memory"); }
static inline void __enable_irq(void) { __asm volatile("cpsie i" : : : "memory"); }
#endif
