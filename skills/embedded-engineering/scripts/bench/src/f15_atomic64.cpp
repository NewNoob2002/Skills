#include "bench.h"
#include <atomic>
std::atomic<uint64_t> g_counter64{0U};
int main() { g_counter64.fetch_add(1U, std::memory_order_relaxed); g_sink = static_cast<uint32_t>(g_counter64.load()); return 0; }
