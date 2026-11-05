#include "adc.hpp"

#include <cstdint>

namespace proj::bsp
{
namespace
{
// NOTE: 虚构的 ADC 数据寄存器地址，只用于链接与体积分析，不对应真实芯片。
constexpr std::uintptr_t kAdcDataAddress = 0x40012440U;
} // namespace

std::int32_t
adc_read () noexcept
{
    auto const * const data = reinterpret_cast<std::uint32_t const volatile *>(kAdcDataAddress);
    return static_cast<std::int32_t>(*data & 0x0FFFU);
}

} // namespace proj::bsp
