# C++ 资源等级与特性决策表

不简单禁止现代 C++：按“代价是否可见、是否有界”取舍。本文件给出资源等级（T0–T3）、实时路径规则、特性决策表和实测数据。编码细节见 [cpp/coding.md](coding.md)，模式见 [cpp/patterns.md](patterns.md)，验证方法见 [verification/cpp-testing.md](../verification/cpp-testing.md)。

## 1. 适用范围

| Profile | C++ | 默认等级 |
| --- | --- | --- |
| `mcu-baremetal` | ✅ | T0 或 T1（按资源） |
| `mcu-rtos`（FreeRTOS、ThreadX、CMSIS-RTOS2） | ✅ | T1 或 T2 |
| `zephyr` | ⚠️ 仅应用层；内核、驱动、`SYS_INIT` 保持 C（Zephyr 官方 C++ 文档） | T1 或 T2 |
| `linux-kernel` | ❌ 内核不支持 C++，不得引入 | — |
| `linux-userspace` | ✅ | T3 |

## 2. 资源等级

任一条件满足即归入较低等级。`scripts/detect_profile.py` 会从链接脚本的 `MEMORY` 区域推算建议等级，结论需人工确认。

| 等级 | 资源 | 典型器件 | 关键约束 |
| --- | --- | --- | --- |
| **T0** | Flash ≤ 64 KB 或 RAM ≤ 16 KB | Cortex-M0/M0+/M23、小型 RISC-V、8 位 | 每 100 B 都要有理由；ARMv6-M 没有 LDREX/STREX |
| **T1** | Flash 64 KB–1 MB，RAM 16–512 KB | Cortex-M3/M4/M33，单核 RTOS | 无堆，或仅初始化期分配 |
| **T2** | Flash ≥ 1 MB 或 RAM ≥ 512 KB，有 cache 或多核 | Cortex-M7/M55/M85、ESP32-S3、双核 MCU | 确定性池或注入式分配器；cache 一致性；SMP |
| **T3** | MMU + Linux 用户态 | Cortex-A | 完整标准库；是否用异常由项目决定 |

两个正交维度：

- **RT 路径**：ISR、控制环、硬实时任务、DMA 完成路径。无论等级，都禁止分配、阻塞、异常和无界算法；虚调用需有界，且计入时序预算。
- **安全覆盖层**：功能安全项目在等级规则之上执行 MISRA C++:2023（面向 C++17，取代 MISRA C++:2008 与 AUTOSAR C++14）。需要商业工具检查，clang-tidy 不提供 MISRA C++ 检查集。

### 各等级规则集

| 规则 | T0 | T1 | T2 | T3 |
| --- | --- | --- | --- | --- |
| 语言标准 | C++17（C++20 可选） | C++17 基线，C++20 可选 | C++17/20 | C++20/23 |
| 异常、RTTI | 禁用 | 禁用 | 禁用 | 项目决定；RT 线程与 C 边界内不抛 |
| 堆 | 禁止 | 仅初始化期，之后锁定 | 池/注入分配器；ISR 与 RT 禁止 | 允许；RT 线程预分配 |
| `virtual` | 少数边界，须测量 | 运行期选择的边界 | 同 T1 | 自由 |
| 模板实例化 | 记录实例数，重模板走非模板核心 | 监控 `nm --size-sort` 前 20 | 同 T1 | 自由 |
| 标准库 | 白名单 | 白名单 + 灰名单 | 白名单 + 灰名单 | 全部（RT 线程除外） |
| 格式化输出 | 禁 printf 族，用令牌化日志 | snprintf 仅非 RT | 同 T1 | 自由 |
| 原子 RMW | 禁止（会链接失败），用临界区 | ≤ 32 位 lock-free；64 位用临界区 | 同 T1 + 多核内存序 | 自由 |
| 局部静态动态初始化 | 禁止 | 仅调度器启动前首次触达 | 同 T1，或提供 RTOS 感知 guard | 允许 |
| `cpp_cost.py check --tier` | T0 | T1 | T2 | T3（仅报告） |

## 3. 特性决策表

✅ 推荐　⚠️ 有条件（见最后一列）　❌ 禁止。实测增量见 §4，指相对空 C++ 程序的 Flash（text）增量。

