#include "bench.h"
#include <span>
#include <array>
__attribute__((noinline)) static uint32_t sum(std::span<const uint32_t> data) { uint32_t s = 0U; for (uint32_t x : data) { s += x; } return s; }
std::array<uint32_t, 8> g_data{1, 2, 3, 4, 5, 6, 7, 8};
int main() { g_data[0] = g_reg; g_sink = sum(g_data); return 0; }
