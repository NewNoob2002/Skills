/// @file dma_buffer.hpp
/// @brief DMA 接收缓冲区与所有权租约。
///
/// DMA 不属于 C++ 内存模型：CPU 与 DMA 的可见性靠 cache 维护与屏障，而不是 std::atomic。
/// 租约存活期间 CPU 不得访问缓冲区；complete() 在 invalidate D-cache 后交还只读视图。
/// Ops 需提供：start_rx(span)、abort(span)、invalidate_dcache(span)，均为 noexcept。

#ifndef PROJ_DMA_BUFFER_HPP
#define PROJ_DMA_BUFFER_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <utility>

#include "etl/span.h"

namespace proj
{

/// Cortex-M7 的 D-cache 行为 32 字节；无 cache 的内核可设为 alignof(std::max_align_t)。
inline constexpr std::size_t kCacheLineSize = 32U;

template <std::size_t Size> struct alignas(kCacheLineSize) DmaBuffer
{
    static_assert((Size % kCacheLineSize) == 0U, "DMA buffer must cover whole cache lines");
    std::array<std::uint8_t, Size> bytes{};
};

template <class Ops> class DmaRxLease
{
  public:
    DmaRxLease (etl::span<std::uint8_t> buffer, Ops & ops) noexcept : buffer_(buffer), ops_(&ops)
    {
        ops_->start_rx(buffer_);
    }

    DmaRxLease (DmaRxLease && other) noexcept
        : buffer_(other.buffer_), ops_(std::exchange(other.ops_, nullptr))
    {
    }

    DmaRxLease & operator=(DmaRxLease &&)      = delete;
    DmaRxLease (const DmaRxLease &)            = delete;
    DmaRxLease & operator=(const DmaRxLease &) = delete;

    ~DmaRxLease ()
    {
        if (nullptr != ops_)
        {
            ops_->abort(buffer_);
        }
    }

    /// 传输完成（通常由 DMA 完成通知唤醒的任务调用）后取回数据；之后租约失效。
    [[nodiscard]] etl::span<const std::uint8_t>
    complete () noexcept
    {
        ops_->invalidate_dcache(buffer_);
        ops_ = nullptr;
        return buffer_;
    }

  private:
    etl::span<std::uint8_t> buffer_;
    Ops *                   ops_;
};

} // namespace proj

#endif // PROJ_DMA_BUFFER_HPP
