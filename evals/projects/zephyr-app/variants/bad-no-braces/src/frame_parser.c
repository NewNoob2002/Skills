/*
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include <app/frame_parser.h>

int frame_parse(const uint8_t *buf, size_t size, struct frame *out)
{
	uint8_t sum;
	uint8_t len;

	if ((buf == NULL) || (out == NULL) || (size < 1U) || (buf[0] != FRAME_START)) {
		return -EINVAL;
	}

	if (size < 2U) {
		return -EAGAIN;
	}

	len = buf[1];
	/* Validate the length field before touching the payload (PROTO-001). */
	if (len > FRAME_MAX_PAYLOAD)
		return -EMSGSIZE;

	if (size < ((size_t)len + 3U)) {
		return -EAGAIN;
	}

	sum = len;
	for (size_t i = 0; i < len; i++) {
		sum = (uint8_t)(sum + buf[2U + i]);
	}

	if (sum != buf[2U + len]) {
		return -EBADMSG;
	}

	out->len = len;
	memcpy(out->payload, &buf[2], len);

	return 0;
}
