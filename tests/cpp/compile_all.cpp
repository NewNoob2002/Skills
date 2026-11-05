// skill 自测：实例化 assets/cpp/templates 中的全部模板，供 arm-none-eabi-g++ 严格告警编译。
// 测试夹具本身的常量不受魔数规则约束；被包含的模板仍受全部检查。
// NOLINTBEGIN(readability-magic-numbers)
#include <cstdint>
#include <mutex>

#include "bme280.hpp"
#include "dma_buffer.hpp"
#include "irq_lock.hpp"
#include "os_mutex.hpp"
#include "uart_divider.hpp"
#include "vendor_i2c_bus.hpp"
#if !defined(PROJ_SKIP_SPSC)
#include "spsc_ring.hpp"
#endif

namespace
{
struct FakeDmaOps
{
    void start_rx (etl::span<std::uint8_t>) noexcept {}
    void abort (etl::span<std::uint8_t>) noexcept {}
    void invalidate_dcache (etl::span<std::uint8_t>) noexcept {}
};

constinit proj::VendorI2cBus g_bus{0x76U};
constinit proj::Bme280<proj::VendorI2cBus> g_sensor{g_bus};
proj::DmaBuffer<64> g_dma;
#if !defined(PROJ_SKIP_SPSC)
constinit proj::SpscRing<std::uint8_t, 64> g_ring;
#endif
static_assert(proj::UartDivider<80000000U, 115200U>::kDivider == 694U);
} // namespace

extern volatile std::uint32_t g_brr;
volatile std::uint32_t g_brr = 0U;

int compile_all_entry (osMutexId_t mutex_id)
{
    g_brr = proj::UartDivider<80000000U, 115200U>::kDivider;
    {
        const proj::IrqLock lock;
    }
    proj::OsMutex mutex(mutex_id);
    {
        const std::lock_guard<proj::OsMutex> guard(mutex);
    }
#if !defined(PROJ_SKIP_SPSC)
    std::uint8_t byte = 0U;
    static_cast<void>(g_ring.push(0x55U));
    static_cast<void>(g_ring.pop(byte));
#endif
    FakeDmaOps ops;
    proj::DmaRxLease<FakeDmaOps> lease(g_dma.bytes, ops);
    const auto data = lease.complete();
    return (proj::Status::kOk == g_sensor.init()) ? static_cast<int>(data.size()) : -1;
}
// NOLINTEND(readability-magic-numbers)
