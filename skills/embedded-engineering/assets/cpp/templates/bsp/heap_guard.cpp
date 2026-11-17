/// @file heap_guard.cpp
/// @brief T1 初始化期线性区：全局 C++17 new/delete 护栏；不是 C malloc 拦截器。
///
/// 普通 new 失败进入故障，nothrow 失败返回 nullptr。仅支持单线程初始化，非 ISR；
/// 锁定前完成全部分配，调度器启动前调用 heap_guard_lock。释放非空块视为设计错误。

#include "heap_guard.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <new>

namespace
{

constexpr std::size_t kInitArenaSize = 1024U; // 按项目初始化需求设置并记录依据
constexpr std::size_t kMaxAlignment  = 64U;   // 超出此对齐的请求明确失败，不回落系统堆

alignas(kMaxAlignment) std::array<std::uint8_t, kInitArenaSize> g_arena{};
std::size_t g_arena_used = 0U;
bool        g_locked     = false;

[[noreturn]] void
heap_fault () noexcept
{
    // 真实项目：记录故障原因后进入安全态/复位。
    __builtin_trap();
}

void *
try_allocate (std::size_t size, std::size_t alignment) noexcept
{
    if (g_locked || (alignment == 0U) || (alignment > kMaxAlignment) ||
        ((alignment & (alignment - 1U)) != 0U))
    {
        return nullptr;
    }
    if (size == 0U)
    {
        size = 1U; // 零长请求仍返回不同的非空块，直到容量耗尽
    }
    const std::size_t padding = (alignment - (g_arena_used & (alignment - 1U))) & (alignment - 1U);
    const std::size_t remaining = kInitArenaSize - g_arena_used;
    if ((padding > remaining) || (size > (remaining - padding)))
    {
        return nullptr; // 先减后比较，防止 SIZE_MAX 请求在舍入中溢出
    }
    void * p_block = &g_arena[g_arena_used + padding];
    g_arena_used += padding + size;
    return p_block;
}

void *
allocate_or_fault (std::size_t size, std::size_t alignment)
{
    void * p_block = try_allocate(size, alignment);
    if (p_block == nullptr)
    {
        heap_fault();
    }
    return p_block;
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
    return allocate_or_fault(size, alignof(std::max_align_t));
}

void *
operator new[](std::size_t size)
{
    return operator new(size);
}

void *
operator new(std::size_t size, const std::nothrow_t &) noexcept
{
    return try_allocate(size, alignof(std::max_align_t));
}

void *
operator new[](std::size_t size, const std::nothrow_t & tag) noexcept
{
    return operator new(size, tag);
}

void *
operator new(std::size_t size, std::align_val_t alignment)
{
    return allocate_or_fault(size, static_cast<std::size_t>(alignment));
}

void *
operator new[](std::size_t size, std::align_val_t alignment)
{
    return operator new(size, alignment);
}

void *
operator new(std::size_t size, std::align_val_t alignment, const std::nothrow_t &) noexcept
{
    return try_allocate(size, static_cast<std::size_t>(alignment));
}

void *
operator new[](std::size_t size, std::align_val_t alignment, const std::nothrow_t & tag) noexcept
{
    return operator new(size, alignment, tag);
}

// 标准 replacement delete 必须接收 void*；这里只检查地址，不解引用。
void
operator delete(void * p_block) noexcept // NOLINT(misc-const-correctness)
{
    if (p_block != nullptr)
    {
        heap_fault();
    }
}

void
operator delete[](void * p_block) noexcept
{
    operator delete(p_block);
}

void
operator delete(void * p_block, std::size_t) noexcept
{
    operator delete(p_block);
}

void
operator delete[](void * p_block, std::size_t) noexcept
{
    operator delete(p_block);
}

void
operator delete(void * p_block, const std::nothrow_t &) noexcept
{
    operator delete(p_block);
}

void
operator delete[](void * p_block, const std::nothrow_t &) noexcept
{
    operator delete(p_block);
}

void
operator delete(void * p_block, std::align_val_t) noexcept
{
    operator delete(p_block);
}

void
operator delete[](void * p_block, std::align_val_t) noexcept
{
    operator delete(p_block);
}

void
operator delete(void * p_block, std::size_t, std::align_val_t) noexcept
{
    operator delete(p_block);
}

void
operator delete[](void * p_block, std::size_t, std::align_val_t) noexcept
{
    operator delete(p_block);
}

void
operator delete(void * p_block, std::align_val_t, const std::nothrow_t &) noexcept
{
    operator delete(p_block);
}

void
operator delete[](void * p_block, std::align_val_t, const std::nothrow_t &) noexcept
{
    operator delete(p_block);
}
