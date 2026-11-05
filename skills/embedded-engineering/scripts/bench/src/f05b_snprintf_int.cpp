#include "bench.h"
#include <cstdio>
char g_buf[32];
int main() { std::snprintf(g_buf, sizeof g_buf, "%lu", static_cast<unsigned long>(g_reg)); g_sink = static_cast<uint32_t>(g_buf[0]); return 0; }
