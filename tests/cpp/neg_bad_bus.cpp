// 预期编译失败：总线 read 返回 int 而不是 proj::Status
#include "bme280.hpp"
struct BadBus
{
    int read (std::uint8_t, etl::span<std::uint8_t>) { return 0; }
    proj::Status write (std::uint8_t, etl::span<const std::uint8_t>) { return proj::Status::kOk; }
};
BadBus g_bad;
proj::Bme280<BadBus> g_dev{g_bad};
