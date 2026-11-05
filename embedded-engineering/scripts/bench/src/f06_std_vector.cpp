#include "bench.h"
#include <vector>
int main() { std::vector<uint32_t> v; for (uint32_t i = 0; i < g_reg; ++i) { v.push_back(i); } g_sink = static_cast<uint32_t>(v.size()); return 0; }
