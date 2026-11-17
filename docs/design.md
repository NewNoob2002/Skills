# embedded-engineering 技能：设计、实施与测试策略

本文件合并原任务要求中的架构设计、实施计划与测试策略三份文档。验证结果见 [validation-report.md](validation-report.md)，来源评估与规范冲突见 [../research/source-matrix.md](../research/source-matrix.md)、[../research/conflict-analysis.md](../research/conflict-analysis.md)。

## 1. 目标与范围

交付一套能被 Agent 实际调用、带有自动检查、并经验证案例检验的嵌入式工程技能，覆盖 MCU 裸机、RTOS（FreeRTOS、ThreadX、CMSIS-RTOS2）、Zephyr、嵌入式 Linux 内核与用户态，语言为 C 与 C++17/20。

不在范围内：替代 MISRA 商业检查工具；直接操作硬件（flash、HIL 只给方法与模板，执行需用户授权）；Linux 内核树与 Zephyr 合规检查的完整执行（需要相应源码树与提交区间）。

## 2. 交付物结构

```text
skills/embedded-engineering/      唯一的安装单元（install.sh 原样复制）
  SKILL.md                        护栏、profile 判定、工作流路由、reference 路由、机械门禁、输出约定（< 150 行）
  standards/rules.yaml            135 条带 ID 的规则：profile、等级、验证方法与覆盖范围、出处章节、冲突
  profiles/<id>.yaml              6 个 profile 的规范、测试基线、门禁命令
  references/                     按领域分目录，按需加载（workflows、architecture、c、cpp、rtos、platforms、verification）
  scripts/                        detect_profile、arch_lint、cpp_cost、BARR-C 门禁、开销基准
  assets/                         BARR-C 与 C++ 的格式/静态分析配置、Ceedling 模板、代码模板、CI 模板
tools/                            仓库级开发工具（不随技能安装）：validate_skill、run_evals、run_agent_evals、安装脚本
evals/projects/                   六个验证工程（good + 故意引入问题的变体 + 预期）
evals/agent/                      Agent 行为评测用例
tests/                            上述脚本与工具的回归测试
```

## 3. 关键决策与取舍

| # | 决策 | 理由 | 代价与风险 |
| --- | --- | --- | --- |
| 1 | **一个技能、内部分模块**，而不是任务书建议的 7 个独立技能 | 7 个技能的描述高度重叠，Agent 靠描述选择技能时容易选错；技能之间不能确定性地互相调用；护栏与 profile 判定会被复制多份 | 单个技能的描述需要覆盖所有触发词；P5 发现 Claude Code 在知识型问题上不调用技能（见验证报告） |
| 2 | **渐进加载**：SKILL.md 只放路由，规则细节在 references，按任务读取 | 符合 Agent Skills 规范的上下文预算建议；Codex 实测按路由表只读取需要的 reference | reference 之间的交叉引用需要机械检查（`validate_skill.py` 的 links、sections） |
| 3 | **rules.yaml 只收录可检查、有冲突或需按 ID 引用的规则**，不复制全部标准 | 全量结构化会与 references 漂移且无人消费 | 规则正文仍在 references；靠 `ref` 字段与“文档引用的 Rule ID 必须存在”检查保持一致 |
| 4 | **自动验证要声明覆盖范围**（`coverage: full / partial` + `gap`） | 第二轮审查发现多条 `auto` 规则被工具部分覆盖却声称完整；验证工程进一步证实 3 条 `full` 声明不成立 | `full` 现仅 2 条（C-005、CFMT-002 因头文件缺口降为 partial）；其余 45 条靠 review 补足，需人工判断 |
| 5 | **按 profile 裁决冲突**，冲突双向登记 | 各生态规则本质冲突（格式、命名、错误码），无法统一 | 混合仓库需要按目录判定 profile |
| 6 | **现代 C++ 按资源等级 T0–T3 取舍**，以链接产物为证据 | 不一刀切禁止；实测开销决定取舍；`cpp_cost.py` 在 ELF 上检出禁止的运行时 | 符号检查是间接证据：区分不了 ISR 内外的分配，`std::function` 只经 throw 辅助被检出 |
| 7 | **校验器依赖 PyYAML**（放弃自写 YAML 子集解析器） | 两轮审查中子集解析器贡献了 10 余条缺陷；校验器是仓库工具，不随技能安装 | 没有 PyYAML 时退出码 2，并提示 `uv run --with pyyaml` |
| 8 | **验证工程用“good + 变体叠加”**，预期在运行前写定 | 变体只放差异文件，便于审查；首次运行的不一致先分诊再修改，记录在 `evals/TRIAGE.md` | 预期与样例由同一作者编写，独立性不足（见 §6） |
| 9 | **Agent 行为评测用不同厂商的评委模型** | 避免被测模型给自己打分 | 评委本身也有误判可能；单次运行，存在随机性 |
| 10 | **修复工作可委派给其他模型，但由协调者验收** | 第二轮修复由 Gemini 4 Argon 完成；协调者把新测试放到修复前的代码上运行以确认测试强度，并纠正了 3 条不成立的 `full` 声明 | 委派需要写清楚的任务书与验收方法 |

