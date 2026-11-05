#include "bench.h"
#include "etl/inplace_function.h"
etl::inplace_function<void(), 16> g_cb;
int main() { uint32_t a = g_reg, b = g_reg, c = g_reg, d = g_reg; g_cb = [a, b, c, d]() { g_sink = a + b + c + d; }; g_cb(); return 0; }
