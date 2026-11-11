# 验证工程运行结果

生成时间：2026-11-06 19:25:13；技能提交：`fa6f054-dirty`。本文件由 `tools/run_evals.py` 生成，不要手改。

变体结论：MATCH 43，KNOWN_GAP 7，MISMATCH 0，NOT_RUN 0。
良好样例通过 6；问题变体检出 37 + 已知漏报 7。

## esp-idf-app（profile `esp-idf`）

帧解析组件（host 可测）+ GPIO 事件计数组件（IRAM ISR、portMUX 自旋锁、ESP_RETURN_ON_ERROR）+ OTA 回滚确认的应用；分别为 esp32 与 esp32s31 构建。

| 变体 | 违反的规则 | 结论 | build_esp32 | build_esp32s31 | iram_esp32 | iram_esp32s31 | host_test |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS | PASS | PASS |
| `bad-no-iram` | `ESP-002` | MATCH | PASS | PASS | FAIL | FAIL | PASS |
| `bad-xtensa-only` | `ESP-008` | MATCH | PASS | FAIL | PASS | BLOCKED | PASS |
| `bad-legacy-driver` | `ESP-009` | MATCH | FAIL | FAIL | BLOCKED | BLOCKED | PASS |
| `bad-no-length-check` | `PROTO-001` | MATCH | PASS | PASS | PASS | PASS | FAIL |
| `bad-disable-interrupts` | `ESP-001` | KNOWN_GAP | PASS | PASS | PASS | PASS | PASS |
| `bad-error-check-abort` | `ESP-004` | KNOWN_GAP | PASS | PASS | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-disable-interrupts`：ESP-001 是 review 规则：taskDISABLE_INTERRUPTS 只屏蔽当前核，构建与 host 测试都无法发现跨核竞争；需要双核目标上的压力测试或代码审查
- `bad-error-check-abort`：ESP-004 是 review 规则：两种用法都能编译，host 测试不覆盖该组件，错误路径只能在审查或故障注入中发现

未执行的检查：

- `iram_esp32`：needs build_esp32 (FAIL)
- `iram_esp32s31`：needs build_esp32s31 (FAIL)

## freertos-cpp（profile `mcu-rtos`）

C++17 遥测模块（滑动平均 + 纯虚输出接口）：Cortex-M0+ T0 目标构建与 cpp_cost 门禁、CppUTest 单元测试、FreeRTOS POSIX 集成测试。

| 变体 | 违反的规则 | 结论 | arch_lint | format | cross_build | cpp_cost | unit | rtos_host |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS | PASS | PASS | PASS |
| `bad-std-function` | `CPP-004` | MATCH | PASS | PASS | PASS | FAIL | PASS | PASS |
| `bad-std-vector` | `CPP-005` | MATCH | PASS | PASS | PASS | FAIL | PASS | PASS |
| `bad-local-static` | `CPP-009` | MATCH | PASS | PASS | PASS | FAIL | PASS | PASS |
| `bad-atomic-rmw` | `CPP-008` | MATCH | PASS | PASS | FAIL | BLOCKED | PASS | PASS |
| `bad-public-virtual-dtor` | `CPP-011` | MATCH | PASS | PASS | PASS | FAIL | PASS | PASS |
| `bad-throw` | `CPP-001` | MATCH | PASS | PASS | FAIL | BLOCKED | FAIL | FAIL |
| `bad-layering` | `ARCH-001` | MATCH | FAIL | PASS | PASS | PASS | PASS | PASS |
| `bad-average-divisor` | 缺陷：MovingAverage 总是除以窗口大小 N，未满窗口时平均值偏小 | MATCH | PASS | PASS | PASS | PASS | FAIL | PASS |
| `bad-consumer-deadlock` | 缺陷：consumer 任务在一个永远没有人写入的队列上等待 | MATCH | PASS | PASS | PASS | PASS | PASS | FAIL |
| `bad-rtti` | `CPP-002` | MATCH | PASS | PASS | PASS | FAIL | PASS | PASS |

未执行的检查：

- `cpp_cost`：needs cross_build (FAIL)

## linux-kernel-module（profile `linux-kernel`）

ACME 帧接收 platform 驱动（devm、线程化中断、spinlock、dev_err_probe）与 DT schema binding；运行内核头文件构建 W=1 -Werror、checkpatch --strict、dtschema 校验。

| 变体 | 违反的规则 | 结论 | kbuild | checkpatch | dt_binding |
| --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS |
| `bad-typedef` | `LNXK-002` | MATCH | PASS | FAIL | PASS |
| `bad-no-spdx` | `LNXK-007` | MATCH | PASS | FAIL | PASS |
| `bad-bug-on` | `LNXK-010` | MATCH | PASS | FAIL | PASS |
| `bad-missing-static` | `LNXK-009` | MATCH | FAIL | PASS | PASS |
| `bad-volatile-mmio` | `LNXK-004` | MATCH | PASS | FAIL | PASS |
| `bad-binding-no-additional` | `LNXK-008` | MATCH | PASS | PASS | FAIL |
| `bad-binding-example` | `LNXK-008` | MATCH | PASS | PASS | FAIL |
| `bad-hungarian` | `LNXK-002` | KNOWN_GAP | PASS | PASS | PASS |
| `bad-sleep-in-hardirq` | `LNXK-006` | KNOWN_GAP | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-hungarian`：LNXK-002 的命名部分是 review 规则：checkpatch 只报 typedef，不识别匈牙利命名或类型前缀
- `bad-sleep-in-hardirq`：LNXK-006 是 review 规则：构建与 checkpatch 都不检查中断上下文睡眠；运行期需 CONFIG_DEBUG_ATOMIC_SLEEP 在目标上发现

