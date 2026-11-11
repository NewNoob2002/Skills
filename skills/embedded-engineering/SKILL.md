---
name: embedded-engineering
description: >-
  Embedded C/C++17/20 engineering for MCU bare-metal, FreeRTOS/ThreadX, Zephyr, ESP-IDF (ESP32 Xtensa/RISC-V) and embedded Linux drivers/userspace.
  Use when designing, writing, reviewing, refactoring, testing or debugging firmware and drivers;
  analyzing HardFault/traps and fault registers; designing bootloader/OTA/firmware updates with power-loss safety;
  or building Ceedling/CppUTest host tests.
  Also use for API/rule questions without edits: FreeRTOS ISR-safe calls, ThreadX priority mapping,
  Zephyr DEVICE_DT_GET/device_is_ready, driver buffer allocation, flash/RDP safety and upstream DCO/AI attribution.
  Covers BARR-C, C++ feature/Flash/RAM trade-offs, ETL/Pigweed/modm, ztest/Twister, KUnit/checkpatch,
  CMSIS-RTOS2, BSP/HAL, devicetree/Kconfig, layered architecture, state machines, protocols and RISC-V.
  嵌入式 C/C++（含 ESP-IDF）固件与驱动设计、编写、审查、重构、测试及调试；HardFault/故障寄存器分析、bootloader/OTA 升级与掉电安全、
  Ceedling/CppUTest 主机测试；也用于 FreeRTOS 中断安全调用、ThreadX 优先级换算、Zephyr 设备就绪与驱动缓冲区分配、
  烧录/RDP 安全、上游 DCO/AI 署名等知识问答。
---

# Embedded Engineering Baseline

一个技能、六个 profile、三种角色。先选 profile，再按角色走流程，只加载需要的 reference。

## 0. 不可违反的护栏（所有 profile）

- **硬件动作必须授权**：flash、mass-erase、eFuse/OTP、option bytes、secure boot、驱动执行器/电源设备前，必须得到对该目标和影响范围的明确授权，并说明恢复路径。
- **命令示例不等于执行授权**：型号或工具版本未知时，不写可直接执行的 option bytes/RDP 命令（包括 `-ob RDP=…` 这类赋值），先索取完整芯片型号、参考手册、工具及版本，不猜地址或命令。信息齐全后可展示带风险说明的可复核方案，不必先批准才能看方案；给烧录/保护方案时说明覆盖或不可逆后果，并要求用户在实际执行前明确确认具体芯片、目标板/探针与影响范围，接受不可逆后果并授权。ESP 的 eFuse、Secure Boot、Flash Encryption（Release）与禁用下载模式同属不可逆动作（`ESP-005`）。RDP Level 2 默认按不可逆处理，部分型号的预置 OEM 密钥回退条件须按型号核实（见 [调试授权](references/verification/debugging.md) §1）。
- **不编造硬件事实**：寄存器、位域、时钟、引脚复用、DMA 通道、errata、SDK API 必须来自仓库内头文件/数据手册/参考手册/板级原理图；查不到就标为 `UNKNOWN` 并提问。
- **证据分级**：host 测试、静态检查、仿真、HIL、实测各自给出 `PASS / FAIL / NOT_RUN / BLOCKED`。没有跑过就是 `NOT_RUN`，仿真通过不等于硬件通过。
- **溯源**：Agent 不得添加 `Signed-off-by`（Zephyr 与 Linux 均明确禁止），即使环境只读或没有补丁，也应说明 DCO 由人类审查并签署，而非仅以工具权限拒绝。生成代码需记录工具/模型（Zephyr 用 `Assisted-by:`，BARR-C 生成代码政策要求记录工具与版本，并有具名人类作者负责）。

## 1. 选择 profile（先做这一步）

运行 `python3 scripts/detect_profile.py <repo>`（只读，输出 JSON 证据），或按下表人工判断。一个仓库可以有多个 profile（例如 Cortex-M 协处理器固件 + Linux 驱动），按目录分别适用。

