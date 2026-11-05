/* Ceedling 测试模板：ledctl 模块。
 *
 * gpio_if_t 是函数表接口，CMock 只能 mock 自由函数，因此这里用手写 fake。
 * 期望值来自模块规格（半周期翻转、写失败不改状态），不是复制实现的计算。
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "unity.h"

#include "ledctl.h"

static uint32_t   g_write_count;
static bool       gb_last_level;
static proj_err_t g_write_result;

static proj_err_t
fake_gpio_write (void * p_ctx, bool b_high)
{
    (void) p_ctx;
    g_write_count++;
    gb_last_level = b_high;
    return g_write_result;
}

static gpio_if_t const g_fake_gpio = {fake_gpio_write, NULL};
static ledctl_t        g_led;

void
setUp (void)
{
    g_write_count  = 0U;
    gb_last_level  = true;
    g_write_result = PROJ_ERR_OK;
}

void
tearDown (void)
{
}

void
test_init_turns_led_off (void)
{
    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_init(&g_led, &g_fake_gpio, 2U));
    TEST_ASSERT_EQUAL_UINT32(1U, g_write_count);
    TEST_ASSERT_FALSE(gb_last_level);
}

void
test_init_rejects_null_and_out_of_range (void)
{
    TEST_ASSERT_EQUAL(PROJ_ERR_INVALID_PARAM,
                      ledctl_init(NULL, &g_fake_gpio, 2U));
    TEST_ASSERT_EQUAL(PROJ_ERR_INVALID_PARAM, ledctl_init(&g_led, NULL, 2U));
    TEST_ASSERT_EQUAL(PROJ_ERR_INVALID_PARAM,
                      ledctl_init(&g_led, &g_fake_gpio, 0U));
    TEST_ASSERT_EQUAL(
        PROJ_ERR_INVALID_PARAM,
        ledctl_init(&g_led, &g_fake_gpio, LEDCTL_HALF_PERIOD_MAX_TICKS + 1U));
    TEST_ASSERT_EQUAL_UINT32(0U, g_write_count);
}

void
test_tick_toggles_every_half_period (void)
{
    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_init(&g_led, &g_fake_gpio, 2U));

    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_tick(&g_led));
    TEST_ASSERT_EQUAL_UINT32(1U, g_write_count);

    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_tick(&g_led));
    TEST_ASSERT_EQUAL_UINT32(2U, g_write_count);
    TEST_ASSERT_TRUE(gb_last_level);

    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_tick(&g_led));
    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_tick(&g_led));
    TEST_ASSERT_EQUAL_UINT32(3U, g_write_count);
    TEST_ASSERT_FALSE(gb_last_level);
}

void
test_tick_propagates_gpio_error_and_keeps_state (void)
{
    TEST_ASSERT_EQUAL(PROJ_ERR_OK, ledctl_init(&g_led, &g_fake_gpio, 1U));
    g_write_result = PROJ_ERR_IO;

    TEST_ASSERT_EQUAL(PROJ_ERR_IO, ledctl_tick(&g_led));
    TEST_ASSERT_FALSE(g_led.b_led_on);
}

void
test_tick_requires_init (void)
{
    ledctl_t uninit = {0};

    TEST_ASSERT_EQUAL(PROJ_ERR_NOT_INITIALIZED, ledctl_tick(&uninit));
    TEST_ASSERT_EQUAL(PROJ_ERR_INVALID_PARAM, ledctl_tick(NULL));
}
