// T2 示例：std::vector + 固定块池分配器。容量编译期固定，构造期一次性分配，运行期只读写。
#ifndef PROJ_MODULE_FILTER_MOVING_AVERAGE_POOL_HPP
#define PROJ_MODULE_FILTER_MOVING_AVERAGE_POOL_HPP

#include <cstddef>
#include <cstdint>
#include <vector>

#include "fixed_pool_allocator.hpp"

namespace proj::filter
{

template <std::size_t N> class MovingAveragePool final
{
    static_assert((N > 0U) && (N <= 64U), "window must be 1..64 samples");

  public:
    MovingAveragePool () noexcept : buffer_(N, 0, Alloc(pool_)) {}

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
    using Alloc = FixedPoolAllocator<std::int32_t, N>;

    FixedBlockPool<std::int32_t, N>  pool_{};
    std::vector<std::int32_t, Alloc> buffer_;
    std::int64_t                     sum_{0};
    std::size_t                      next_{0U};
    std::size_t                      count_{0U};
};

} // namespace proj::filter

#endif // PROJ_MODULE_FILTER_MOVING_AVERAGE_POOL_HPP
