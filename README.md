# embedded-engineering：嵌入式 C/C++ 开发 Agent 技能

把以下来源合成为**一个**可安装的 Agent Skill（agentskills.io 格式，Claude Code / Codex / Grok Build / Hermes 等通用），外加一份放进固件仓库、每次会话都会加载的 `AGENTS.md` 模板：

| 层 | 来源 | 在技能中的位置 |
| --- | --- | --- |
| Agent 工作流 | brunofbloq/embedded-agent-skills | `references/workflows/workflow.md`（Architect → Developer → QA、两阶段架构门、证据级别） |
| MCU 架构规则 | rovinax/embedded-skills（已修订） | `references/architecture/mcu-architecture.md`、`references/rtos/mcu-isr-rtos.md`、`scripts/arch_lint.py` |
| C 代码规范 | BARR-C:2018 + Barr Group 官方 enforcement kit | `references/c/barr-c.md`、`assets/barr-c/`、`scripts/barrc/check.sh` |
| MCU 测试 | Ceedling 1.x（Unity + CMock） | `references/verification/ceedling.md`、`assets/ceedling/project.yml`、`assets/templates/tests/` |
| 平台官方规范 | Zephyr、Linux kernel 树内文档 | `references/platforms/zephyr.md`、`references/platforms/linux-kernel.md`、`references/platforms/linux-userspace.md` |
| Modern Embedded C++ | Pigweed、modm、ETL、C++ Core Guidelines、Zephyr C++ 文档 + 本地实测开销 | `references/cpp/coding.md`、`references/cpp/features.md`、`references/cpp/patterns.md`、`assets/cpp/`、`scripts/cpp_cost.py`、`scripts/bench/` |
| C++ 测试 | CppUTest + CppUMock | `references/verification/cpp-testing.md`、`assets/cpp/templates/tests/` |

## 为什么是“Skill + AGENTS.md + 脚本”

- **Skill**：按需加载。`SKILL.md` 不到 100 行（profile 选择、角色、reference 路由表），十几页的规则只在相关任务时读取，不占每次会话的上下文。
- **AGENTS.md（项目内）**：保存这个仓库特有、必须每次都知道的事实，如芯片型号、SDK 版本、构建/测试命令、硬件授权范围。这些信息不应该写进通用技能。
- **脚本与配置**：可以机械检查的规则（格式、命名、分层依赖）交给工具判定，而不是靠模型“记得遵守”。BARR-C 部分直接使用 Barr Group 官方 kit。

这几个来源之间互相冲突，例如 BARR-C 要求 Allman 花括号、4 空格缩进和 `g_` 前缀，Linux 要求 tab、K&R 风格且禁止类型前缀，Zephyr 禁止 `//` 注释。技能先判定 **profile**（`mcu-baremetal`、`mcu-rtos`、`zephyr`、`linux-kernel`、`linux-userspace`），再按 `references/profiles.md` 的冲突裁决矩阵决定用哪套规则。BARR-C 拆成“安全核心”（全 profile 适用）和“格式/命名层”（仅 MCU）。

C++ 部分不简单禁止现代特性，而是按资源等级（T0 极小 MCU … T3 Linux 用户态）和实时路径取舍，取舍依据是在 Cortex-M0+/M4 上实测的 Flash/RAM 增量。

- **几乎免费**：模板、Concepts、CRTP、RAII、`constexpr`、`std::optional/variant/span`，增量都在 0–70 B。
- **代价大**：异常 +9.9 KB；`std::function`、`std::vector` 各约 +1 KB 并引入堆；iostream 在 newlib-nano 下无法链接。
- **隐性陷阱**：
  - 公有虚析构会拉入 `malloc`。
  - Cortex-M0+ 上 32 位 `std::atomic::fetch_add` 链接失败。
  - C++20 弃用 `volatile` 的 `++`。

已确定的方案：

- 语言标准：C++17 基线，C++20 可选。
- 格式：C++ 沿用 BARR-C 布局，列宽 100；命名按 Core Guidelines（命名空间代替模块前缀，不用 `p_`/`b_` 类型前缀）。
- 默认工具库：ETL。
- C++ 单元测试：CppUTest。

## 目录

