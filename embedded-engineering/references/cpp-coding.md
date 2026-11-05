# Modern Embedded C++ 编码规范

适用于 `.cpp/.hpp` 文件（`mcu-*`、`zephyr` 应用层、`linux-userspace`）。C 文件继续适用 [barr-c.md](barr-c.md)。等级 T0–T3 与特性取舍见 [cpp-features.md](cpp-features.md)。

规则来源：

- Pigweed：嵌入式 C++ 指南、尺寸优化、C++ 风格。
- modm：静态类型外设与编译期校验。
- ETL：固定容量容器与 ISR 队列。
- C++ Core Guidelines：下文括号中的编号，如 R.1、C.35。
- 平台文档：Zephyr C++ 文档。

均为意译，原文见 [sources.md](sources.md)。

## 1. 语言标准

- **基线 C++17**；模块确需 C++20（Concepts、`constinit`、`consteval`、`std::span`、指定初始化器）时整体切换，或用特性测试宏提供回退。
- 特性测试宏必须加 `defined()`，否则 C++17 + `-Wundef` 会编译失败：`#if defined(__cpp_concepts) && (__cpp_concepts >= 201907L)`。
- 编译器扩展（`__attribute__`、`__asm`）只出现在 platform 层，并封装在宏或函数里。
- **C++20 迁移陷阱**：对 `volatile` 对象用 `++`、`--`、复合赋值已弃用（`-Wvolatile`，`-Werror` 下失败）。写成显式读-改-写 `reg = reg | mask;`，共享计数改用 `std::atomic`。
- Zephyr：`CONFIG_CPP=y`，并在 `CONFIG_STD_CPP17` / `CONFIG_STD_CPP20` 中选择标准。`CONFIG_MINIMAL_LIBCPP` 不含 STL，此时 ETL 定义 `ETL_NO_STL`。

## 2. 编译与链接

按 `assets/cpp/compile_flags.md` 配置，要点：

- MCU 一律 `-fno-exceptions -fno-rtti -fno-use-cxa-atexit`，并把 `assets/cpp/linker_discard.ld` 并入链接脚本。
- `-fno-threadsafe-statics` 只在满足 §6 前提时使用。
- 严格告警组加 `-Werror`，只作用于自有代码；第三方头（ETL、CMSIS、厂商 SDK、RTOS）用 `-isystem` 引入。
- `-ffunction-sections -fdata-sections -Wl,--gc-sections`，并生成 map 文件与 `-fstack-usage`。
- LTO 默认关闭。
- 每次构建后运行 `scripts/cpp_cost.py check <elf> --tier <Tn>`。

## 3. 命名与格式（方案 A）

- **布局**：沿用 BARR-C 布局（Allman、4 空格、函数名与括号间空格）。C++ 列宽 100，使用 `assets/cpp/.clang-format`；C 文件继续用 `assets/barr-c/.clang-format`（80 列）。C 与 C++ 同目录时，按文件类型分开调用 clang-format。
- **命名**：

| 实体 | 规则 | 示例 |
| --- | --- | --- |
| 命名空间 | `lower_case`，代替 BARR-C 6.1.i 的模块前缀 | `proj::motor` |
| 类、结构体、枚举、别名、Concept、模板参数 | `CamelCase` | `Bme280`、`RegisterBus` |
| 函数、方法、变量、参数 | `lower_case` | `read_register()` |
| 私有/受保护成员 | 后缀 `_` | `bus_` |
| 常量（`constexpr`、枚举值） | 前缀 `k` + `CamelCase` | `kChipId`、`Status::kOk` |
| 可变全局变量 | 前缀 `g_`（作用域标记） | `g_sensor_bus` |
| 宏 | 全大写，只用于宏（NL.9） | `PROJ_REGISTER_BUS` |

- 不用 BARR-C 的类型编码前缀 `p_`、`b_`、`h_`（NL.5）。C 文件仍按 BARR-C。
- 机械检查用 `assets/cpp/.clang-tidy`（`readability-identifier-naming`）。向量表固定名（`USART1_IRQHandler`）用 `NOLINTBEGIN/END(readability-identifier-naming)` 并写明理由。
- 文件：`.cpp`/`.hpp` 为 C++；能被 C 包含的头用 `.h`，且只含 C 构造。头文件用 `#ifndef` guard（与 C 侧一致）。
- Zephyr 应用中的 C++ 跟随 Zephyr 代码风格；Linux 用户态跟随项目风格。

