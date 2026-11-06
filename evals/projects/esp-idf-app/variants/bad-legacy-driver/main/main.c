#include <stdint.h>

#include "esp_log.h"
#include "driver/timer.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "event_counter.h"
#include "frame_parser.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "app";

// 新镜像的最小自检：解析器对已知帧给出预期结果
static bool self_test(void)
{
    static const uint8_t frame[] = {FRAME_PARSER_SOF, 2U, 0x10U, 0x20U, 0x32U};
    frame_parser_frame_t out;
    return frame_parser_parse(frame, sizeof(frame), &out) == ESP_OK && out.len == 2U;
}

// 按 OTA 回滚流程确认或拒绝本镜像（ESP-007）
static void confirm_image(void)
{
    const esp_partition_t *running = esp_ota_get_running_partition();
    esp_ota_img_states_t state;
    if (esp_ota_get_state_partition(running, &state) != ESP_OK || state != ESP_OTA_IMG_PENDING_VERIFY) {
        return;
    }
    if (self_test()) {
        esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
        if (err != ESP_OK) {
            // 未能确认则下次复位会回滚：记录原因，不静默忽略（ESP-004）
            ESP_LOGE(TAG, "cancel rollback failed: %s", esp_err_to_name(err));
        }
    } else {
        ESP_LOGE(TAG, "self-test failed, rolling back");
        // 成功时不会返回；返回即表示回滚失败
        esp_err_t err = esp_ota_mark_app_invalid_rollback_and_reboot();
        ESP_LOGE(TAG, "rollback failed: %s", esp_err_to_name(err));
    }
}

void app_main(void)
{
    // 启动时记录复位原因（FAULT-001）
    ESP_LOGI(TAG, "reset reason: %d", (int)esp_reset_reason());
    confirm_image();
    esp_err_t err = event_counter_start(GPIO_NUM_4);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "event counter disabled: %s", esp_err_to_name(err));
    }
    TickType_t last_wake = xTaskGetTickCount();
    for (;;) {
        event_counter_snapshot_t snap;
        event_counter_get(&snap);
        ESP_LOGI(TAG, "events=%lu", (unsigned long)snap.count);
        xTaskDelayUntil(&last_wake, pdMS_TO_TICKS(1000));
    }
}