```text
skills/embedded-engineering/    # 唯一可安装单元（install.sh 复制此目录）
├── SKILL.md                    # 入口：护栏、profile、角色、路由
├── standards/rules.yaml        # 109 条带 ID 的规则：适用 profile、等级、验证方法、出处章节、冲突
├── profiles/*.yaml            # 每个 profile 的规范、测试基线、门禁命令（与 rules.yaml 声明一一对应）
├── references/                 # 按需读取的规则
│   ├── profiles.md             #   profile 判定与冲突裁决
│   ├── sources.md              #   来源、版本、许可
│   ├── workflows/              #   Architect → Developer → QA、阶段门
│   ├── architecture/           #   MCU 分层、依赖方向、接口/驱动设计
│   ├── c/                      #   BARR-C 规则
│   ├── cpp/                    #   C++ 编码、特性取舍（T0–T3）、模式
│   ├── rtos/                   #   ISR、RTOS、DMA、看门狗
│   ├── platforms/              #   Zephyr、Linux kernel、Linux userspace
│   └── verification/           #   Ceedling、CppUTest、审查清单
├── scripts/
│   ├── detect_profile.py       # profile 识别（只读，JSON）
│   ├── arch_lint.py            # 分层依赖/HAL/寄存器访问检查（C 与 C++）
│   ├── cpp_cost.py             # ELF 门禁：按等级禁止的运行时符号、段预算、A/B 增量
│   ├── bench/                  # C++ 特性开销微基准（在你的工具链上复现）
│   └── barrc/check.sh          # Barr Group 官方 BARR-C:2018 门禁（原样）
├── assets/
│   ├── AGENTS.md.template      # 固件仓库的常驻规则模板
│   ├── arch_layers.json        # arch_lint 默认层规则
│   ├── barr-c/                 # .clang-format / .clang-tidy / .editorconfig / 编译告警
│   ├── ceedling/project.yml    # Ceedling 1.x 模板
│   ├── templates/              # 符合 BARR-C 的 C interface/module/test 示例
│   └── cpp/                    # C++：.clang-format/.clang-tidy、编译选项、linker_discard.ld、
│       └── templates/          #   驱动/总线/RAII/ISR 队列/DMA/组合根/CppUTest 模板
├── agents/openai.yaml          # Codex 显示元数据
└── THIRD_PARTY_NOTICES.md
tools/validate_skill.py         # Skill 自检：frontmatter、链接/路径/§ 引用、可达性、脚本、数据文件、规则库与 profile、打包卫生
tools/validate_skill.json       # 每个技能的自检配置（SKILL.md 行数预算、外部源码树路径白名单）
tests/test_scripts.py           # arch_lint、detect_profile 回归测试
tests/test_validate_skill.py    # validate_skill 变异测试（逐项注入缺陷，含 rules/profiles）与 YAML 子集解析测试
tests/test_cpp.py               # cpp_cost、C++ 模板矩阵、CppUTest 模板
tests/cpp/                      # C++ 模板编译与负向编译检查
install.sh                      # 安装器
```

## 安装

```sh
# 安装到某个固件仓库（项目级），同时放入 AGENTS.md 模板与 BARR-C 配置（已有同名文件时跳过）
./install.sh --agent claude --project-dir ~/work/fw --with-agents-md --with-barrc

# 安装到用户级（所有项目可用）
./install.sh --agent claude --scope user
./install.sh --agent codex  --scope user        # ~/.agents/skills/
./install.sh --dest /path/to/other/agent/skills # 其他兼容 Agent Skills 的工具
```

`--dry-run` 只打印操作；已安装时需要 `--overwrite`。装好后新开会话，Claude Code 中可用 `/embedded-engineering` 显式调用，也会根据描述自动触发。Claude Code 用户可在仓库建一个只含 `@AGENTS.md` 的 `CLAUDE.md` 来复用模板。

## 使用示例

```text
用 embedded-engineering 对 firmware/ 做一次架构评审，停在批准门。
给 module/motor 加一个过流保护，按 BARR-C 写，补 Ceedling 测试。
审查这个 Zephyr 传感器驱动补丁，按 Zephyr 规范和 ztest 要求给出清单。
这个 Linux SPI 驱动能不能上游？按 checkpatch 和 coding-assistants 规则检查。
把 module/imu 改成 C++17，目标是 STM32G474（T1），驱动用模板注入总线，补 CppUTest 测试并给出 Flash 增量。
这个 Cortex-M0+ 项目能不能用 std::atomic 和 virtual？给出依据。
对比 build/base.elf 和 build/app.elf，说明多出来的 Flash 是哪些符号。
```

## 验证状态

