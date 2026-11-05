// MovingAverage 与 Telemetry 的 host 单元测试。期望值按定义手算：平均值 = 窗口内样本和 / 样本数。
#include <cstdint>
#include <vector>

#include "moving_average.hpp"
#include "report_sink.hpp"
#include "telemetry.hpp"

#include "CppUTest/TestHarness.h" // CppUTest 头必须最后包含（见 references/verification/cpp-testing.md §2）

namespace
{

class FakeSink final : public proj::ReportSink
{
  public:
    void
    report (std::int32_t average) noexcept override
    {
        reports.push_back(average);
    }
    std::vector<std::int32_t> reports;
};

} // namespace

TEST_GROUP(MovingAverage){};

TEST(MovingAverage, EmptyAverageIsZero)
{
    proj::filter::MovingAverage<4> avg;
    LONGS_EQUAL(0, avg.average());
}

TEST(MovingAverage, PartialWindowAveragesExistingSamples)
{
    proj::filter::MovingAverage<4> avg;
    avg.add(10);
    avg.add(20);
    LONGS_EQUAL(15, avg.average());
}

TEST(MovingAverage, FullWindowDropsOldestSample)
{
    proj::filter::MovingAverage<4> avg;
    for (std::int32_t s : {10, 20, 30, 40, 50})
    {
        avg.add(s);
    }
    LONGS_EQUAL(35, avg.average()); // (20+30+40+50)/4
}

TEST(MovingAverage, NegativeSamples)
{
    proj::filter::MovingAverage<2> avg;
    avg.add(-10);
    avg.add(-30);
    LONGS_EQUAL(-20, avg.average());
}

TEST_GROUP(Telemetry){};

TEST(Telemetry, ReportsEveryFourSamples)
{
    FakeSink                   sink;
    proj::telemetry::Telemetry telemetry{sink};
    for (std::int32_t s : {1, 2, 3})
    {
        telemetry.on_sample(s);
    }
    LONGS_EQUAL(0, static_cast<long>(sink.reports.size()));
    telemetry.on_sample(6);
    LONGS_EQUAL(1, static_cast<long>(sink.reports.size()));
    LONGS_EQUAL(3, sink.reports[0]); // (1+2+3+6)/4
}
