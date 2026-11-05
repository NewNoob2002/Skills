# C++ 单元测试、Mock、静态分析、开销评估与 HIL

证据分级沿用 [workflows/workflow.md](../workflows/workflow.md)：host、静态、仿真、HIL、实测各自给出 `PASS / FAIL / NOT_RUN / BLOCKED`。

## 1. 框架选择

| 代码 | 默认 | 备选 |
| --- | --- | --- |
| C 模块（MCU） | Ceedling（[verification/ceedling.md](ceedling.md)） | CppUTest（与 C++ 统一时） |
| C++ 模块（MCU） | **CppUTest** + CppUMock | GoogleTest/gMock（仅 host，项目已使用时）；Pigweed 项目用 `pw_unit_test` |
| Zephyr 应用（C/C++） | ztest + Twister（[platforms/zephyr.md](../platforms/zephyr.md)） | 纯逻辑可额外用 CppUTest |
| Linux 用户态 C++ | 项目既有框架；无则 CppUTest | GoogleTest（项目已使用时） |

## 2. CppUTest 要点

模板：`assets/cpp/templates/tests/`（`test_bme280.cpp`、`support/vendor_i2c_mock.cpp`、`all_tests.cpp`、`CMakeLists.txt`）。

```sh
# 安装 CppUTest（发布版 v4.0）。CMake ≥ 4 需要策略参数，因为 v4.0 声明的最低版本低于 3.5。
cmake -S cpputest -B build-cpputest -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DTESTS=OFF \
      -DCMAKE_INSTALL_PREFIX=$HOME/.local/cpputest
cmake --build build-cpputest && cmake --install build-cpputest

# 主机测试
cmake -S tests -B build-host -DETL_INCLUDE_DIR=<etl>/include -DCMAKE_PREFIX_PATH=$HOME/.local/cpputest
cmake --build build-host && ctest --test-dir build-host --output-on-failure
build-host/host_tests -r2 -s        # 重复两次 + 随机顺序：暴露测试间残留的静态状态
```

已验证的注意事项：

- **CppUTest 头文件必须最后包含**。其内存泄漏检测把 `new` 定义为宏，之后包含的 STL/ETL 头里的 placement new（`::new (p) T`）会编译失败。
- **目标名随版本不同**：v4.0 发布版导出 `CppUTest`、`CppUTestExt`，master 另有 `CppUTest::` 别名。模板 `CMakeLists.txt` 两种都支持。
- 内存泄漏检测在静态分配设计中仍应保留，它能捕获意外的 `new`。测试构建不要链接 `heap_guard.cpp`（与 CppUTest 的 `new` 替换冲突）。
- host 测试不必使用 `-fno-exceptions`，但严格告警组与 ASan/UBSan 必须开启。生产代码的 `-fno-exceptions -fno-rtti` 由目标机构建保证。
- CppUMock 参数类型必须两侧一致：实际调用中把 `uint8_t`、`size_t` 统一转成 `unsigned int`，期望值写 `0x76U`。
- 断言写法：
  - `expectOneCall(...).withParameter(...).withOutputParameterReturning(...).andReturnValue(...)`
  - `actualCall(...).withOutputParameter(...).returnIntValueOrDefault(...)`
  - 每个测试组的 `teardown()` 中调用 `mock().checkExpectations(); mock().clear();`
- 上板运行：CppUTest 可裁剪（`CPPUTEST_STD_C_LIB_DISABLED`、`CPPUTEST_MEM_LEAK_DETECTION_DISABLED`），附 IAR/armcc 移植，经半主机或 RTT 输出结果。

## 3. 接缝（依赖注入）

| 接缝 | 形式 | 运行期开销 | 适用 |
| --- | --- | --- | --- |
| 编译期 | 模板参数换成 `FakeBus`（`Bme280<FakeBus>`） | 0 | 首选：驱动与模块 |
| 链接期 | 测试构建链接 `vendor_i2c_mock.cpp`，不链接 SDK | 0 | bsp 包装层、厂商 C API |
| C 函数 mock | CppUMock（C 代码用 `mock_c()`）或 Ceedling CMock | 仅测试 | 厂商 C API |
| 运行期 | 纯虚接口的 Fake 实现 | vtable | 生产代码本身已需运行期多态时 |
| 预处理 | `#ifdef UNIT_TEST` | 0 | 最后手段，需说明理由 |

期望值来自规格与数据手册（例如 BME280 chip_id 0x60、复位命令 0xB6），不复制实现的计算结果。

## 4. 编译期测试

