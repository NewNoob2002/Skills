/* io_write_all：部分写、EINTR、错误传播。期望值来自 write(2) 的语义，而不是实现。 */
#include <errno.h>
#include <string.h>

#include "unity.h"

#include "io_util.h"
#include "mock_sysio.h"

#define MAX_CALLS 8

static ssize_t g_ret[MAX_CALLS];
static int g_err[MAX_CALLS];
static size_t g_len[MAX_CALLS];
static int g_calls;

static ssize_t scripted_write(int fd, const void *buf, size_t len, int num_calls)
{
    (void)fd;
    (void)buf;
    TEST_ASSERT_LESS_THAN(MAX_CALLS, num_calls);
    g_len[num_calls] = len;
    g_calls = num_calls + 1;
    errno = g_err[num_calls];
    return g_ret[num_calls];
}

void setUp(void)
{
    memset(g_ret, 0, sizeof(g_ret));
    memset(g_err, 0, sizeof(g_err));
    memset(g_len, 0, sizeof(g_len));
    g_calls = 0;
    sysio_write_Stub(scripted_write);
}

void tearDown(void)
{
}

void test_single_full_write(void)
{
    const uint8_t data[4] = {1, 2, 3, 4};

    g_ret[0] = 4;
    TEST_ASSERT_EQUAL_INT(0, io_write_all(3, data, sizeof(data)));
    TEST_ASSERT_EQUAL_INT(1, g_calls);
}

void test_partial_write_is_continued(void)
{
    const uint8_t data[10] = {0};

    g_ret[0] = 3;
    g_ret[1] = 7;
    TEST_ASSERT_EQUAL_INT(0, io_write_all(3, data, sizeof(data)));
    TEST_ASSERT_EQUAL_INT(2, g_calls);
    TEST_ASSERT_EQUAL_UINT(10U, g_len[0]);
    TEST_ASSERT_EQUAL_UINT(7U, g_len[1]);
}

void test_eintr_is_retried(void)
{
    const uint8_t data[5] = {0};

    g_ret[0] = -1;
    g_err[0] = EINTR;
    g_ret[1] = 5;
    TEST_ASSERT_EQUAL_INT(0, io_write_all(3, data, sizeof(data)));
    TEST_ASSERT_EQUAL_INT(2, g_calls);
}

void test_error_is_propagated(void)
{
    const uint8_t data[5] = {0};

    g_ret[0] = -1;
    g_err[0] = ENOSPC;
    TEST_ASSERT_EQUAL_INT(-ENOSPC, io_write_all(3, data, sizeof(data)));
}
