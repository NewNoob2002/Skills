// T2 组合根（Cortex-M0+）：演示池分配器容器的有界用法，目标 ELF 不含堆符号。

#include "../module/filter/moving_average_pool.hpp"

int
main ()
{
    proj::filter::MovingAveragePool<32> filter;
    filter.add(123);
    filter.add(456);
    return (filter.count() == 2U) ? static_cast<int>(filter.average()) : -1;
}
