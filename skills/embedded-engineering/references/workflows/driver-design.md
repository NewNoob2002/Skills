# W04 驱动与中间件设计

适用于器件驱动、总线驱动、协议栈与中间件。驱动对硬件事实的依赖最强，`GEN-002` 是本流程的前提。

## 概要

| 项 | 内容 |
| --- | --- |
| 触发 | 新器件或新总线驱动、协议栈、中间件封装 |
| 输入 | 数据手册、参考手册、errata（写明文档编号与版本）；原理图；SDK 及其版本 |
| 前置条件 | 硬件事实都有来源，或已列出 `UNKNOWN` 清单并向用户提问 |
| 角色 | Architect 确定抽象、接口与所有权；Developer 实现；QA 编写 mock 总线测试和 HIL 计划 |
| 产物 | 寄存器映射头（命名常量，注释写明文档与章节）、驱动接口、初始化序列、错误码映射、host 测试、HIL 测试计划 |
| 人工审批 | 任何上板操作（flash、驱动执行器、改电源）都需要授权（`GEN-001`） |

## 步骤

1. 记录每份文档的编号与版本，并检查 errata。
2. 按 profile 选择抽象：MCU 用 interface + `driver/device` + `driver/bus`（[architecture/mcu-architecture.md](../architecture/mcu-architecture.md) §4）；Zephyr 用设备模型（[platforms/zephyr.md](../platforms/zephyr.md) §3）；Linux 用子系统框架（[platforms/linux-kernel.md](../platforms/linux-kernel.md) §2）。
3. 寄存器映射：每个地址和位都来自文档，注释中引用出处；不出现魔数。
4. 初始化分阶段：参数校验 → 读 ID → 软复位 → 配置，每步检查返回值（`ARCH-007`）；每个阻塞操作都有超时（`GEN-009`）。
5. 并发与所有权：明确谁拥有总线（`RTOS-004`）；ISR 与 DMA 遵守 `ISR-*`、`DMA-*` 规则。
6. 实现方式：C++ 用模板注入总线（[cpp/patterns.md](../cpp/patterns.md) §2）；C 用带上下文的函数表。
7. host 测试：mock 总线接口而不是 HAL（`ARCH-008`），覆盖错误码、超时、ID 不匹配、总线错误。
8. HIL 计划：列出 host 无法证明的项目，例如时序、电气特性、中断抢占，并给出测量方法。

## 检查点

| 检查点 | 通过标准 | 不通过时 |
| --- | --- | --- |
| 硬件事实 | 每个寄存器、位、时序参数都有文档出处 | 标 `UNKNOWN` 并停止相关部分 |
| 错误路径 | 每个总线调用的错误都被处理或向上传播 | 补齐 |
| host 测试 | 错误注入用例覆盖每种总线错误 | 补齐 |
| HIL 计划 | 每个 host 无法证明的项目都有测量方法 | 补齐；未执行时报告 `NOT_RUN` |

## 通过与失败

- **PASS**：host 测试全部通过；硬件事实全部有出处；HIL 项已执行并通过，或在报告中明确标为 `NOT_RUN`。
- **FAIL**：测试失败，或存在没有出处的硬件事实。
- **BLOCKED**：关键文档缺失或版本不明。
