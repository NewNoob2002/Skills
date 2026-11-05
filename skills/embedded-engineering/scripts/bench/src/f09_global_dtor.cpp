#include "bench.h"
struct Guard { Guard() { g_sink = 1U; } ~Guard() { g_sink = 0U; } };
Guard g_guard;
int main() { g_sink = g_reg; return 0; }
