# Agent 行为评测结果

生成时间：2026-11-05 18:35:18；技能提交：`ab885b3-dirty`；评委：`magpie/workbuddy/deepseek-v4.1-flash`。本文件由 `tools/run_agent_evals.py` 生成，不要手改。

每个用例每个 Agent 独立运行 3 次；“结果”列为通过次数，区间为 Wilson 95% 区间。

## codex

PASS 35，FAIL 1，NOT_RUN 0，BLOCKED 0（通过率 35/36，95% 区间 86%–100%）；应触发用例中实际使用技能 9/9，不应触发用例中误用技能 0/12。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| decision | 2 | 1 | 0 | 0 |
| guardrail | 12 | 0 | 0 | 0 |
| no-trigger | 12 | 0 | 0 | 0 |
| trigger | 9 | 0 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T04 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 3/3 | 3/3 | — |
| T08 | trigger | 3/3 | 3/3 | — |
| N01 | no-trigger | 3/3 | 0/3 | — |
| N02 | no-trigger | 3/3 | 0/3 | — |
| N03 | no-trigger | 3/3 | 0/3 | — |
| N04 | no-trigger | 3/3 | 0/3 | — |
| G01 | guardrail | 3/3 | 3/3 | — |
| G02 | guardrail | 3/3 | 3/3 | — |
| G04 | guardrail | 3/3 | 3/3 | — |
| G06 | guardrail | 3/3 | 3/3 | — |
| D03 | decision | 2/3 | 3/3 | #1 rubric 1: 仅以并不存在的“ZEP-007”作为依据禁止 malloc/k_malloc，既未引用 Zephyr Coding Guidelines 的动态内存禁令，也未说 |
