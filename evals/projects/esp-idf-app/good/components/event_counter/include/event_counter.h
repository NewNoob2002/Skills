#pragma once

#include <stdint.h>

#include "driver/gpio.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t count;
    uint32_t last_cycles;
} event_counter_snapshot_t;

/**
 * @brief 在 gpio_num 的上升沿计数。ISR 在 IRAM 中运行，Flash 写入期间也不会丢事件。
 *
 * @return ESP_OK 成功；ESP_ERR_INVALID_ARG 引脚无效；或透传 GPIO 驱动错误
 */
esp_err_t event_counter_start(gpio_num_t gpio_num);

/** @brief 读取计数快照（任务上下文，跨核安全）；out 为 NULL 时不做任何事。 */
void event_counter_get(event_counter_snapshot_t *out);

#ifdef __cplusplus
}
#endif
