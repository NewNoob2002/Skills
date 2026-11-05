# C++ 架构模式与示例

分层规则不变（[mcu-architecture.md](mcu-architecture.md)）：`APP → MODULE → INTERFACE → BSP/DRIVER → PLATFORM`，`scripts/arch_lint.py` 同样检查 `.cpp/.hpp`。

示例的完整版本在 `assets/cpp/templates/`。它们已用 arm-none-eabi-g++ 15.3 在 C++17/C++20 × Cortex-M0+/M4/M7 下以严格告警加 `-Werror` 编译，并通过 C++ clang-tidy 配置；CppUTest 测试在 host 上以 ASan/UBSan 运行通过（见 `tests/cpp/run_cpp_checks.sh`）。

## 1. 分层在 C++ 中的形态

| 层 | C++ 形态 | 模板 |
| --- | --- | --- |
| `interface/` | Concept（构建期绑定）或纯虚接口（运行期绑定）；`Status`/`Result` | `interface/proj_status.hpp`、`interface/register_bus.hpp` |
| `driver/device/` | 以总线 Concept 为模板参数的类模板 | `driver/device/bme280.hpp` |
| `driver/bus/`、`bsp/` | 封装厂商 SDK 的具体总线类，错误码在此映射；板级运行时策略（堆护栏） | `bsp/vendor_i2c_bus.hpp`、`bsp/heap_guard.cpp` |
| `platform/` | 厂商 C SDK、CMSIS、启动文件（保持 C）；中断锁 | `platform/irq_lock.hpp` |
| `osal/` | RTOS 原语的薄 RAII 包装 | `osal/os_mutex.hpp` |
| `lib/` | 与硬件无关的通用组件 | `lib/spsc_ring.hpp`、`lib/uart_divider.hpp`、`lib/dma_buffer.hpp` |
| `app/` | 组合根：`constinit` 对象、初始化顺序、`extern "C" app_main()`、ISR 向量 | `app/app_main.cpp` |

## 2. 静态多态驱动（首选）

每块板的总线在构建期确定，所以用模板参数注入，零间接调用（实测 +28 B，与 CRTP 相同）。C++20 用 Concept 约束，C++17 用 trait + `static_assert` 回退，两种标准下都会给出可读的错误信息：

```cpp
template <PROJ_REGISTER_BUS Bus> class Bme280
{
    static_assert(kIsRegisterBus<Bus>, "Bus must provide Status read(uint8_t, etl::span<uint8_t>) ...");
  public:
    constexpr explicit Bme280 (Bus & bus) noexcept : bus_(bus) {}   // 不碰硬件，可 constinit
    [[nodiscard]] Status init () noexcept;                         // 时钟就绪后由组合根调用
  private:
    Bus & bus_;
};
```

板级选择只发生在组合根：`constinit Bme280<VendorI2cBus> g_barometer{g_sensor_bus};`。测试时实例化 `Bme280<FakeBus>`，不需要 `virtual`。

## 3. 运行期接口（只在需要运行期替换时）

例如同一固件按板 ID 支持两种 Flash、插件式协议。代价与 C 函数表相同（+88 B，调用点 2 次 `blx`）：

```cpp
class FlashStorage
{
  public:
    [[nodiscard]] virtual Status read (std::uint32_t addr, etl::span<std::uint8_t> out) noexcept = 0;
  protected:
    FlashStorage () = default;
    ~FlashStorage () = default;                          // 受保护非虚：不拉入 operator delete
    FlashStorage (const FlashStorage &) = delete;        // C.67
    FlashStorage & operator= (const FlashStorage &) = delete;
};
class InternalFlash final : public FlashStorage { /* override ... */ };   // final 利于去虚化
```

## 4. RAII 资源管理

| 资源 | 类型 | 要点 |
| --- | --- | --- |
| 中断临界区 | `IrqLock` | 保存/恢复 PRIMASK，可嵌套；只保护极短区间（CP.43） |
| RTOS 互斥量 | `OsMutex` + `std::lock_guard` | BasicLockable；ISR 中不可用 |
| 片选 | `ChipSelect<Pin>`（构造拉低、析构拉高；模式，未单独提供模板） | 消除“提前 return 忘记释放 CS”这一类 C 缺陷 |
| DMA 缓冲区 | `DmaRxLease<Ops>` | 仅可移动；存活期间 CPU 不访问；`complete()` 先 invalidate D-cache 再交还视图 |
| 池块、DMA 通道 | `std::unique_ptr<T, Deleter>` | 自定义删除器归还资源，零开销 |

