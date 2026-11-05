# 验证工程预期的独立复核

日期：2026-11-05。复核对象是 `evals/projects/*/eval.yaml` 的预期、样例与技能检查脚本。这些预期与样例由同一作者编写，
因此用一个独立模型做只读复核，只看源码、检查命令与工具的实际行为，不执行任何检查。

复核模型：`magpie/workbuddy/deepseek-v4.1-flash`（与被测的 Claude Code、Codex 不同源；与最终评委是同一模型，原定评委 Gemini 4 Argon 因区域限制不可用，因此复核无法独立于评委偏好，这是本轮的局限），只开放 `read`/`grep`/`glob` 工具，
工作目录是工程定义、样例与技能脚本的只读副本。

| 工程 | 变体数 | 复核结论 |
| --- | --- | --- |
| `freertos-cpp` | 11 | 9 AGREE / 1 DISAGREE / 1 UNSURE |
| `linux-kernel-module` | 10 | 10 AGREE |
| `linux-userspace` | 7 | 6 AGREE / 1 DISAGREE |
| `mcu-baremetal-c` | 9 | 9 AGREE |
| `zephyr-app` | 6 | 6 AGREE |

表中 DISAGREE 为 2 项（`freertos-cpp`、`linux-userspace` 的 good）；另有 2 个 good 样例的强制规则违规（`mcu-baremetal-c` 的 `C-008`、`linux-kernel-module` 的 `LNXK-005`）写在对应工程的“其他发现”里，因为该变体的表行判定为 AGREE（检查结果确实符合预期）。合计 4 个 good 样例违反强制规则，UNSURE 的 1 项是失败机制描述；处理记录见 `../evals/TRIAGE.md` 第三轮（#13–#22）。
修正后 `python3 tools/run_evals.py --strict` 重跑：43 MATCH、0 MISMATCH、0 NOT_RUN。

## 复核提示词

```text
你是独立审查者，复核一个嵌入式编码规范技能的“验证工程”的预期结果。这些预期与样例由同一作者编写，你的任务是找出预期中站不住的地方。
你没有执行权限，只能阅读文件；不要假设任何运行结果，依据源码、检查命令与工具的工作方式判断。

目录：
- projects/<工程>/eval.yaml：检查（checks，每项有 run 命令与 rules）与变体（variants）。每个变体的 expect 列出预期为 FAIL 的检查，未列出的检查预期 PASS；known_gap 表示预期所有检查都 PASS（自动检查漏报）。
- projects/<工程>/good/：已知良好样例；projects/<工程>/variants/<名>/：叠加到 good 副本上的差异文件（只含改动文件）。
- skill/standards/rules.yaml：规则定义；skill/scripts、skill/assets：检查脚本与配置（arch_lint、BARR-C 门禁、clang-format/clang-tidy 配置、cpp_cost 等）。

请只审查工程：linux-kernel-module。对每个变体（含 good）逐一判断：
1. 变体是否确实违反了 violates 中的规则（或确实引入了 defect 描述的缺陷），且没有意外引入别的问题；
2. 每个检查的预期（FAIL 或 PASS）是否符合该检查命令与工具的实际行为——特别注意：预期 PASS 的检查是否其实会失败，预期 FAIL 的检查是否可能因为别的原因失败（失败原因与规则不对应）；
3. known_gap 是否属实（是否其实有某个现有检查能发现）；
4. good 是否本身违反了该工程 profile 下的强制规则。

输出格式（只输出这些）：
## linux-kernel-module
| 变体 | 结论 | 理由（一两句，引用文件与行或工具行为） |
其中结论取 AGREE / DISAGREE / UNSURE。表格后列出“其他发现”（例如检查命令本身的问题、规则引用不当），没有就写“无”。
```

## `freertos-cpp`

## freertos-cpp

