/// @file vendor_i2c_mock.cpp
/// @brief 厂商 C SDK 的 CppUMock 替身（链接期接缝：测试构建链接本文件而不是 SDK）。

#include <cstddef>
#include <cstdint>

#include "vendor_i2c.h"

// CppUTest 头最后包含（见 test_bme280.cpp）。
#include "CppUTestExt/MockSupport.h"

extern "C" vendor_status_t
vendor_i2c_read (uint8_t addr, uint8_t reg, uint8_t * p_buf, size_t len)
{
    return static_cast<vendor_status_t>(mock()
                                            .actualCall("vendor_i2c_read")
                                            .withParameter("addr", static_cast<unsigned int>(addr))
                                            .withParameter("reg", static_cast<unsigned int>(reg))
                                            .withParameter("len", static_cast<unsigned int>(len))
                                            .withOutputParameter("p_buf", p_buf)
                                            .returnIntValueOrDefault(VENDOR_OK));
}

extern "C" vendor_status_t
vendor_i2c_write (uint8_t addr, uint8_t reg, uint8_t const * p_buf, size_t len)
{
    return static_cast<vendor_status_t>(
        mock()
            .actualCall("vendor_i2c_write")
            .withParameter("addr", static_cast<unsigned int>(addr))
            .withParameter("reg", static_cast<unsigned int>(reg))
            .withParameter("len", static_cast<unsigned int>(len))
            .withParameter("p_buf", static_cast<const void *>(p_buf))
            .returnIntValueOrDefault(VENDOR_OK));
}
