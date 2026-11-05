# Linux kernel profile（驱动、BSP、DT binding）

来源：内核树 `Documentation/process/` 下的 `coding-style.rst`、`submitting-patches.rst`、`coding-assistants.rst`、`generated-content.rst`、`volatile-considered-harmful.rst`，以及 `Documentation/dev-tools/kunit/`、`Documentation/devicetree/bindings/`。以目标内核版本的树内文档为准，厂商 BSP 内核同样适用。

## 1. coding-style.rst 要点

1. 缩进用 8 宽 tab；`switch` 与 `case` 同列；无行尾空白。
2. 行宽首选 80；不拆分用户可见字符串（便于 grep）。
3. 非函数块左花括号在行尾，函数左花括号独占一行；只在需要时加花括号（单语句不加，但 `if/else` 任一分支多语句则都加）；关键字后加空格，`sizeof`/`typeof`/`__attribute__` 后不加；`*` 靠近变量名。
4. 命名：局部变量短（`i`、`tmp`），全局要描述性；**不用匈牙利命名**（因此不用 BARR-C 的 `g_`/`p_` 前缀）。
5. **不要 typedef 结构体或指针**；typedef 只用于不透明对象、明确的整数抽象、sparse 类型检查等。
6. 函数短小专一，局部变量约 5–10 个以内；原型带参数名，不写 `extern`。
7. 多出口共享清理用 `goto`，标签按用途命名（`out_free_buffer`），不用 `err1`。
8. 注释说明做什么、为什么，不说怎么做；导出 API 用 kernel-doc。
12. 常量和枚举标签大写；多语句宏用 `do { } while (0)`；优先 `static inline` 函数；宏不改变控制流、不依赖隐式局部名。
13. 设备相关消息用 `dev_err/dev_warn/dev_info/dev_dbg`，其余用 `pr_*`；默认用 `dev_dbg`/`pr_debug`。
14. 分配：不强转 `void *` 返回值；分配失败无需额外打印（分配器已输出）；用当前树提供的分配辅助宏（新树为 `kmalloc_obj`/`kzalloc_obj` 等，老树为 `kmalloc(sizeof(*p), ...)`）。
16. 动作类函数返回 0 或负 errno；谓词函数返回 `bool`；返回指针的函数用 `NULL` 或 `ERR_PTR()`。
18. 用 `ARRAY_SIZE()`、`sizeof_field()`、`min()`/`max()`，不自己实现。
21. `.c` 中避免 `#ifdef`，在头文件中提供空 stub；用 `IS_ENABLED()`。
22. 不新增 `BUG()`/`BUG_ON()`；能恢复就用 `WARN_ON_ONCE()`；`BUILD_BUG_ON()` 鼓励使用。

另：`fallthrough;` 伪关键字标注贯穿；`volatile` 基本视为有害，寄存器访问用 `readl()/writel()`（或 regmap），并发共享用锁、原子操作、`READ_ONCE()/WRITE_ONCE()`。

## 2. 驱动惯用法

- 按子系统框架实现（platform/i2c/spi driver、regmap、IIO、input、gpio、pinctrl、clk、regulator 等），不发明私有抽象层。
- 探测函数中资源获取遵循子系统惯例：子系统普遍使用 managed 接口（`devm_*`）时使用它，并注意 `devm` 与非 `devm` 资源混用时的释放顺序。
- 错误路径用 `dev_err_probe()` 返回并处理 `-EPROBE_DEFER`。
- 硬件描述来自 devicetree/ACPI；`of_match_table` 的 compatible 必须有对应的 binding。
- 中断：`request_threaded_irq()`/`devm_request_threaded_irq()`；硬中断上下文只做确认与唤醒，耗时工作放线程化中断或 workqueue；中断上下文不睡眠。
- 新文件首行 SPDX，代码需兼容 GPL-2.0-only：`// SPDX-License-Identifier: GPL-2.0-only`（`.c`），头文件用 `/* */` 形式。

## 3. DT binding

- 新 binding 用 DT schema YAML（`Documentation/devicetree/bindings/<subsys>/<vendor>,<device>.yaml`），含 `$id`、`$schema`、`maintainers`、`compatible`、`required`、`additionalProperties`/`unevaluatedProperties`、`examples`。
- 检查：`make dt_binding_check DT_SCHEMA_FILES=<file>`，`make dtbs_check`（需 `dtschema`）。
- binding 补丁与驱动补丁分开，binding 在前。

## 4. 验证门禁

| 检查 | 命令 |
| --- | --- |
| 风格与常见错误 | `./scripts/checkpatch.pl --strict -g HEAD`（或对补丁文件） |
| 构建无新增告警 | `make W=1 <dir>/`（必要时 `W=12`） |
| sparse | `make C=1`（全部重查用 `C=2`） |
| 静态分析（可选） | `make coccicheck MODE=report M=<dir>`、`smatch` |
| KUnit | `./tools/testing/kunit/kunit.py run --kunitconfig=<dir>` |
| kselftest | `make -C tools/testing/selftests TARGETS=<t> run_tests` |
| DT | `make dt_binding_check`、`make dtbs_check` |
| 维护者 | `./scripts/get_maintainer.pl <patch>` |

交叉编译：`make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- ...`。

### KUnit 最小示例

```c
#include <kunit/test.h>

static void foo_parse_rejects_short_frame(struct kunit *test)
{
	u8 buf[2] = { 0 };

	KUNIT_EXPECT_EQ(test, foo_parse(buf, sizeof(buf)), -EINVAL);
}

static struct kunit_case foo_test_cases[] = {
	KUNIT_CASE(foo_parse_rejects_short_frame),
	{}
};

static struct kunit_suite foo_test_suite = {
	.name = "foo",
	.test_cases = foo_test_cases,
};
kunit_test_suite(foo_test_suite);
```

## 5. AI 辅助贡献（`coding-assistants.rst` 与 `generated-content.rst`）

- **AI Agent 不得添加 `Signed-off-by`**；只有人类能认证 DCO，人类提交者审查代码、确认许可、添加自己的 `Signed-off-by` 并承担全部责任。
- 代码必须兼容 GPL-2.0-only，使用 SPDX 标识。
- 修复缺陷：非平凡问题先做复现；构建通过且不新增告警；通过 checkpatch；提交信息写明问题、方案和 `Fixes:` 标签；用 `get_maintainer.pl` 找维护者；**说明哪些步骤未能完成**（未构建、未测试、未复现）。
- Agent 永远不自己发送补丁或邮件，由人决定提交什么。
- 在 cover letter/changelog 中透明说明工具使用：用了什么工具、输入（如 Coccinelle 脚本或提示词摘要）、影响了哪些部分、如何测试。
