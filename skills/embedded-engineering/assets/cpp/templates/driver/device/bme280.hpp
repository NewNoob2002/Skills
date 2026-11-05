/// @file bme280.hpp
/// @brief BME280 器件驱动骨架（示例模板）：以寄存器总线为模板参数的静态多态驱动。
///
/// 寄存器值来源：Bosch BME280 数据手册，chip_id 寄存器 0xD0，复位值 0x60。
/// 上下文：非 ISR-safe；非 thread-safe（由所属任务独占）。

#ifndef PROJ_BME280_HPP
#define PROJ_BME280_HPP

#include <cstdint>

#include "etl/span.h"
#include "proj_status.hpp"
#include "register_bus.hpp"

namespace proj
{

template <PROJ_REGISTER_BUS Bus> class Bme280
{
    static_assert(kIsRegisterBus<Bus>,
                  "Bus must provide Status read(uint8_t, etl::span<uint8_t>) and "
                  "Status write(uint8_t, etl::span<const uint8_t>)");

  public:
    static constexpr std::uint8_t kRegChipId    = 0xD0U;
    static constexpr std::uint8_t kRegReset     = 0xE0U;
    static constexpr std::uint8_t kChipId       = 0x60U;
    static constexpr std::uint8_t kResetCommand = 0xB6U;

    /// 构造不访问硬件、不会失败，可用于 constinit 全局对象。
    constexpr explicit Bme280 (Bus & bus) noexcept : bus_(bus) {}

    /// 时钟与总线就绪后由组合根调用：校验 ID，再软复位。
    [[nodiscard]] Status
    init () noexcept
    {
        Result<std::uint8_t> chip_id = read_register(kRegChipId);
        if (!chip_id.has_value())
        {
            return chip_id.error();
        }
        if (kChipId != chip_id.value())
        {
            return Status::kNotReady;
        }
        const std::uint8_t command = kResetCommand;
        const Status status = bus_.write(kRegReset, etl::span<const std::uint8_t>(&command, 1U));
        ready_              = (Status::kOk == status);
        return status;
    }

    ~Bme280 ()                         = default;
    Bme280 (const Bme280 &)            = delete; // 一个驱动实例独占一个器件
    Bme280 & operator=(const Bme280 &) = delete;

    [[nodiscard]] bool
    ready () const noexcept
    {
        return ready_;
    }

  private:
    [[nodiscard]] Result<std::uint8_t>
    read_register (std::uint8_t reg) noexcept
    {
        std::uint8_t value  = 0U;
        const Status status = bus_.read(reg, etl::span<std::uint8_t>(&value, 1U));
        if (Status::kOk != status)
        {
            return fail(status);
        }
        return value;
    }

    Bus & bus_;
    bool  ready_ = false;
};

} // namespace proj

#endif // PROJ_BME280_HPP
