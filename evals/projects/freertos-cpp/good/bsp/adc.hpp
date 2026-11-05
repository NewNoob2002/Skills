// 板级 ADC 读取（验证工程用的虚构寄存器）。
#ifndef PROJ_BSP_ADC_HPP
#define PROJ_BSP_ADC_HPP

#include <cstdint>

namespace proj::bsp
{

[[nodiscard]] std::int32_t adc_read () noexcept;

} // namespace proj::bsp

#endif // PROJ_BSP_ADC_HPP
