# 来源与版本（核实日期 2026-11-04）

上游会更新。规则与当前上游不一致时，以上游为准，并更新本技能。

| 角色 | 来源 | 使用方式 | 许可 |
| --- | --- | --- | --- |
| Agent 工作流基础 | <https://github.com/brunofbloq/embedded-agent-skills> | 借鉴 architect/developer/qa 分工、两阶段架构门、证据级别、任务契约；**独立改写，未复制原文**（该仓库未声明许可证） | 未声明 |
| MCU 架构规则参考 | <https://github.com/rovinax/embedded-skills> | 分层架构、驱动、ISR、RTOS 规则，按 BARR-C 与实际工程修订 | MIT |
| C 代码规范基线 | BARR-C:2018 *Embedded C Coding Standard*，<https://barrgroup.com/embedded-c-coding-standard> | 规则编号与要点（意译） | 免费发布 |
| BARR-C 门禁 | <https://github.com/netrinomike/barr-c>（Barr Group 官方 enforcement kit，`2018/`，commit `75bcc16`） | 原样附带 `.clang-format`、`.clang-tidy`、`.editorconfig`、`check.sh`、`COMPILER_FLAGS.md`、`CODE_GENERATION_POLICY.md` | MIT |
| MCU 测试基线 | Ceedling <https://github.com/ThrowTheSwitch/Ceedling>（1.2.2），文档 `docs/` 与 mkdocs 站点 | 1.x 配置、命令、插件 | MIT |
| Zephyr 规范 | <https://docs.zephyrproject.org/latest/contribute/style/code.html>、`/contribute/coding_guidelines/`、`/contribute/guidelines.html`、`/develop/test/ztest.html` | 风格、MISRA 子集、提交规则、ztest/Twister | Apache-2.0 文档 |
| Linux 规范 | 内核树 `Documentation/process/coding-style.rst`、`submitting-patches.rst`、`coding-assistants.rst`、`generated-content.rst`；`Documentation/dev-tools/kunit/` | 风格、提交、AI 辅助规则、测试 | GPL-2.0 文档 |
| Modern Embedded C++ | Pigweed <https://github.com/google/pigweed>（`docs/sphinx/embedded_cpp_guide.rst`、`size_optimizations.rst`、`style/cpp.rst`，commit `dd2d565`） | 标准库白/灰/黑名单、无异常与无堆策略、ISR/线程安全标注、尺寸优化选项 | Apache-2.0 |
| 同上 | modm <https://github.com/modm-io/modm>（`docs/src/how-modm-works.md`、`docs/coding_convention.md`，commit `8e942c2`） | 静态类型外设、编译期波特率/分频校验 | MPL-2.0 |
| 同上 | ETL <https://github.com/ETLCPP/etl>（commit `b2c437c`） | 固定容量容器、`queue_spsc_isr`、`delegate`、`expected`、`etl_profile.h` | MIT |
| 同上 | C++ Core Guidelines <https://github.com/isocpp/CppCoreGuidelines>（commit `5baf9fe`） | 规则编号与要点（意译） | Standard C++ Foundation 许可 |
| C++ 测试基线 | CppUTest <https://github.com/cpputest/cpputest>（发布版 v4.0；文档与 API 核对于 commit `42feb87`） | CppUTest/CppUMock 用法、CMake 目标名 | BSD 风格 |
| Zephyr C++ | <https://docs.zephyrproject.org/latest/develop/languages/cpp/index.html>、`lib/cpp/Kconfig` | C++ Kconfig、minimal libc++ 限制 | Apache-2.0 文档 |
| MISRA C++:2023 | MathWorks/QA Systems 公开资料 | 面向 C++17，取代 MISRA C++:2008 与 AUTOSAR C++14 | — |