| 项 | 结果 |
| --- | --- |
| `python3 tools/validate_skill.py`（技能 13 项 + README 3 项检查） | PASS |
| `python3 -m unittest discover -s tests -v`（105 个用例，含规则库与 `arch_lint`/`cpp_cost`/`detect_profile` 实现的一致性测试；见下行环境变量；未设置时 C++ 工具链相关用例跳过） | PASS |
| C++ 模板：arm-none-eabi-g++ 15.3，C++17/C++20 × Cortex-M0+/M4/M7，严格告警组 `-Werror`（18 次编译） | PASS |
| C++ 负向编译：波特率超差、不合规总线（Concept/`static_assert`）、ARMv6-M 上的无锁环形缓冲、DMA 缓冲未按 cache 行对齐 | PASS（均按预期编译失败） |
| C++ 模板 clang-format（`assets/cpp/.clang-format`）与 clang-tidy（`assets/cpp/.clang-tidy`，含头文件） | PASS |
| C++ 模板 `arch_lint.py` 分层检查 | PASS |
| CppUTest v4.0 测试模板：host 构建（`-Werror` + ASan/UBSan），`-r2 -s` 运行 5 个用例（编译期 Fake + CppUMock） | PASS |
| `cpp_cost.py`：对实测 ELF 检出异常、RTTI、堆、atexit、guard、throw 辅助、printf；预算与 diff | PASS |
| `scripts/bench/run.sh` 在 Cortex-M4F 与 M0+ 上复现开销表 | PASS |
| `linker_discard.ld`（INSERT 形式）链接后移除 `.fini/.fini_array` | PASS |
| 模板 `clang-format --dry-run --Werror`（BARR-C 配置，clang-format 23） | PASS |
| 模板 `clang-tidy`（BARR-C 配置，含头文件） | PASS |
| 模板 gcc 16 / clang 编译，使用 BARR-C 全部告警门禁并加 `-Werror` | PASS |
| `test_ledctl.c` 链接真实 Unity，开启 ASan/UBSan 运行（5 个用例） | PASS |
| `install.sh`：项目安装、拒绝重复安装、`--overwrite`、`--dry-run` | PASS |
| `scripts/barrc/check.sh` 整体执行 | NOT_RUN：本环境自动审批不允许执行下载的脚本；其中的 clang-format/clang-tidy/词法检查已分别手动执行 |
| `ceedling test:all` 使用 `assets/ceedling/project.yml` | NOT_RUN：本机没有 Ruby/Ceedling；YAML 键已对照 Ceedling 1.x 文档核对 |
| Zephyr（`west twister`、`check_compliance.py`）、Linux（checkpatch、KUnit） | NOT_RUN：只是文档规则，本仓库没有对应源码树 |
| C++ 在目标板上的执行时间、栈水位、ISR 时延 | NOT_RUN：没有目标板；方法见 `references/verification/cpp-testing.md` §6–§7 |
| 非 GCC 工具链（Clang 裸机、IAR、ARM Compiler 6）上的 C++ 模板与开销 | NOT_RUN：本机无对应工具链/sysroot |

## 维护

- 上游版本与核实日期见 `skills/embedded-engineering/references/sources.md`；BARR-C:2026 发布后替换 `assets/barr-c/` 并更新 `references/c/barr-c.md`。
- 修改技能内任何文件后运行 `python3 tools/validate_skill.py`（`--json` 输出机器可读结果；退出码 0 无 FAIL、1 有 FAIL、2 用法错误）。约定：反引号中相对技能根的路径不加 `./`；`./` 开头的视为外部源码树路径（如 `./scripts/checkpatch.pl`），不检查；不带 `./` 的外部路径登记到 `tools/validate_skill.json` 的 `external_paths`。引用其他文件的章节时写成 `.md` 链接或路径加 `§N`。
- 新增或修改规则：编辑 `skills/embedded-engineering/standards/rules.yaml`（ID 永不复用；`verify.method: auto` 必须给出已声明的工具；跨 profile 冲突在双方的 `conflicts` 中登记），再运行 `validate_skill.py`。工具新增检查项时同步更新 `verify_tools.<tool>.checks`，`tests/test_scripts.py` 的一致性测试会比对脚本实现。
- 修改脚本后运行 `python3 -m unittest discover -s tests -v`。完整运行 C++ 用例需要：
  - `arm-none-eabi-g++`（用于 cpp_cost 与模板矩阵）
  - `ETL_INCLUDE=<etl>/include`
  - `CPPUTEST_PREFIX=<CppUTest 安装前缀>`，用于构建 CppUTest 模板；构建方法见 `references/verification/cpp-testing.md` §2
- 修改 C++ 模板后运行 `ETL_INCLUDE=<etl>/include tests/cpp/run_cpp_checks.sh`。
- 更换工具链或编译选项后运行 `skills/embedded-engineering/scripts/bench/run.sh`，并更新 `references/cpp/features.md` §4。
- 修改模板后运行 `clang-format --style=file:skills/embedded-engineering/assets/barr-c/.clang-format --dry-run --Werror skills/embedded-engineering/assets/templates/*/*.[ch]`。
