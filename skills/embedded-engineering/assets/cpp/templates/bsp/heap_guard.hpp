/// @file heap_guard.hpp
/// @brief T1 “仅初始化期分配”规则的运行期护栏。

#ifndef PROJ_HEAP_GUARD_HPP
#define PROJ_HEAP_GUARD_HPP

namespace proj
{

/// 单线程初始化完成、启动调度器之前调用；之后普通 new 故障，nothrow 返回 nullptr。
/// 不可与分配并发；不拦截 C 分配或类专属分配器，详见 references/cpp/heap-guard.md。
void heap_guard_lock () noexcept;

} // namespace proj

#endif // PROJ_HEAP_GUARD_HPP
