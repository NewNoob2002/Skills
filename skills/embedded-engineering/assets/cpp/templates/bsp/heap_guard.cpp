/// @file heap_guard.cpp
/// @brief 替换全局 operator new/delete：初始化期从固定线性区分配，锁定后或释放时立即陷入故障。
///
/// 适用 T1（仅初始化期分配）。T0 不应链接本文件：T0 禁止任何堆，由 cpp_cost.py 检查
/// operator new 是否存在。T2 应改为注入式分配器或固定池。
/// 与 -fno-exceptions 配合：分配失败不抛 std::bad_alloc，直接故障。

#include <array>
#include <cstddef>
#include <cstdint>
#include <new>

#include "heap_guard.hpp"

namespace
{

constexpr std::size_t kInitArenaSize = 1024U; // 按项目初始化期实际需求设置并记录依据

alignas(std::max_align_t) std::array<std::uint8_t, kInitArenaSize> g_arena{};
std::size_t g_arena_used = 0U;
bool        g_locked     = false;

[[noreturn]] void
heap_fault () noexcept
{
    // 真实项目：记录故障原因后进入安全态/复位。
    __builtin_trap();
}

} // namespace

void
proj::heap_guard_lock () noexcept
{
    g_locked = true;
}

void *
operator new(std::size_t size)
{
    constexpr std::size_t kAlign  = alignof(std::max_align_t);
    const std::size_t     rounded = (size + (kAlign - 1U)) & ~(kAlign - 1U);

    if (g_locked || (rounded > (kInitArenaSize - g_arena_used)))
    {
        heap_fault();
    }
    void * p_block = &g_arena[g_arena_used];
    g_arena_used += rounded;
    return p_block;
}

void *
operator new[](std::size_t size)
{
    return operator new(size);
}

void
operator delete(void *) noexcept
{
    heap_fault();
}

void
operator delete[](void *) noexcept
{
    heap_fault();
}

void
operator delete(void *, std::size_t) noexcept
{
    heap_fault();
}

void
operator delete[](void *, std::size_t) noexcept
{
    heap_fault();
}
