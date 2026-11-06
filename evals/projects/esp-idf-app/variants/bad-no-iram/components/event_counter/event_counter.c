#include "event_counter.h"

#include "esp_attr.h"
#include "esp_check.h"
#include "esp_cpu.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "event_counter";

// ISR 与任务可能运行在不同核上：用自旋锁而不是 taskDISABLE_INTERRUPTS（ESP-001）
static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static DRAM_ATTR event_counter_snapshot_t s_state;

// Flash 写入期间 cache 关闭：处理函数放 IRAM，数据放 DRAM（ESP-002）
static void event_counter_isr(void *arg)
{
    (void)arg;
    // esp_cpu_get_cycle_count() 在 Xtensa 与 RISC-V 目标上都可用（ESP-008）
    const uint32_t cycles = (uint32_t)esp_cpu_get_cycle_count();
    taskENTER_CRITICAL_ISR(&s_lock);
    s_state.count++;
    s_state.last_cycles = cycles;
    taskEXIT_CRITICAL_ISR(&s_lock);
}

esp_err_t event_counter_start(gpio_num_t gpio_num)
{
    ESP_RETURN_ON_FALSE(GPIO_IS_VALID_GPIO(gpio_num), ESP_ERR_INVALID_ARG, TAG, "invalid gpio %d", gpio_num);
    const gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << gpio_num,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_POSEDGE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&cfg), TAG, "gpio_config failed");
    ESP_RETURN_ON_ERROR(gpio_install_isr_service(ESP_INTR_FLAG_IRAM), TAG, "isr service failed");
    ESP_RETURN_ON_ERROR(gpio_isr_handler_add(gpio_num, event_counter_isr, NULL), TAG, "handler add failed");
    return ESP_OK;
}

void event_counter_get(event_counter_snapshot_t *out)
{
    if (out == NULL) {
        return;
    }
    taskENTER_CRITICAL(&s_lock);
    *out = s_state;
    taskEXIT_CRITICAL(&s_lock);
}
