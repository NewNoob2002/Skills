/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Frame format: 0x7E | len (1 byte) | payload (len bytes) | checksum (1 byte).
 * The checksum is the 8-bit sum of len and all payload bytes.
 */

#ifndef APP_FRAME_PARSER_H_
#define APP_FRAME_PARSER_H_

#include <stddef.h>
#include <stdint.h>

#define FRAME_START       0x7E
#define FRAME_MAX_PAYLOAD 16U

struct frame {
	uint8_t len;
	uint8_t payload[FRAME_MAX_PAYLOAD];
};

/**
 * @brief Parse one complete frame from a buffer.
 *
 * @param buf Input bytes, starting with FRAME_START.
 * @param size Number of valid bytes in @p buf.
 * @param out Parsed frame on success.
 *
 * @retval 0 Frame parsed.
 * @retval -EINVAL Bad start byte or NULL argument.
 * @retval -EMSGSIZE Length field exceeds FRAME_MAX_PAYLOAD.
 * @retval -EAGAIN Buffer does not yet hold a complete frame.
 * @retval -EBADMSG Checksum mismatch.
 */
int frame_parse(const uint8_t *buf, size_t size, struct frame *out);

#endif /* APP_FRAME_PARSER_H_ */
