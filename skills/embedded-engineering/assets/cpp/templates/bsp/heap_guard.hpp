/// @file heap_guard.hpp
/// @brief T1 “仅初始化期分配”规则的运行期护栏。

#ifndef PROJ_HEAP_GUARD_HPP
#define PROJ_HEAP_GUARD_HPP

namespace proj
{

/// 初始化完成、启动调度器之前调用；之后的 operator new 触发故障。
void heap_guard_lock () noexcept;

} // namespace proj

#endif // PROJ_HEAP_GUARD_HPP