## 5. 编译期配置校验（modm 思路）

```cpp
static_assert(proj::UartDivider<80000000U, 115200U>::kDivider == 694U);
// proj::UartDivider<80000000U, 3000000U>::kDivider → 编译失败：baud rate error exceeds tolerance
```

适用于分频、波特率误差、定时器周期、缓冲区大小与对齐、结构体布局、`is_always_lock_free`。运行期只写常量。

## 6. ISR → 任务

| 场景 | 选择 |
| --- | --- |
| M3/M4/M7/M33，单字节/小结构流 | `proj::SpscRing<T, N>`（lock-free，acquire/release） |
| M0/M0+（无 lock-free RMW） | `etl::queue_spsc_isr<T, N, proj::IrqAccessPolicy>`（ISR 用 `push_from_isr`，任务用 `pop`） |
| 只需唤醒 | RTOS 任务通知 / `k_sem_give`，不传数据 |
| DMA 完成 | 通知任务；数据处理在任务中，经 `DmaRxLease::complete()` 取回 |

`SpscRing` 在 ARMv6-M 上编译即失败（`needs lock-free 32-bit atomics`），迫使你选对实现。

## 7. C SDK 边界

```cpp
extern "C"
{
    [[noreturn]] void app_main (void);    // main.c 在 USER CODE 区调用
    // NOLINTBEGIN(readability-identifier-naming)
    void USART1_IRQHandler (void);        // 必须 extern "C"，否则弱默认处理函数生效
    // NOLINTEND(readability-identifier-naming)
}

// SDK 回调：noexcept 静态蹦床把 void* 上下文转回对象
static void rx_trampoline (void * p_ctx, std::uint8_t byte) noexcept
{
    static_cast<Console *>(p_ctx)->on_rx(byte);
}
```

SDK 错误码在 bsp 层一次性映射为 `Status`（`VendorI2cBus::map`）。跨边界的结构体加 `static_assert(std::is_standard_layout_v<T> && std::is_trivially_copyable_v<T>)`。

## 8. 生命周期与组合根

```cpp
constinit VendorI2cBus g_sensor_bus{kBme280Address};          // 常量初始化，不依赖构造顺序
constinit Bme280<VendorI2cBus> g_barometer{g_sensor_bus};

[[noreturn]] void app_main (void)
{
    board_clock_init();
    if (Status::kOk != g_barometer.init()) { app_enter_safe_state(); }
    heap_guard_lock();                                         // T1：此后 operator new 触发故障
    /* 启动调度器 */
}
```

## 9. 状态机

| 等级 | 选择 |
| --- | --- |
| T0 | `enum class State` + `switch`（BARR-C 8.3 的 `default`、`break` 规则同样适用） |
| T1+ | `std::variant<Idle, Run, Fault>` + `std::visit`（实测 +60 B）；需要层次状态或消息路由时用 `etl::fsm/hfsm` |

## 10. 反模式

| 反模式 | 问题 | 改为 |
| --- | --- | --- |
| 为了单元测试给每个驱动加 `virtual` | vtable 开销；阻碍内联与 `--gc-sections` 回收 | 模板参数 Fake 或链接期替换 |
| 全局对象构造函数里初始化外设 | 时钟未就绪；构造顺序不确定 | `constexpr` 构造 + 显式 `init()` |
| `std::function` 存回调 | 堆 + atexit + throw 辅助（+1.1 KB） | `etl::delegate`、`etl::inplace_function` |
| 单例 `static T& get() { static T t; ... }` | guard、首次触达竞争、ISR 中首次触达 | `constinit` 全局 + 组合根传引用 |
| `volatile` 计数器 `++` 作为线程同步 | 非原子；C++20 已弃用 | `std::atomic`（≤ 32 位，lock-free）或临界区 |
| 公有虚析构的接口 | 拉入 `operator delete`→`malloc` | 受保护非虚析构 |
| 在头文件中写 `using namespace` | 污染包含者（SF.7） | 只在 `.cpp` 局部使用 |
