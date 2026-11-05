# W02 现有工程架构审查

只读审查，不修改代码。审查结论只给出发现和建议；需要重构时转入 [refactor-planning.md](refactor-planning.md)。

## 概要

| 项 | 内容 |
| --- | --- |
| 触发 | 接手项目、重大变更前、定期健康检查、用户要求评审架构 |
| 输入 | 仓库（只读）、`AGENTS.md`、构建文件；有需求文档时一并提供 |
| 前置条件 | 只读权限；不运行 flash 或任何硬件动作 |
| 角色 | Architect 负责审查；QA 复核机械检查结果；不需要 Developer |
| 产物 | 审查报告：profile 证据、`arch_lint` JSON、按严重度排序的发现（Rule ID + `file:line`）、风险、建议的架构 delta、所需证据 |
| 人工审批 | 报告本身无需审批；任何重构建议需批准后才能进入 W09 |

## 步骤

1. 运行 `scripts/detect_profile.py <repo>`，核对证据文件；多 profile 仓库按目录划分。
2. 读项目显式规则（[profiles.md](../profiles.md) §1）。
3. 机械检查：MCU 运行 `scripts/arch_lint.py`；仓库可构建时检查编译告警；有 ELF 时运行 `scripts/cpp_cost.py check`。
4. 人工审查：MCU 用 [architecture/mcu-architecture.md](../architecture/mcu-architecture.md) §5 的清单；Zephyr 看设备模型、devicetree、Kconfig；内核看子系统框架。
5. 审查 ISR、RTOS 与 DMA（[rtos/mcu-isr-rtos.md](../rtos/mcu-isr-rtos.md)）。
6. 用 map/size 核对资源余量（无构建产物时标 `NOT_RUN`）。
7. 汇总：每条发现给出 Rule ID、证据、危害和建议，按严重度排序。

## 检查点

| 检查点 | 通过标准 | 不通过时 |
| --- | --- | --- |
| profile 判定 | 有证据文件支撑 | 询问用户 |
| `arch_lint` | 退出码 0 或 1；退出码 2 表示配置与目录不符，不能当作通过 | 调整 `--config`，或报告 `BLOCKED` |
| 发现可追溯 | 每条都有 `file:line` 和 Rule ID（没有对应规则时写明依据） | 删去没有证据的发现 |
| 结果分开 | 机械检查结果与人工审查结果分开报告 | 重新整理报告 |

## 通过与失败

- **PASS**：没有 `mandatory` 规则违规。
- **FAIL**：存在 `mandatory` 违规，逐条列出。
- `NOT_RUN` / `BLOCKED` 的检查单独列出并写明原因，不计入 PASS。