| 变体 | 结论 | 理由（一两句，引用文件与行或工具行为） |
|---|---|---|
| good | DISAGREE | 六项检查确实都会 PASS（7 个文件都能映射到层且无违规；目标 ELF 无禁用符号；`unit` 的 15/35/−20/3 与 `rtos` 的 65 均算得通）。但 good 本身违反 CPP-012：`good/app/app_main.cpp:21` 用 `std::int32_t volatile last_average_` 保存普通 RAM 值（非 MMIO/DMA），而本工程没有 `cpp_compiler_flags` 检查、C++17 下也无 `-Wvolatile`，属无人发现的强制规则违规，"已知良好样例"不成立。 |
| bad-std-function | UNSURE | `cpp_cost` FAIL 成立，但成因不是 note 说的"堆"：`this` 捕获的 lambda 是 location-invariant 且 4 B < libstdc++ 16 B SBO 缓冲，`_M_init_functor` 只实例化 placement-new 分支，ELF 中不会出现 `operator new`/`malloc`；实际由 `std::__throw_bad_function_call`（`operator()` 路径）与 `__aeabi_atexit`（DebugSink 析构变非平凡）命中。另外 `app/app_main.cpp:22-23` 成员声明未按 `AlignConsecutiveDeclarations` 对齐、lambda 体在列 50 另起一行（`AllowShortLambdasOnASingleLine` 下 clang-format 更可能在 `on_report_{` 处断行），`format` 是否仍 PASS 需实跑 clang-format 才能定。 |
| bad-std-vector | AGREE | `std::vector<int32_t>(N,0)` 在 `g_telemetry` 动态初始化时调用 `operator new`→`malloc`（replaceable，不可被优化掉），`heap` 类别必命中；行为不变（`average()` 只用 `count_`），unit 四条断言与 rtos 的 65 都仍成立。 |
| bad-local-static | AGREE | 运行期初始化的函数局部静态会生成 `__cxa_guard_acquire/release`（`-fno-threadsafe-statics` 未开启），`local_static_guard` 命中；`unit`/`rtos` 的源列表只有 `module/telemetry/telemetry.cpp`，不含 `bsp/adc.cpp`，故 PASS 正确。 |
| bad-atomic-rmw | AGREE | ARMv6-M 无 LDREX/STREX，`fetch_add` 走 `__atomic_fetch_add_4`，Makefile 未链接 `-latomic` → 链接失败、`build/app_m0.elf` 不存在；`cmd_check` 的 `require_file` 抛 `ToolError` → 退出码 2 → BLOCKED，其余检查不编译 `app_main.cpp`。 |
| bad-public-virtual-dtor | AGREE | 公有虚析构让 vtable 的删除析构器引用 `operator delete`→`free`（`heap` 类），并使 DebugSink 析构非平凡而产生 `__aeabi_atexit`（`static_dtor`），`cpp_cost` 必 FAIL；但 CPP-011 在 rules.yaml 里是 review 规则（见其他发现）。 |
| bad-throw | AGREE | `cross` 因 `-fno-exceptions` 编译失败（变体 Makefile:8），无 ELF → `cpp_cost` 阻塞；`unit`/`rtos` 用 `$(STRICT)` 含 `-Werror`，noexcept 函数内的 `throw` 触发默认开启的 `-Wterminate`，两条 host 构建都失败。 |
| bad-layering | AGREE | `arch_lint` 经 `by_basename` 把 `"adc.hpp"` 解析到 `bsp/adc.hpp`，module 的 `allow` 只有 `[module, interface]` → `layer_dependency`，退出码 1；`-Ibsp` 在 `INCS` 中，其余构建仍可编译。 |
| bad-average-divisor | AGREE | 未满窗口时 `30/4=7` 使 `tests/test_telemetry.cpp:35-41` 的 `LONGS_EQUAL(15, ...)` 失败；集成测试两次上报都在 `count_==N` 时发生，(50+60+70+80)/4=65 仍成立，`rtos_host` 通过（其余三条断言也仍成立）。 |
| bad-consumer-deadlock | AGREE | `consumer_task` 阻塞在无人写入的 `g_unused`（`main_posix.cpp:69`），producer 第 5 次 `xQueueSend` 后也阻塞；watchdog `vTaskDelay(2000)` 后 `exit(2)`（:79-81），`make` 失败；`cross`/`unit` 不编译 `host_rtos`。 |
| bad-rtti | AGREE | 去掉 `-fno-rtti` 后 DebugSink 的 vtable 引用 typeinfo，`nm -C` 输出 `typeinfo for (anonymous namespace)::DebugSink`，命中正则 `^typeinfo (?:name )?for `；`-fno-exceptions` 保留，链接无新增依赖。 |

**其他发现**

