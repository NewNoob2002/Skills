/// @file vendor_i2c_bus.hpp
/// @brief 把厂商 C SDK 的 I2C 接口适配为 RegisterBus（bsp 层；唯一允许包含 SDK 头的地方）。
///
/// 错误码在这里一次性映射为 proj::Status，不向上层泄漏 SDK 类型。

#ifndef PROJ_VENDOR_I2C_BUS_HPP
#define PROJ_VENDOR_I2C_BUS_HPP

#include <cstddef>
#include <cstdint>

#include "etl/span.h"
#include "proj_status.hpp"
#include "vendor_i2c.h"

namespace proj
{

class VendorI2cBus
{
  public:
    constexpr explicit VendorI2cBus (std::uint8_t address) noexcept : address_(address) {}

    [[nodiscard]] Status
    read (std::uint8_t reg, etl::span<std::uint8_t> out) noexcept
    {
        return map(vendor_i2c_read(address_, reg, out.data(), out.size()));
    }

    [[nodiscard]] Status
    write (std::uint8_t reg, etl::span<const std::uint8_t> in) noexcept
    {
        return map(vendor_i2c_write(address_, reg, in.data(), in.size()));
    }

  private:
    static constexpr Status
    map (vendor_status_t status) noexcept
    {
        switch (status)
        {
            case VENDOR_OK:
                return Status::kOk;
            case VENDOR_TIMEOUT:
                return Status::kTimeout;
            case VENDOR_BUSY:
                return Status::kBusy;
            default:
                return Status::kIo;
        }
    }

    std::uint8_t address_;
};

} // namespace proj

#endif // PROJ_VENDOR_I2C_BUS_HPP
