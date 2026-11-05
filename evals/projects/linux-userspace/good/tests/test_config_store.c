/* config_save：原子写的调用顺序与失败处理（LNXU-002）。 */
#include <errno.h>
#include <fcntl.h>
#include <string.h>

#include "unity.h"

#include "config_store.h"
#include "io_util.h"
#include "mock_sysio.h"

static const uint8_t g_data[3] = {7, 8, 9};

static ssize_t write_all_at_once(int fd, const void *buf, size_t len, int num_calls)
{
    (void)fd;
    (void)buf;
    (void)num_calls;
    return (ssize_t)len;
}

void setUp(void)
{
    sysio_write_Stub(write_all_at_once);
}

void tearDown(void)
{
}

void test_writes_tmp_then_renames_and_syncs_dir(void)
{
    sysio_open_ExpectAndReturn("/etc/app/cfg.bin.tmp", O_WRONLY | O_CREAT | O_TRUNC, 0600, 5);
    sysio_fsync_ExpectAndReturn(5, 0);
    sysio_close_ExpectAndReturn(5, 0);
    sysio_rename_ExpectAndReturn("/etc/app/cfg.bin.tmp", "/etc/app/cfg.bin", 0);
    sysio_open_ExpectAndReturn("/etc/app", O_RDONLY | O_DIRECTORY, 0, 6);
    sysio_fsync_ExpectAndReturn(6, 0);
    sysio_close_ExpectAndReturn(6, 0);

    TEST_ASSERT_EQUAL_INT(0, config_save("/etc/app", "/etc/app/cfg.bin", g_data, sizeof(g_data)));
}

void test_fsync_failure_aborts_before_rename(void)
{
    sysio_open_ExpectAndReturn("/etc/app/cfg.bin.tmp", O_WRONLY | O_CREAT | O_TRUNC, 0600, 5);
    sysio_fsync_ExpectAndReturn(5, -1);
    sysio_close_ExpectAndReturn(5, 0);
    errno = EIO;

    /* 不允许调用 rename：目标文件必须保持旧内容 */
    TEST_ASSERT_EQUAL_INT(-EIO, config_save("/etc/app", "/etc/app/cfg.bin", g_data, sizeof(g_data)));
}