1. **`format` 检查的规则引用不当**：`eval.yaml` 把 `format` 归到 `CPP-015`，但 CPP-015 是"严格告警组 + `-Werror` + 第三方头 `-isystem`"，与 clang-format 排版无关；rules.yaml 里也没有 C++ 排版规则（`CFMT-001` 的 `lang: [c]`）。该检查在规则体系中无对应条目。
2. **`cpp_cost` 引用了 review 规则**：`checks.cpp_cost.rules` 含 `CPP-011`/`CPP-002` 之外，`CPP-011` 在 rules.yaml:906-915 是 `verify.method: review`（无自动工具）。`bad-public-virtual-dtor` 的 FAIL 只是 `heap`/`static_dtor` 症状，不能据此声称自动覆盖 CPP-011（例如未被删除的公有虚析构本身不会产生这两个符号）。
3. **`bad-std-function` 的 note 机制写错**：如表中所述，`this` 捕获的 lambda 走 SBO，"检出堆"不成立；实际是 `std::__throw_*`（还可能连带 `__cxa_throw`）与 `__aeabi_atexit`。结论不会变，但 note 会误导后续维护者以为 cpp_cost 的 `heap` 覆盖了 `std::function`。
4. **CPP-008 的自动检查从未被验证**：`bad-atomic-rmw` 让 `cross_build` 先失败，`cpp_cost` 的 `atomic_libcall` 类别在整个工程里一次都没跑过——预期本身自洽，但用它来"验证"该检查是无效的。
5. **`unit` 的 requires 不完整**：`unit` 只列 `{cpputest}/lib/libCppUTest.a`，而 Makefile 链接 `-lCppUTest -lCppUTestExt`（`tests/all_tests.cpp` 用 `CommandLineTestRunner`、`tests/test_telemetry.cpp` 用 `TestHarness`）。缺 `libCppUTestExt.a` 时会在链接期失败而不是被标 BLOCKED。
6. **覆盖缺口**：没有任何变体触发 `ARCH-002/003/004/005/006` 与 `CPP-006/007/012`，这些检查在本工程里永远 PASS；good 的 CPP-012 违规正好是一个"未声明的 known_gap"（本工程也没有任何 `known_gap` 变体）。

## `linux-kernel-module`

## linux-kernel-module

| 变体 | 结论 | 理由（一两句，引用文件与行或工具行为） |
|---|---|---|
| good | AGREE | 三项检查按预期 PASS：`checkpatch -f --strict` 对 good/acme-frame.c 无可触发项（续行对齐满足 `pos_last_openparen` 计算、最长行 84<100、spelling.txt 无命中）；binding 有 `additionalProperties: false` 满足 core.yaml 的 oneOf，example 经 dt-extract-example→dtc→dt-validate 无输出；clang + `-Werror` 下无告警。但 good 自身未完全满足强制 LNXK-005（见其他发现 1）。 |
| bad-typedef | AGREE | `typedef struct {…} acme_frame_priv_t;` 命中 checkpatch `NEW_TYPEDEFS` WARN（checkpatch.pl:4855-4863）；WARN 使 `$clean=0`→退出码 1，原因对应 LNXK-002；typedef 本身编译无误，kbuild PASS 成立。 |
| bad-no-spdx | AGREE | 首行 `/*`：`-f` 用 `diff -u /dev/null` 生成全 `+` 行（checkpatch.pl:1344-1346），`$realline==1` 进入 SPDX 分支，.c 只接受 `//`（3829-3857），报 "Missing or malformed SPDX…" WARN→FAIL，对应 LNXK-007。 |
| bad-bug-on | AGREE | `-f` 文件模式把 BUG 检查降级为 CHK（checkpatch.pl:4922-4926），Makefile 传了 `--strict` 使 `$check=1`、CHK 报告且 `$clean=0`（2531-2534）→FAIL；BUG_ON 经 slab.h→`<linux/bug.h>` 可见，kbuild PASS。 |
| bad-missing-static | AGREE | 去 static 后 clang 的 `-Wmissing-prototypes`/`-Wmissing-declarations`（$KDIR/scripts/Makefile.warn:20-21，常开）+ `KCFLAGS=-Werror`（kernel Makefile:1242 并入 KBUILD_CFLAGS）→kbuild FAIL。checkpatch 无“缺原型”检查（`AVOID_EXTERNS` 只对以 `;` 结尾的原型生效，7229-7261），PASS 成立；但失败与 W=1 无关（见其他发现 2）。 |
| bad-volatile-mmio | AGREE | `*(volatile u32 *)…` 触发 `VOLATILE` WARN（checkpatch.pl:6356-6361，无条件致命）→checkpatch FAIL，对应 LNXK-004；`void *` 上的算术/强转只在 `-Wpointer-arith`（W=3，Makefile.warn:181）告警，W=1 不告警，kbuild PASS 成立。 |
| bad-binding-no-additional | AGREE | 根 schema 两者皆缺，dtschema 的 core meta-schema（meta-schemas/core.yaml：`oneOf: required unevaluatedProperties / additionalProperties`）校验失败，dt-doc-validate 输出错误，脚本以“输出非空”判 FAIL；example 本身合法，不会误触其它检查。 |
| bad-binding-example | AGREE | schema 自身合法（doc 阶段无输出），但 example 新增未定义属性 `acme,fifo-depth`，`additionalProperties: false` 使 dt-validate 报错；dt-validate 诊断写 stderr（dtb_validate.py `_emit_diagnostics`），脚本 `2>&1` 捕获→FAIL。 |
| bad-hungarian | AGREE | 仅把成员/局部改成 `p_dev`/`p_base`/`u32_frames_*`，编译无告警；checkpatch 没有匈牙利/类型前缀检查（唯一相关是 NEW_TYPEDEFS），kbuild/checkpatch/dt_binding 全 PASS，known_gap 属实。 |
| bad-sleep-in-hardirq | AGREE | 改成 `devm_request_irq` 硬中断并在其中 `usleep_range(1000,2000)`（第 77、115 行），违反 LNXK-006；同时第 10 行补了 `<linux/delay.h>`，可编译；checkpatch 不查中断上下文睡眠，`usleep_range` 参数 min<max 不触发 7171-7183 的检查，三检查全 PASS，known_gap 属实。 |

