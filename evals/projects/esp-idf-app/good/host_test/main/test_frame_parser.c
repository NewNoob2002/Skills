#include <stdlib.h>

#include "frame_parser.h"
#include "unity.h"

// 期望值来自 frame_parser.h 的帧格式与返回码说明，而不是实现输出（GEN-006）

void setUp(void)
{
}

void tearDown(void)
{
}

static void test_valid_frame(void)
{
    const uint8_t buf[] = {FRAME_PARSER_SOF, 2U, 0x10U, 0x20U, 0x32U};
    frame_parser_frame_t out;
    TEST_ASSERT_EQUAL(ESP_OK, frame_parser_parse(buf, sizeof(buf), &out));
    TEST_ASSERT_EQUAL_UINT8(2U, out.len);
    TEST_ASSERT_EQUAL_HEX8(0x20U, out.payload[1]);
}

static void test_null_args(void)
{
    const uint8_t buf[] = {FRAME_PARSER_SOF, 0U, 0U};
    frame_parser_frame_t out;
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, frame_parser_parse(NULL, sizeof(buf), &out));
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, frame_parser_parse(buf, sizeof(buf), NULL));
}

static void test_bad_sof(void)
{
    const uint8_t buf[] = {0x5AU, 0U, 0U};
    frame_parser_frame_t out;
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_RESPONSE, frame_parser_parse(buf, sizeof(buf), &out));
}

static void test_oversized_length_rejected(void)
{
    // 长度字段 200 超过上限：即使缓冲区足够大也必须拒绝，不能写越界
    static uint8_t buf[203];
    buf[0] = FRAME_PARSER_SOF;
    buf[1] = 200U;
    frame_parser_frame_t out;
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_SIZE, frame_parser_parse(buf, sizeof(buf), &out));
}

static void test_bad_checksum(void)
{
    const uint8_t buf[] = {FRAME_PARSER_SOF, 1U, 0x10U, 0x00U};
    frame_parser_frame_t out;
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_CRC, frame_parser_parse(buf, sizeof(buf), &out));
}

void app_main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_valid_frame);
    RUN_TEST(test_null_args);
    RUN_TEST(test_bad_sof);
    RUN_TEST(test_oversized_length_rejected);
    RUN_TEST(test_bad_checksum);
    exit(UNITY_END() == 0 ? 0 : 1);
}