| Profile | 识别特征 | 编码规范 | 架构规则 | 测试基线 |
| --- | --- | --- | --- | --- |
| [`mcu-baremetal`](profiles/mcu-baremetal.yaml) | 启动文件 `startup_*.s`、链接脚本 `*.ld/*.sct`、CMSIS 设备头 | **BARR-C:2018 全量**（C）/ C++ 规范（`.cpp`） | 分层架构（rovinax 修订版） | **Ceedling**（C）/ **CppUTest**（C++）+ 目标机构建 |
| [`mcu-rtos`](profiles/mcu-rtos.yaml) | `FreeRTOSConfig.h`、`cmsis_os2.h`、RT-Thread 等 | **BARR-C:2018 全量**（C）/ C++ 规范（`.cpp`） | 分层架构 + RTOS/ISR 规则 | **Ceedling**（C）/ **CppUTest**（C++）+ 目标机构建 |
| [`zephyr`](profiles/zephyr.yaml) | `west.yml`、`prj.conf`、`find_package(Zephyr)`、`zephyr/module.yml` | **Zephyr 官方**（Linux 风格 + 例外 + MISRA 子集） | Zephyr 设备模型/devicetree/Kconfig | **ztest + Twister** |
| [`esp-idf`](profiles/esp-idf.yaml) | `sdkconfig(.defaults)`、`idf_component_register`、`idf_component.yml`、`project.cmake` | **ESP-IDF Style Guide**（Astyle）+ BARR-C 安全核心 | IDF 组件模型 + SMP/IRAM/Xtensa·RISC-V 规则 | **IDF Unity + pytest-embedded**；纯逻辑 host 测试 |
| [`linux-kernel`](profiles/linux-kernel.yaml) | `Kbuild`、`obj-m`/`obj-y`、`MAINTAINERS`、DT bindings | **Linux 内核官方** coding-style + checkpatch | 内核子系统框架 | **KUnit / kselftest** + 构建告警门禁 |
| [`linux-userspace`](profiles/linux-userspace.yaml) | 守护进程/工具、Yocto recipe、CMake/Meson 的 Linux 应用 | 项目既有规范；无则 BARR-C 安全核心（C）/ C++ 规范 T3（`.cpp`） | 平台隔离 + 进程/服务边界 | 项目既有框架；无则 Ceedling/Unity（C）/ CppUTest（C++） |

**规则库**：[standards/rules.yaml](standards/rules.yaml) 收录可机械检查、跨生态冲突或需要按 ID 引用的规则（`GEN`、`ARCH`、`C`、`CFMT`、`ISR`、`RTOS`、`DMA`、`CPP`、`ZEP`、`ESP`、`LNXK`、`LNXU`、`TEST`），每条给出适用 profile、强制等级、验证方法和出处章节。某 profile 适用的规则 = `profiles` 含该 profile 或 `all`，且 `when` 条件成立的条目（无 `when` 视为成立）；每个 profile 文件（上表第一列链接）列出该 profile 的规范、测试基线和门禁命令。规则细节以 `ref` 指向的 reference 为准。

**语言**：`.c/.h` 按上表的 C 规范；`.cpp/.hpp` 按 [cpp/coding.md](references/cpp/coding.md)，并按资源等级 T0–T3 取舍特性（[cpp/features.md](references/cpp/features.md)）。等级由 `detect_profile.py` 的 `resource_tier` 给出建议，需对照芯片资源确认。`linux-kernel` 不引入 C++；Zephyr 只在应用层使用 C++，内核、驱动、系统初始化保持 C。测试框架按 profile 与语言选择（见上表）：`mcu-*` 与 `linux-userspace` 的 C 用 Ceedling、C++ 用 CppUTest；`zephyr` 以 ztest + Twister 为准，只有不依赖 Zephyr API 的纯逻辑可额外做 host 测试；`linux-kernel` 用 KUnit/kselftest。

**平台问答也按规则回答**：题目中的平台决定该问题的 profile，不以沙箱示例工程覆盖它。Zephyr 驱动缓冲区按 `ZEP-007` 不用 malloc/通用堆；先说明约束，再给每实例静态缓冲区或固定块池方案，不能用“可以，但不推荐”替代强制规则（见 [Zephyr](references/platforms/zephyr.md) §3）。

