#include "bench.h"
__attribute__((noinline)) static uint32_t check(uint32_t v) { if (v > 10U) { throw 1; } return v; }
int main() { try { g_sink = check(g_reg); } catch (int) { g_sink = 0U; } return 0; }