**其他发现**

1. **good 违反强制规则 LNXK-005**：probe 中 `devm_platform_ioremap_resource`（good/acme-frame.c:104-106）和 `platform_get_irq`（108-110）的错误路径直接 `return PTR_ERR(...)`/`return irq`，只有 `devm_request_threaded_irq` 用 `dev_err_probe()`（115）；而 LNXK-005（mandatory，verify=review）要求 probe 错误路径用 dev_err_probe 并处理 -EPROBE_DEFER（`platform_get_irq` 恰是会返回 -EPROBE_DEFER 的路径）。没有任何 check 映射到 LNXK-005，所以“good 全 PASS”仍成立，但 good 不是规则完全合规的样例。
2. **bad-missing-static 的机制说明不准确**：7.3 内核把 `-Wmissing-declarations`/`-Wmissing-prototypes` 放在 `$KDIR/scripts/Makefile.warn` 的“always enabled”段（20-21 行），不是 W=1 才启用；期望 FAIL 仍成立（KCFLAGS=-Werror），但 eval.yaml 的 note 和 Makefile 注释、LNXK-009 的 gap 描述中“W=1 告警默认不改变退出码”的说法在这个内核上只对部分 W=1 专属告警成立。
3. **bad-bug-on 隐式依赖 `--strict`**：`-f` 下 AVOID_BUG 是 CHECK（4922-4926），只有 `$check` 真时才输出（2531）；若 Makefile 去掉 `--strict`，该变体会静默 PASS。这是 eval 的一个脆弱点，建议在 note 中写明。
4. **checkpatch 的判定面大于 `checks.checkpatch.rules`**：`-f` 把整文件当新增扫描（1344-1346），`--strict` 会额外启用 CAMELCASE、LINE_SPACING、TYPO_SPELLING、PARENTHESIS_ALIGNMENT、OPEN_ENDED_LINE 等与 LNXK-001/002/004/007/010 无关的 CHECK（TYPO_SPELLING 依赖 checkpatch 同目录的 scripts/spelling.txt，本机存在）；当前 good 恰好干净，但任何这类 CHECK 都会让全部变体（含 good）失败。另外 `-f` 实际调用 `diff -u /dev/null <file>`（1345），而 `requires: [make, perl]` 未列 `diff`。
5. **sparse 完全未执行**：`kbuild` 只跑 `make … modules`，没有 `C=1`；LNXK-004 的 verify 工具本是 kernel_build/sparse（rules.yaml LNXK-004），checkpatch 只能发现 `volatile` 关键字（VOLATILE WARN）。因此“非 volatile 的 `__iomem` 直接解引用/无 readl”这类 LNXK-004 违规在本工程漏检，而 `checks.checkpatch.rules` 含 LNXK-004 会让人误以为已覆盖（eval.yaml 头部虽声明 sparse 未覆盖）。
6. **check_binding.sh**：`dt-doc-validate -u bindings` 的 `-u` 在 dtschema 里是已弃用的 `--url-path`，且 `doc_validate.py` 的 `check_doc()` 根本没用这个参数；脚本注释“dt-doc-validate 发现错误时退出码仍可能为 0”只对 `check_schema_refs()` 的 stderr 输出成立（check_doc 对 meta-schema 错误返回 1）。此外 `dt-mk-schema`/`dtc` 失败时 `set -e` 直接中止、不打印 “FAIL:”，且 `dt_binding` 无 blocked_codes，缺 uv/断网会记为 FAIL 而非 BLOCKED；`uv tool run --from dtschema==2026.9` 首次需联网（PyPI 上 2026.9 确为当前版本）。
7. **good/Makefile 的 LLVM_FLAG 只 grep `.config`**：`test -d …/build` 通过但 `.config` 缺失时，`$(if $(shell grep …))` 静默为空，会用 gcc 编译 clang(+LTO) 内核的模块；kbuild 的阻塞守卫没有检查 `.config`。
8. **LNXK-008 只覆盖后半**：`dt_binding` 只校验 schema 与 example，驱动的 `of_match_table` compatible 与 binding 是否一致（LNXK-008 后半）没有检查，也没有对应变体；rules.yaml 的 gap 已说明，但 checks 的 `rules: [LNXK-008]` 容易被理解为全覆盖。

