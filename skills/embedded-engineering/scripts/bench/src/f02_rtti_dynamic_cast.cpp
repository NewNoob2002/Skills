#include "bench.h"
struct Base { virtual ~Base() = default; virtual uint32_t id() const { return 1U; } };
struct Derived : Base { uint32_t id() const override { return 2U; } };
Base g_b; Derived g_d; Base* volatile gp = &g_d;
int main() { g_sink = (dynamic_cast<Derived*>(gp) != nullptr) ? 1U : 0U; return 0; }
