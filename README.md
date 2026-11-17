# embedded-engineering：嵌入式 C/C++ 开发 Agent 技能

当前版本：**v0.1**（`skills/embedded-engineering/SKILL.md` 的 `metadata.version`）。

把以下来源合成为**一个**可安装的 Agent Skill（agentskills.io 格式，Claude Code / Codex / Grok Build / Hermes 等通用），外加一份放进固件仓库、每次会话都会加载的 `AGENTS.md` 模板：

| 层 | 来源 | 在技能中的位置 |
| --- | --- | --- |
| Agent 工作流 | brunofbloq/embedded-agent-skills | `references/workflows/workflow.md`（Architect → Developer → QA、两阶段架构门、证据级别） |
| MCU 架构规则 | rovinax/embedded-skills（已修订） | `references/architecture/mcu-architecture.md`、`references/rtos/mcu-isr-rtos.md`、`scripts/arch_lint.py` |
| C 代码规范 | BARR-C:2018 + Barr Group 官方 enforcement kit | `references/c/barr-c.md`、`assets/barr-c/`、`scripts/barrc/check.sh` |
| MCU 测试 | Ceedling 1.x（Unity + CMock） | `references/verification/ceedling.md`、`assets/ceedling/project.yml`、`assets/templates/tests/` |
| 平台官方规范 | Zephyr、Linux kernel 树内文档、ESP-IDF v6.1 Programming Guide | `references/platforms/zephyr.md`、`references/platforms/esp-idf.md`、`references/platforms/linux-kernel.md`、`references/platforms/linux-userspace.md` |
| Modern Embedded C++ | Pigweed、modm、ETL、C++ Core Guidelines、Zephyr C++ 文档 + 本地实测开销 | `references/cpp/coding.md`、`references/cpp/features.md`、`references/cpp/patterns.md`、`assets/cpp/`、`scripts/cpp_cost.py`、`scripts/bench/` |
| C++ 测试 | CppUTest + CppUMock | `references/verification/cpp-testing.md`、`assets/cpp/templates/tests/` |

## 为什么是“Skill + AGENTS.md + 脚本”

- **Skill**：按需加载。`SKILL.md` 当前 128 行（预算 150 行，包含 profile 选择、角色、reference 路由表），十几页的规则只在相关任务时读取，不占每次会话的上下文。
- **AGENTS.md（项目内）**：保存这个仓库特有、必须每次都知道的事实，如芯片型号、SDK 版本、构建/测试命令、硬件授权范围。这些信息不应该写进通用技能。
- **脚本与配置**：可以机械检查的规则（格式、命名、分层依赖）交给工具判定，而不是靠模型“记得遵守”。BARR-C 部分直接使用 Barr Group 官方 kit。

这几个来源之间互相冲突，例如 BARR-C 要求 Allman 花括号、4 空格缩进和 `g_` 前缀，Linux 要求 tab、K&R 风格且禁止类型前缀，Zephyr 禁止 `//` 注释。技能先判定 **profile**（`mcu-baremetal`、`mcu-rtos`、`zephyr`、`esp-idf`、`linux-kernel`、`linux-userspace`），再按 `references/profiles.md` 的冲突裁决矩阵决定用哪套规则。BARR-C 拆成“安全核心”（全 profile 适用）和“格式/命名层”（仅 MCU）。

C++ 部分不简单禁止现代特性，而是按资源等级（T0 极小 MCU … T3 Linux 用户态）和实时路径取舍，取舍依据是在 Cortex-M0+/M4 上实测的 Flash/RAM 增量。

- **几乎免费**：模板、Concepts、CRTP、RAII、`constexpr`、`std::optional/variant/span`，增量都在 0–70 B。
- **代价大**：异常 +9.9 KB；`std::function`、默认分配器的 `std::vector` 各约 +1 KB 并引入堆；iostream 在 newlib-nano 下无法链接。
- **隐性陷阱**：
  - 公有虚析构会拉入 `malloc`。
  - Cortex-M0+ 上 32 位 `std::atomic::fetch_add` 链接失败。
  - C++20 弃用 `volatile` 的 `++`。

已确定的方案：