## `linux-userspace`

## linux-userspace

| 变体 | 结论 | 理由（一两句，引用文件与行或工具行为） |
|---|---|---|
| good | DISAGREE | 三项检查确实都会 PASS，但“已知良好”不成立：`src/config_store.c:50` 的 `(void)sysio_close(fd);` 丢弃系统调用返回值，违反强制 LNXU-001；且 `src/daemon_signals.c:15,29` 两个公共函数无任何测试（`tests/` 只有 io_util/config_store/msg_parse 三个文件），违反强制 TEST-002，而 eval 把 TEST-002 挂在 `unit` 下。 |
| bad-partial-write | AGREE | `src/io_util.c:9-11` 只调用一次 `sysio_write` 即返回 0；`test_partial_write_is_continued` 的 `g_calls==2` 断言失败（另 `test_eintr_is_retried` 也失败），unit FAIL 成立且原因正是 LNXU-001；编译告警与 cppcheck 无触发点。 |
| bad-eintr | AGREE | 删除 EINTR 分支后 `test_eintr_is_retried` 得到 `-EINTR` 而非 0（且只写 1 次），unit FAIL 成立；无额外告警。 |
| bad-unchecked-fsync | AGREE | `src/config_store.c` 中 `(void)sysio_fsync(fd);` 后仍走 rename；`test_fsync_failure_aborts_before_rename` 在未预期的 `sysio_rename` 调用处由 CMock 记 Unity 失败（随后返回值断言也不成立），失败原因与 LNXU-002 对应。 |
| bad-nonatomic-save | AGREE | 改为 `sysio_open(path, O_WRONLY|O_CREAT|O_TRUNC)` 并删去 rename；两个 config_store 测试都因期望的 `.tmp` 路径/rename 从未出现而 FAIL。 |
| bad-name-overflow | AGREE | 去掉 `name_len >= out_cap` 后，`test_name_too_long_for_output_is_rejected` 的 `char out[8]` 被 `memcpy` 20 字节：ASan 报 stack-buffer-overflow；即使没有 ASan，函数返回 0 也会让 `-EMSGSIZE` 断言失败。 |
| bad-signal-printf | AGREE | 处理器中 `fprintf` 不触发任何 `-Wformat/-Wall` 告警，cppcheck 无 async-signal-safety 检查，`tests/` 也没有 daemon_signals 用例，故三项检查全 PASS，known_gap 属实。 |

其他发现：

1. `unit` ↔ TEST-002 的映射站不住：跑既有测试只能证明“已有测试通过”，不能证明“每个公共函数都有测试”；good 的 `daemon_signals_install/daemon_stop_requested` 与 5 个 `sysio_*` 包装（`src/daemon_signals.c:15,29`、`src/sysio.c`）均无用例，因此该 PASS 不构成 TEST-002 的证据。
2. `cppcheck` ↔ GEN-010 的映射站不住：cppcheck 没有“外部输入长度/范围校验”检查器；GEN-010 自身 `verify.method` 也是 `test`，所以 cppcheck PASS 对 GEN-010 无任何证据力。
3. `bad-name-overflow` 的 PROTO-001 引用不当：`src/msg_parse.c:17` 已按输入剩余长度校验长度字段（`size < 1U + name_len`），真正缺失的是输出缓冲容量校验（`out_cap`），应归 GEN-010/接口契约，而非 PROTO-001 的“帧长/剩余缓冲区”。
4. `bad-unchecked-fsync` 与 `bad-nonatomic-save` 实际失败在 CMock 的“未预期调用”（Unity 失败），而非返回值断言；与缺陷一致，但说明这两个测试断言的是调用序列，报错信息不会指向 LNXU-001/002。
5. `warnings` 未使用 `assets/barr-c/COMPILER_FLAGS.md`：缺 `-Werror=parentheses`、`-Wfloat-equal`、`-Wswitch-default`、`-Wimplicit-fallthrough`、`-Wvla`，因此 profile 内 C-007/C-011/C-012/C-013 在本工程完全没有自动覆盖（eval 只声明 C-006/C-014，故不算误报，但 `warnings: PASS` 的覆盖面远小于 profile）。
6. good 的 `src/config_store.c:22` 只判 `snprintf(...) >= (int)sizeof(tmp)`，未处理负返回值（此时 `tmp` 内容未定义），属 GEN-010 边界缺口且无用例覆盖；另 `src/daemon_signals.c:27` 未设 `SA_RESTART`，只有 `io_write_all` 重试 EINTR，`config_save` 的 open/fsync/rename/close 直接返回 `-EINTR`，按 LNXU-001“处理 EINTR”的严格读法同样是缺口。
7. 悬空引用：`eval.yaml` 注释引用的 `evals/TRIAGE.md` 在本树不存在；`rules.yaml` 所有 `ref` 指向 `references/**`，而 `skill/` 下只有 `assets/`、`scripts/`、`standards/`，引用无法解析。
8. 条件性发现：若判定本工程采用 BARR-C 格式层，good 还违反 CFMT-004（`src/config_store.c:18`、`src/msg_parse.c:10` 的 `dir == NULL` 等常量在右）与 CFMT-003（指针无 `p_` 前缀）；eval 未声明该 `when` 条件，故未计入结论。

