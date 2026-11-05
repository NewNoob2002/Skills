#ifndef MSG_PARSE_H
#define MSG_PARSE_H

#include <stddef.h>
#include <stdint.h>

/*
 * 消息格式：name_len（1 字节）| name（name_len 字节，不含结尾 0）。
 * 把 name 复制到 out（以 0 结尾）。成功返回 0；输入不完整返回 -EAGAIN；
 * name 放不进 out 返回 -EMSGSIZE；参数为空返回 -EINVAL。
 */
int msg_parse_name(const uint8_t *buf, size_t size, char *out, size_t out_cap);

#endif /* MSG_PARSE_H */
