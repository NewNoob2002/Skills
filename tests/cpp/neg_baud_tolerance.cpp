// 预期编译失败：baud rate error exceeds tolerance
#include "uart_divider.hpp"
std::uint32_t neg () { return proj::UartDivider<80000000U, 3000000U>::kDivider; }