| 特性 | 实测增量 / 代价 | T0 | T1 | T2 | T3 | RT | 条件与替代 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `namespace`、`enum class`、引用、`auto`、结构化绑定、`if constexpr`、`[[nodiscard]]`、`static_assert` | 0 | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `class` 封装、非虚成员 | 0 | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| RAII（锁、片选、资源句柄） | ≈0 | ✅ | ✅ | ✅ | ✅ | ✅ | 静态对象析构见 [cpp/coding.md](coding.md) §6 |
| `constexpr` 函数/变量 | 0 运行期 | ✅ | ✅ | ✅ | ✅ | ✅ | 非平凡 `constexpr` 函数在运行期调用时可能内联膨胀 |
| `consteval` 查找表 | CRC8 表 +268 B Flash、0 RAM；运行期生成 +52 B Flash、+256 B RAM | ✅ | ✅ | ✅ | ✅ | ✅ | 按 Flash 与 RAM 哪个更紧选择 |
| `constinit`（C++20） | 0 | ✅ | ✅ | ✅ | ✅ | — | C++17 用 `constexpr` 构造 |
| 函数/类模板 | 每个实例一份代码 | ⚠️ | ✅ | ✅ | ✅ | ✅ | 控制实例数（[cpp/coding.md](coding.md) §9） |
| Concepts（C++20） | 0（模板驱动 +28 B） | ✅ | ✅ | ✅ | ✅ | ✅ | C++17 用 `static_assert` + trait 回退 |
| CRTP | +28 B（同模板） | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ | 只在静态多态类型间共享实现；C++20 优先 Concept + 自由函数 |
| `virtual`（受保护非虚析构 + `final`） | +88 B；调用点与 C 函数表相同 | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | 仅运行期选择的边界 |
| 公有虚析构 | +340 B Flash、+412 B RAM（拉入 `operator delete`→`malloc/free`） | ❌ | ⚠️ | ⚠️ | ✅ | — | 无堆构建改为受保护非虚析构 |
| 多重继承（纯接口） | 每基类一个 vptr | ❌ | ⚠️ | ⚠️ | ✅ | ⚠️ | 虚继承在 T0–T2 禁止 |
| Lambda（局部使用） | 0 | ✅ | ✅ | ✅ | ✅ | ✅ | 存储的回调注意捕获的生命周期（F.53） |
| `std::function` | +1148 B；拉入 `operator new`、`malloc`、`atexit`、`__throw_bad_function_call` | ❌ | ❌ | ❌ | ✅ | ❌ | `etl::delegate`（+72 B）、`etl::inplace_function`（+200 B）、`pw::Function` |
| 异常 | +9877 B Flash、+460 B RAM；unwinder、RTTI、malloc | ❌ | ❌ | ❌ | ⚠️ | ❌ | `Status`/`Result` |
| RTTI / `dynamic_cast` | 同层次无 RTTI 为 +252 B，有 RTTI 为 +1276 B | ❌ | ❌ | ❌ | ⚠️ | ❌ | `enum class` 类型标签、`std::variant` |
| `new`/`delete`/`malloc` | 堆、碎片、非确定时间 | ❌ | ⚠️ | ⚠️ | ✅ | ❌ | T1 仅初始化期（`heap_guard.cpp`）；T2 注入分配器/池 |
| `unique_ptr` + 自定义删除器（非堆资源） | 0 | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `shared_ptr` | 控制块堆分配 + 原子引用计数 | ❌ | ❌ | ❌ | ⚠️ | ❌ | 单一所有者（R.21） |
| `std::vector/string/map/list/deque/unordered_*` | `vector` +1030 B；`operator new`、`malloc`、`__throw_length_error` | ❌ | ❌ | ❌ | ✅ | ❌ | `etl::vector<T,N>`（+48 B）、`etl::string<N>`、`etl::flat_map` |
| `std::array`、`std::span`（C++20）、`std::string_view` | span 求和比 C 指针+长度多 20 B | ✅ | ✅ | ✅ | ✅ | ✅ | C++17 用 `etl::span` |
| `std::optional` | +44 B | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `std::variant` + `std::visit` | +60 B（3 种状态） | ✅ | ✅ | ✅ | ✅ | ✅ | 状态机；T0 也可用 `enum` + `switch` |
| `expected`/`Result` | 与 `optional` 同量级 | ✅ | ✅ | ✅ | ✅ | ✅ | `etl::expected`、`pw::Result`，C++23 `std::expected` |
| `<algorithm>` | 依算法而定 | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | 排除会分配的 `stable_sort`、`inplace_merge` |
| iostream | newlib-nano 下无法链接；完整 newlib 约 +391 KB | ❌ | ❌ | ❌ | ⚠️ | ❌ | 令牌化日志、轻量格式化库 |
| printf / snprintf | +3932 B / +2611 B，均拉入 malloc | ❌ | ⚠️ | ⚠️ | ✅ | ❌ | 令牌化日志（如 `pw_tokenizer`） |
| `std::atomic` ≤ 32 位 RMW | M3/M4/M7/M33：内联 LDREX/STREX（+20 B）；**M0/M0+：链接失败** | ❌ | ✅ | ✅ | ✅ | ✅ | `static_assert(is_always_lock_free)`；ARMv6-M 用临界区 |
| `std::atomic` 64 位（32 位 MCU） | **链接失败**（`__atomic_*_8` 无实现） | ❌ | ❌ | ❌ | ✅ | ❌ | 临界区保护 |
| `std::thread/mutex/condition_variable` | MCU RTOS 上不可用或不集成 | ❌ | ❌ | ❌ | ✅ | ⚠️ | RTOS 包装 + `std::lock_guard` |
| 函数局部静态（动态初始化） | +84 B（含 `__cxa_guard_acquire`）；`-fno-threadsafe-statics` 下 +36 B | ❌ | ⚠️ | ⚠️ | ✅ | ❌ | 改用 `constinit` 全局 |
| 全局对象的非平凡析构 | +84 B 与 atexit 注册；`-fno-use-cxa-atexit` 下 +24 B | ⚠️ | ⚠️ | ⚠️ | ✅ | — | `linker_discard.ld` |
| 协程（C++20） | 帧默认堆分配 | ❌ | ❌ | ⚠️ | ⚠️ | ❌ | 只通过框架（如 `pw_async2`）使用 |
| 模块（C++20） | 嵌入式工具链/构建支持不足 | ❌ | ❌ | ❌ | ⚠️ | — | — |
| `volatile` 复合运算 | C++20 弃用（`-Wvolatile`） | ❌ | ❌ | ❌ | ❌ | ❌ | 显式读-改-写或 `std::atomic` |
| 位域映射寄存器 | 布局由实现定义 | ❌ | ❌ | ❌ | ❌ | ❌ | 掩码与移位常量、类型安全寄存器 |
| 用户自定义字面量（单位） | 0 | ✅ | ✅ | ✅ | ✅ | ✅ | 放在命名空间中 |
| 指定初始化器（C++20） | 0 | ✅ | ✅ | ✅ | ✅ | ✅ | 按声明顺序，不与普通初始化混用 |
| LTO | 体积可能减小；与链接脚本放置、调试冲突 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | — | 只在空间不足时开启，并完整回归 |

