#include "bench.h"
#include <variant>
struct Idle {}; struct Run { uint32_t speed; }; struct Fault { uint32_t code; };
using State = std::variant<Idle, Run, Fault>;
State g_state;
struct V { uint32_t operator()(Idle) const { return 0U; } uint32_t operator()(Run r) const { return r.speed; } uint32_t operator()(Fault f) const { return f.code | 0x80000000U; } };
int main() { if (g_reg == 1U) { g_state = Run{g_reg}; } else if (g_reg == 2U) { g_state = Fault{g_reg}; } g_sink = std::visit(V{}, g_state); return 0; }
