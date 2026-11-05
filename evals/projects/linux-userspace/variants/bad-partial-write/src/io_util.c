#include "io_util.h"

#include <errno.h>

#include "sysio.h"

int io_write_all(int fd, const uint8_t *buf, size_t len)
{
    ssize_t n = sysio_write(fd, buf, len);

    return (n < 0) ? -errno : 0;
}
