#include "adc.hpp"

#include <cstdint>

namespace proj::bsp
{
namespace
{
// NOTE: 虚构的 ADC 数据寄存器地址，只用于链接与体积分析，不对应真实芯片。
constexpr std::uintptr_t kAdcDataAddress = 0x40012440U;
constexpr std::uintptr_t kAdcTrimAddress = 0x40012444U;

struct Calibration
{
    std::int32_t offset;
};

Calibration const &
calibration () noexcept
{
    // 运行期读取校准值来初始化函数局部静态：触发线程安全 guard
    static Calibration const cal{static_cast<std::int32_t>(
        *reinterpret_cast<std::uint32_t const volatile *>(kAdcTrimAddress))};
    return cal;
}
} // namespace

std::int32_t
adc_read () noexcept
{
    auto const * const data = reinterpret_cast<std::uint32_t const volatile *>(kAdcDataAddress);
    return static_cast<std::int32_t>(*data & 0x0FFFU) - calibration().offset;
}

} // namespace proj::bsp