### 多态方式选择

```text
实现在构建期就确定（每块板固定一种总线/器件）？
 ├─ 是 → Concept/模板注入                       +28 B，调用点无间接跳转
 └─ 否：需要运行期选择（按板 ID 选器件、插件式协议）？
      ├─ 是 → 纯虚接口 + final 实现 + 受保护非虚析构   +88 B，与 C 函数表持平
      └─ 否：需要暴露给 C 或跨库 ABI？
           ├─ 是 → C 函数表 / 不透明句柄
           └─ 否 → 普通类或自由函数
只为在静态多态类型间复用代码 → CRTP（C++17）或 Concept + 自由函数（C++20）
“为了单元测试”不是引入 virtual 的理由：先用模板参数 Fake 或链接期替换
```

## 4. 实测数据

- **工具链与选项**：Arm GNU Toolchain 15.3.Rel2（GCC 15.3.1），`-Os -ffunction-sections -fdata-sections -Wl,--gc-sections --specs=nano.specs --specs=nosys.specs`；C++ 默认 `-std=c++20 -fno-exceptions -fno-rtti`。
- **Cortex-M4F 基线**：text 448 / data 8 / bss 40，C 与 C++ 相同。
- **复现**：`scripts/bench/run.sh [--cpu ...] [--etl <etl>/include]`。

