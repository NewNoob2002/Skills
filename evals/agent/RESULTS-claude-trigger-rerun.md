# Agent 行为评测结果

生成时间：2026-11-05 15:17:07；技能提交：`7080cf2-dirty`；评委：`magpie/antigravity/gemini-4-argon`。本文件由 `tools/run_agent_evals.py` 生成，不要手改。

每个用例每个 Agent 只运行一次；Agent 输出有随机性，单次结果不代表稳定通过率。

## claude

PASS 6，FAIL 2，NOT_RUN 0，BLOCKED 0；应触发用例中实际使用技能 6/8，不应触发用例中误用技能 —；花费约 $1.73。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| trigger | 6 | 2 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | PASS | 是 | — |
| T02 | trigger | PASS | 是 | — |
| T03 | trigger | PASS | 是 | — |
| T04 | trigger | FAIL | 否 | expect_skill: expected True, skill_used=False |
| T05 | trigger | PASS | 是 | — |
| T06 | trigger | PASS | 是 | — |
| T07 | trigger | PASS | 是 | — |
| T08 | trigger | FAIL | 否 | expect_skill: expected True, skill_used=False |
