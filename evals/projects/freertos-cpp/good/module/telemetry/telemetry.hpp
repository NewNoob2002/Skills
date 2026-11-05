// 遥测：对采样做滑动平均，每 kReportEvery 个样本输出一次平均值。
// 线程模型：只在一个任务中调用 on_sample()；不可在 ISR 中调用（ISR 只把样本放进队列）。
#ifndef PROJ_MODULE_TELEMETRY_TELEMETRY_HPP
#define PROJ_MODULE_TELEMETRY_TELEMETRY_HPP

#include <cstddef>
#include <cstdint>

#include "moving_average.hpp"
#include "report_sink.hpp"

namespace proj::telemetry
{

class Telemetry final
{
  public:
    static constexpr std::size_t kWindow      = 4U;
    static constexpr std::size_t kReportEvery = 4U;

    explicit constexpr Telemetry (ReportSink & sink) noexcept : sink_{sink} {}

    void on_sample (std::int32_t sample) noexcept;

  private:
    ReportSink &                   sink_;
    filter::MovingAverage<kWindow> filter_{};
    std::size_t                    since_report_{0U};
};

} // namespace proj::telemetry

#endif // PROJ_MODULE_TELEMETRY_TELEMETRY_HPP
