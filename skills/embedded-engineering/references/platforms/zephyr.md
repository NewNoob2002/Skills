# Zephyr profile

来源：Zephyr 官方 Code Style、Coding Guidelines、Contribution Guidelines、Test Framework 文档（见 [sources.md](../sources.md)）。Zephyr 每个版本都可能调整，动手前核对目标仓库所用版本的 `doc/` 与 `scripts/`。

## 1. 代码风格（官方 code style）

- 总体遵循 Linux 内核风格，并有以下规定：
  - 行宽 ≤ **100** 列（文档中的 URL 可例外）。
  - `if`、`else`、`do`、`while`、`for`、`switch` 体**一律加花括号**，即使只有一行。
  - tab 宽 8；声明后的对齐注释用空格。
  - 只用 C89 风格 `/* */` 注释，**禁止 `//`**；需要进入文档的用 `/** */` Doxygen。
  - 注释中名词大小写正确（`UART`、`CMake`）。
  - 代码与变量用 snake_case；避免二进制字面量 `0b...`；避免非 ASCII 字符，禁止 emoji。
- 不要求修正你未修改的既有代码风格；规范未覆盖时依次跟随所在函数 → 文件 → 子系统的写法。
- 工具：仓库根有 `.clang-format`；风格与提交格式由 `scripts/ci/check_compliance.py` 检查（内部调用 checkpatch 等）。

## 2. Coding Guidelines（MISRA C:2012 子集，均为 Required）

以目标版本 `doc/contribute/coding_guidelines/index.rst` 的规则表为准。生成/审查代码时重点检查：

- Dir 4.1 减少运行期失败；Dir 4.4 不注释掉代码；Dir 4.6 用表明宽度与符号的 typedef；Dir 4.7 检查错误返回值；Dir 4.9 能用函数就不用函数式宏；Dir 4.10 头文件防重复包含；Dir 4.11/4.14 校验传给库函数的值和外部来源的值；Dir 4.12 不使用动态内存分配；Dir 4.13 资源操作函数按正确顺序调用。
- Rule 1.2/1.3 无语言扩展、无未定义行为；Rule 2.x 无不可达/死代码、无未用类型/标签/参数；Rule 5.x 标识符互不混淆、内层不遮蔽外层。
- 附加规则：
  - **A.1** 头文件中不条件编译函数或结构体声明（结构体内部字段可条件排除）。
  - **A.2** 使用包容性术语（不新增 master/slave、blacklist/whitelist 等）。
  - **A.3** 不重定义、不加前缀、不 `#ifndef` 包裹 `MIN`、`MAX`、`ARRAY_SIZE` 等通用宏。
  - **A.4** 内核代码（`kernel/`、`lib/os/`、`arch/`、`subsys/logging/`）只用列出的 C11 函数与 `strnlen()`。
  - **A.5** 内核以外的代码可用 C11 标准库（不含 Annex K），另允许 `gmtime_r()`、`strnlen()`、`strtok_r()`。

## 3. Zephyr 惯用法（替代 MCU 分层中的 interface/BSP）