- `static_assert` 覆盖配置计算：波特率、分频、缓冲区大小与对齐、结构体布局、`is_always_lock_free`。
- **负向编译测试**：断言非法配置必须编译失败，防止约束被意外放宽。
  - 做法：CMake `try_compile` 或脚本检查编译失败且输出含预期信息。
  - 本技能的示例：`tests/cpp/neg_*.cpp`，包括波特率超差、不合规总线、ARMv6-M 上的 `SpscRing`、DMA 缓冲区未按 cache 行对齐。

## 5. 静态分析

| 工具 | 配置 | 说明 |
| --- | --- | --- |
| 编译器 | `assets/cpp/compile_flags.md` 告警组 + `-Werror` | 第三方头用 `-isystem` |
| clang-tidy | `assets/cpp/.clang-tidy`；`platform/` 用 `clang-tidy-platform.yaml` | 关闭项及原因写在配置注释中 |
| clang-format | `assets/cpp/.clang-format`（C++）/ `assets/barr-c/.clang-format`（C） | 按文件类型分开调用 |
| arch_lint | `scripts/arch_lint.py`（同时扫描 `.c/.h/.cpp/.hpp/.cc/.hh`） | 分层依赖、HAL 调用、寄存器访问 |
| Clang `-Wthread-safety` | 锁注解宏 | 可选 |
| cppcheck | — | 补充 |
| MISRA C++:2023 | 商业工具 | 功能安全项目 |

## 6. 开销评估（Flash / RAM / 栈 / 时间）

原则：同一工具链、同一选项下做 A/B 对比（基线提交与候选提交），只看增量。[cpp/features.md](../cpp/features.md) 中的微基准只作先验，最终以项目 ELF 为准。

| 指标 | 方法 | 门禁 |
| --- | --- | --- |
| 禁用运行时符号 | `scripts/cpp_cost.py check app.elf --tier T1` | fail 级发现即失败；已评审的例外用 `--allow <class>` 并在评审记录中说明 |
| 段预算 | `cpp_cost.py check app.elf --tier T1 --budget budget.json`（键：`text_max data_max bss_max flash_max ram_max`） | 超出即失败 |
| 增量 | `cpp_cost.py diff base.elf new.elf --top 20` | 报告中附段增量与前 20 符号 |
| 工具链复现 | `scripts/bench/run.sh --cpu <cpu> [--float-abi soft] --etl <etl>/include` | 新工具链/新选项落地时运行一次 |
| 栈 | `-fstack-usage` + 调用图最坏路径；运行期水位线 | 每个任务余量 ≥ 项目阈值 |
| 执行时间 | Cortex-M3+：DWT `CYCCNT` 包围被测代码；ISR 时延/抖动：GPIO 翻转 + 逻辑分析仪；M0/M0+：SysTick 或 GPIO | 关键路径实测分布进报告；未测记 `NOT_RUN` |
| 启动时间 | 复位到 `main()`、到调度器启动的 GPIO 标记 | 全局构造增多时复测 |

`cpp_cost.py` 的符号类别：

| 类别 | 含义 | T0 | T1 | T2 | T3 |
| --- | --- | --- | --- | --- | --- |
| `exceptions` | 异常运行时（unwinder、personality） | fail | fail | fail | info |
| `rtti` | `typeinfo` | fail | fail | fail | info |
| `iostream` | 流 | fail | fail | fail | info |
| `throw_helpers` | `std::__throw_*` | fail | fail | warn | info |
| `static_dtor` | atexit 注册 | fail | fail | warn | info |
| `atomic_libcall` | `__atomic_*_N` 库实现 | fail | fail | warn | info |
| `heap` | `malloc`、`operator new` 等 | fail | warn | warn | info |
| `local_static_guard` | `__cxa_guard_*` | fail | warn | warn | info |
| `stdio_format` | printf 族 | fail | warn | warn | info |

报告模板：

```markdown
| 指标 | 基线 | 候选 | 增量 | 预算 | 结果 |
| --- | --- | --- | --- | --- | --- |
| flash (text+data) | 51234 | 51490 | +256 | 60000 | PASS |
| ram (data+bss) | 9876 | 9876 | 0 | 12000 | PASS |
| 受限符号（T1） | — | heap(warn: heap_guard) | — | — | PASS |
| 控制环 WCET（DWT，1e5 次） | 41.2 µs | 41.9 µs | +0.7 µs | 50 µs | PASS |
| ISR 时延（逻辑分析仪） | — | — | — | — | NOT_RUN（无台架） |
```

## 7. HIL / 上板

沿用现有证据分级。C++ 特有的检查项：

- **全局构造全部执行**：调试构建中让构造函数置位标记，启动自检确认；或检查 `.init_array` 条目数与 map 文件一致。
- **ISR 向量指向 C++ 实现**：调试器中查看向量表地址，不能是 `Default_Handler`。
- **栈水位线**在预算内。
- **RT 路径时序**满足预算。
- **`heap_guard` 锁定后**不再有分配：故障计数为 0。