## 4. 类设计

- 有不变量用 `class`，成员可独立变化用 `struct`（C.2）。
- 优先 rule of zero（C.20）。一旦声明任一拷贝、移动或析构函数，就把其余几个也显式声明或删除（C.21）。
- 单参数构造 `explicit`（C.46）；成员用默认初始化器（C.48）；简单构造函数标 `constexpr`，使全局对象可常量初始化。
- 多态基类：**受保护的非虚析构**（C.35）+ 删除公开拷贝（C.67）+ 实现类 `final`。公有虚析构会在无堆构建中拉入 `operator delete`→`malloc/free`（实测 +340 B Flash、+412 B RAM）。
- 虚函数恰好标注 `virtual`、`override`、`final` 之一（C.128）；不用受保护数据成员（C.133）。
- 多重继承只用于多个纯接口；T0–T2 禁止虚继承。
- 独占硬件的对象（驱动、外设包装）删除拷贝，表达“一个实例对应一个器件”。
- **构造与硬件**（对 NR.5、C.41 的正当偏离）：全局对象构造早于时钟与引脚初始化，且没有异常可报告构造失败。因此：
  - 构造函数：`constexpr`、不失败、不访问硬件，只保存配置和依赖引用。
  - `[[nodiscard]] Status init()`：时钟与总线就绪后由组合根显式调用。
  - 运行期动态创建的对象（T2/T3）用工厂 `static Result<T> create(...)`，不产生半初始化对象。

## 5. 错误处理（无异常，E.25/E.27）

- **可恢复错误**：
  - 用 `enum class Status` + `Result<T>`（`etl::expected<T, Status>`、`pw::Result<T>`，C++23 起可用 `std::expected`），返回值标 `[[nodiscard]]`。
  - 模板：`assets/cpp/templates/interface/proj_status.hpp`。
  - 故意忽略时写 `static_cast<void>(...)`。
- **致命错误**（不变量破坏、内存损坏）：项目断言宏 → 故障处理（记录、进入安全态、复位），不直接 `abort()`。新增断言要谨慎，避免现场设备因此反复重启。
- **`noexcept`**：ISR、C 回调蹦床、析构函数、移动操作一律标注（F.6、E.12）。
- **SDK 错误码**（`HAL_StatusTypeDef`、`esp_err_t`、负 errno）在 bsp 层一次性映射为 `Status`，不向上泄漏（见 `vendor_i2c_bus.hpp`）。
- **T3 启用异常时**：不得穿越 `extern "C"` 边界，不得在 RT 线程中抛出。

## 6. 内存、栈与对象生命周期

存储期优先级：有界的自动存储 > `constinit` 静态存储 > 固定池（`etl::pool`、ThreadX block pool、`K_MEM_SLAB`）> 仅初始化期的堆 > 通用堆（仅 T3 非 RT）。

- **全局对象**：
  - 尽量 `constinit`（C++20）或 `constexpr` 构造（C++17），使其进入 `.data/.bss`，消除跨编译单元的初始化顺序问题（I.22）。
  - 非平凡的动态初始化在 `main()` 之前执行（`__libc_init_array`）：不得访问硬件、RTOS 或日志。
  - 析构永不执行：用 `-fno-use-cxa-atexit` + `linker_discard.ld` 去掉注册代码。Zephyr 不支持静态析构。
- **启动代码**：确认调用了 `__libc_init_array`（CubeMX 启动文件会调用）。自写启动文件若遗漏，非 `constinit` 的全局对象都不会被构造。
- **函数局部静态**（Meyers 单例）：
  - 动态初始化会链接 `__cxa_guard_acquire`；arm-none-eabi 的 libstdc++ 不与你的 RTOS 集成。
  - 改用 `constinit` 全局。确需时，保证首次调用在调度器启动前或单线程上下文，再用 `-fno-threadsafe-statics`。
  - 绝不在 ISR 中首次触达（CP.110 同理）。