## linux-userspace（profile `linux-userspace`）

守护进程基础库：写满全部字节（部分写与 EINTR）、配置原子保存、消息名解析、信号处理；Ceedling + CMock + ASan/UBSan。

| 变体 | 违反的规则 | 结论 | warnings | cppcheck | unit |
| --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS |
| `bad-partial-write` | `LNXU-001` | MATCH | PASS | PASS | FAIL |
| `bad-eintr` | `LNXU-001` | MATCH | PASS | PASS | FAIL |
| `bad-unchecked-fsync` | `LNXU-001`, `LNXU-002` | MATCH | PASS | PASS | FAIL |
| `bad-nonatomic-save` | `LNXU-002` | MATCH | PASS | PASS | FAIL |
| `bad-name-overflow` | `GEN-010` | MATCH | PASS | PASS | FAIL |
| `bad-signal-printf` | `LNXU-004` | KNOWN_GAP | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-signal-printf`：LNXU-004 是 review 规则：编译告警、cppcheck 与单元测试都不检查信号处理函数中是否只调用 async-signal-safe 函数

## mcu-baremetal-c（profile `mcu-baremetal`）

分层的 LED 控制固件：interface + module/ledctl + bsp + platform 向量入口 + app 组合根；Ceedling 测试 ledctl。

| 变体 | 违反的规则 | 结论 | arch_lint | barrc | warnings | cross_build | qemu | unit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS | PASS | PASS | PASS |
| `bad-layering` | `ARCH-001` | MATCH | FAIL | PASS | PASS | PASS | PASS | FAIL |
| `bad-hal-call` | `ARCH-004` | MATCH | FAIL | FAIL | PASS | PASS | FAIL | FAIL |
| `bad-signed-bitwise` | `C-005` | MATCH | PASS | FAIL | PASS | PASS | PASS | PASS |
| `bad-implicit-decl` | `C-014` | MATCH | PASS | FAIL | FAIL | FAIL | FAIL | FAIL |
| `bad-missing-braces` | `CFMT-002` | MATCH | PASS | FAIL | PASS | PASS | PASS | PASS |
| `bad-toggle-late` | 缺陷：ledctl_tick 用 > 代替 >=，LED 晚一个节拍翻转 | MATCH | PASS | PASS | PASS | PASS | FAIL | FAIL |
| `bad-isr-name` | 缺陷：SysTick 中断入口名写成 Systick_Handler，与向量表不符，中断落到弱符号默认处理函数 | MATCH | PASS | PASS | PASS | PASS | FAIL | PASS |
| `bad-isr-heavy` | `ISR-001` | KNOWN_GAP | PASS | PASS | PASS | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-isr-heavy`：ISR-001 是 review 规则：platform/ 不在 BARR-C 门禁范围内，arch_lint 不检查 ISR 内容，自动检查全部通过；QEMU 不做周期精确仿真，目标测试也测不出 ISR 耗时（ISR-006 需上板实测）

## zephyr-app（profile `zephyr`）

协议帧解析库 + 应用（device_is_ready、LOG_*）+ ztest 测试套件；Twister 在 native_sim/native/64 上构建应用并运行测试。

| 变体 | 违反的规则 | 结论 | checkpatch | zephyr_format | twister |
| --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS |
| `bad-cpp-comment` | `ZEP-002` | MATCH | FAIL | PASS | PASS |
| `bad-no-braces` | `ZEP-001` | MATCH | FAIL | FAIL | PASS |
| `bad-no-length-check` | `PROTO-001` | MATCH | PASS | PASS | FAIL |
| `bad-checksum-ignored` | 缺陷：解析器不比较校验和 | MATCH | PASS | PASS | FAIL |
| `bad-no-device-ready` | `ZEP-004` | KNOWN_GAP | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-no-device-ready`：ZEP-004 是 review 规则：checkpatch 与 clang-format 不分析就绪检查；sample 是 build_only，ztest 只链接 tests/parser 与 src/frame_parser.c，src/main.c 的 main() 从不执行，设备是否就绪无从观察

## 规则覆盖

`verify.method: auto` 的规则共 47 条，被至少一个变体违反并检验的有 21 条：`ARCH-001`, `ARCH-004`, `C-005`, `C-014`, `CFMT-002`, `CPP-001`, `CPP-002`, `CPP-004`, `CPP-005`, `CPP-008`, `CPP-009`, `ESP-008`, `ESP-009`, `LNXK-002`, `LNXK-004`, `LNXK-007`, `LNXK-008`, `LNXK-009`, `LNXK-010`, `ZEP-001`, `ZEP-002`。

所有 `coverage: full` 的规则都至少被一个变体检验。
