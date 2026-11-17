// 主机分进程验证护栏；故障路径必须打印预期标记并收到 trap 信号。
#include "../../skills/embedded-engineering/assets/cpp/templates/bsp/heap_guard.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <limits>
#include <new>

namespace {
constexpr std::align_val_t kAlign = std::align_val_t{64};

void* allocate(unsigned index, std::size_t size)
{
    switch (index) {
    case 0:
        return ::operator new(size);
    case 1:
        return ::operator new[](size);
    case 2:
        return ::operator new(size, std::nothrow);
    case 3:
        return ::operator new[](size, std::nothrow);
    case 4:
        return ::operator new(size, kAlign);
    case 5:
        return ::operator new[](size, kAlign);
    case 6:
        return ::operator new(size, kAlign, std::nothrow);
    default:
        return ::operator new[](size, kAlign, std::nothrow);
    }
}

void release(unsigned index, void* block)
{
    switch (index) {
    case 0:
        ::operator delete(block);
        break;
    case 1:
        ::operator delete[](block);
        break;
    case 2:
        ::operator delete(block, std::size_t{8});
        break;
    case 3:
        ::operator delete[](block, std::size_t{8});
        break;
    case 4:
        ::operator delete(block, std::nothrow);
        break;
    case 5:
        ::operator delete[](block, std::nothrow);
        break;
    case 6:
        ::operator delete(block, kAlign);
        break;
    case 7:
        ::operator delete[](block, kAlign);
        break;
    case 8:
        ::operator delete(block, std::size_t{8}, kAlign);
        break;
    case 9:
        ::operator delete[](block, std::size_t{8}, kAlign);
        break;
    case 10:
        ::operator delete(block, kAlign, std::nothrow);
        break;
    default:
        ::operator delete[](block, kAlign, std::nothrow);
        break;
    }
}
} // namespace

int main(int argc, char** argv)
{
    if (argc != 2) {
        return 90;
    }
    const char* mode = argv[1];
    if (std::strcmp(mode, "before") == 0) {
        for (unsigned index = 0; index < 8; ++index) {
            void* block = allocate(index, 8);
            if (block == nullptr ||
                (index >= 4 && reinterpret_cast<std::uintptr_t>(block) % 64 != 0)) {
                return 91;
            }
        }
    } else if (std::strcmp(mode, "capacity") == 0) {
        if (::operator new(1024, kAlign, std::nothrow) == nullptr ||
            ::operator new(1, std::nothrow) != nullptr) {
            return 92;
        }
    } else if (std::strcmp(mode, "overflow") == 0) {
        const auto huge = std::numeric_limits<std::size_t>::max();
        if (::operator new(huge, std::nothrow) != nullptr ||
            ::operator new(huge, kAlign, std::nothrow) != nullptr) {
            return 93;
        }
    } else if (std::strcmp(mode, "padding") == 0) {
        if (::operator new(1000, std::nothrow) == nullptr ||
            ::operator new(1, kAlign, std::nothrow) != nullptr ||
            ::operator new(24, std::align_val_t{1}, std::nothrow) == nullptr) {
            return 94;
        }
    } else if (std::strcmp(mode, "invalid-align") == 0) {
        for (auto alignment : {0U, 3U, 128U}) {
            if (::operator new(1, std::align_val_t{alignment}, std::nothrow) != nullptr) {
                return 95;
            }
        }
    } else if (std::strcmp(mode, "zero") == 0) {
        void* first = ::operator new(0, std::nothrow);
        void* second = ::operator new(0, std::nothrow);
        if (first == nullptr || second == nullptr || first == second) {
            return 96;
        }
    } else if (std::strcmp(mode, "delete-null") == 0) {
        for (unsigned index = 0; index < 12; ++index) {
            release(index, nullptr);
        }
    } else if (std::strncmp(mode, "lock", 4) == 0) {
        const unsigned index = static_cast<unsigned>(mode[4] - '0');
        proj::heap_guard_lock();
        if (index == 2 || index == 3 || index >= 6) {
            if (allocate(index, 8) != nullptr) {
                return 97;
            }
        } else {
            std::printf("HEAP_EXPECT_TRAP:%s\n", mode);
            std::fflush(stdout);
            (void)allocate(index, 8);
            return 98;
        }
    } else if (std::strncmp(mode, "free", 4) == 0) {
        const unsigned index = static_cast<unsigned>(mode[4] - 'A');
        void* block = ::operator new(8);
        std::printf("HEAP_EXPECT_TRAP:%s\n", mode);
        std::fflush(stdout);
        release(index, block);
        return 98;
    } else if (std::strcmp(mode, "oversize") == 0) {
        std::printf("HEAP_EXPECT_TRAP:%s\n", mode);
        std::fflush(stdout);
        (void)::operator new(std::numeric_limits<std::size_t>::max());
        return 98;
    } else {
        return 99;
    }
    std::printf("HEAP_PASS:%s\n", mode);
    return 0;
}
