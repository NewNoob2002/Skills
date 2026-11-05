// 固定窗口滑动平均。容量在编译期确定，不分配内存；未满窗口时按已有样本数求平均。
#ifndef PROJ_MODULE_FILTER_MOVING_AVERAGE_HPP
#define PROJ_MODULE_FILTER_MOVING_AVERAGE_HPP

#include <array>
#include <cstddef>
#include <cstdint>

namespace proj::filter
{

template <std::size_t N> class MovingAverage final
{
    static_assert((N > 0U) && (N <= 64U), "window must be 1..64 samples");

  public:
    void
    add (std::int32_t sample) noexcept
    {
        sum_ -= buffer_[next_];
        buffer_[next_] = sample;
        sum_ += sample;
        next_ = (next_ + 1U) % N;
        if (count_ < N)
        {
            ++count_;
        }
    }

    [[nodiscard]] std::int32_t
    average () const noexcept
    {
        if (count_ == 0U)
        {
            return 0;
        }
        return static_cast<std::int32_t>(sum_ / static_cast<std::int64_t>(count_));
    }

    [[nodiscard]] std::size_t
    count () const noexcept
    {
        return count_;
    }

  private:
    std::array<std::int32_t, N> buffer_{};
    std::int64_t                sum_{0};
    std::size_t                 next_{0U};
    std::size_t                 count_{0U};
};

} // namespace proj::filter

#endif // PROJ_MODULE_FILTER_MOVING_AVERAGE_HPP
