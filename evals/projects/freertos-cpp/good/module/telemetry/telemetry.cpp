#include "telemetry.hpp"

namespace proj::telemetry
{

void
Telemetry::on_sample (std::int32_t sample) noexcept
{
    filter_.add(sample);
    ++since_report_;
    if (since_report_ >= kReportEvery)
    {
        since_report_ = 0U;
        sink_.report(filter_.average());
    }
}

} // namespace proj::telemetry
