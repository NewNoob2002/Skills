#include "bench.h"
#include <array>
#include <cstddef>
consteval std::array<uint8_t, 256> make_crc8() { std::array<uint8_t, 256> t{}; for (std::size_t i = 0; i < 256; ++i) { uint8_t c = static_cast<uint8_t>(i); for (int b = 0; b < 8; ++b) { c = static_cast<uint8_t>((c & 0x80U) ? ((c << 1) ^ 0x07U) : (c << 1)); } t[i] = c; } return t; }
constexpr auto kCrc8 = make_crc8();
int main() { g_sink = kCrc8[g_reg & 0xFFU]; return 0; }
