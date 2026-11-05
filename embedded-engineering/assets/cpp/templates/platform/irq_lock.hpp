/// @file irq_lock.hpp
/// @brief Cortex-M 中断锁（RAII）：保存并恢复 PRIMASK，可嵌套。
///
/// 只保护极短临界区（Core Guidelines CP.43）。会屏蔽所有可屏蔽中断，包括高于
/// configMAX_SYSCALL_INTERRUPT_PRIORITY 的控制环中断；需要只屏蔽部分优先级时改用 BASEPRI。
/// 上下文：ISR-safe，thread-safe（单核）。多核 SMP 上不足以互斥，需要自旋锁。

#ifndef PROJ_IRQ_LOCK_HPP
#define PROJ_IRQ_LOCK_HPP

#include <cstdint>

#include "cmsis_compiler.h"

namespace proj
{

class IrqLock
{
  public:
    IrqLock () noexcept : primask_(__get_PRIMASK()) { __disable_irq(); }

    ~IrqLock () { __set_PRIMASK(primask_); }

    IrqLock (const IrqLock &)            = delete;
    IrqLock & operator=(const IrqLock &) = delete;

  private:
    std::uint32_t primask_;
};

/// etl::queue_spsc_isr 等组件要求的静态访问策略（TAccess::lock / unlock）。
/// 不可嵌套：只用于 ETL 内部成对调用的短区间。
struct IrqAccessPolicy
{
    static void
    lock () noexcept
    {
        __disable_irq();
    }

    static void
    unlock () noexcept
    {
        __enable_irq();
    }
};

} // namespace proj

#endif // PROJ_IRQ_LOCK_HPP