## `mcu-baremetal-c`

## mcu-baremetal-c

| 变体 | 结论 | 理由（引用文件/行或工具行为） |
|---|---|---|
| good | AGREE | arch_layers.json 的 allow 覆盖 good 的全部 include（app→bsp/module、bsp→platform、module/interface→interface），arch_lint 走 layer/hal_call/register_access/cycle 均不报；barrc 侧静态核对无违规（无 tab/CR/尾空格、无 >80 字节行、Allman+声明对齐、`g_`/`p_`/`b_` 前缀、无 short/long/auto/register/exit）。unit 之所以 PASS 成立，是因为 Ceedling 1.2.2 只编译测试 `#include` 命中的源（test_build_planner.rb:160,257-321、test_search_paths.rb:41-51），`bsp/**`/`app/**` 虽在 `:source` 但不会进 unit 编译，所以 `:include` 缺 bsp/platform 不导致失败；target_main.c:19-20 的期望 5 次写与 ledctl.c:64 的 `>=` 语义一致。 |
| bad-layering | AGREE | arch_lint 的 `resolve_include` 按 basename 解析 `board_led.h`→`bsp/board_led.h`，module 的 allow 仅 `[module, interface]`（arch_layers.json:10）→ layer_dependency FAIL；unit FAIL 的机制与 note 一致（Ceedling 只把 `:include`=interface/module 加为 -I，board_led.h 找不到），barrc/warnings/cross 因 Makefile INCS 与 gen_compdb.py 都带 `-Ibsp` 而仍 PASS。 |
| bad-hal-call | AGREE | arch_lint: ledctl.c:82 命中 `hal_call` 正则 → FAIL；unit/qemu 在链接期缺 `HAL_Delay` 定义 → FAIL；warnings/cross 只有声明无定义故 PASS。但 note 的“命名门禁报函数名非小写”不成立：check.sh:34-56 的命名门禁只检查**文件名**，真正的失败来自 clang-tidy 的 `readability-identifier-naming.FunctionCase: lower_case`（且 barrc.rules 里没有能覆盖“函数名大小写”的规则 ID）。 |
| bad-signed-bitwise | AGREE | ledctl.c:77 `ticks & 1` 两侧均为有符号 int → `bugprone-signed-bitwise`（hicpp 别名已由 LLVM 23 移除，`bugprone-` 仍生效）→ barrc FAIL；其余路（arch_lint/warnings/cross/qemu）不受影响。附带问题：新增公共函数 `ledctl_is_odd`（ledctl.c:74-78、ledctl.h:62）没有任何测试，属 TEST-002 违规而 unit 仍 PASS。 |
| bad-implicit-decl | AGREE | ledctl.c:83 调用未声明的 `ledctl_trace`：clang≥16 在 C99 下把隐式声明当错误（compdb 带 `-std=c99`）→ barrc FAIL；warnings/cross/qemu 因 `-Werror=implicit-function-declaration` 失败，unit 的 project.yml `:flags:` 同样含该 flag → 五路 FAIL 与预期一致。 |
| bad-missing-braces | AGREE | ledctl.c:80-81 去掉单语句花括号 → clang-tidy `readability-braces-around-statements`（即 CFMT-002）；clang-format 不会加回花括号、其余检查与行为不变，故只有 barrc FAIL。 |
| bad-toggle-late | AGREE | ledctl.c:64 用 `>`：half_period=2 的用例在第 2 拍不翻转（test_ledctl.c:76-84 期望 2 次写）→ unit FAIL；目标侧 200 拍内只翻转 3 次（4 次写 ≠ EXPECTED_WRITE 5，target_main.c:19-20）→ qemu FAIL；其余检查不受影响。 |
| bad-isr-name | AGREE | vectors.c:14 定义 `Systick_Handler`，启动文件 startup.c:16 的 `SysTick_Handler` 是 weak alias→`default_handler`，向量表第 15 项因此落到默认处理函数，打印 FAIL 并 `semihost_exit(1)` → qemu FAIL；platform/ 不在 barrc 文件列表、arch_lint 不看 ISR 内容、unit 只编译 module/ledctl/ledctl.c，故其余 PASS 成立（note 的说法正确）。 |
| bad-isr-heavy | AGREE | known_gap 属实：platform/ 被 barrc 排除、arch_lint 无 ISR 规则、QEMU 中 `g_led`（vectors.c:19 经 app_led_service）仍是零初始化且 target_main 用自己的 fake，故 6 项自动检查全 PASS；额外发现该变体还引入 `app_led_service` 无公共头原型（main.c:19 / vectors.c:13 各写一遍），违反 C-002（review），known_gap 未提及。 |