- **硬件描述在 devicetree**，板级差异放 `boards/<board>.overlay` 或应用 `app.overlay`；新硬件写 binding YAML（`dts/bindings/`）。代码通过 `DT_NODELABEL`、`DT_ALIAS`、`DEVICE_DT_GET`、`GPIO_DT_SPEC_GET` 等宏取得设备，不硬编码地址。
- **配置在 Kconfig**，`prj.conf` 只放应用选项；用 `IS_ENABLED(CONFIG_X)` 在 C 条件中判断，少用 `#ifdef`。
- **设备就绪检查**：`if (!device_is_ready(dev)) { return -ENODEV; }`。
- **错误码**：函数返回 `int`，0 成功，负 errno 失败；调用者检查并传播。
- **驱动**：实现子系统 API 结构体（新版本用 `DEVICE_API(<subsys>, ...)`），用 `DEVICE_DT_INST_DEFINE` 与 `DT_INST_FOREACH_STATUS_OKAY` 实例化；`static` 配置结构体放 ROM。
- **ISR**：`IRQ_CONNECT()`/`irq_enable()` 或驱动框架回调；ISR 中只用 ISR 安全 API（`k_sem_give`、`k_msgq_put(..., K_NO_WAIT)`、`k_work_submit`、`k_poll_signal_raise`），不阻塞；工作推迟到 `k_work`/线程。
- **内核对象静态定义**：`K_THREAD_DEFINE`、`K_MSGQ_DEFINE`、`K_SEM_DEFINE`、`K_MUTEX_DEFINE`。
- **日志**：`LOG_MODULE_REGISTER(name, CONFIG_<X>_LOG_LEVEL)` + `LOG_ERR/WRN/INF/DBG`，不用 `printk` 做常规日志。
- **fall-through**：`__fallthrough;`。
- **头文件 guard**：`#ifndef ZEPHYR_INCLUDE_<PATH>_H_`。
- **SPDX**：新文件首行 `/* SPDX-License-Identifier: Apache-2.0 */`（Zephyr 主线）或项目许可证。

## 4. 测试：ztest + Twister

```c
#include <zephyr/ztest.h>

ZTEST_SUITE(ringbuf_suite, NULL, NULL, NULL, NULL, NULL);
/* 参数：名称、predicate、setup、before、after、teardown */

ZTEST(ringbuf_suite, test_put_rejects_when_full)
{
	zassert_equal(-ENOMEM, my_ringbuf_put(&rb, 0xAA), "full buffer accepted data");
}
```

- `prj.conf`：`CONFIG_ZTEST=y`。断言族：`zassert_*`（失败即终止该用例）、`zexpect_*`（继续）、`zassume_*`（跳过）。`ZTEST_F` 带 fixture，`ZTEST_USER` 在用户态线程运行。
- 测试元数据 `testcase.yaml`（示例程序用 `sample.yaml`）：

```yaml
tests:
  app.lib.ringbuf:
    platform_allow:
      - native_sim
    integration_platforms:
      - native_sim
    tags: ringbuf
```

- 运行：`west twister -T tests/lib/ringbuf/`；单个场景 `--scenario app.lib.ringbuf`。Twister 只在 Linux 上完整支持。
- 纯逻辑单元测试：`type: unit` 使用 `unit_testing` 伪板，不含内核，依赖需 stub/mock。
- Mock：`#include <zephyr/fff.h>`，`DEFINE_FFF_GLOBALS;`、`FAKE_VALUE_FUNC(...)`/`DEFINE_FAKE_VOID_FUNC(...)`，在 `ZTEST_RULE` 或 `before` 中 `RESET_FAKE(...)`；驱动可用 devicetree 中的 fake 设备（如 `zephyr,fake-pwm`）。
- 不依赖 Zephyr API 的算法模块也可以用 Ceedling 测试，但以 ztest 为准入基线。

## 5. 提交与合规

- 每个提交需要 `Signed-off-by:`（真实姓名，邮箱与作者一致，禁止 GitHub noreply）。**AI Agent 不得添加 `Signed-off-by`**，由人类提交者认证 DCO。
- AI 辅助的贡献添加 `Assisted-by:` 标签，例如 `Assisted-by: Claude:claude-opus-5-5`（`git`、`gcc` 等基础工具不列）。
- 标题 `area: subarea: summary`，少于 72 字符，空一行；正文不能为空，每行一般 ≤ 75 字符，说明做了什么、为什么、假设、如何验证。
- 本地合规检查：`./scripts/ci/check_compliance.py -c origin/main..HEAD`（`-p N` 限制并行度）。
- 可能影响测试时先提交 draft PR 让 CI 跑 Twister；CI 日志会给出本地复现命令。