**规则优先级**（高 → 低）：运行时/授权限制 → 项目显式规则（`AGENTS.md`、`CLAUDE.md`、既有 `.clang-format`、MISRA 偏离记录）→ 目标生态官方规范（Zephyr/Linux，**向上游提交时强制**）→ BARR-C → 分层架构规则 → 本工作流默认值。冲突的详细裁决见 [profiles.md](references/profiles.md)。

**项目常驻规则**：目标仓库没有 `AGENTS.md` 时，可按 `assets/AGENTS.md.template` 起草（芯片、SDK、命令、硬件授权范围只写已核实的事实，未知写 `UNKNOWN`），经用户确认后再放入仓库。

## 2. 选择角色与评审深度

基于 brunofbloq/embedded-agent-skills 的“架构 / 实现 / 验证分离”工作流，详细步骤见 [workflows/workflow.md](references/workflows/workflow.md)。

- **Architect**：新产品、新子系统、跨核/跨进程接口、OS 选型、资源预算变化 → 完整两阶段评审，Phase 1 结束必须拿到**明确批准**才进入实现。有界变更 → architecture delta。孤立缺陷 → fast path，直接交给 Developer。
- **Developer**：检查 → 定契约 → 核实硬件假设 → 窄范围实现 → 审计故障路径 → 验证 → 报告。
- **QA**：独立定义测试 oracle（来自需求/规格，而非复制实现输出），选成本最低且可信的后端，按证据级别报告。

用户只要求“改个 bug”时不要强加完整评审；用户要求“评审架构”时不要直接写代码。

**工作流**（每页含输入、前置条件、步骤、检查点、通过/失败标准与人工审批条件；角色分离规则见 [workflows/workflow.md](references/workflows/workflow.md) §7）：

| 任务 | 工作流 |
| --- | --- |
| 新工程/新子系统架构 | [W01](references/workflows/new-architecture.md) |
| 审查现有工程架构 | [W02](references/workflows/architecture-review.md) |
| 新模块设计与实现 | [W03](references/workflows/module-implementation.md) |
| 驱动、协议栈、中间件 | [W04](references/workflows/driver-design.md) |
| C/C++ 代码审查 | [W05](references/workflows/code-review.md) |
| 生成测试用例 | [W06](references/workflows/test-generation.md) |
| 性能与资源分析 | [W07](references/workflows/performance.md) |
| 回归测试 | [W08](references/workflows/regression.md) |
| 重构规划 | [W09](references/workflows/refactor-planning.md) |
| 最终质量验收 | [W10](references/workflows/acceptance.md) |

## 3. 按需加载 reference（不要全部读）

| 任务 | 读取 |
| --- | --- |
| 判定 profile、处理规则冲突 | [profiles.md](references/profiles.md) |
| 架构评审、阶段门、交接、报告格式 | [workflows/workflow.md](references/workflows/workflow.md) |
| MCU 目录分层、依赖方向、接口/驱动设计 | [architecture/mcu-architecture.md](references/architecture/mcu-architecture.md) |
| ISR、RTOS 任务/优先级/IPC、DMA、看门狗 | [rtos/mcu-isr-rtos.md](references/rtos/mcu-isr-rtos.md) |
| ThreadX（与 FreeRTOS 的差异） | [rtos/threadx.md](references/rtos/threadx.md) |
| RISC-V 中断、原子、内存序 | [platforms/riscv.md](references/platforms/riscv.md) |
| 状态机、协议解析、超时、断言、日志、故障恢复 | [architecture/state-protocol-fault.md](references/architecture/state-protocol-fault.md) |
| bootloader、镜像校验、OTA、掉电安全 | [architecture/boot-update.md](references/architecture/boot-update.md) |
| HardFault/trap 分析、调试器、RTT/SWO、map 与栈分析 | [verification/debugging.md](references/verification/debugging.md) |
| 写/审 C 代码（MCU 与 userspace） | [c/barr-c.md](references/c/barr-c.md) |
| 写/审 C++ 代码：语言标准、命名、类设计、错误处理、生命周期、并发、C SDK 边界 | [cpp/coding.md](references/cpp/coding.md) |
| 某个 C++ 特性能不能用、资源等级、实测开销 | [cpp/features.md](references/cpp/features.md) |
| C++ 驱动/业务架构、RAII、ISR→任务、DMA、组合根示例 | [cpp/patterns.md](references/cpp/patterns.md) |
| C++ 单元测试（CppUTest）、Mock 接缝、开销评估、HIL | [verification/cpp-testing.md](references/verification/cpp-testing.md) |
| MCU host 单元测试、mock、覆盖率 | [verification/ceedling.md](references/verification/ceedling.md) |
| Zephyr 应用/驱动/模块 | [platforms/zephyr.md](references/platforms/zephyr.md) |
| ESP-IDF v6.x：组件、SMP 临界区、IRAM/cache、Xtensa 与 RISC-V 兼容、OTA 回滚、eFuse/安全启用 | [platforms/esp-idf.md](references/platforms/esp-idf.md) |
| Linux 内核驱动、DT binding、补丁提交 | [platforms/linux-kernel.md](references/platforms/linux-kernel.md) |
| 嵌入式 Linux 用户态 | [platforms/linux-userspace.md](references/platforms/linux-userspace.md) |
| 合并前的最终审查清单 | [verification/review-checklist.md](references/verification/review-checklist.md) |
| 版本与来源 | [sources.md](references/sources.md) |

