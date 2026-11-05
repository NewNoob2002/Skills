// 预期在 Cortex-M0/M0+ 上编译失败：SpscRing needs lock-free 32-bit atomics
#include "spsc_ring.hpp"
proj::SpscRing<unsigned char, 16> g_ring;