- 语言标准：C++17 基线，C++20 可选。
- 格式默认方案 A：自有 MCU C++ 沿用 BARR-C 布局，列宽 100；命名空间代替模块前缀，不用 `p_`/`b_` 类型前缀。既有项目/平台配置优先。可另行显式选择 [readable-cpp](skills/embedded-engineering/references/cpp/readable-cpp.md)，其函数花括号换行、控制花括号同行、方法和局部变量 lowerCamelCase，不改变 profile 或资源等级。
- 默认工具库：ETL。
- C++ 单元测试：CppUTest。

## 目录

```text
skills/embedded-engineering/    # 唯一可安装单元（install.sh 复制此目录）
├── SKILL.md                    # 入口：护栏、profile、角色、路由
├── standards/rules.yaml        # 135 条带 ID 的规则：适用 profile、等级、验证方法与覆盖范围、出处章节、冲突
├── profiles/*.yaml            # 每个 profile 的规范、测试基线、门禁命令（与 rules.yaml 声明一一对应）
├── references/                 # 按需读取的规则
│   ├── profiles.md             #   profile 判定与冲突裁决
│   ├── sources.md              #   来源、版本、许可
│   ├── workflows/              #   角色与阶段门 + W01–W10 十个工作流（输入/步骤/检查点/通过标准/审批）
│   ├── architecture/           #   MCU 分层、接口/驱动设计、状态机/协议/故障、启动与升级
│   ├── c/                      #   BARR-C 规则
│   ├── cpp/                    #   C++ 编码、特性取舍（T0–T3）、模式
│   ├── rtos/                   #   ISR、RTOS、DMA、看门狗、ThreadX
│   ├── platforms/              #   Zephyr、ESP-IDF v6.x、Linux kernel、Linux userspace、RISC-V
│   └── verification/           #   Ceedling、CppUTest、审查清单、调试与故障分析
├── scripts/
│   ├── detect_profile.py       # profile 识别（只读，JSON）
│   ├── arch_lint.py            # 分层依赖/HAL/寄存器访问检查（C 与 C++）
│   ├── cpp_cost.py             # ELF 门禁：按等级禁止的运行时符号、段预算、A/B 增量
│   ├── bench/                  # C++ 特性开销微基准（在你的工具链上复现）
│   ├── style_gate.py           # 显式 C/C++ 范围、布局/命名、默认 Doxygen 块存在性
│   └── barrc/check.sh          # Barr Group 官方 BARR-C:2018 门禁封装
├── assets/
│   ├── AGENTS.md.template      # 固件仓库的常驻规则模板
│   ├── arch_layers.json        # arch_lint 默认层规则
│   ├── barr-c/                 # .clang-format / .clang-tidy / .editorconfig / 编译告警
│   ├── ceedling/project.yml    # Ceedling 1.x 模板
│   ├── templates/              # 符合 BARR-C 的 C interface/module/test 示例
│   ├── ci/                     # GitHub Actions / GitLab CI 模板（构建、静态检查、host 测试）
│   └── cpp/                    # C++：.clang-format/.clang-tidy、编译选项、linker_discard.ld、
│       ├── readable-cpp/       #   显式可选配置与正反例；abi/ 为 C 调用 C++ 的共享头样例
│       └── templates/          #   驱动/总线/RAII/ISR 队列/DMA/组合根/CppUTest 模板
├── agents/openai.yaml          # Codex 显示元数据
└── THIRD_PARTY_NOTICES.md
tools/validate_skill.py         # Skill 自检：frontmatter、链接/路径/§ 引用、可达性、脚本、数据文件、规则库与 profile、规模计数声明、打包卫生
tools/validate_skill.json       # 每个技能的自检配置（SKILL.md 行数预算、外部源码树路径白名单）
tests/test_scripts.py           # arch_lint、detect_profile 回归测试
tests/test_validate_skill.py    # validate_skill 变异测试（逐项注入缺陷，含 rules/profiles）与 YAML 解析测试
tests/test_readable_cpp.py      # G474 混编 / RK3588 SocketCAN+epoll 临时主机工程与失败诊断
tests/test_heap_guard.py        # C++17/20 分配入口运行边界和 ARM 导出符号检查
tests/test_cpp.py               # cpp_cost、C++ 模板矩阵、CppUTest 模板
tests/test_run_evals.py         # run_evals 判定语义（变体结论与检查状态）与定义校验
tests/cpp/                      # C++ 模板编译与负向编译检查
install.sh                      # 安装器
tools/run_evals.py              # 运行验证工程并对照预期：--report 生成 evals/RESULTS.md
tools/install_eval_tools.sh     # 验证工程所需的用户级工具（west、Zephyr、FreeRTOS、ETL、CppUTest、Renode）
evals/projects/<name>/          # 验证工程包含三类内容：good/ 已知良好样例、variants/ 故意引入问题的变体、eval.yaml 预期
evals/RESULTS.md                # run_evals 生成的结果（不要手改）
evals/TRIAGE.md                 # 首次运行时预期与结果不一致的分诊记录
evals/agent/                    # Agent 行为评测：cases.yaml 用例、RESULTS*.md 结果（runs/ 原始记录不入库）
tools/run_agent_evals.py        # 在沙箱仓库中运行 Claude Code / Codex 并判定
docs/design.md                  # 设计、实施与测试策略
docs/validation-report.md       # 验证报告（汇总各层实际运行结果）
research/                       # 来源矩阵与规范冲突分析
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

仅在现有的自有 C++ 目录显式安装风格；不会替换该目录及项目根内祖先的已有配置，`--overwrite` 也不覆盖它们：

```sh
./install.sh --agent codex --scope project --project-dir ~/work/fw \
  --cpp-style readable-cpp --cpp-dir app_cpp
