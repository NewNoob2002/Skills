# 合并前审查清单

逐项给出 `PASS / FAIL / N/A / NOT_RUN`，FAIL 附 `file:line` 与修正建议。机械门禁结果与人工审查结果分开写。

## A. 所有 profile

- [ ] profile 判定有证据；规则冲突按 [profiles.md](../profiles.md) 裁决
- [ ] 硬件事实（寄存器、位、时钟、引脚、DMA、errata）有来源；无来源的标 `UNKNOWN`
- [ ] 所有等待有界，超时时钟在当前启动/休眠阶段有效；tick 回绕处理正确
- [ ] 错误返回值全部检查并传播；外部输入校验长度与范围
- [ ] 无未定义行为：越界、有符号溢出、未初始化、对齐违例、严格别名
- [ ] 共享数据有明确同步；没有用 `volatile` 代替同步
- [ ] 复位、掉电、升级中断时持久状态不损坏
- [ ] 无注释掉的代码；假设写在注释里
- [ ] 未经授权没有 flash/擦除/熔丝/安全配置操作
- [ ] 测试 oracle 来自规格；证据按级别报告
- [ ] 提交未含 Agent 添加的 `Signed-off-by`；生成代码已按项目/上游要求披露

## B. `mcu-baremetal` / `mcu-rtos`

- [ ] `scripts/arch_lint.py` 通过（或违规已列出并说明）
- [ ] `scripts/barrc/check.sh` 通过；`// barr-c:allow` 例外均有理由
- [ ] 编译告警门禁无新增告警（`COMPILER_FLAGS.md`）
- [ ] BARR-C 代码审查类条目：cast 注释（1.6.a）、`static`/`const`（1.8.a/b）、命名前缀（7.1.j–o）、≥ 3 字符变量名（7.1.e）、常量在左（8.6.a）、`else if` 以 `else` 结束（8.2.d）、`break` 对齐（8.3.a）、结构体填充/位序（5.5）
- [ ] ISR：只捕获事件；`_isr` 命名与 `static`；W1C 标志直接写；`FromISR`/零超时 API；调用 RTOS API 的 ISR 优先级不高于 `configMAX_SYSCALL_INTERRUPT_PRIORITY`
- [ ] 任务：单一职责、`DelayUntil` 周期、栈预算与溢出检测、静态分配
- [ ] 看门狗基于各子系统进展
- [ ] DMA 缓冲区对齐与 cache 维护（有 D-cache 时）
- [ ] Ceedling（C 模块；C++ 模块见 F 节 CppUTest 条目）：新增/修改的公共函数有测试（正常、参数错误、依赖错误、边界）；`ceedling test:all` 结果与覆盖率已报告
- [ ] map 文件/size：Flash、RAM 余量变化已报告（目标构建可用时）

## C. `zephyr`

- [ ] 100 列、强制花括号、无 `//` 注释、snake_case
- [ ] Coding guidelines：无动态内存、检查返回值、无死代码、无遮蔽、A.1–A.5
- [ ] 硬件来自 devicetree、配置来自 Kconfig；`device_is_ready()` 检查
- [ ] 返回 `int` 负 errno
- [ ] ISR 中只用 ISR 安全 API
- [ ] ztest 用例 + `testcase.yaml`；`west twister -T <dir>` 结果
- [ ] `./scripts/ci/check_compliance.py -c <range>` 结果
- [ ] 提交标题 `area: summary` < 72 字符、正文非空、`Assisted-by:`

## D. `linux-kernel`

- [ ] `checkpatch.pl --strict` 无错误；告警已处理或说明
- [ ] `make W=1` 无新增告警；`make C=1`（sparse）无新增
- [ ] 无 typedef struct、无匈牙利命名、`goto` 清理标签按用途命名
- [ ] 正确使用子系统框架、`dev_err_probe()`、`-EPROBE_DEFER`
- [ ] 寄存器访问用 `readl/writel` 或 regmap；并发用锁/原子/`READ_ONCE`
- [ ] SPDX、GPL-2.0-only 兼容
- [ ] DT binding YAML 通过 `dt_binding_check`；compatible 与驱动一致
- [ ] KUnit/kselftest 结果；未能执行的步骤已说明

## E. `linux-userspace`

- [ ] 系统调用返回值、`EINTR`、部分读写已处理
- [ ] 文件原子写；资源成对释放
- [ ] 非 root、最小权限
- [ ] 单元测试 + sanitizer 结果；host 与目标结果分开

## F. C++（任何 profile 中的 `.cpp/.hpp`）

- [ ] 资源等级已确定，特性使用符合 [cpp/features.md](../cpp/features.md) 决策表
- [ ] `cpp_cost.py check <elf> --tier <Tn>` 通过；`--allow` 例外有评审理由；如有预算文件，段预算通过
- [ ] 与基线相比的 `cpp_cost.py diff` 增量已报告
- [ ] 目标构建使用 `-fno-exceptions -fno-rtti -fno-use-cxa-atexit`（T0–T2），严格告警组 `-Werror`，第三方头 `-isystem`
- [ ] clang-format（`assets/cpp/.clang-format`）与 clang-tidy（`assets/cpp/.clang-tidy`）无新增发现
- [ ] 全局对象 `constinit`/`constexpr` 构造；构造函数不访问硬件；硬件在显式 `init()` 中初始化
- [ ] 无 ISR 中首次触达的函数局部静态；无动态初始化的 Meyers 单例（T0）
- [ ] 多态基类为受保护非虚析构 + `final` 实现；`virtual` 只在运行期选择的边界
- [ ] 无 `std::function`、`std::vector/string/map`、iostream、异常、RTTI（T0–T2）
- [ ] 原子类型有 `static_assert(is_always_lock_free)`；ARMv6-M 与 64 位用临界区
- [ ] 无 `volatile` 复合运算（C++20）；`volatile` 只用于 MMIO/DMA 描述符
- [ ] ISR 向量 `extern "C"` 且名字与启动文件一致；C 回调用 `noexcept` 蹦床；跨边界类型为标准布局
- [ ] SDK 错误码在 bsp 层映射为 `Status`，返回值 `[[nodiscard]]` 且被检查
- [ ] CppUTest（`mcu-*`、`linux-userspace`；`zephyr` 的 C++ 以 C 节 ztest + Twister 为准，纯逻辑可额外 CppUTest）：新增/修改的公共行为有测试；接缝优先编译期 Fake；`-r2 -s` 运行通过；CppUTest 头最后包含
- [ ] 负向编译测试覆盖关键 `static_assert`（配置校验、Concept 约束）