## 4. 工作流与角色分离

十个工作流（W01–W10）各有一页，固定结构为：概要（触发、输入、前置条件、角色、产物、人工审批）→ 步骤 → 检查点 → 通过与失败。目录与角色分离规则在 `references/workflows/workflow.md` §7：

- 架构结论由 Architect 给出并经用户批准（`GEN-005`）。
- 验收测试由 QA 在实现之前或独立于实现编写，期望值来自规格（`GEN-006`）。
- 实现与验收不能是同一角色步骤：要么由另一个 Agent、会话或人员验收，要么验收测试在实现之前提交；两者都不满足时验收结论为 `BLOCKED`。
- 最终验收（W10）由人签字。

本项目自身也按这一规则执行：审查由 omp + GPT-6.1-Sol（Codex）在独立 worktree 中完成；第二轮修复由 Gemini 4 Argon 在独立分支完成，再由协调者验收。

## 5. 测试策略

| 层 | 工具 | 证明什么 | 不能证明什么 |
| --- | --- | --- | --- |
| 技能结构 | `tools/validate_skill.py`（技能 14 项 + 文档 3 项） | frontmatter 合规、引用与章节存在、可达性、规则库与 profile 的结构和一致性、SKILL.md/README/design.md 中 profile、规则、验证工程与变体数和实际一致、打包卫生 | 内容在语义上正确 |
| 脚本与工具 | `tests/`（unittest，变异测试为主） | 每个检查能检出对应缺陷；工具声明与实现一致（arch_lint、cpp_cost、detect_profile、clang-tidy 检查名） | 在真实工程上的检出率 |
| 验证工程 | `tools/run_evals.py` | 在六个真实工程上，良好样例通过；问题变体按预期检出或单列 KNOWN_GAP；失败可用 expect_output 匹配完整日志中的诊断 | 未建模的错误类型；目标板上的时序与电气行为 |
| Agent 行为 | `tools/run_agent_evals.py` | 技能是否被调用；护栏是否守住；技术决策是否符合规则 | 通过率的稳定性（已做 3 次重复并给 Wilson 区间）；未覆盖的提问方式 |
| 硬件 | 方法与模板（`verification/cpp-testing.md` §6–§7、`verification/debugging.md`） | — | 本项目没有目标板，全部为 NOT_RUN |

状态语义在所有层一致：PASS / FAIL / NOT_RUN（前提不存在或工具缺失）/ BLOCKED（依赖的检查失败或工具报告配置错误）。NOT_RUN 与 BLOCKED 都不是通过。验证工程的变体结论另含 KNOWN_GAP：有 known_gap 且无预期 FAIL、检查均符合预期时单列；--strict 不视为失败，规则覆盖排除所有 known_gap 变体。

## 6. 风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 工具链升级使第三方配置静默失效 | 规则看似被检查，实际没有（已发生：`hicpp-signed-bitwise`） | `ClangTidyConfigTest`；验证工程在升级后重跑 |
| 验证工程的预期与样例由同一作者编写 | 预期可能迁就工具行为 | 首次运行的每处不一致都分诊并记录；已由独立模型复核 `eval.yaml`（`docs/independent-review.md`） |
| 未对照原文的参考（RISC-V、ThreadX、MCUboot） | Agent 可能引用不准确的细节 | `sources.md` 标明核实状态；规则 `GEN-002` 要求具体芯片以手册为准 |
| Agent 不调用技能 | 护栏与项目规则在知识型问答中不生效 | 见验证报告的 P5 结果与改进建议 |
| 只有 21 条 auto 规则被验证工程检验（共 47 条） | 其余 auto 规则的检出能力未经实测 | 规则覆盖统计写入 `evals/RESULTS.md`；后续逐步补变体 |

## 7. 验收标准与完成状态

| 标准 | 状态 |
| --- | --- |
| `validate_skill.py` 0 FAIL | 达成 |
| `unittest` 全部通过（设置 `ETL_INCLUDE`、`CPPUTEST_PREFIX` 时无跳过） | 达成 |
| 六个验证工程：良好样例全部 PASS，问题变体检出与已知漏报分列 | 检出 37 + 已知漏报 7，另 6 个良好样例通过（43 MATCH + 7 KNOWN_GAP；本轮结果见 evals/RESULTS.md） |
| 所有 `coverage: full` 的规则至少被一个变体检验 | 达成（2/2） |
| Agent 行为评测有真实的运行记录 | 见验证报告 |
| 未执行的验证标记为 NOT_RUN 并说明原因 | 达成（README 验证状态表、验证报告） |