## 4. 机械门禁（能跑就跑，跑不了就报告 NOT_RUN）

脚本都在本技能目录下，路径相对于本 `SKILL.md`；对目标仓库传参，不要把脚本复制进去执行。

- `scripts/detect_profile.py <repo>`：profile 识别。
- `scripts/arch_lint.py <repo> [--config layers.json]`：MCU 分层依赖检查（`#include` 方向、app/module 中的 HAL 调用与寄存器访问）。默认层映射见 `assets/arch_layers.json`。
- `scripts/barrc/check.sh <files...>`：Barr Group 官方 BARR-C:2018 enforcement kit（clang-format + clang-tidy + 词法门禁）。需要目标仓库根目录有 `assets/barr-c/` 中的 `.clang-format`、`.clang-tidy`；只对 MCU 生产代码中的 `.c/.h` 运行，不对 C++ 文件、`tests/`、`platform/` 厂商代码运行。
- 编译告警门禁：`assets/barr-c/COMPILER_FLAGS.md`（C）、`assets/cpp/compile_flags.md`（C++，含 `-fno-exceptions -fno-rtti` 与 `linker_discard.ld`）。
- C++：`assets/cpp/.clang-format`、`assets/cpp/.clang-tidy`（`platform/` 用 `clang-tidy-platform.yaml`）；模板在 `assets/cpp/templates/`。
- `scripts/cpp_cost.py check <elf> --tier T0|T1|T2|T3 [--budget budget.json]`：检查链接产物中按等级禁止的运行时（异常、RTTI、堆、atexit、guard、printf、iostream、原子库调用）与段预算；`cpp_cost.py diff <base.elf> <new.elf>`：A/B 尺寸增量。
- `scripts/bench/run.sh --cpu <cpu> [--etl <etl>/include]`：在项目工具链上复现 C++ 特性开销表。
- Zephyr：`./scripts/ci/check_compliance.py -c <range>`、`west twister -T <dir>`。
- ESP-IDF：`idf.py set-target <target> && idf.py build`（Xtensa 与 RISC-V 目标各构建一次）、`idf.py size-components`、`pre-commit run astyle_py --files <files>`。
- CI 模板：`assets/ci/github-actions.yml`、`assets/ci/gitlab-ci.yml`（只含构建、静态检查与 host 测试，不含硬件动作）。
- Linux：`./scripts/checkpatch.pl --strict`、`make W=1`、`make C=1`（sparse）、`./tools/testing/kunit/kunit.py run`、`make dt_binding_check`。

## 5. 输出约定

每次交付简要说明：profile 与依据；审查发现标注 Rule ID（如 `ISR-002`），没有对应规则的发现说明依据；改动文件与公共接口变化；硬件假设及来源；实际执行的命令和结果（逐项 `PASS/FAIL/NOT_RUN/BLOCKED`）；未验证的风险与原因。不要把长日志粘进对话，给出日志位置和关键行。
