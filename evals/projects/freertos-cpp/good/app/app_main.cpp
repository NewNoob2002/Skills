// 组合根（Cortex-M0+ 目标）：把 ADC 采样喂给遥测，结果写入调试可见的全局变量。
#include <cstdint>

#include "adc.hpp"
#include "report_sink.hpp"
#include "telemetry.hpp"

namespace
{

class DebugSink final : public proj::ReportSink
{
  public:
    void
    report (std::int32_t average) noexcept override
    {
        last_average_ = average;
    }

  private:
    std::int32_t last_average_{0};
};

DebugSink                  g_sink;
proj::telemetry::Telemetry g_telemetry{g_sink};

} // namespace

int
main ()
{
    for (;;)
    {
        g_telemetry.on_sample(proj::bsp::adc_read());
    }
}
