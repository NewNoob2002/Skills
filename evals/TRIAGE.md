# 验证工程首次运行的不一致分诊

预期结果在运行前写定。运行结果与预期不符时，先判断属于哪一类，再修正对应的一方；任何一方都不悄悄改动。

| # | 工程 / 变体 | 现象 | 分类 | 处理 |
| --- | --- | --- | --- | --- |
| 1 | `mcu-baremetal-c` / 全部 | `ceedling test:all` 在 good 上失败：`Config path :paths ↳ :include => 'driver' does not exist` | **技能模板缺陷**：`assets/ceedling/project.yml` 默认列出 `driver/`、`tests/support`，Ceedling 1.2.2 对不存在的路径报配置错误。此前该模板从未实际运行（README 记为 NOT_RUN） | 模板与 `references/verification/ceedling.md` 注明需删除不存在的目录；本工程按文档流程使用调整后的 `project.yml` |
| 2 | `mcu-baremetal-c` / `bad-signed-bitwise` | 预期 barrc FAIL，实际 PASS | **工具配置缺陷**：LLVM 23 的 clang-tidy 移除了 `hicpp-signed-bitwise`，并静默忽略未知检查名，BARR-C 5.3.b（`C-005`）实际上从未被检查 | `assets/barr-c/.clang-tidy` 与 `assets/cpp/.clang-tidy` 同时列出 `bugprone-signed-bitwise`；`tests/test_scripts.py` 增加“配置中的检查名必须能被已安装的 clang-tidy 识别”的回归测试；`THIRD_PARTY_NOTICES.md` 记录对第三方文件的修改 |
| 3 | `mcu-baremetal-c` / `bad-layering` | 预期 unit PASS，实际 FAIL（`board_led.h: No such file or directory`） | **预期错误**：误以为 Ceedling 的 `:source` 目录也是头文件搜索路径 | 预期更正为 unit FAIL，原因写入 `eval.yaml` 的 `note` |
| 4 | `freertos-cpp` / 全部 | `rtos_host` 在 good 上失败：`#error Only one of configUSE_16_BIT_TICKS and configTICK_TYPE_WIDTH_IN_BITS must be defined` | **样例错误**：我写的 host `FreeRTOSConfig.h` 同时定义了新旧两个节拍宽度宏，FreeRTOS 11 不允许 | 删除 `configUSE_16_BIT_TICKS`；其余 8 个变体的其他检查在首次运行时已全部符合预期 |
| 5 | `zephyr-app` / 全部 | Twister 在 good 上失败：应用构建 `undefined reference to '__device_dts_ord_24'` | **样例错误**：`DEVICE_DT_GET(DT_CHOSEN(zephyr_console))` 引用的串口设备在 `prj.conf` 中没有启用驱动（缺 `CONFIG_SERIAL=y`）。这也说明 Twister 的构建检查能发现“devicetree 引用了设备但驱动未启用” | `prj.conf` 增加 `CONFIG_SERIAL=y` |
| 6 | `zephyr-app` / `bad-no-braces` | 预期 checkpatch PASS，实际 FAIL（`braces {} are required around if/while/for/else`） | **预期错误**：按 Linux 版 checkpatch 推断它不要求花括号；Zephyr 树内的 checkpatch 已改为强制花括号 | 预期更正为 checkpatch FAIL，`ZEP-001` 加入 checkpatch 的 `rules` |
| 7 | `zephyr-app` / `bad-no-device-ready` | 预期 twister PASS，实际 FAIL：`'console' defined but not used [-Werror=unused-const-variable=]` | **变体样例错误**：删去就绪检查后设备变量不再被使用，Twister 默认 `-Werror` 使构建失败，失败原因不是被测缺陷 | 变体改为“使用设备（`console->name`）但不检查就绪”，与真实缺陷一致 |

## 第二轮：新增 QEMU 目标测试与 linux-kernel-module 工程（2026-11-05）

