// 预期编译失败：DMA buffer must cover whole cache lines
#include "dma_buffer.hpp"
proj::DmaBuffer<40> g_bad;
