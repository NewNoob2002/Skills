# 来源矩阵

技能内的权威版本表在 `skills/embedded-engineering/references/sources.md`（随技能安装，供 Agent 查阅）。本文件面向维护者：说明每个来源**用了什么、没用什么、可信到什么程度、维护风险在哪里**。评估只依据本项目实际验证过的事实，没有核实的项写明“未核实”。

## 1. 矩阵

| 来源 | 版本 / 提交 | 许可 | 本技能采用的部分 | 有意不采用的部分 | 本项目验证过的事实 | 维护风险 |
| --- | --- | --- | --- | --- | --- | --- |
| brunofbloq/embedded-agent-skills | 未锁定提交 | 未声明 | Architect / Developer / QA 分工、两阶段架构门、证据级别、任务契约（`workflows/workflow.md`） | 原文（无许可证，只借鉴结构，独立改写） | — | 无许可证意味着不能复制文本；结构思想不受影响 |
| rovinax/embedded-skills | 未锁定提交 | MIT | 分层架构、驱动设计、ISR 与 RTOS 规则（`architecture/mcu-architecture.md`、`rtos/mcu-isr-rtos.md`） | 固定的 ISR 时间表、W1C 寄存器 `\|=` 写法、优先级 0 调用 `FromISR` 等错误做法 | 原文存在 6 处与芯片手册、FreeRTOS 约束或 BARR-C 不符的地方，修订表见 `mcu-isr-rtos.md` §7 与 `mcu-architecture.md` §8 | 社区规则不可直接当权威；每条都需对照手册 |
| BARR-C:2018 标准 | 2018 版 | 免费发布 | 规则编号与意译要点（`c/barr-c.md`） | 原文复制 | 勘误 4 条已记录（`barr-c.md` §5） | 2026 版发布后需整体替换 |
| netrinomike/barr-c（Barr Group 官方 enforcement kit） | `2018/`，commit `75bcc16` | MIT | `.clang-format`、`.clang-tidy`、`check.sh`、告警门禁 | — | **clang-tidy 23 静默忽略其中的 `hicpp-signed-bitwise`**，BARR-C 5.3.b 因此失效（`evals/TRIAGE.md` #2）；已本地补 `bugprone-signed-bitwise`，并加入检查名有效性的回归测试 | 工具链升级会让“原样”配置悄悄失效；需要 `ClangTidyConfigTest` 持续守护 |
| Ceedling | 1.2.2（gem） | MIT | 1.x 配置、命令、CMock 插件（`verification/ceedling.md`、`assets/ceedling/project.yml`） | — | 1.2.2 对 `:paths:` 中不存在的目录报配置错误（TRIAGE #1）；只用 `:include` 作为头文件路径（TRIAGE #3） | 0.31 → 1.x 有破坏性变更；版本需锁定 |
| CppUTest | v4.0（源码构建） | BSD 风格 | CppUTest / CppUMock 用法、CMake 目标名 | — | v4.0 需要 `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` 才能用 CMake ≥ 4 构建；模板与验证工程均已在其上运行 | 发布节奏慢，master 与 v4.0 的目标名不同 |
| Zephyr 官方文档与源码树 | v4.5.0 | Apache-2.0 | code style、Coding Guidelines（MISRA 子集）、贡献规则、ztest/Twister | — | 树内 checkpatch 强制花括号（与 Linux 版相反，TRIAGE #6）；`.checkpatch.conf` 不容忍 `//` 注释；`.clang-format` 启用 `InsertBraces`；`native_sim/native/64` 无需 SDK | 规则表与 `Assisted-by:` 格式随版本变化 |
| Linux 内核树文档 | 未锁定版本 | GPL-2.0 | coding-style、提交规则、AI 辅助贡献规则、KUnit | — | 未在本机内核树上运行（NOT_RUN） | 分配辅助宏等随内核版本变化 |
| FreeRTOS-Kernel | V11.3.3 | MIT | ISR API、优先级约束、静态分配；POSIX 移植用于 host 集成测试 | — | V11 不允许同时定义 `configUSE_16_BIT_TICKS` 与 `configTICK_TYPE_WIDTH_IN_BITS`（TRIAGE #4） | 配置宏随大版本演进 |
| Pigweed | commit `dd2d565` | Apache-2.0 | 无异常、无堆策略，ISR/线程安全标注，尺寸优化 | 框架本身（不要求项目引入 Pigweed） | — | 文档路径变动频繁 |
| modm | commit `8e942c2` | MPL-2.0 | 编译期外设与波特率校验思路 | 代码 | — | 只借鉴思路，风险低 |
| ETL | commit `b2c437c`（文档）；20.49.0（验证） | MIT | 固定容量容器、`delegate`、`queue_spsc_isr` | — | C++ 模板矩阵在 20.49.0 上编译通过；ETL 头需 `-isystem`，否则触发 `-Wold-style-cast` | 发布频繁，需锁定版本 |
| C++ Core Guidelines | commit `5baf9fe` | Standard C++ Foundation | 规则编号与要点（意译） | — | — | 规则编号稳定 |
| Agent Skills 规范 | <https://agentskills.io/specification>（2026-11-05 核实） | — | frontmatter 约束、目录结构、引用深度（`tools/validate_skill.py`） | — | — | 规范仍在演进 |
| Codex 技能元数据 | <https://learn.chatgpt.com/docs/build-skills>（2026-11-05 核实） | — | `agents/openai.yaml` 字段与发现目录 | — | Codex 0.166 能从 `.agents/skills/` 发现技能并按路由表读取 reference（P5 冒烟测试） | 字段文档较少 |
| ARM 架构手册与 CMSIS 头文件 | ARM DDI 0403 / DDI 0553；CMSIS 4、5 | ARM | Cortex-M fault 寄存器（`verification/debugging.md` §2） | — | 地址与位号与 `core_cm4.h`、`core_cm33.h` 逐项一致；栈帧与 EXC_RETURN 语义未核对 | — |
| RISC-V 规范、Eclipse ThreadX、MCUboot | 未锁定 | 各自许可 | `platforms/riscv.md`、`rtos/threadx.md`、`architecture/boot-update.md` | — | **未对照原文核实**（`sources.md` 的核实状态） | 使用前需对照原文 |
| computerguided/embedded-software-development-guidelines | — | — | — | — | **尚未研究**（原计划列入 P2） | — |

## 2. 结论

- 社区技能仓库（brunofbloq、rovinax）只能作为结构与清单的起点：一个没有许可证，一个有多处与手册矛盾的规则，两者都经过改写与修订。
- 官方工具配置也不能“原样即正确”：BARR-C kit 的 clang-tidy 配置在新工具链上静默失效，是本项目通过验证工程才发现的。凡是“原样附带”的第三方配置，都需要有能在工具升级时失败的回归测试。
- 有版本号且在本机实际运行过的来源（Ceedling 1.2.2、CppUTest v4.0、Zephyr v4.5.0、FreeRTOS V11.3.3、ETL 20.49.0）可信度最高；文档类来源次之；未对照原文的参考（RISC-V、ThreadX、MCUboot）在报告中明确标为未核实。
