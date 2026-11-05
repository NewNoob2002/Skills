/// @file uart_divider.hpp
/// @brief 编译期计算并校验 UART 分频（思路来自 modm）：误差超限或超出硬件范围即编译失败，
/// 运行期只把常量写入波特率寄存器。
///
/// 公式对应“过采样 16、BRR = fck / baud”的 USART（例如 STM32 USART 的 OVER8=0 模式）；
/// 其他外设按其参考手册修改 kDivider 计算与范围。

#ifndef PROJ_UART_DIVIDER_HPP
#define PROJ_UART_DIVIDER_HPP

#include <cstdint>

namespace proj
{

inline constexpr std::uint32_t kUartDefaultTolerancePermille = 10U;     // 1 %
inline constexpr std::uint32_t kUartMinDivider               = 16U;     // 过采样 16
inline constexpr std::uint32_t kUartMaxDivider               = 0xFFFFU; // 16 位 BRR
inline constexpr std::uint64_t kPermille                     = 1000U;

template <std::uint32_t ClockHz, std::uint32_t Baud,
          std::uint32_t TolerancePermille = kUartDefaultTolerancePermille>
struct UartDivider
{
    static_assert(Baud > 0U, "baud rate must be positive");

    static constexpr std::uint32_t kDivider = (ClockHz + (Baud / 2U)) / Baud;
    static_assert((kDivider >= kUartMinDivider) && (kDivider <= kUartMaxDivider),
                  "divider out of hardware range");

    static constexpr std::uint32_t kActualBaud = ClockHz / kDivider;
    static constexpr std::uint64_t kErrorPermille =
        (static_cast<std::uint64_t>((kActualBaud > Baud) ? (kActualBaud - Baud)
                                                         : (Baud - kActualBaud)) *
         kPermille) /
        Baud;
    static_assert(kErrorPermille <= TolerancePermille, "baud rate error exceeds tolerance");
};

} // namespace proj

#endif // PROJ_UART_DIVIDER_HPP
