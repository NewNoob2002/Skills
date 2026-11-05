#include "bench.h"
#include "etl/vector.h"
int main() { etl::vector<uint32_t, 16> v; for (uint32_t i = 0; (i < g_reg) && !v.full(); ++i) { v.push_back(i); } g_sink = static_cast<uint32_t>(v.size()); return 0; }
