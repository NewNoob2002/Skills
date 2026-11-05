/* msg_parse_name：长度校验先于复制（GEN-010、PROTO-001）。在 ASan 下运行，越界即失败。 */
#include <errno.h>
#include <string.h>

#include "unity.h"

#include "msg_parse.h"

void setUp(void)
{
}

void tearDown(void)
{
}

void test_valid_name(void)
{
    const uint8_t buf[] = {3, 'a', 'b', 'c'};
    char out[8];

    TEST_ASSERT_EQUAL_INT(0, msg_parse_name(buf, sizeof(buf), out, sizeof(out)));
    TEST_ASSERT_EQUAL_STRING("abc", out);
}

void test_name_too_long_for_output_is_rejected(void)
{
    uint8_t buf[1 + 20];
    char out[8];

    memset(buf, 'x', sizeof(buf));
    buf[0] = 20;
    TEST_ASSERT_EQUAL_INT(-EMSGSIZE, msg_parse_name(buf, sizeof(buf), out, sizeof(out)));
}

void test_truncated_input(void)
{
    const uint8_t buf[] = {5, 'a', 'b'};
    char out[8];

    TEST_ASSERT_EQUAL_INT(-EAGAIN, msg_parse_name(buf, sizeof(buf), out, sizeof(out)));
}