### 其他发现

1. **bad-hal-call 的 barrc 失败原因与规则不对应**：eval.yaml:45 归因于“命名门禁”，但 check.sh 的命名门禁只比对文件名 basename；实际触发者是 `.clang-tidy` 的 `readability-identifier-naming.FunctionCase: lower_case`。rules.yaml 里没有“函数名小写”这条规则 ID（CFMT-003 只管前缀），barrc.rules 列出的 8 条规则都无法解释这次 FAIL。
2. **good 违反强制规则 C-008**：`platform/board/board_regs.h:12-16` 是寄存器映射结构体，既无显式 padding 也无 `static_assert(sizeof)` 校验；C-008 在 mcu-baremetal 为 mandatory（review 类），现有自动检查不覆盖，且 `-std=c99` 没有 `_Static_assert`（需用负数组技巧）。
3. **barrc 对头文件实际不起作用**：`checks.barrc.run` 把 `.h` 也传给 check.sh，但 `gen_compdb.py` 只为 `.c` 生成条目，clang-tidy 对不在 DB 的文件输出 “Skipping … Compile command not found” 并跳过，因此 check.sh:126 注释设想的 `-x c` 头文件检查路径根本走不到；bad-signed-bitwise 的 `ledctl.h:62`、`interface/*.h` 等头文件内容不参与 clang-tidy 检查，（若该 clang-tidy 版本对缺失条目改为报错，则所有变体的 barrc 都会失败）。
4. **unit 覆盖面被高估**：Ceedling 1.x 按测试的 `#include` 决定编译哪些源，unit 只覆盖 `module/ledctl/ledctl.c`；`bsp/board_led.c`、`bsp/board_tick.c`、`app/main.c` 一律不 host 编译，所以 note 中“unit FAIL 发现分层问题”其实是 include 路径配置的副产物，而非分层校验。
5. **无法执行验证的残余风险**：若 `readability-magic-numbers` 对宏体内字面量也报错，`bsp/board_led.c:14-15` 的 `5U`/`16U`、`app/main.c:12` 的 `500U` 会让 good、bad-layering、bad-toggle-late、bad-isr-name、bad-isr-heavy 的 barrc 意外 FAIL；建议单独实测该项。
6. **规则/profile 引用不当**：`checks.arch_lint.rules` 含 ARCH-003（profiles 仅 mcu-rtos），在 mcu-baremetal 工程不可能触发；eval 引用的 `evals/TRIAGE.md` 与 `docs/validation-report.md` 在工作区内都不存在。
7. **bad-isr-heavy 的额外违规**：`app_led_service` 只有两处手写 extern 声明、无公共头原型（C-002，mcu-baremetal mandatory），除 ISR-001 外还引入第二个未被任何自动检查或 note 覆盖的问题。

## `zephyr-app`

## zephyr-app

