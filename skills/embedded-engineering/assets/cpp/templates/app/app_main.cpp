/// @file app_main.cpp
/// @brief 组合根（示例模板）：静态对象、初始化顺序、C 入口与 ISR 向量。
///
/// 生成代码（CubeMX 等）的 main.c 保持为 C，在 USER CODE 区调用 app_main()。
/// 全局对象全部 constinit：常量初始化进 .data/.bss，不依赖 __libc_init_array 的执行顺序。

#include <cstdint>

#include "bme280.hpp"
#include "heap_guard.hpp"
#include "proj_status.hpp"
#include "vendor_i2c_bus.hpp"

namespace proj
{
namespace
{

constexpr std::uint8_t kBme280Address = 0x76U;

constinit VendorI2cBus         g_sensor_bus{kBme280Address};
constinit Bme280<VendorI2cBus> g_barometer{g_sensor_bus};

} // namespace
} // namespace proj

extern "C"
{
    void board_clock_init (void);
    void app_enter_safe_state (void);

    /// 由 main.c 在 HAL/时钟初始化之后调用；不返回。
    [[noreturn]] void
    app_main (void)
    {
        board_clock_init();

        if (proj::Status::kOk != proj::g_barometer.init())
        {
            // 依赖缺失：进入降级/安全态，而不是带着未初始化的驱动继续运行。
            app_enter_safe_state();
        }

        // 初始化期结束：此后任何 operator new 都会陷入故障（T1 规则）。
        proj::heap_guard_lock();

        for (;;)
        {
            // 启动调度器（osKernelStart / vTaskStartScheduler），正常情况下不会回到这里。
        }
    }

    /// ISR 向量必须 extern "C" 且与启动文件中的名字一致，否则弱默认处理函数生效。
    // 名字由启动文件的向量表决定，不适用 C++ 命名规则。
    // NOLINTBEGIN(readability-identifier-naming)
    void
    USART1_IRQHandler (void)
    {
        // 只捕获事件并转交任务：例如 g_rx_ring.push(byte)，见 spsc_ring.hpp。
    }
    // NOLINTEND(readability-identifier-naming)
}
