# Agent 行为评测结果

生成时间：2026-11-06 11:31:11；技能提交：`d161384-dirty`；评委：`magpie/workbuddy/deepseek-v4.1-flash`。本文件由 `tools/run_agent_evals.py` 生成，不要手改。

每个用例每个 Agent 独立运行 3 次；“结果”列为通过次数，区间为 Wilson 95% 区间。

## claude

实际模型：`claude-opus-5-5`。

PASS 12，FAIL 3，NOT_RUN 0，BLOCKED 0（通过率 12/15，95% 区间 55%–93%）；应触发用例中实际使用技能 12/15，不应触发用例中误用技能 —；花费约 $3.06。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| trigger | 12 | 3 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | 3/3 | 3/3 | — |
| T02 | trigger | 3/3 | 3/3 | — |
| T05 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 0/3 | 0/3 | #1 expect_skill: expected True, skill_used=False；#2 expect_skill: expected True, skill_used=False；#3 expect_skill: expected True, skill_used=False |
| T07 | trigger | 3/3 | 3/3 | — |

## codex

PASS 11，FAIL 4，NOT_RUN 0，BLOCKED 0（通过率 11/15，95% 区间 48%–89%）；应触发用例中实际使用技能 12/15，不应触发用例中误用技能 —。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| trigger | 11 | 4 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | 3/3 | 3/3 | — |
| T02 | trigger | 1/3 | 1/3 | #2 expect_skill: expected True, skill_used=False；#3 expect_skill: expected True, skill_used=False |
| T05 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 3/3 | 3/3 | — |
| T07 | trigger | 1/3 | 2/3 | #2 expect_skill: expected True, skill_used=False；#3 rubric 2: 回答明确把期望值来源写成 `ledctl.c:20/62/66/80` 的实现行为，而非仅依据 `ledctl.h` 契约或规格；P0-9 的首个翻转方向、P1 |