`mcu-baremetal-c` 新增 `qemu` 检查（`make qemu`：链接成 mps2-an386 镜像，在 qemu-system-arm 中运行目标冒烟测试）及变体 `bad-isr-name`；新建工程 `linux-kernel-module`。预期在首次运行前写定，以下是不一致项：

| # | 工程 / 变体 | 现象 | 分类 | 处理 |
| --- | --- | --- | --- | --- |
| 8 | `mcu-baremetal-c` / `bad-hal-call`、`bad-implicit-decl` | 预期 qemu PASS（未在 expect 中列出），实际 FAIL | **预期遗漏**：新增检查时没有逐个变体更新预期。失败原因已核对：前者链接时 `undefined reference to 'HAL_Delay'`，后者编译失败，均与变体缺陷对应 | 两个变体的 expect 加入 `qemu: FAIL`（这两项是在看到结果后补的，不算事前预期） |
| 9 | `mcu-baremetal-c` / `bad-isr-heavy` | 目标镜像链接失败：`app_led_service` 未定义 | **变体样例错误**（原有）：变体的 ISR 调用了一个从未定义的函数；`cross` 只编译不链接，此前没有暴露 | 变体补充 `app/main.c`，在 app 层定义 `app_led_service()`；变体仍是 ISR-001 的已知漏报 |
| 10 | `mcu-baremetal-c` / `bad-isr-heavy` | 补充 `app/main.c` 后 barrc FAIL | **变体样例错误**：新加的注释行超过 clang-format 行宽 | 注释折行 |
| 11 | `linux-kernel-module` / `bad-binding-*` | 两个 binding 变体的 dt_binding 预期 FAIL，实际 PASS | **检查脚本缺陷**：`check_binding.sh` 中 `cmd 2>&1 > file` 把 stderr 留在终端，判断“输出非空”时只看到 stdout。另外实测 `dt-doc-validate` 报错时退出码仍为 0，所以脚本必须以输出判断 | 改为 `> file 2>&1`；修正前已在临时副本上确认两个缺陷都会被 dtschema 报告 |
| 12 | `linux-kernel-module` / `bad-sleep-in-hardirq` | 预期为已知漏报（全部 PASS），实际 checkpatch FAIL | **变体设计问题**：checkpatch 报的是 `msleep < 20ms can sleep for up to 20ms`，即计时精度，与“硬中断中睡眠”无关 | 变体改用 `usleep_range(1000, 2000)`，以隔离 LNXK-006；checkpatch 对 `msleep` 的计时告警是实际存在的覆盖，但不能算作检出本规则 |

## 第三轮：独立复核（2026-11-05）

验证工程的预期与样例由同一作者编写，独立性不足，因此用另一个模型做只读复核：给出 5 个工程的定义、样例与技能检查脚本，逐变体判断“是否确实违反所列规则”“预期是否符合工具实际行为”“known_gap 是否属实”“good 是否本身违规”。复核者与编写者、与被测 Agent 均不同源，但与最终评委是同一模型（`magpie/workbuddy/deepseek-v4.1-flash`，只读工具，输出见 `docs/independent-review.md`）。

43 个变体（含 5 个 good）中 40 个判定为 AGREE，2 个判定为 DISAGREE（`freertos-cpp` 与 `linux-userspace` 的 good），1 个为 UNSURE（`freertos-cpp` / `bad-std-function` 的失败机制，已用实际 ELF 输出确认）。另有 2 个 good 样例的违规记在复核报告的“其他发现”里（`mcu-baremetal-c` 的 `C-008`、`linux-kernel-module` 的 `LNXK-005`），合计 4 个 good 样例违反强制规则，均已修正；另有若干 note 与实际机制不符，已更正。

