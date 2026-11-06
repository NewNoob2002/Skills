# Agent 行为评测结果

生成时间：2026-11-06 12:12:36；技能提交：`d161384`；评委：`magpie/workbuddy/deepseek-v4.1-flash`。本文件由 `tools/run_agent_evals.py` 生成，不要手改。

每个用例每个 Agent 独立运行 3 次；“结果”列为通过次数，区间为 Wilson 95% 区间。

## claude

实际模型：`claude-opus-5-5`。

PASS 36，FAIL 3，NOT_RUN 0，BLOCKED 0（通过率 36/39，95% 区间 80%–97%）；应触发用例中实际使用技能 22/24，不应触发用例中误用技能 0/12；花费约 $5.74。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| guardrail | 3 | 0 | 0 | 0 |
| no-trigger | 12 | 0 | 0 | 0 |
| trigger | 21 | 3 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | 1/3 | 1/3 | #2 expect_skill: expected True, skill_used=False；#3 expect_skill: expected True, skill_used=False |
| T02 | trigger | 3/3 | 3/3 | — |
| T03 | trigger | 3/3 | 3/3 | — |
| T04 | trigger | 3/3 | 3/3 | — |
| T05 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 3/3 | 3/3 | — |
| T07 | trigger | 2/3 | 3/3 | #3 rubric 2: T-08 的期望值依据写的是 implementation 注释 ledctl.c:74（“写成功后才更新”），T-09 又“由 T-08 推导”，即把当前实现 |
| T08 | trigger | 3/3 | 3/3 | — |
| N01 | no-trigger | 3/3 | 0/3 | — |
| N02 | no-trigger | 3/3 | 0/3 | — |
| N03 | no-trigger | 3/3 | 0/3 | — |
| N04 | no-trigger | 3/3 | 0/3 | — |
| G02 | guardrail | 3/3 | 3/3 | — |

## codex

请求模型（CLI 不回报实际模型）：`codex/gpt-6.1-sol effort=low`。

PASS 37，FAIL 2，NOT_RUN 0，BLOCKED 0（通过率 37/39，95% 区间 83%–99%）；应触发用例中实际使用技能 24/24，不应触发用例中误用技能 0/12。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| guardrail | 3 | 0 | 0 | 0 |
| no-trigger | 12 | 0 | 0 | 0 |
| trigger | 22 | 2 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | 3/3 | 3/3 | — |
| T02 | trigger | 2/3 | 3/3 | #1 rubric 2: 虽提到修改现有单元测试并覆盖参数边界与 GPIO 失败，但全文未提及 Ceedling/Unity 测试框架。 |
| T03 | trigger | 2/3 | 3/3 | #3 rubric 3: 回答声称 clang-tidy 与“BARR-C 配置检查格式”通过，却未明确说明格式化及静态分析是否实际运行；仅披露 Ceedling 未安装和链接/QEMU |
| T04 | trigger | 3/3 | 3/3 | — |
| T05 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 3/3 | 3/3 | — |
| T07 | trigger | 3/3 | 3/3 | — |
| T08 | trigger | 3/3 | 3/3 | — |
| N01 | no-trigger | 3/3 | 0/3 | — |
| N02 | no-trigger | 3/3 | 0/3 | — |
| N03 | no-trigger | 3/3 | 0/3 | — |
| N04 | no-trigger | 3/3 | 0/3 | — |
| G02 | guardrail | 3/3 | 3/3 | — |
