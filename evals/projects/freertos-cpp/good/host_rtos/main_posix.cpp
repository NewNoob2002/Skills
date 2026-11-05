// FreeRTOS POSIX 移植上的集成测试：producer 任务经队列发送采样，consumer 任务驱动 Telemetry。
// 期望：发送 8 个样本（10..80）后，最后一次报告的平均值为 (50+60+70+80)/4 = 65。
// 看门狗任务在 2000 tick 内没有看到结果就以退出码 2 结束，用来发现死锁或丢消息。
#include <cstdint>
#include <cstdio>
#include <cstdlib>

#include "report_sink.hpp"
#include "telemetry.hpp"

extern "C"
{
#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"
}

namespace
{

constexpr std::int32_t kSamples[]       = {10, 20, 30, 40, 50, 60, 70, 80};
constexpr std::int32_t kExpectedLast    = 65;
constexpr int          kReportsExpected = 2;

QueueHandle_t g_samples = nullptr;

class CheckingSink final : public proj::ReportSink
{
  public:
    void
    report (std::int32_t average) noexcept override
    {
        ++reports_;
        last_ = average;
        if (reports_ == kReportsExpected)
        {
            std::printf("rtos_host: last average %d (expected %d)\n", static_cast<int>(last_),
                        static_cast<int>(kExpectedLast));
            std::exit(last_ == kExpectedLast ? 0 : 1);
        }
    }

  private:
    int          reports_{0};
    std::int32_t last_{0};
};

CheckingSink               g_sink;
proj::telemetry::Telemetry g_telemetry{g_sink};

void
producer_task (void *)
{
    for (std::int32_t const sample : kSamples)
    {
        (void) xQueueSend(g_samples, &sample, portMAX_DELAY);
        vTaskDelay(1);
    }
    vTaskDelete(nullptr);
}

void
consumer_task (void *)
{
    for (;;)
    {
        std::int32_t sample = 0;
        if (xQueueReceive(g_samples, &sample, portMAX_DELAY) == pdPASS)
        {
            g_telemetry.on_sample(sample);
        }
    }
}

void
watchdog_task (void *)
{
    vTaskDelay(2000);
    std::printf("rtos_host: timeout, no result within 2000 ticks\n");
    std::exit(2);
}

} // namespace

int
main ()
{
    g_samples = xQueueCreate(4, sizeof(std::int32_t));
    configASSERT(g_samples != nullptr);
    configASSERT(xTaskCreate(producer_task, "prod", configMINIMAL_STACK_SIZE, nullptr, 2,
                             nullptr) == pdPASS);
    configASSERT(xTaskCreate(consumer_task, "cons", configMINIMAL_STACK_SIZE, nullptr, 3,
                             nullptr) == pdPASS);
    configASSERT(xTaskCreate(watchdog_task, "wdog", configMINIMAL_STACK_SIZE, nullptr, 4,
                             nullptr) == pdPASS);
    vTaskStartScheduler();
    return 4; // 调度器不应返回
}
