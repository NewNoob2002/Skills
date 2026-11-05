/** @file vendor_i2c.h
 *
 * @brief 示例：厂商 C SDK 的 I2C 接口形态（真实项目中由 SDK
 * 提供，此文件只为模板可编译）。
 */

#ifndef VENDOR_I2C_H
#define VENDOR_I2C_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

    typedef enum
    {
        VENDOR_OK = 0,
        VENDOR_TIMEOUT,
        VENDOR_BUSY,
        VENDOR_ERROR,
    } vendor_status_t;

    vendor_status_t vendor_i2c_read (uint8_t addr, uint8_t reg, uint8_t * p_buf,
                                     size_t len);
    vendor_status_t vendor_i2c_write (uint8_t addr, uint8_t reg,
                                      uint8_t const * p_buf, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* VENDOR_I2C_H */

/*** end of file ***/
