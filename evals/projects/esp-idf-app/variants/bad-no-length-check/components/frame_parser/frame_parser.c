#include <string.h>

#include "frame_parser.h"

static uint8_t checksum(const uint8_t *data, size_t len)
{
    uint32_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return (uint8_t)(sum & 0xFFU);
}

esp_err_t frame_parser_parse(const uint8_t *buf, size_t buf_len, frame_parser_frame_t *out)
{
    if (buf == NULL || out == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (buf_len < 3U) {
        return ESP_ERR_INVALID_SIZE;
    }
    if (buf[0] != FRAME_PARSER_SOF) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    const uint8_t len = buf[1];
    // 先校验长度字段，再访问 payload（PROTO-001）
    if (buf_len < (size_t)len + 3U) {
        return ESP_ERR_INVALID_SIZE;
    }
    if (checksum(&buf[1], (size_t)len + 1U) != buf[len + 2U]) {
        return ESP_ERR_INVALID_CRC;
    }
    out->len = len;
    memcpy(out->payload, &buf[2], len);
    return ESP_OK;
}
