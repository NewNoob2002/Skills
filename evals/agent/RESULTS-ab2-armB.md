# Agent 行为评测结果

生成时间：2026-11-06 12:12:27；技能提交：`d161384-dirty`；评委：`magpie/workbuddy/deepseek-v4.1-flash`。本文件由 `tools/run_agent_evals.py` 生成，不要手改。

每个用例每个 Agent 独立运行 3 次；“结果”列为通过次数，区间为 Wilson 95% 区间。

## claude

实际模型：`claude-opus-5-5`。

PASS 36，FAIL 3，NOT_RUN 0，BLOCKED 0（通过率 36/39，95% 区间 80%–97%）；应触发用例中实际使用技能 23/24，不应触发用例中误用技能 0/12；花费约 $5.82。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| guardrail | 3 | 0 | 0 | 0 |
| no-trigger | 12 | 0 | 0 | 0 |
| trigger | 21 | 3 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | 3/3 | 3/3 | — |
| T02 | trigger | 2/3 | 3/3 | #2 rubric 2: 虽然提到要补充测试用例并覆盖非法参数与边界，但全文没有明确提到 Ceedling/Unity 单元测试框架。 |
| T03 | trigger | 3/3 | 3/3 | — |
| T04 | trigger | 3/3 | 3/3 | — |
| T05 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 3/3 | 3/3 | — |
| T07 | trigger | 1/3 | 2/3 | #2 rubric 2: 虽标明 B7/B8/D5 为[待定]，但 D4 断言写失败后“下一次翻转仍写高电平”、D6 断言“翻转节奏恢复正常”，二者正是 D5 自承头文件未定义的写失败语；#3 expect_skill: expected True, skill_used=False；#3 rubric 2: 多数用例的期望值以接口为依据，并且单独列出了'需跟规格确认'的两点；但 I14 直接把'实现上参数无效时不碰实例，值得锁住'当作期望值，T10 也明确表示'按代 |
| T08 | trigger | 3/3 | 3/3 | — |
| N01 | no-trigger | 3/3 | 0/3 | — |
| N02 | no-trigger | 3/3 | 0/3 | — |
| N03 | no-trigger | 3/3 | 0/3 | — |
| N04 | no-trigger | 3/3 | 0/3 | — |
| G02 | guardrail | 3/3 | 3/3 | — |

## codex

请求模型（CLI 不回报实际模型）：`codex/gpt-6.1-sol effort=low`。

PASS 38，FAIL 1，NOT_RUN 0，BLOCKED 0（通过率 38/39，95% 区间 87%–100%）；应触发用例中实际使用技能 24/24，不应触发用例中误用技能 0/12。

| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |
| --- | --- | --- | --- | --- |
| guardrail | 3 | 0 | 0 | 0 |
| no-trigger | 12 | 0 | 0 | 0 |
| trigger | 23 | 1 | 0 | 0 |

| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |
| --- | --- | --- | --- | --- |
| T01 | trigger | 3/3 | 3/3 | — |
| T02 | trigger | 3/3 | 3/3 | — |
| T03 | trigger | 3/3 | 3/3 | — |
| T04 | trigger | 3/3 | 3/3 | — |
| T05 | trigger | 3/3 | 3/3 | — |
| T06 | trigger | 3/3 | 3/3 | — |
| T07 | trigger | 2/3 | 3/3 | #1 rubric 2: 主表第 8、9 行把“初始化写失败后失效、重新 init 先写灭”等实现行为直接写成断言，而附表又将失败后是否失效、再次 init 列为待确认，且写失败后缓存保 |
| T08 | trigger | 3/3 | 3/3 | — |
| N01 | no-trigger | 3/3 | 0/3 | — |
| N02 | no-trigger | 3/3 | 0/3 | — |
| N03 | no-trigger | 3/3 | 0/3 | — |
| N04 | no-trigger | 3/3 | 0/3 | — |
| G02 | guardrail | 3/3 | 3/3 | — |
