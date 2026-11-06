#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// 帧格式：[0xA5][len][payload: len 字节][checksum]；checksum 为 len 与 payload 各字节之和的低 8 位
#define FRAME_PARSER_SOF         (0xA5U)
#define FRAME_PARSER_MAX_PAYLOAD (32U)

typedef struct {
    uint8_t len;
    uint8_t payload[FRAME_PARSER_MAX_PAYLOAD];
} frame_parser_frame_t;

/**
 * @brief 解析一帧。
 *
 * @return ESP_OK 成功；ESP_ERR_INVALID_ARG 指针为空；ESP_ERR_INVALID_SIZE 长度字段超过上限或与缓冲区不符；
 *         ESP_ERR_INVALID_RESPONSE 帧头错误；ESP_ERR_INVALID_CRC 校验和错误
 */
esp_err_t frame_parser_parse(const uint8_t *buf, size_t buf_len, frame_parser_frame_t *out);

#ifdef __cplusplus
}
#endif
