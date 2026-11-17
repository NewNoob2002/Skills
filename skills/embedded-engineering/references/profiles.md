# Profile 判定与规则冲突裁决

## 1. 判定流程

1. 读项目显式规则：`AGENTS.md`、`CLAUDE.md`、`CONTRIBUTING*`、`.clang-format`、`.clang-tidy`、`.checkpatch.conf`、`.editorconfig`、MISRA/BARR-C 偏离记录。存在即优先。
2. 运行 `scripts/detect_profile.py <repo>`，核对它给出的证据文件，而不是只看结论。
3. 按目录划分 profile。常见混合形态：
   - `firmware/`（`mcu-rtos`）+ `linux/drivers/`（`linux-kernel`）+ `app/`（`linux-userspace`）
   - Zephyr 应用中的纯算法库：仍属 `zephyr`；不依赖 Zephyr API 的部分可额外用 Ceedling（C）或 CppUTest（C++）做 host 测试（见 §5）。
4. 判定不了且会影响结果（例如要不要改成 Allman 风格）时询问用户；不影响结果时选择与周边代码一致的规则并在报告中说明。

## 2. 每个 profile 的规范来源

| Profile | 格式/命名 | 语义/安全规则 | 架构 | 测试 | 提交 |
| --- | --- | --- | --- | --- | --- |
| `mcu-baremetal` | BARR-C 全量 | BARR-C 全量 + 项目 MISRA（如有） | `architecture/mcu-architecture.md` | Ceedling（C）/ CppUTest（C++） | BARR-C 生成代码政策 |
| `mcu-rtos` | BARR-C 全量 | 同上 + `rtos/mcu-isr-rtos.md` | `architecture/mcu-architecture.md` | Ceedling（C）/ CppUTest（C++） | BARR-C 生成代码政策 |
| `zephyr` | Zephyr code style | Zephyr coding guidelines（MISRA C:2012 子集）+ BARR-C 安全核心中不冲突部分 | Zephyr 设备模型 | ztest + Twister | Zephyr DCO / `Assisted-by` |
| `esp-idf` | ESP-IDF Style Guide（Astyle，`#pragma once`，行宽 120） | ESP-IDF 规则（`ESP-*`）+ BARR-C 安全核心中不冲突部分 | IDF 组件模型（[platforms/esp-idf.md](platforms/esp-idf.md)） | IDF Unity + pytest-embedded；纯逻辑 Ceedling/CppUTest | 上游按 Espressif 贡献协议；`GEN-004` |
| `linux-kernel` | `coding-style.rst` + checkpatch | 内核惯例 + BARR-C 安全核心中不冲突部分 | 内核子系统框架 | KUnit / kselftest | DCO、工具生成内容披露 |
| `linux-userspace` | 项目既有；无则 BARR-C 格式层可选 | BARR-C 安全核心 | 平台隔离 | 项目既有；无则 Ceedling（C）/ CppUTest（C++） | 项目约定 |

## 3. 冲突裁决矩阵

“安全核心”指 [c/barr-c.md](c/barr-c.md) §2 中不依赖格式的规则；“格式层”指 §3。

| 主题 | BARR-C | Zephyr | Linux kernel | 裁决 |
| --- | --- | --- | --- | --- |
| 缩进 | 4 空格，禁止 tab（3.4.a / 3.5.a） | 8 宽 tab | 8 宽 tab | 按 profile；跨生态不混用 |
| 行宽 | 80（1.2.a） | 100 | 80 首选 | 按 profile |
| 花括号位置 | Allman（1.3.b） | K&R（Linux 风格） | K&R | 按 profile |
| 单语句花括号 | 必须（1.3.a） | 必须（`if/else/do/while/for/switch`） | 只在需要时 | MCU、Zephyr 必须；kernel 遵循 checkpatch |
| `//` 注释 | 允许（2.1.a） | 禁止，只用 `/* */` | 允许但惯用 `/* */` | 按 profile |
| typedef struct | 需要 typedef 并以 `_t` 结尾（5.1.a/b） | 跟随 Linux：少用 | 禁止 typedef struct/指针 | 按 profile |
| 全局/指针前缀 `g_` `p_` `b_` `h_` | 要求（7.1.j–n） | 不用 | 禁止类型编码命名 | 只在 MCU profile |
| 常量放 `==` 左边 | 要求（8.6.a） | 不要求 | checkpatch 警告此写法 | 只在 MCU profile；其他用 `-Werror=parentheses` 与 clang-tidy 防误赋值 |
| `goto` | 尽量避免（1.7.c） | 允许清理路径 | 推荐集中清理 `goto out_*` | MCU 尽量避免；kernel 按内核惯例 |
| `short`/`long` | 禁止（5.2.b） | 少用，用定宽类型 | `unsigned long` 是指针宽度惯用法 | MCU 禁止；kernel 按惯例 |
| `int` 返回错误码 | 定宽优先 | `int` + 负 errno | `int` + 负 errno | Zephyr/Linux 必须用负 errno，不要自造 `error_t` |
| fall-through | 注释说明（8.3.c） | `__fallthrough` | `fallthrough;` | 按 profile 使用平台宏 |
| 动态内存 | 不禁止，但 rovinax 架构禁运行期 malloc | coding guidelines Dir 4.12 禁止 | 正常使用，必须处理失败 | MCU：初始化后禁 malloc；kernel：检查失败、优先 `devm_*` 仅当子系统惯例如此 |
| `volatile` | 1.8.c（线程共享用途已撤回） | 寄存器经设备 API 访问 | `volatile` 视为有害，用 `READ_ONCE`/`readl` | 任何 profile 都不得用 `volatile` 做线程同步 |
| ISR 命名 `_isr`（6.5.b） | 要求 | 不要求 | `*_irq_handler` 等惯例 | MCU：自写 ISR 用 `_isr`；向量表固定名（`USART1_IRQHandler`）为记录在案的例外 |
| 头文件保护 | `#ifndef` guard（4.2.b），`#pragma` 受限（1.1.c） | `#ifndef ZEPHYR_..._H_` guard | `#ifndef _LINUX_FOO_H` guard | 统一用 guard，不用 `#pragma once` |

