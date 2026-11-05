#include "bench.h"
struct Cfg { uint32_t v; Cfg() : v(g_reg) {} };
__attribute__((noinline)) static Cfg& cfg() { static Cfg c; return c; }
int main() { g_sink = cfg().v; return 0; }