| 变体 | 结论 | 理由（一两句，引用文件与行或工具行为） |
|---|---|---|
| good | AGREE | 三条检查均 PASS 且与配置一致：Zephyr v4.5 的 `.clang-format` 有 `InsertBraces: true`、`AlignConsecutiveMacros: AcrossComments`、`UseTab: ForContinuationAndIndentation`，`include/app/frame_parser.h:13-14` 的宏空格对齐正是其产物；`main.c:24` 有 `device_is_ready`，`frame_parser.c:24-29` 先查上限再查剩余长度，PROTO-001/002、ZEP-001/002/004/005/007/009、C-003/004/010/016、TEST-001 均未违反。 |
| bad-cpp-comment | AGREE | 仅 `src/frame_parser.c:24` 把块注释改成 `//`：checkpatch 以 `ERROR("C99_COMMENTS", …)`（checkpatch.pl:4203）失败，clang-format 不改注释风格、语义不变，故 `checkpatch` FAIL（原因就是 ZEP-002）+ 其余 PASS 正确。 |
| bad-no-braces | AGREE | `frame_parser.c:25` 单语句 `if` 去花括号：Zephyr checkpatch 用 `WARN("BRACES", "braces {} are required around if/while/for/else")`（checkpatch.pl:5855），WARN 置 `$clean=0`（2372-2375）→ 主循环 `!process()` 使 `$exit=1`；Zephyr `.clang-format` 的 `InsertBraces: true` 使 clang-format 报 25-26 行差异 → 两个 FAIL 都恰对应 ZEP-001。 |
| bad-no-length-check | AGREE | 删掉 `len > FRAME_MAX_PAYLOAD`（good 的 frame_parser.c:25-27）：`test_oversized_length_rejected`（tests/parser/src/main.c:36-42）中 size=35、len=32，`size < len+3` 恰好为假，sum=0x20 而 `buf[34]=0` → 返回 `-EBADMSG` 而非 `-EMSGSIZE`，只有该用例失败，与 note 一致；缺陷真实（`memcpy(out->payload, &buf[2], len)` 现可越界写）。 |
| bad-checksum-ignored | AGREE | 校验和只算不比（`(void)sum;`，frame_parser.c:38），`test_bad_checksum_rejected` 期望 `-EBADMSG` 得到 0 → twister FAIL；checkpatch/clang-format 无相关诊断，预期 PASS 成立，`defect` 未映射规则也不矛盾。 |
| bad-no-device-ready | AGREE | `main.c:24-28` 删掉 `device_is_ready` 改为直接用 `console->name`：应用场景 `sample.yaml:4-5` 是 `build_only: true`，ztest 只链接 `tests/parser/src/main.c` 与 `../../src/frame_parser.c`，`main()` 从不执行，三检查都观察不到——known_gap 结论成立（但给出的机理见下）。 |

其他发现：

1. 规则→检查映射与 `rules.yaml` 不符：ZEP-001/ZEP-002 的 `verify.tool` 登记为 `zephyr_compliance`（rules.yaml:1013、1027），`profiles/zephyr.yaml` 的 gates 也只列 `zephyr_compliance`+`twister`；eval.yaml:11/15 却把 checkpatch/zephyr_format 记成这两条规则的检查，`check_compliance.py` 从未运行，ZEP-010 因此完全无检查。建议改成临时工具映射或补齐 `zephyr_compliance`。
2. `checkpatch` 未加 `--strict`：`CHK()` 在 `$check` 为假时不输出（checkpatch.pl:2382），"Unbalanced braces around else"（5863）、"Blank lines aren't necessary…"（5868/5875）等 ZEP-001 相关检查被静默跳过；bad-no-braces 能 FAIL 纯因 Zephyr 把该检查实现为 WARN（5855），而 Linux 上游同位置是语义相反的 CHK——该预期依赖 Zephyr fork 版本（当前 v4.5.0），eval 未固定版本。
3. `checkpatch` 非自包含：因 `cd {zephyr_base}`，`which_conf` 会读 `./.checkpatch.conf` 与 `$HOME/.checkpatch.conf`（checkpatch.pl:1242）。Zephyr 配置带入 `--max-line-length=100`、`--ignore SPDX_LICENSE_TAG/COMPARISON_TO_NULL/…`：ZEP-001 的行宽实际由该配置决定，SPDX 头完全不校验，用户级配置还能改变结论。
4. 两条静态检查范围不一致：checkpatch 扫整个 `$PWD`（仅排除 `*/build/*`），zephyr_format 只扫 `src include tests`；根目录或第三方向 C 文件会得到分叉结论。
5. `zephyr_format` 依赖 clang-format 认得 Zephyr `.clang-format` 的键（`InsertBraces`≥15、`InsertNewlineAtEOF`≥16），而 `requires: [clang-format]` 未固定最低版本；旧版本会把未知键当错误，使 good FAIL、bad-no-braces 的 `zephyr_format: FAIL` 变成“版本错误”而非格式违反。
6. `twister` 无 `blocked_codes`：venv/工具链缺失会判 FAIL 而非 BLOCKED（linux-kernel 项目用了 77），环境问题会污染规则结论；`requires` 里也没有 `west`/gcc 版本约束。
7. eval.yaml:3 声称“预期结果在运行前写定”，但 eval.yaml:31 的 note 明说 bad-no-braces 的 checkpatch 预期是首次运行后发现并改的；引用的 `evals/TRIAGE.md` 不在交付目录内，无法核验。
8. `bad-no-device-ready` 的 known_gap 论证不完整：真正未被发现的原因是应用场景 `build_only: true` 且 ztest 不链接 `src/main.c`（`main()` 从不执行），“console 设备在 native_sim 上总是就绪”这条没有任何检查或测试证据支撑。
9. 覆盖缺口：`bad-no-length-check` 同时违反 GEN-010（rules.yaml:177-183，“外部输入使用前校验长度与范围”），variants 只登记了 PROTO-001；且现有用例只验证返回码（tests/parser/src/main.c:38-42 的 len=32 帧校验和错误），校验和匹配的超长帧（真正触发 `memcpy` 越界写）没有用例。
