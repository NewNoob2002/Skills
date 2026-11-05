/* 系统调用的薄封装：生产代码直接转发给 POSIX，测试中由 CMock 替换，以注入部分写、EINTR 等情形。 */
#ifndef SYSIO_H
#define SYSIO_H

#include <stddef.h>
#include <sys/types.h>

int sysio_open(const char *path, int flags, int mode);
ssize_t sysio_write(int fd, const void *buf, size_t len);
int sysio_fsync(int fd);
int sysio_close(int fd);
int sysio_rename(const char *from, const char *to);

#endif /* SYSIO_H */