- **堆**：
  - T0 禁止：`cpp_cost.py --tier T0` 检出 `heap` 类即失败。
  - T1 只在初始化期分配，之后锁定（`assets/cpp/templates/bsp/heap_guard.cpp`）。
  - T2 把分配器作为参数注入（Pigweed 做法），库内部不直接 `new`；ISR 与 RT 路径禁止。
  - FreeRTOS 项目若需要堆，`operator new` 映射到 `pvPortMalloc` 并沿用同样的锁定规则。
- **栈**：模板内联与大型局部对象是 C++ 栈膨胀的主因，例如任务栈上的 `etl::vector<T, 256>`。用 `-fstack-usage` + 调用图估算最坏情况，再用运行期水位线（`uxTaskGetStackHighWaterMark`、`k_thread_stack_space_get`）复核。
- **内存区域**：DMA 可达区、TCM、non-cacheable 区的对象，用 `alignas` + section 属性放置，由类型本身约束对齐（`dma_buffer.hpp`）。
- **被 ISR/DMA 引用的对象**：必须是静态存储期，或由 RAII 注册对象覆盖其生命周期：构造时注册，析构时注销并等待在途传输结束。

## 7. ISR、DMA、RTOS 与并发

- **上下文标注**（Pigweed）：每个公共函数在文档注释中写明 `ISR-safe`、`thread-safe` 或两者都不是。未标注的视为都不安全。ISR 专用方法以 `_from_isr` 结尾。
- **ISR 内禁止**：分配、阻塞、获取非 ISR 安全的锁、异常、`std::function`、非 ISR 安全的日志。虚调用允许，代价约等于 C 函数指针，但要计入时序预算。
- **共享数据**：
  - 不用 `volatile` 同步（CP.8），`volatile` 只用于 MMIO 与 DMA 描述符（CP.200）。
  - 锁用 RAII（CP.20），guard 具名（CP.44），互斥量与被保护数据定义在一起（CP.50），临界区尽量短（CP.43）。
- **原子**（实测）：

| 目标 | 32 位 load/store | 32 位 RMW | 64 位 |
| --- | --- | --- | --- |
| ARMv7-M/v8-M Mainline（M3/M4/M7/M33） | lock-free | lock-free（LDREX/STREX） | **链接失败**，需临界区 |
| ARMv6-M（M0/M0+）、M23 | 对齐时原子 | **链接失败**（`__atomic_fetch_add_4` 未定义），需临界区 | 链接失败 |

  每个用于 ISR/线程共享的原子类型都写 `static_assert(std::atomic<T>::is_always_lock_free)`。内存序：计数器可用 `relaxed`，发布/消费数据用 `release`/`acquire`。多核上用 `seq_cst` 需说明理由。
- **无锁结构**：只用经过审查的实现（`etl::queue_spsc_isr`、`spsc_ring.hpp`），不自造（CP.100）。
- **DMA 不属于 C++ 内存模型**：CPU 与 DMA 之间的可见性依赖 cache clean/invalidate 和 `__DSB()`，不依赖 `std::atomic`。缓冲区所有权用租约类型表达（`dma_buffer.hpp`）。
- **RTOS 包装**：
  - 静态创建：`xTaskCreateStatic`、`tx_thread_create`（静态栈）、`K_THREAD_DEFINE`。
  - 任务入口用静态成员蹦床 `static void entry(void* p_ctx)`。
  - 互斥量包装成 BasicLockable，以便使用 `std::lock_guard`（`os_mutex.hpp`）。
  - 二值信号首选任务通知（FreeRTOS）。
  - 调试构建中断言调用上下文：`xPortIsInsideInterrupt()`、`k_is_in_isr()`。
- **ThreadX**：ISR 中调用服务时等待选项只能是 `TX_NO_WAIT`；RT 路径用 block pool（确定性），不用 byte pool。
- **Zephyr**：内核 API 是 C，C++ 只写应用层包装；没有 `std::thread`、`std::mutex`。
- **FreeRTOS**：调用 FreeRTOS API 的 ISR 优先级约束见 [mcu-isr-rtos.md](mcu-isr-rtos.md) §3；`IrqLock` 会屏蔽全部可屏蔽中断，只适合极短区间。
- **Linux 用户态（T3）**：可用 `std::thread/mutex/condition_variable`；RT 线程用 `SCHED_FIFO` + `mlockall` + 启动期预分配。

## 8. C SDK 与 C++ 的边界

