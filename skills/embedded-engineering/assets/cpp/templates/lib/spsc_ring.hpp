/// @file spsc_ring.hpp
/// @brief 单生产者单消费者无锁环形缓冲（例如 ISR 生产、任务消费）。
///
/// 要求 32 位原子为 lock-free：Cortex-M3/M4/M7/M33 满足；Cortex-M0/M0+（ARMv6-M）不满足，
/// 此时编译失败，应改用 etl::queue_spsc_isr<T, N, proj::IrqAccessPolicy>。
/// 上下文：push 只能在唯一生产者上下文调用，pop 只能在唯一消费者上下文调用；两者都 ISR-safe。

#ifndef PROJ_SPSC_RING_HPP
#define PROJ_SPSC_RING_HPP

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>

namespace proj
{

template <class T, std::size_t Capacity> class SpscRing
{
    static_assert((Capacity & (Capacity - 1U)) == 0U, "Capacity must be a power of two");
    static_assert(Capacity <= 0x80000000U, "Capacity must fit the 32-bit index arithmetic");
    static_assert(std::atomic<std::uint32_t>::is_always_lock_free,
                  "SpscRing needs lock-free 32-bit atomics; use etl::queue_spsc_isr instead");

  public:
    constexpr SpscRing () noexcept = default;

    [[nodiscard]] bool
    push (const T & value) noexcept
    {
        const std::uint32_t head = head_.load(std::memory_order_relaxed);
        if ((head - tail_.load(std::memory_order_acquire)) == Capacity)
        {
            return false;
        }
        buffer_[head & kMask] = value;
        head_.store(head + 1U, std::memory_order_release);
        return true;
    }

    [[nodiscard]] bool
    pop (T & out) noexcept
    {
        const std::uint32_t tail = tail_.load(std::memory_order_relaxed);
        if (tail == head_.load(std::memory_order_acquire))
        {
            return false;
        }
        out = buffer_[tail & kMask];
        tail_.store(tail + 1U, std::memory_order_release);
        return true;
    }

  private:
    static constexpr std::uint32_t kMask = static_cast<std::uint32_t>(Capacity - 1U);

    std::array<T, Capacity>    buffer_{};
    std::atomic<std::uint32_t> head_{0U};
    std::atomic<std::uint32_t> tail_{0U};
};

} // namespace proj

#endif // PROJ_SPSC_RING_HPP
