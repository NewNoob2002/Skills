/// @file test_bme280.cpp
/// @brief CppUTest 模板：两种接缝。
///   1. 编译期接缝：Bme280<FakeBus>，零运行期开销，不需要 virtual。
///   2. C 函数 mock：VendorI2cBus 调用的厂商 C SDK 由 CppUMock 替换（vendor_i2c_mock.cpp）。
/// 期望值来自数据手册（chip_id 0x60、复位命令 0xB6），不复制实现的计算。

#include <array>
#include <cstdint>

#include "bme280.hpp"
#include "vendor_i2c_bus.hpp"

// CppUTest 头必须最后包含：其内存泄漏检测把 new 定义为宏，会破坏之后 STL/ETL 头中的 placement new。
#include "CppUTest/TestHarness.h"
#include "CppUTestExt/MockSupport.h"

namespace
{

/// 可编程的寄存器总线替身：read 返回预置寄存器值，write 记录最后一次写入。
struct FakeBus
{
    std::array<std::uint8_t, 256> registers{};
    proj::Status                  next_status      = proj::Status::kOk;
    std::uint8_t                  last_write_reg   = 0U;
    std::uint8_t                  last_write_value = 0U;
    unsigned                      write_count      = 0U;

    proj::Status
    read (std::uint8_t reg, etl::span<std::uint8_t> out) noexcept
    {
        for (std::size_t idx = 0U; idx < out.size(); ++idx)
        {
            out[idx] = registers.at((reg + idx) & 0xFFU);
        }
        return next_status;
    }

    proj::Status
    write (std::uint8_t reg, etl::span<const std::uint8_t> in) noexcept
    {
        last_write_reg   = reg;
        last_write_value = in.empty() ? 0U : in[0];
        ++write_count;
        return next_status;
    }
};

} // namespace

TEST_GROUP(Bme280WithFakeBus) { FakeBus bus; };

TEST(Bme280WithFakeBus, InitSucceedsAndResetsWhenChipIdMatches)
{
    bus.registers.at(0xD0U) = 0x60U;
    proj::Bme280<FakeBus> sensor(bus);

    CHECK(proj::Status::kOk == sensor.init());
    CHECK_TRUE(sensor.ready());
    LONGS_EQUAL(0xE0U, bus.last_write_reg);
    LONGS_EQUAL(0xB6U, bus.last_write_value);
}

TEST(Bme280WithFakeBus, InitRejectsWrongChipIdWithoutWriting)
{
    bus.registers.at(0xD0U) = 0x58U; // BMP280 的 chip_id，不是 BME280
    proj::Bme280<FakeBus> sensor(bus);

    CHECK(proj::Status::kNotReady == sensor.init());
    CHECK_FALSE(sensor.ready());
    LONGS_EQUAL(0U, bus.write_count);
}

TEST(Bme280WithFakeBus, InitPropagatesBusError)
{
    bus.next_status = proj::Status::kTimeout;
    proj::Bme280<FakeBus> sensor(bus);

    CHECK(proj::Status::kTimeout == sensor.init());
    CHECK_FALSE(sensor.ready());
}

TEST_GROUP(VendorI2cBusMapsSdk){void teardown() override{mock().checkExpectations();
mock().clear();
}
}
;

TEST(VendorI2cBusMapsSdk, ReadPassesAddressRegisterAndReturnsData)
{
    const std::uint8_t chip_id = 0x60U;
    mock()
        .expectOneCall("vendor_i2c_read")
        .withParameter("addr", 0x76U)
        .withParameter("reg", 0xD0U)
        .withParameter("len", 1U)
        .withOutputParameterReturning("p_buf", &chip_id, sizeof(chip_id))
        .andReturnValue(static_cast<int>(VENDOR_OK));

    proj::VendorI2cBus bus(0x76U);
    std::uint8_t       value = 0U;

    CHECK(proj::Status::kOk == bus.read(0xD0U, etl::span<std::uint8_t>(&value, 1U)));
    LONGS_EQUAL(0x60U, value);
}

TEST(VendorI2cBusMapsSdk, SdkTimeoutMapsToStatusTimeout)
{
    mock()
        .expectOneCall("vendor_i2c_write")
        .ignoreOtherParameters()
        .andReturnValue(static_cast<int>(VENDOR_TIMEOUT));

    proj::VendorI2cBus bus(0x76U);
    const std::uint8_t command = 0xB6U;

    CHECK(proj::Status::kTimeout == bus.write(0xE0U, etl::span<const std::uint8_t>(&command, 1U)));
}
