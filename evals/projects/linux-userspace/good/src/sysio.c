#include "sysio.h"

#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int sysio_open(const char *path, int flags, int mode)
{
    return open(path, flags, (mode_t)mode);
}

ssize_t sysio_write(int fd, const void *buf, size_t len)
{
    return write(fd, buf, len);
}

int sysio_fsync(int fd)
{
    return fsync(fd);
}

int sysio_close(int fd)
{
    return close(fd);
}

int sysio_rename(const char *from, const char *to)
{
    return rename(from, to);
}