# 保持原 C++ 方案时使用 --cpp-style default-cpp
```

按 [清单示例](skills/embedded-engineering/references/cpp/readable-cpp.md) 创建 `style-gate.json`，然后用 `python3 skills/embedded-engineering/scripts/style_gate.py --root /path/to/project --manifest /path/to/project/style-gate.json` 执行。GitHub/GitLab 模板使用同一门禁，要求真实 `compile_commands.json`、显式文件范围和校验工具主版本；空范围不扩大到全仓。`.h` 由契约和清单分类，C API 仍按平台 C 规则。Zephyr/ESP-IDF 保留平台门禁，Linux 不继承 MCU 运行时/链接约束。

[可选应用结构参考](skills/embedded-engineering/references/architecture/ui-application.md) 用原创背光例子说明页面、业务服务与硬件适配。默认规则要求所有新增自有 C/C++ 函数/方法有 Doxygen（声明或定义择一；类注释不能替代；默认英文，项目可指定语言）；工具只检查块是否存在，英文和语义由人评审。遗留/第三方/生成代码不选入门禁；显式关闭须记录原因。

可直接构建的 readable-cpp 分层示例见 [examples/g474-backlight](examples/g474-backlight/)：C ABI 入口、页面、业务服务、端口和假适配器分层，附主机测试与 `style-gate.json`；目标板运行仍为 `NOT_RUN`。

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

最新增量验证为 **2026-11-17**，对象为 `5cae6d9b5fdbec57222016c80de2701db020bbc9` 上的本轮工作树：结构 32 项 PASS；完整 Python 回归 268 passed、178 subtests passed、无跳过；三项工程 27 个变体为 25 MATCH、2 KNOWN_GAP、0 MISMATCH/NOT_RUN；真实临时写入 Agent、G474 混编主机运行和 Cortex-M4 ABI 编译链接、RK3588 风格 Linux 主机工程、可构建的 readable-cpp 分层示例均通过。逐函数 Doxygen 已改为默认规则，`test_doxygen_defaults_to_enabled` 同时验证 C/C++ 缺失诊断和显式关闭；完整命令、版本、预期失败诊断和未执行项见 [本轮独立报告](docs/evidence/readable-cpp-2026-11-17.md)。目标 MCU/RK3588 板上运行和 GitHub/GitLab 托管 CI 为 NOT_RUN。

下表保留 **2026-11-06 及更早的历史记录**；这些历史 PASS 不代表本轮重跑，不能与新增证据混用。

| 项 | 结果 |
| --- | --- |
| `python3 tools/validate_skill.py`（技能 14 项 + README、docs/、research/ 的 6 份文档各 3 项检查，共 32 项） | PASS |
| `uv run -q --with pytest --with pyyaml python -B -m pytest -q tests`（2026-11-06 本轮；设置下文的 `ETL_INCLUDE`/`CPPUTEST_PREFIX` 可运行完整模板检查） | 248 passed、2 skipped（缺少上述两个环境变量）；历史 221 用例验收见 `docs/validation-report.md` §1 |
| `python3 tools/run_evals.py --strict`：6 个验证工程、50 个变体（6 个良好样例 + 44 个故意引入问题的变体），结果见 `evals/RESULTS.md` | 检出 37 + 已知漏报 7，另 6 个良好样例通过；43 MATCH、7 KNOWN_GAP、0 MISMATCH、0 NOT_RUN（known_gap 变体不计规则覆盖） |
| C++ 模板：arm-none-eabi-g++ 15.3，C++17/C++20 × Cortex-M0+/M4/M7，严格告警组 `-Werror`（18 次编译） | PASS |
| C++ 负向编译：波特率超差、不合规总线（Concept/`static_assert`）、ARMv6-M 上的无锁环形缓冲、DMA 缓冲未按 cache 行对齐 | PASS（均按预期编译失败） |
| C++ 模板 clang-format（`assets/cpp/.clang-format`）与 clang-tidy（`assets/cpp/.clang-tidy`，含头文件） | PASS |
| C++ 模板 `arch_lint.py` 分层检查 | PASS |
| CppUTest v4.0 测试模板：host 构建（`-Werror` + ASan/UBSan），`-r2 -s` 运行 5 个用例（编译期 Fake + CppUMock） | PASS |
| `cpp_cost.py`：对实测 ELF 检出异常、RTTI、堆、atexit、guard、throw 辅助、printf；预算与 diff | PASS |
| `scripts/bench/run.sh` 在 Cortex-M4F 与 M0+ 上复现开销表 | PASS |
| `linker_discard.ld`（INSERT 形式）链接后移除 `.fini/.fini_array` | PASS |
| 模板 `clang-format --dry-run --Werror`（BARR-C 配置，clang-format 23） | PASS |
| 模板 `clang-tidy`（BARR-C 配置，含头文件） | PASS。注意：2026-11-05 的验证工程发现 `hicpp-signed-bitwise` 在 clang-tidy 23 上被静默忽略，此前这一行的 PASS 并不包含 BARR-C 5.3.b；配置已补 `bugprone-signed-bitwise`，并有回归测试 |
| 模板 gcc 16 / clang 编译，使用 BARR-C 全部告警门禁并加 `-Werror` | PASS |
| `test_ledctl.c` 链接真实 Unity，开启 ASan/UBSan 运行（5 个用例） | PASS |
| `install.sh`：项目安装、拒绝重复安装、`--overwrite`、`--dry-run` | PASS |
| `assets/ci/*.yml` CI 模板 | 仅做 YAML 解析检查（`data-yaml` PASS）；NOT_RUN：未在 GitHub/GitLab 上实际运行，本机没有 actionlint |
| P3 新增参考的事实核对 | Cortex-M fault 寄存器地址与位号已对照 CMSIS 头文件核实；RISC-V、ThreadX、MCUboot 内容 NOT_RUN（未对照原文，见 `references/sources.md`） |
| `scripts/barrc/check.sh` 整体执行 | PASS：在 `mcu-baremetal-c` 的 8 个变体上执行，检出符号位运算、缺花括号、隐式声明与命名违规 |
| `ceedling test:all`（Ceedling 1.2.2） | PASS：`mcu-baremetal-c` 与 `linux-userspace`（CMock + ASan/UBSan）。首次运行发现模板默认的 driver 与 tests/support 目录不存在时 Ceedling 报配置错误，已在模板与文档注明 |
| FreeRTOS V11.3.3 POSIX 移植上的 host 集成测试 | PASS：`freertos-cpp` 的 `rtos_host`，可检出死锁（看门狗任务超时） |
| Zephyr v4.5.0：Twister（`native_sim/native/64`，无需 SDK）、树内 checkpatch 与 `.clang-format` | PASS：`zephyr-app` 的 6 个变体 |
| Linux 内核：树外模块构建（运行内核头文件包）、checkpatch、dtschema binding（`linux-kernel-module`） | PASS：10 个变体；KUnit、`make dt_binding_check`、`make C=1`（sparse）NOT_RUN：本机没有内核源码树，sparse 未安装 |
| Zephyr `check_compliance.py` 整体 | NOT_RUN：需要 Zephyr 树内的提交区间（已执行其中的 checkpatch 与 clang-format） |
| QEMU 目标冒烟（`mcu-baremetal-c` 的 `make qemu`，mps2-an386） | PASS：链接并在 QEMU 中运行，可检出向量表入口名错误与行为缺陷（`bad-isr-name`、`bad-toggle-late`） |
| Renode 1.17 仿真 | NOT_RUN：工具已安装，尚无基于它的验证用例 |
| Agent 当前定义 28 个用例；下列为历史批次：25 个用例 × 3 次 × Claude Code / Codex（每个 Agent 75 次），评委为 omp + DeepSeek V4.1 Flash（原 Gemini 4 Argon 因区域限制不可用） | 历史结果：Claude 61/75（71%–89%）、Codex 63/75（74%–91%）PASS；失败项逐条复核见 `docs/validation-report.md` §4 |
| C++ 在目标板上的执行时间、栈水位、ISR 时延 | NOT_RUN：没有目标板；方法见 `references/verification/cpp-testing.md` §6–§7 |
| 非 GCC 工具链（Clang 裸机、IAR、ARM Compiler 6）上的 C++ 模板与开销 | NOT_RUN：本机无对应工具链/sysroot |

## 维护

- 上游版本与核实日期见 `skills/embedded-engineering/references/sources.md`；BARR-C:2026 发布后替换 `assets/barr-c/` 并更新 `references/c/barr-c.md`。
- 修改技能内任何文件后运行 `python3 tools/validate_skill.py`（依赖 PyYAML，缺少时可用 `uv run --with pyyaml python3 tools/validate_skill.py`；`--json` 输出机器可读结果；状态为 `PASS`/`FAIL`/`NOT_RUN`/`BLOCKED`，后两者都不是通过；退出码 0 无 FAIL、1 有 FAIL、2 用法或环境错误）。约定：反引号中以 `scripts/`、`assets/`、`references/`、`standards/`、`profiles/`、`agents/` 开头（可带 `./`）的路径都按技能根检查；Zephyr/Linux 源码树中的同名路径（如 `./scripts/checkpatch.pl`）登记到 `tools/validate_skill.json` 的 `external_paths`。引用其他文件的章节写成 `.md` 链接或路径加 `§N`（允许“的”等连接词）；`§N` 前紧挨着非 `.md` 的英文词会报歧义。YAML 1.1/1.2 读法不同的标量（`yes`、`012`、日期等）必须加引号。
- 新增或修改规则：编辑 `skills/embedded-engineering/standards/rules.yaml`（ID 永不复用；`verify.method: auto` 必须给出已声明的工具与 `coverage: full | partial`，`partial` 必须写明 `gap`；跨 profile 冲突在双方的 `conflicts` 中登记），再运行 `validate_skill.py`。工具新增检查项时同步更新 `verify_tools.<tool>.checks`，`tests/test_scripts.py` 的一致性测试会比对脚本实现。
- 修改脚本后运行 `python3 -m unittest discover -s tests -v`。完整运行 C++ 用例需要：
  - `arm-none-eabi-g++`（用于 cpp_cost 与模板矩阵）
  - `ETL_INCLUDE=<etl>/include`
  - `CPPUTEST_PREFIX=<CppUTest 安装前缀>`，用于构建 CppUTest 模板；构建方法见 `references/verification/cpp-testing.md` §2
- 修改 C++ 模板后运行 `ETL_INCLUDE=<etl>/include tests/cpp/run_cpp_checks.sh`。
- 更换工具链或编译选项后运行 `skills/embedded-engineering/scripts/bench/run.sh`，并更新 `references/cpp/features.md` §4。
- 修改模板后运行 `clang-format --style=file:skills/embedded-engineering/assets/barr-c/.clang-format --dry-run --Werror skills/embedded-engineering/assets/templates/*/*.[ch]`。
