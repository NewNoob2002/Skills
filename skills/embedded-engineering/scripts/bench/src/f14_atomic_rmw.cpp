#include "bench.h"
#include <atomic>
std::atomic<uint32_t> g_counter{0U};
int main() { g_counter.fetch_add(1U, std::memory_order_relaxed); g_sink = g_counter.load(std::memory_order_acquire); return 0; }
