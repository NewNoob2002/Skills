#include "bench.h"
#include <stddef.h>
__attribute__((noinline)) static uint32_t sum(uint32_t const * p, size_t n) { uint32_t s = 0U; for (size_t i = 0U; i < n; i++) { s += p[i]; } return s; }
uint32_t g_data[8] = {1, 2, 3, 4, 5, 6, 7, 8};
int main(void) { g_data[0] = g_reg; g_sink = sum(g_data, 8U); return 0; }