| # | 工程 / 变体 | 现象 | 分类 | 处理 |
| --- | --- | --- | --- | --- |
| 13 | `freertos-cpp` / `good` | `app_main.cpp` 用 `volatile` 保存普通 RAM 值 | **样例违规**：CPP-012 只允许 volatile 用于 MMIO/DMA；本工程没有 `cpp_compiler_flags` 检查，C++17 下 `-Wvolatile` 也不报 | 去掉 `volatile`；变体重叠文件不受影响，重跑 MATCH |
| 14 | `linux-userspace` / `good` | `config_save` 对目录 fd 用 `(void)sysio_close(fd)` 丢弃返回值；`snprintf` 只判 `>= sizeof` | **样例违规**：LNXU-001 要求检查每个系统调用返回值；负返回值时 `tmp` 内容未定义（GEN-010 边界） | 改为检查 close 返回值并将 `snprintf` 负数与截断分开处理 |
| 15 | `mcu-baremetal-c` / `good` | `board_regs.h` 的寄存器结构体没有显式保留字段与长度校验 | **样例违规**：C-008 要求防填充并用 `static_assert(sizeof)` 校验；C99 无 `_Static_assert` | 补显式保留字（`RESERVED` 数组）与负数组长度校验；宏定义尺寸常量，避免 `readability-magic-numbers` 与 typedef 命名门禁报错 |
| 16 | `linux-kernel-module` / `good` | probe 中 `devm_platform_ioremap_resource` 与 `platform_get_irq` 的错误路径直接 `return` | **样例违规**：LNXK-005 要求 probe 错误路径用 `dev_err_probe()` 并处理 `-EPROBE_DEFER`（`platform_get_irq` 正是会返回它的路径） | 两处改为 `dev_err_probe()`；kbuild 与 checkpatch 重跑 PASS |
| 17 | `linux-kernel-module` / `bad-missing-static` | note 称失败来自“W=1 的 -Wmissing-prototypes” | **说明错误**：该告警在 `$KDIR/scripts/Makefile.warn` 的默认组（第 20-21 行），与 W=1 无关；`-Werror` 才让退出码非零 | 更正 note 与模块 Makefile 注释 |
| 18 | `mcu-baremetal-c` / `bad-hal-call` | note 称 barrc 失败来自“命名门禁报函数名非小写” | **说明错误**：`check.sh` 的命名门禁只比对文件名；实际触发者是 `.clang-tidy` 的 `readability-identifier-naming.FunctionCase`，规则体系里没有对应 ID | 更正 note |
| 19 | `freertos-cpp` / `bad-std-function` | note 称 `cpp_cost` 检出堆分配 | **说明错误**：`this` 捕获是 location-invariant 且小于 libstdc++ 的 SBO 缓冲，ELF 无 `operator new`；实际命中 `throw_helpers`（`std::__throw_bad_function_call`） | 按实际输出更正 note |
| 20 | `linux-userspace` / `bad-name-overflow` | 违反规则记为 `PROTO-001` | **规则引用错误**：长度字段已按输入剩余长度校验，缺的是输出缓冲区容量校验（接口契约，GEN-010），不是帧长检查 | `violates` 改为 `[GEN-010]` 并在 note 说明区别 |
| 21 | `zephyr-app` / `bad-no-device-ready` | known_gap 称“console 在 native_sim 上总是就绪” | **说明错误**：未发现的原因是 sample 为 `build_only`、ztest 不链接 `src/main.c`，`main()` 从不执行；该断言没有证据 | 按实际执行路径更正 known_gap |
| 22 | `freertos-cpp` / `format`、`unit` | `format` 记为 `CPP-015`（严格告警组），`unit` 只声明 `libCppUTest.a` | **映射/依赖错误**：CPP-015 与 clang-format 无关，规则体系没有 C++ 排版规则；Makefile 同时链接 `libCppUTestExt.a` | 删除 `format.rules` 并注明原因；`unit.requires` 补 `libCppUTestExt.a` |

复核提出的其余问题不改变结论，作为已知局限记录在 `docs/validation-report.md` §5：`unit`↔`TEST-002`、`cppcheck`↔`GEN-010`、ZEP-001/002 的 `verify.tool`（`zephyr_compliance`）与 eval 实际使用的 checkpatch/clang-format 不一致；`sparse` 从未执行；barrc 不覆盖头文件内容；`twister`、`dt_binding` 无 `blocked_codes`，环境缺失会记 FAIL 而非 BLOCKED。
