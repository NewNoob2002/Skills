#include "bench.h"
#include "etl/delegate.h"
struct Ctx { uint32_t a, b, c, d; void run() { g_sink = a + b + c + d; } };
Ctx g_ctx; etl::delegate<void()> g_cb;
int main() { g_ctx = {g_reg, g_reg, g_reg, g_reg}; g_cb = etl::delegate<void()>::create<Ctx, &Ctx::run>(g_ctx); g_cb(); return 0; }
