# Agent 工作流：Architect → Developer → QA

工作流结构参考 brunofbloq/embedded-agent-skills（architect / developer / qa 三角色、两阶段架构门、按证据级别报告）。本文为独立改写，不含该仓库原文。

## 1. 评审深度选择

| 深度 | 触发条件 | 要求 |
| --- | --- | --- |
| **Full** | 新产品/子系统；OS 或计算平台选型；跨核、跨处理器、跨进程接口；资源预算或安全边界改变；用户明确要求架构评审 | Phase 1 全流程 + 明确批准 → Phase 2 逐模块 |
| **Delta** | 既有架构内的有界变化：新增接口、改并发模型、改生命周期、改内存布局 | 只评估受影响边界、权衡、回归范围；需要时请求批准 |
| **Fast path** | 孤立缺陷、无架构影响的小改动 | 声明“无需架构门”，直接进入 Developer 流程 |

不要从沉默或泛泛的“去实现吧”推断架构已批准。同一架构修订版本此前的明确批准可以沿用。

## 2. Phase 1：架构评审与决策（Architect）

1. **上下文**：芯片/板卡精确型号与修订版、已核实的外设能力、OS/SDK 版本、现有模块、工作状态、外部接口、硬性验收标准、CPU/RAM/Flash 余量、时限与抖动、功耗、可靠性、成本。分别标注 **事实 / 假设 / 实测**。
2. **拓扑与备选**：画出软硬件职责、数据流与控制流、存储/启动/升级、错误隔离、复位与恢复、ISR/任务/进程边界。只比较真正可行的方案（裸机、RTOS、Zephyr、Linux、异构）。不要默认需要 Linux、RPMsg、第二个核或容器。
3. **接口优先**：先定义模块职责、输入输出与失败语义、消息/API 结构、时序期望、并发与兼容边界，再谈文件。
4. **评估矩阵**：对每个方案按以下维度给出 `Good / Trade-off / Problem / Unknown` 与一句理由：硬件效率、复杂度、可维护性、实时性、健壮性；相关时加功耗、成本、安全、可升级性。没测过的就是 `Unknown`，不编造 benchmark。
5. **决策门**：结论为 `Proceed / Revise / Reject`，列出阻塞项、按依赖排序的模块列表、每个模块需要的验证证据。**Full 评审必须在此停下请求批准。**

### 评估矩阵模板

```markdown
| 维度 | 方案 A: FreeRTOS on STM32G4 | 方案 B: Zephyr on nRF5340 |
| --- | --- | --- |
| 硬件效率 | Good: ... | Trade-off: ... |
| 复杂度 | ... | ... |
| 可维护性 | ... | ... |
| 实时性 | Unknown: 未测 ISR 延迟 | ... |
| 健壮性 | ... | ... |
| 结论 | Proceed / Revise / Reject + 理由 |
```

## 3. Phase 2：逐模块实现（批准后）

按依赖从低到高排序。每个模块：

```text
公共契约/接口 → 实现（Developer）→ 构建/单元/集成证据（QA）→ checkpoint → 下一模块
```

每个 checkpoint 报告：改动文件、公共 API、依赖、实际执行的测试、已知限制、与批准方案的偏离。默认在 checkpoint 请求继续许可；用户明确授权“有界自动批次”时可以连续推进，但不得跳过验证证据，也不得绕过新发现的架构变化——范围或设计实质变化时回到 Phase 1。

## 4. Developer 流程

1. **选择性检查**：受影响文件、项目规则、目标 MCU/板卡修订版、工具链与构建、启动/链接/分区文件、SDK/RTOS 版本、现有测试。
2. **按改动规模匹配**：小缺陷 → 最小补丁 + 聚焦测试；新驱动/子系统 → 先写一页契约（所有权、接口、错误、时延）。
3. **核实硬件假设**：改寄存器、引脚复用、时钟、DMA、NVIC、cache、启动、Flash、低功耗前，先查确切的数据手册/参考手册/errata、原理图与 SDK 头文件。
4. **窄范围实现**：遵循 profile 规范与生成代码边界；不做无关重构；在有用的可移植/可测边界做封装，不为每个 GPIO 加冗余层。
5. **审计故障路径**：等待外设必须有界，且超时所用时钟在该启动/休眠阶段有效；tick 回绕；缓冲区边界；队列溢出；初始化顺序；取消；复位与掉电；安全态。
6. **验证**：host 测试、目标机构建、格式与静态检查、size/map/栈分析（适用时）。
7. **报告**：见 SKILL.md §5。

## 5. QA 流程

