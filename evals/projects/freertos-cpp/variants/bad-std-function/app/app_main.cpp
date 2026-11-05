// 组合根（Cortex-M0+ 目标）：把 ADC 采样喂给遥测，结果写入调试可见的全局变量。
#include <cstdint>
#include <functional>

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
        on_report_(average);
    }

  private:
    std::int32_t volatile last_average_{0};
    std::function<void(std::int32_t)> on_report_{[this] (std::int32_t avg)
                                                 { last_average_ = avg; }};
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
