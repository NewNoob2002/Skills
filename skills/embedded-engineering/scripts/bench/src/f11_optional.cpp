#include "bench.h"
#include <optional>
__attribute__((noinline)) static std::optional<uint32_t> parse(uint32_t v) { if (v > 100U) { return std::nullopt; } return v * 2U; }
int main() { auto r = parse(g_reg); g_sink = r.value_or(0U); return 0; }
