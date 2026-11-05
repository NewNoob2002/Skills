# 规范冲突分析

各来源之间的规则互相冲突。本技能不试图“统一”它们，而是先判定 profile，再按 profile 选用规则；跨 profile 的冲突在 `standards/rules.yaml` 中以 `conflicts` 双向登记，由 `tools/validate_skill.py` 检查对称性。逐项的裁决矩阵在 `../skills/embedded-engineering/references/profiles.md` §3（随技能安装）。

## 1. 裁决原则

1. **优先级**（高 → 低）：运行时与授权限制 → 项目显式规则（`AGENTS.md`、既有 `.clang-format`、偏离记录）→ 目标生态官方规范（Zephyr、Linux；向上游提交时强制，`GEN-008`）→ BARR-C → 分层架构规则 → 本工作流默认值。
2. **按 profile 选择，不混用**：同一文件只适用一套格式与命名规则；跨生态的目录（例如 MCU 固件 + Linux 驱动）按目录分别判定 profile。
3. **安全核心与格式层分开**：BARR-C 中与格式无关的安全规则（`C-*`）在不与官方规范冲突时适用于所有 C 代码；格式与命名层（`CFMT-*`）只用于 MCU profile，以及明确采用它的 Linux 用户态项目。
4. **现代 C++ 按条件取舍**：不一刀切禁止，按资源等级 T0–T3 与是否处于实时路径决定（`references/cpp/features.md`），并用 `cpp_cost.py` 在链接产物上验证。

## 2. 登记的规则冲突

| 规则 A（适用 profile） | 规则 B（适用 profile） | 冲突点 | 裁决 |
| --- | --- | --- | --- |
| `CFMT-001` BARR-C 布局（MCU、userspace*） | `ZEP-001` Zephyr code style（zephyr） | 4 空格 / Allman / 80 列 vs 8 宽 tab / K&R / 100 列 | 按 profile；Zephyr 代码一律 Zephyr 风格 |
| `CFMT-001` | `LNXK-001` 内核 coding-style（linux-kernel） | 同上，内核为 80 列首选 | 按 profile |
| `CFMT-002` 单语句也加花括号 | `LNXK-001` | 内核只在需要时加花括号 | 按 profile；Zephyr 与 BARR-C 一致（强制花括号） |
| `CFMT-003` `g_`/`p_`/`b_`/`h_` 前缀 | `LNXK-002` 禁止匈牙利命名与 typedef 结构体 | 命名约定相反 | 只在 MCU profile 使用前缀 |
| `CFMT-004` 常量在 `==` 左边 | `LNXK-001` | checkpatch 对此写法告警 | MCU 使用；其他 profile 用 `-Werror=parentheses` 与 clang-tidy 防误赋值 |
| `CFMT-005` 禁止 `short`/`long` | `LNXK-001` | 内核惯用 `unsigned long` 表示指针宽度 | MCU 禁止；内核按惯例 |
| `CFMT-006` 尽量不用 `goto` | `LNXK-003` 用 `goto` 集中清理 | 清理模式相反 | MCU 尽量避免；内核按惯例 |
| `CPP-003` 堆按等级受控（T1 允许初始化期分配） | `ZEP-007` 不使用动态内存 | Zephyr 应用层 C++ 是否允许初始化期分配 | zephyr profile 以 `ZEP-007` 为准（写在 `CPP-003` 的 `except`） |

\* `CFMT-*` 对 linux-userspace 只在项目采用 BARR-C 格式层时适用（`when` 条件）。

## 3. 未作为规则冲突登记、但需要注意的张力

| 主题 | 张力 | 处理 |
| --- | --- | --- |
| 测试框架 | Zephyr 以 ztest + Twister 为准入基线；不依赖 Zephyr API 的纯逻辑也可以用 Ceedling/CppUTest | `TEST-001` 的例外限定为 MCU 与 userspace；Zephyr、内核的其他框架只能作为补充 |
| `volatile` | BARR-C 1.8.c 曾允许线程共享数据使用 `volatile`（已撤回）；内核视其为有害 | `C-001`：任何 profile 都不用 `volatile` 做同步 |
| 错误码 | BARR-C 偏好项目枚举；Zephyr 与内核要求负 errno | MCU 用 `proj_err_t`；Zephyr、内核用负 errno（`ZEP-005`，谓词返回 `bool`、指针用 `NULL`/`ERR_PTR()`） |
| 头文件保护 | BARR-C 限制 `#pragma`；各生态都使用 `#ifndef` guard | `C-016`：统一用 guard |
| 花括号与 checkpatch | Linux 版 checkpatch 提示“单语句不需要花括号”；Zephyr 树内 checkpatch 改为强制花括号 | 对 Zephyr 代码使用 Zephyr 树内的 checkpatch（验证工程 `zephyr-app` 已确认） |
| C++ 在 Zephyr | 应用层可用 C++；内核、驱动、`SYS_INIT` 保持 C | `CPP-018` |
| 生成代码 | BARR-C 要求生成代码同样合规；厂商生成代码（CubeMX 等）不应被重排 | `GEN-007`：厂商生成代码只改保护区并排除出格式门禁；Agent 生成的代码适用全部规则（`GEN-004`） |

## 4. 冲突的自动检查

- `validate_skill.py` 的 `rules` 检查：`conflicts` 必须双向登记，引用的规则必须存在。
- `RulesConsistencyTest.test_r2_17_*`：规则的 `profiles` 与其标题、`when` 条件一致，保证 SKILL.md 中的筛选公式能选中适用的规则。
- 验证工程覆盖了冲突的两侧：`mcu-baremetal-c/bad-missing-braces`（`CFMT-002`）与 `zephyr-app/bad-no-braces`（`ZEP-001`）分别用 BARR-C 门禁与 Zephyr 树内工具检出。
