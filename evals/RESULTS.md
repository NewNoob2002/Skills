# 验证工程运行结果

生成时间：2026-11-05 13:01:38；技能提交：`e586ced`。本文件由 `tools/run_evals.py` 生成，不要手改。

变体结论：MATCH 32，MISMATCH 0，NOT_RUN 0。

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

## linux-userspace（profile `linux-userspace`）

守护进程基础库：写满全部字节（部分写与 EINTR）、配置原子保存、消息名解析、信号处理；Ceedling + CMock + ASan/UBSan。

| 变体 | 违反的规则 | 结论 | warnings | cppcheck | unit |
| --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS |
| `bad-partial-write` | `LNXU-001` | MATCH | PASS | PASS | FAIL |
| `bad-eintr` | `LNXU-001` | MATCH | PASS | PASS | FAIL |
| `bad-unchecked-fsync` | `LNXU-001`, `LNXU-002` | MATCH | PASS | PASS | FAIL |
| `bad-nonatomic-save` | `LNXU-002` | MATCH | PASS | PASS | FAIL |
| `bad-name-overflow` | `GEN-010`, `PROTO-001` | MATCH | PASS | PASS | FAIL |
| `bad-signal-printf` | `LNXU-004` | MATCH | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-signal-printf`：LNXU-004 是 review 规则：编译告警、cppcheck 与单元测试都不检查信号处理函数中是否只调用 async-signal-safe 函数

## mcu-baremetal-c（profile `mcu-baremetal`）

分层的 LED 控制固件：interface + module/ledctl + bsp + platform 向量入口 + app 组合根；Ceedling 测试 ledctl。

| 变体 | 违反的规则 | 结论 | arch_lint | barrc | warnings | cross_build | unit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS | PASS | PASS |
| `bad-layering` | `ARCH-001` | MATCH | FAIL | PASS | PASS | PASS | FAIL |
| `bad-hal-call` | `ARCH-004` | MATCH | FAIL | FAIL | PASS | PASS | FAIL |
| `bad-signed-bitwise` | `C-005` | MATCH | PASS | FAIL | PASS | PASS | PASS |
| `bad-implicit-decl` | `C-014` | MATCH | PASS | FAIL | FAIL | FAIL | FAIL |
| `bad-missing-braces` | `CFMT-002` | MATCH | PASS | FAIL | PASS | PASS | PASS |
| `bad-toggle-late` | 缺陷：ledctl_tick 用 > 代替 >=，LED 晚一个节拍翻转 | MATCH | PASS | PASS | PASS | PASS | FAIL |
| `bad-isr-heavy` | `ISR-001` | MATCH | PASS | PASS | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-isr-heavy`：ISR-001 是 review 规则：platform/ 不在 BARR-C 门禁范围内，arch_lint 不检查 ISR 内容，自动检查全部通过

## zephyr-app（profile `zephyr`）

协议帧解析库 + 应用（device_is_ready、LOG_*）+ ztest 测试套件；Twister 在 native_sim/native/64 上构建应用并运行测试。

| 变体 | 违反的规则 | 结论 | checkpatch | zephyr_format | twister |
| --- | --- | --- | --- | --- | --- |
| `good` | — | MATCH | PASS | PASS | PASS |
| `bad-cpp-comment` | `ZEP-002` | MATCH | FAIL | PASS | PASS |
| `bad-no-braces` | `ZEP-001` | MATCH | FAIL | FAIL | PASS |
| `bad-no-length-check` | `PROTO-001` | MATCH | PASS | PASS | FAIL |
| `bad-checksum-ignored` | 缺陷：解析器不比较校验和 | MATCH | PASS | PASS | FAIL |
| `bad-no-device-ready` | `ZEP-004` | MATCH | PASS | PASS | PASS |

已知漏报（自动检查不能发现，需 review 或 test 补足）：

- `bad-no-device-ready`：ZEP-004 是 review 规则：checkpatch、clang-format 与 native_sim 上的构建和测试都不能发现缺少就绪检查（console 设备在 native_sim 上总是就绪）

## 规则覆盖

`verify.method: auto` 的规则共 44 条，被至少一个变体违反并检验的有 13 条：`ARCH-001`, `ARCH-004`, `C-005`, `C-014`, `CFMT-002`, `CPP-001`, `CPP-002`, `CPP-004`, `CPP-005`, `CPP-008`, `CPP-009`, `ZEP-001`, `ZEP-002`。

所有 `coverage: full` 的规则都至少被一个变体检验。