| 变体 | text | data | bss | Δtext | 拉入的受限运行时（`cpp_cost.py` 类别） |
| --- | --- | --- | --- | --- | --- |
| C 函数表驱动（2 实现） | 528 | 12 | 40 | +80 | — |
| `virtual`，受保护非虚析构 | 536 | 20 | 40 | +88 | — |
| `virtual`，公有虚析构 | 788 | 100 | 360 | +340 | heap |
| 模板 + Concept | 476 | 8 | 44 | +28 | — |
| CRTP | 476 | 8 | 44 | +28 | — |
| 异常（`-fexceptions`，一次 throw/catch） | 10325 | 104 | 404 | +9877 | exceptions、heap、rtti、throw_helpers |
| RTTI + `dynamic_cast` | 1724 | 96 | 356 | +1276 | heap、rtti |
| 同层次、无 RTTI | 700 | 96 | 356 | +252 | heap（公有虚析构） |
| `std::function`（4 个捕获） | 1596 | 96 | 392 | +1148 | heap、static_dtor、throw_helpers |
| `etl::delegate` | 520 | 8 | 64 | +72 | — |
| `etl::inplace_function<16>` | 648 | 16 | 60 | +200 | static_dtor（全局对象析构；`-fno-use-cxa-atexit` 可去除） |
| `std::cout << x` | 链接失败（newlib-nano 缺宽字符函数）；完整 newlib：400556 / 4508 / 7052 | | | ≈ +391 KB | iostream |
| `printf("%lu")` | 4380 | 100 | 368 | +3932 | heap、stdio_format |
| `snprintf("%lu")` | 3059 | 88 | 404 | +2611 | heap、stdio_format |
| `std::vector::push_back` | 1478 | 88 | 376 | +1030 | heap、throw_helpers |
| `etl::vector<uint32_t,16>` | 496 | 8 | 40 | +48 | — |
| 函数局部静态（默认） | 532 | 8 | 48 | +84 | local_static_guard |
| 函数局部静态（`-fno-threadsafe-statics`） | 484 | 8 | 48 | +36 | — |
| 全局对象非平凡析构（默认） | 532 | 16 | 44 | +84 | static_dtor |
| 全局对象非平凡析构（`-fno-use-cxa-atexit`） | 472 | 16 | 40 | +24 | — |
| `std::span` 求和 / C 指针+长度 | 508 / 488 | 40 | 40 | +60 / +40 | — |
| `std::optional` | 492 | 8 | 40 | +44 | — |
| `std::variant` + `std::visit`（3 状态） | 508 | 8 | 48 | +60 | — |
| `consteval` CRC8 表 / 运行期生成（C） | 716 / 500 | 8 | 40 / 296 | +268 / +52 | — |
| `std::atomic<uint32_t>::fetch_add` | 468 | 8 | 40 | +20 | — |
| `std::atomic<uint64_t>::fetch_add` | 链接失败：`__atomic_fetch_add_8`、`__atomic_load_8` 未定义 | | | | — |

Cortex-M0+（`-mfloat-abi=soft`）基线为 468 B，其余增量与 M4 同量级：

- 异常 +10245 B，`std::function` +1228 B，`std::vector` +1062 B。
- 虚函数 +88 B，模板 +28 B。
- `std::atomic<uint32_t>::fetch_add` **链接失败**（`__atomic_fetch_add_4` 未定义），`is_always_lock_free` 为 false。

调用点（M4，`main` 指令数 / 间接调用数）：模板 20 / 0；`virtual` 23 / 2；C 函数表 23 / 2。

**解读边界**：

- 这些是隔离的微基准增量，不能直接相加；共享的运行时（如 malloc）只计一次。
- 换编译器（Clang、IAR、ARM Compiler 6）、libc（picolibc）或优化级别后数字会变，以项目 ELF 上的 `cpp_cost.py diff` 为准。
- 执行时间未在此测量，需按 [verification/cpp-testing.md](../verification/cpp-testing.md) §6 在目标板上测。
