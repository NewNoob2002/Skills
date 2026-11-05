/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Expected values are computed from the frame format in frame_parser.h,
 * not from the implementation.
 */

#include <errno.h>

#include <zephyr/ztest.h>

#include <app/frame_parser.h>

ZTEST_SUITE(frame_parser, NULL, NULL, NULL, NULL, NULL);

ZTEST(frame_parser, test_valid_frame)
{
	/* len 2, payload 0x10 0x20, checksum 2 + 0x10 + 0x20 = 0x32 */
	const uint8_t buf[] = {FRAME_START, 2U, 0x10U, 0x20U, 0x32U};
	struct frame frame;

	zassert_equal(frame_parse(buf, sizeof(buf), &frame), 0);
	zassert_equal(frame.len, 2U);
	zassert_equal(frame.payload[0], 0x10U);
	zassert_equal(frame.payload[1], 0x20U);
}

ZTEST(frame_parser, test_bad_checksum_rejected)
{
	const uint8_t buf[] = {FRAME_START, 2U, 0x10U, 0x20U, 0x33U};
	struct frame frame;

	zassert_equal(frame_parse(buf, sizeof(buf), &frame), -EBADMSG);
}

ZTEST(frame_parser, test_oversized_length_rejected)
{
	uint8_t buf[2U + 32U + 1U] = {FRAME_START, 32U};
	struct frame frame;

	zassert_equal(frame_parse(buf, sizeof(buf), &frame), -EMSGSIZE);
}

ZTEST(frame_parser, test_incomplete_frame)
{
	const uint8_t buf[] = {FRAME_START, 2U, 0x10U};
	struct frame frame;

	zassert_equal(frame_parse(buf, sizeof(buf), &frame), -EAGAIN);
}

ZTEST(frame_parser, test_bad_start_byte)
{
	const uint8_t buf[] = {0x00U, 0U, 0U};
	struct frame frame;

	zassert_equal(frame_parse(buf, sizeof(buf), &frame), -EINVAL);
}
