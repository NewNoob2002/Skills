#include "config_store.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>

#include "io_util.h"
#include "sysio.h"

#define TMP_SUFFIX ".tmp"

int config_save(const char *dir, const char *path, const uint8_t *data, size_t len)
{
    char tmp[256];
    int fd;
    int ret;

    if ((dir == NULL) || (path == NULL) || ((data == NULL) && (len > 0U))) {
        return -EINVAL;
    }
    if (snprintf(tmp, sizeof(tmp), "%s%s", path, TMP_SUFFIX) >= (int)sizeof(tmp)) {
        return -ENAMETOOLONG;
    }

    fd = sysio_open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0) {
        return -errno;
    }
    ret = io_write_all(fd, data, len);
    if ((ret == 0) && (sysio_fsync(fd) != 0)) {
        ret = -errno;
    }
    if ((sysio_close(fd) != 0) && (ret == 0)) {
        ret = -errno;
    }
    if (ret != 0) {
        return ret;
    }

    /* rename 之后 fsync 目录，保证目录项在掉电后也已落盘。 */
    fd = sysio_open(dir, O_RDONLY | O_DIRECTORY, 0);
    if (fd < 0) {
        return -errno;
    }
    ret = (sysio_fsync(fd) != 0) ? -errno : 0;
    (void)sysio_close(fd);
    return ret;
}