1. **检查**：实际固件目标、板卡/硅片修订版、工具链、现有测试基础设施、需求、构建产物、可用的 host/仿真器/调试器。复用现有测试与工具，不随意引入新框架。
2. **独立的 oracle**：把需求转成可观测的正向、负向、边界、故障、恢复断言；期望值来自规格与测试向量，不复制实现的输出。
3. **选择最低成本且可信的后端**：

| 后端 | 适合证明 | 不能证明 |
| --- | --- | --- |
| Host 单元测试（Ceedling / CppUTest / ztest unit / KUnit） | 状态机、协议解析、算法、驱动对总线接口的调用序列 | 时序、中断抢占、DMA/cache、电气 |
| 静态分析（clang-tidy、编译告警、checkpatch、sparse） | 规则符合性、部分缺陷类别 | 运行期行为 |
| 仿真（Renode、QEMU、`native_sim`） | 模型覆盖的 CPU/外设行为、集成流程 | 未建模外设；模型缺失时记 `BLOCKED_BY_MODEL` |
| HIL / 实板 | 真实时序、复位、功耗、外设交互 | 未覆盖的环境条件 |

4. **构建与运行**：记录固件版本/commit、模型版本、脚本、激励、退出码、有界超时。先跑定向测试再跑回归。隔离共享资源（调试器、串口、电源），不得并发占用。未经授权不 flash。
5. **按证据级别报告**：每一级单独给 `PASS / FAIL / NOT_RUN / INCOMPLETE / BLOCKED`；模型覆盖缺口与测试覆盖缺口分开记录。

## 6. 任务契约与交接

拆分任务时，每个任务写清：

```yaml
task: <名称>
observable_outcome: <可观测的验收结果>
frozen_inputs: [<commit/文件/规格版本>]
owner: <实现方>
outputs: [<文件、构建产物、报告位置>]
affected_checks: [<需要运行的检查，每项一个执行者>]
stop_conditions: [<遇到即停并报告的情况>]
hardware_gap: <没有硬件时哪些证据缺失>
```

- 注册表/构建接线或 `NOT_RUN` 桩不能证明功能可用。
- 有界修正失败后：保存已完成/剩余清单并报告阻塞，不要静默开始同样的重试。
- 缺硬件是显式的“台架缺口”，不是无限循环做软件评审的理由。

## 7. 工作流目录与角色分离

| # | 工作流 | 文件 | 主导角色 | 独立验证者 |
| --- | --- | --- | --- | --- |
| W01 | 新工程架构设计 | [new-architecture.md](new-architecture.md) | Architect | QA 定义每个模块的证据；用户批准 |
| W02 | 现有工程架构审查 | [architecture-review.md](architecture-review.md) | Architect | QA 复核机械检查 |
| W03 | 新模块设计与实现 | [module-implementation.md](module-implementation.md) | Developer | QA（测试先于实现冻结） |
| W04 | 驱动与中间件设计 | [driver-design.md](driver-design.md) | Architect → Developer | QA（mock 总线测试 + HIL 计划） |
| W05 | C/C++ 代码审查 | [code-review.md](code-review.md) | Reviewer（QA） | 不是作者本人 |
| W06 | 测试用例生成 | [test-generation.md](test-generation.md) | QA | 变异检查证明用例能失败 |
| W07 | 性能与资源分析 | [performance.md](performance.md) | Developer | QA 复核方法 |
| W08 | 回归测试 | [regression.md](regression.md) | QA | 与基线比较 |
| W09 | 重构规划 | [refactor-planning.md](refactor-planning.md) | Architect | QA 维护行为基线 |
| W10 | 最终工程质量验收 | [acceptance.md](acceptance.md) | QA（独立） | 人工最终签字 |

每页的固定结构：概要（触发、输入、前置条件、角色、产物、人工审批）→ 步骤 → 检查点 → 通过与失败。

**角色分离规则**（任务要求：架构与测试不得仅由代码作者自行验收）：

- 架构结论由 Architect 给出，并经用户批准；Developer 不得为了实现方便而修改已批准的接口，需要修改时回到架构门。
- 验收测试由 QA 在实现之前或独立于实现编写，期望值来自规格（`GEN-006`）。
- 同一个 Agent 会话中，实现与验收必须是不同的角色步骤，并至少满足以下一条：(a) 验收由另一个 Agent、会话或人员执行；(b) 验收所用的测试在实现之前已提交（task contract 的 `frozen_inputs`）。两条都不满足时，验收结论为 `BLOCKED`（缺少独立验证），不能报告为 PASS。
- 最终验收（W10）的签字只能由人完成。
