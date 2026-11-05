#include "bench.h"
#include <functional>
std::function<void()> g_cb;
int main() { uint32_t a = g_reg, b = g_reg, c = g_reg, d = g_reg; g_cb = [a, b, c, d]() { g_sink = a + b + c + d; }; g_cb(); return 0; }