**ESP-IDF**（`esp-idf` profile，依据 ESP-IDF Style Guide，见 [platforms/esp-idf.md](platforms/esp-idf.md) §2）：4 空格缩进、禁止 tab；函数定义花括号换行、控制语句花括号同行；行宽 120；静态变量 `s_` 前缀而非 `g_`/`p_`/`b_`；头文件用 `#pragma once`（与 `C-016` 冲突，按 `ESP-006` 裁决）；`//` 注释允许。BARR-C 格式/命名层不用于 IDF 组件，安全核心中不冲突的规则仍适用。

## 4. 上游与私有代码

- 要提交到 Zephyr 主线、Linux 主线或厂商 BSP 上游的代码：**只用该上游的规范**，不得混入 BARR-C 格式或 `g_` 前缀。
- 私有 Zephyr 应用：默认 Zephyr 风格（与 API、生成代码、示例一致）；若团队已全面采用 BARR-C 格式且有 `.clang-format` 证据，则沿用团队规则，但驱动/模块代码仍按 Zephyr 风格以便将来上游。
- 厂商生成代码（CubeMX、MCUXpresso、ESP-IDF 组件、`platform/`）：不重排、不改格式，只在 `USER CODE BEGIN/END` 等保护区内修改，并把它们排除在 BARR-C 门禁之外。

## 5. C/C++ 混合工程

- 规则按语言契约划分：`.c` 适用对应平台 C 规范（自有 MCU 默认 BARR-C）；`.cpp/.cc/.cxx` 与 C++ 专用头适用 [cpp/coding.md](cpp/coding.md)。`.h` 不自动归 C；共享 ABI 头只含 C 构造，用 `#ifdef __cplusplus` 保护 `extern "C"`，并由 C/C++ 各自编译测试。
- 所有新增自有 C/C++ 函数与方法默认必须有 Doxygen（含私有、构造、析构、模板、重载；声明或定义择一，不重复；类级注释不替代）。默认英文，项目可指定语言；`style_gate.py` 的 `doxygen` 默认 `true`，只检查块存在，语义由评审确认。第三方、生成代码和遗留基线不选入门禁。
- C++ 适用性：`mcu-*` 可用；`zephyr` 只在应用层用（内核、驱动、`SYS_INIT` 保持 C）；`linux-kernel` 不用；`linux-userspace` 按 T3。
- 资源等级 T0–T3 决定 C++ 特性取舍（[cpp/features.md](cpp/features.md)）。`detect_profile.py` 的 `resource_tier` 从链接脚本推算，属建议值。
- 平台、资源等级、风格独立选择。自有 MCU 无既有风格时保留方案 A（Allman/100 列）；显式选用的 `readable-cpp` 见 [cpp/readable-cpp.md](cpp/readable-cpp.md)。C API 保持平台 C 命名；同目录混编用显式范围分流，不能按所有 `.h` 或空集合回退全仓。
- Zephyr 应用 C++ 默认 Zephyr 风格与 ztest/Twister；ESP-IDF C++ 用项目/IDF 风格与 IDF 构建、测试；Linux 用户态 C++ 用项目风格、真实编译数据库和项目测试，资源为 T3，不继承 MCU 禁运行时/链接裁剪。只有显式选择的自有目录用 readable-cpp，上游贡献仍按上游规则。
- 测试：C 用 Ceedling，C++ 用 CppUTest；Zephyr 以 ztest + Twister 为准，只有不依赖 Zephyr API 的纯逻辑库可额外做 Ceedling/CppUTest host 测试。

| 主题 | C（BARR-C） | C++（cpp/coding.md） |
| --- | --- | --- |
| 列宽 | 80 | 100 |
| 模块前缀 | `motor_set_speed()` | `proj::motor::set_speed()` |
| 类型名 | `motor_t` | `Motor` |
| 常量 | `MOTOR_MAX_RPM` 宏 | `constexpr kMaxRpm` |
| 错误 | `proj_err_t` 枚举 | `enum class Status` + `Result<T>` |
| 单一出口 | 优先（6.2.c） | 不强制（Core Guidelines NR.2） |
| `goto` | 尽量避免 | 不用（RAII 清理） |
