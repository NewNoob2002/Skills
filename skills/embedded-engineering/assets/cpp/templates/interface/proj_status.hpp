/// @file proj_status.hpp
/// @brief 项目统一错误码与 Result 类型（无异常错误处理，Core Guidelines E.25/E.27）。
/// 上下文：ISR-safe，thread-safe（纯值类型）。

#ifndef PROJ_STATUS_HPP
#define PROJ_STATUS_HPP

#include <cstdint>

#include "etl/expected.h"

namespace proj
{

enum class Status : std::uint8_t
{
    kOk,
    kInvalidArgument,
    kTimeout,
    kBusy,
    kIo,
    kNotReady,
};

/// 值或错误码。C++23 项目可改为 std::expected<T, Status>。
template <class T> using Result = etl::expected<T, Status>;

/// 构造错误结果：return proj::fail(Status::kTimeout);
inline etl::unexpected<Status>
fail (Status status) noexcept
{
    return etl::unexpected<Status>(status);
}

} // namespace proj

#endif // PROJ_STATUS_HPP
