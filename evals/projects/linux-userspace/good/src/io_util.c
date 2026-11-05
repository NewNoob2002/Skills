#include "io_util.h"

#include <errno.h>

#include "sysio.h"

int io_write_all(int fd, const uint8_t *buf, size_t len)
{
    size_t done = 0U;

    while (done < len) {
        ssize_t n = sysio_write(fd, buf + done, len - done);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -errno;
        }
        if (n == 0) {
            return -EIO;
        }
        done += (size_t)n;
    }
    return 0;
}
