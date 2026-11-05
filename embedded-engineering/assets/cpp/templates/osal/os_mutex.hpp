/// @file os_mutex.hpp
/// @brief CMSIS-RTOS2 互斥量的 BasicLockable 包装，可配合 std::lock_guard / std::unique_lock。
///
/// 上下文：thread-safe；**不是 ISR-safe**（互斥量不能在 ISR 中获取）。
/// 只包含 <mutex> 中的 lock_guard / unique_lock，不使用 std::mutex（MCU RTOS 上不可用或不集成）。

#ifndef PROJ_OS_MUTEX_HPP
#define PROJ_OS_MUTEX_HPP

#include "cmsis_os2.h"

namespace proj
{

class OsMutex
{
  public:
    /// id 由 osMutexNew() 在初始化期创建（推荐静态控制块：osMutexAttr_t.cb_mem）。
    explicit OsMutex (osMutexId_t id) noexcept : id_(id) {}

    void
    lock () noexcept
    {
        // 永久等待：返回值只可能是 osOK，或在 ISR 中误用时的 osErrorISR（由调试断言捕获）。
        static_cast<void>(osMutexAcquire(id_, osWaitForever));
    }

    void
    unlock () noexcept
    {
        static_cast<void>(osMutexRelease(id_));
    }

    ~OsMutex ()                          = default;
    OsMutex (const OsMutex &)            = delete;
    OsMutex & operator=(const OsMutex &) = delete;

  private:
    osMutexId_t id_;
};

} // namespace proj

#endif // PROJ_OS_MUTEX_HPP