1. **头文件**：C 可包含的头（`.h`）只含 C 构造，并加 `extern "C"` 保护；C++ 头不得被 C 包含。厂商 SDK 头只在 platform/bsp 层包含，并以 `-isystem` 引入。
2. **ISR 向量**：中断处理函数必须 `extern "C"`，且与启动文件中的名字完全一致。否则 C++ 名字修饰会让链接器继续使用弱默认处理函数，编译链接全部通过，运行时进死循环。
3. **回调**：SDK 的“函数指针 + `void*` 上下文”回调，用 `noexcept` 静态成员蹦床转回对象；异常不得穿越 C 边界。
4. **跨边界数据**：`static_assert(std::is_standard_layout_v<T> && std::is_trivially_copyable_v<T>)`，必要时再用 `sizeof`/`offsetof` 锁定布局。不传引用、模板、`enum class` 或 `std::` 类型。
5. **把 C++ 对象暴露给 C**：用不透明句柄（`struct proj_console;` + `extern "C"` 访问函数）。
6. **生成的 `main.c`**（CubeMX 等）保持为 C，在 `USER CODE` 区调用 `extern "C" void app_main(void)`，由 C++ 实现组合根（`app_main.cpp`）。
7. **寄存器访问**：保留 CMSIS 结构体，或用类型安全寄存器包装（modm `Register/Flags` 思路）。`reinterpret_cast` 只出现在 platform 层的单一访问点（`clang-tidy-platform.yaml` 豁免），且不能用于 `constexpr`。不用位域映射寄存器。
8. **配置值校验**：能在编译期算出的硬件配置（分频、波特率误差、缓冲区对齐）用 `static_assert` 校验（`uart_divider.hpp`，modm 思路）。

## 9. 模板与代码膨胀

- 非平凡模板记录预期实例数；超过 2–3 个时，把与类型无关的逻辑抽到非模板基类或 `.cpp`（T.62、T.84，对应 ETL `ivector`）。
- 重型模板在 `.cpp` 中显式实例化，头文件中用 `extern template` 声明。
- 避免模板化的虚接口（每个实例一套 vtable）。
- 每次引入新模板后用 `cpp_cost.py diff` 查看符号增量。

## 10. 标准库与替代库（T0–T2）

| 类别 | 内容 |
| --- | --- |
| ✅ 允许 | `<array> <cstdint> <cstddef> <limits> <type_traits> <utility> <optional> <variant> <tuple> <string_view> <initializer_list> <iterator> <ratio> <bit> <span>`(C++20) `<concepts>`(C++20) `<c*>` |
| ⚠️ 部分允许 | `<algorithm>`（排除会分配的算法）、`<numeric>`（实例化膨胀）、`<atomic>`（见 §7）、`<bitset>`（禁 `to_string`）、`<functional>`（禁 `std::function`）、`<mutex>`（只用 `lock_guard/unique_lock`）、`<new>`（只用 placement new）、`<chrono>`（只用类型与字面量） |
| ❌ 禁止 | `<vector> <string> <map> <set> <list> <deque> <unordered_*>`、`<iostream>` 等流、`<regex>`、`<thread> <future> <condition_variable>`、`shared_ptr/make_shared`、`<exception> <stdexcept>` |
| 替代（默认 ETL） | `etl::vector<T,N>`、`etl::string<N>`、`etl::flat_map`、`etl::circular_buffer`、`etl::delegate`、`etl::inplace_function`、`etl::expected`、`etl::span`、`etl::queue_spsc_isr`、`etl::fsm/hfsm`；配置见 `assets/cpp/templates/etl_profile.h` |

- 已使用 Pigweed 的项目沿用 `pw::Vector`、`pw::InlineString`、`pw::Function`、`pw::Result`，不混用两套。
- `std::unique_ptr` + 自定义删除器管理非堆资源（归还池块、释放 DMA 通道）是零开销 RAII，允许使用。

## 11. 静态分析

- 编译告警：见 §2。
- clang-tidy：C++ 目录放 `assets/cpp/.clang-tidy`，`platform/` 放 `assets/cpp/clang-tidy-platform.yaml`（重命名为 `.clang-tidy`）。关闭项及原因写在配置注释中。
- 可选：Clang `-Wthread-safety` + 锁注解（Pigweed `pw_sync/lock_annotations.h`）。
- cppcheck 作补充；功能安全项目使用支持 MISRA C++:2023 的商业工具。
