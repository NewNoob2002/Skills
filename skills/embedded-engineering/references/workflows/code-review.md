# W05 C/C++ 代码审查

只读审查一个 diff 或 PR。最终清单见 [verification/review-checklist.md](../verification/review-checklist.md)。

## 概要

| 项 | 内容 |
| --- | --- |
| 触发 | diff、PR 或指定文件的审查请求 |
| 输入 | diff 或文件列表、profile；可选的构建与测试命令 |
| 前置条件 | 只读权限 |
| 角色 | Reviewer 承担 QA 角色，不能与该改动的实现属于同一角色步骤；作者只负责回应 |
| 产物 | 发现列表（严重度、Rule ID、`file:line`、失败场景、建议）、机械门禁结果、未检查项清单 |
| 人工审批 | 不需要（只读） |

## 步骤

1. 确定 profile 和适用规则：读取 `profiles/<id>.yaml`，从 `standards/rules.yaml` 中筛出 `profiles` 含该 profile 或 `all` 的条目。
2. 运行机械门禁（能跑的都跑），记录命令与退出码。
3. 阅读改动本身及其调用方和被调用方，不能只看 diff 行。
4. 逐项过 review-checklist 的 A 节、对应 profile 的那一节；涉及 C++ 时再过 F 节。
5. 每条发现都要给出失败场景（输入 → 错误结果）；给不出场景的降级为“疑问”。
6. 报告：发现按严重度排序，机械门禁结果与人工审查结果分开写。

## 检查点

| 检查点 | 通过标准 | 不通过时 |
| --- | --- | --- |
| 规则来源 | 每条发现都有 Rule ID，或写明依据 | 补齐或删除 |
| 失败场景 | 每条发现都有具体的输入与错误结果 | 降级为疑问 |
| 调用链 | 已阅读受影响的调用方 | 补读 |
| 门禁 | 每项都标明 `PASS/FAIL/NOT_RUN/BLOCKED` | 补齐 |

## 通过与失败

- **PASS**：没有 `mandatory` 违规，机械门禁没有新增 FAIL。
- **FAIL**：存在 `mandatory` 违规或门禁 FAIL。
- 未执行的门禁单独列为 `NOT_RUN` 并写明原因；审查结论中注明哪些部分没有验证。
