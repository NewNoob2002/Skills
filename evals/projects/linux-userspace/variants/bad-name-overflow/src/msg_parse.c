#include "msg_parse.h"

#include <errno.h>
#include <string.h>

int msg_parse_name(const uint8_t *buf, size_t size, char *out, size_t out_cap)
{
    size_t name_len;

    if ((buf == NULL) || (out == NULL) || (out_cap == 0U)) {
        return -EINVAL;
    }
    if (size < 1U) {
        return -EAGAIN;
    }
    name_len = buf[0];
    if (size < (1U + name_len)) {
        return -EAGAIN;
    }
    memcpy(out, &buf[1], name_len);
    out[name_len] = '\0';
    return 0;
}
