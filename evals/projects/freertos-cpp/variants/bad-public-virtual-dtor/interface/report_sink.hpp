// 遥测结果的输出接口。运行期选择实现（UART、日志、测试 fake），因此用纯虚接口：
// 受保护的非虚析构 + final 实现（CPP-011），不经基类指针删除对象，也不拉入 operator delete。
#ifndef PROJ_INTERFACE_REPORT_SINK_HPP
#define PROJ_INTERFACE_REPORT_SINK_HPP

#include <cstdint>

namespace proj
{

class ReportSink
{
  public:
    virtual void report (std::int32_t average) noexcept = 0;
    virtual ~ReportSink ()                              = default;

  protected:
    ReportSink ()                              = default;
    ReportSink (ReportSink const &)            = default;
    ReportSink & operator=(ReportSink const &) = default;
};

} // namespace proj

#endif // PROJ_INTERFACE_REPORT_SINK_HPP
