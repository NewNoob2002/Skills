// 固定容量块池 + 标准库分配器适配：让 std::vector 在 T1/T2 使用有界存储。
// 只允许一次预留；再次分配（扩容）直接中止，避免隐式堆分配。
#ifndef PROJ_MODULE_FILTER_FIXED_POOL_ALLOCATOR_HPP
#define PROJ_MODULE_FILTER_FIXED_POOL_ALLOCATOR_HPP

#include <cstddef>
#include <cstdlib>

namespace proj::filter
{

template <class T, std::size_t Capacity> class FixedBlockPool final
{
    static_assert(Capacity > 0U, "pool capacity must be positive");

  public:
    FixedBlockPool () noexcept                         = default;
    FixedBlockPool (const FixedBlockPool &)            = delete;
    FixedBlockPool & operator=(const FixedBlockPool &) = delete;

    [[nodiscard]] T *
    allocate (std::size_t count) noexcept
    {
        if ((count == 0U) || (count > Capacity) || in_use_)
        {
            // -fno-exceptions：不能返回 nullptr（vector 视为 UB），也不能依赖 bad_alloc。
            std::abort();
        }
        in_use_ = true;
        return static_cast<T *>(static_cast<void *>(storage_));
    }

    void
    deallocate (T * ptr, std::size_t count) noexcept
    {
        static_cast<void>(ptr);
        static_cast<void>(count);
        in_use_ = false;
    }

  private:
    alignas(T) unsigned char storage_[sizeof(T) * Capacity]{};
    bool in_use_{false};
};

template <class T, std::size_t Capacity> class FixedPoolAllocator
{
  public:
    using value_type = T;
    using pool_type  = FixedBlockPool<T, Capacity>;

    template <class U> struct rebind
    {
        using other = FixedPoolAllocator<U, Capacity>;
    };

    explicit FixedPoolAllocator (pool_type & pool) noexcept : pool_(&pool) {}

    template <class U>
    FixedPoolAllocator (const FixedPoolAllocator<U, Capacity> & other) noexcept : pool_(other.pool_)
    {
    }

    [[nodiscard]] std::size_t
    max_size () const noexcept
    {
        return Capacity;
    }

    [[nodiscard]] T *
    allocate (std::size_t count)
    {
        return pool_->allocate(count);
    }

    void
    deallocate (T * ptr, std::size_t count) noexcept
    {
        pool_->deallocate(ptr, count);
    }

    template <class U>
    [[nodiscard]] bool
    operator==(const FixedPoolAllocator<U, Capacity> & other) const noexcept
    {
        return static_cast<const void *>(pool_) == static_cast<const void *>(other.pool_);
    }

    template <class U>
    [[nodiscard]] bool
    operator!=(const FixedPoolAllocator<U, Capacity> & other) const noexcept
    {
        return !(*this == other);
    }

  private:
    pool_type * pool_;

    template <class, std::size_t> friend class FixedPoolAllocator;
};

} // namespace proj::filter

#endif // PROJ_MODULE_FILTER_FIXED_POOL_ALLOCATOR_HPP
