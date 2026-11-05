#ifndef IO_UTIL_H
#define IO_UTIL_H

#include <stddef.h>
#include <stdint.h>

/* 写完全部字节：处理部分写与 EINTR（LNXU-001）。成功返回 0，失败返回 -errno。 */
int io_write_all(int fd, const uint8_t *buf, size_t len);

#endif /* IO_UTIL_H */