| Cortex-M fault 分析 | ARMv7-M Architecture Reference Manual（ARM DDI 0403）、ARMv8-M Architecture Reference Manual（ARM DDI 0553） | CFSR/HFSR/MMFAR/BFAR 地址与位、异常栈帧、EXC_RETURN（[verification/debugging.md](verification/debugging.md) §2） | ARM 文档 |
| RISC-V | RISC-V Unprivileged / Privileged Specification（<https://riscv.org/specifications/>） | mcause 异常码、A 扩展、RVWMO、psABI 栈对齐（[platforms/riscv.md](platforms/riscv.md)） | CC-BY-4.0 |
| ESP-IDF | ESP-IDF Programming Guide v6.1 与 v6.0 发布说明（<https://docs.espressif.com/projects/esp-idf/>，核实于 2026-11-06） | IDF FreeRTOS SMP、Flash cache 与 IRAM、RISC-V panic 寄存器、Style Guide、OTA 回滚、Flash Encryption、v6 迁移（[platforms/esp-idf.md](platforms/esp-idf.md)） | Apache-2.0 |
| ThreadX | Eclipse ThreadX（<https://github.com/eclipse-threadx/threadx>）用户手册与 `tx_api.h` | 优先级语义、抢占阈值、ISR 服务调用、内存池（[rtos/threadx.md](rtos/threadx.md)） | MIT |
| 启动与升级 | MCUboot 设计文档（<https://docs.mcuboot.com/>） | 交换模式、镜像确认与回滚、防回滚计数器（[architecture/boot-update.md](architecture/boot-update.md)） | Apache-2.0 |
| Agent Skills 规范 | <https://agentskills.io/specification>（核实于 2026-11-05） | frontmatter 约束、目录结构、引用深度；由 `tools/validate_skill.py` 机械检查 | — |
| Codex 技能元数据 | <https://learn.chatgpt.com/docs/build-skills>（核实于 2026-11-05） | `agents/openai.yaml` 字段与技能发现目录 | — |

**核实状态**：上表最后两行在 2026-11-05 对照原文核实。Cortex-M 一行中的 CFSR/HFSR/MMFAR/BFAR 地址、CFSR 各位位号、HFSR `FORCED`/`VECTTBL`、ACTLR `DISDEFWBUF` 于 2026-11-05 与 ARM CMSIS 头文件 `core_cm4.h`（CMSIS 4）和 `core_cm33.h`（CMSIS 5）逐项核对一致；异常栈帧与 EXC_RETURN 位语义未核对。RISC-V、ThreadX、MCUboot 三行依据上述文档编写，但没有在本次会话中逐条对照原文；寄存器地址、位号、异常码、API 名称在用于具体芯片之前，必须对照该芯片的参考手册和所用版本的文档（`GEN-002`）。

## 已知需要随上游复核的点

- Zephyr 的 `Assisted-by:` 格式与 coding guidelines 规则表（随版本变化）。
- Linux 分配辅助宏（`kmalloc_obj` 等为较新内核引入，旧 BSP 内核没有）。
- Ceedling 1.x 次版本新增的选项（Partials、Sanitize 插件）。
- C++ 开销表随工具链变化：新工具链落地时运行 `scripts/bench/run.sh` 并更新 `cpp/features.md` §4。
- CppUTest 新发布版（v4.0 之后）的 CMake 目标名与 CMake 版本要求。
- BARR-C:2026 版发布后（官方 kit 计划提供 `2026/` 目录与机器可读规则清单），替换本技能的 2018 基线。
- P3 新增的 riscv、threadx、boot-update 参考，以及 debugging 中的栈帧/EXC_RETURN 描述，尚未逐条对照原文核实（见上表“核实状态”）。
- ESP-IDF：ESP32-S31 在 v6.1 中为 preview 目标，转为正式支持后复核 [platforms/esp-idf.md](platforms/esp-idf.md) §1；该文“来源”末尾列出的未逐条核对项。
- computerguided/embedded-software-development-guidelines 尚未研究（原计划列入 P2，未完成）。
