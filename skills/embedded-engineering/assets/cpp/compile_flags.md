# C++ 编译与链接选项（MCU，T0–T2）

以下选项已在 `assets/cpp/templates/` 上用 arm-none-eabi-g++ 15.3（C++17/C++20，Cortex-M0+/M4/M7）加 `-Werror` 验证。T3（Linux 用户态）按项目选项，至少保留告警组。

## 语言运行时

```text
-fno-exceptions -fno-rtti
-fno-use-cxa-atexit                 # 静态析构不注册 atexit（MCU 上永不执行）
-fno-threadsafe-statics             # 仅当所有函数局部静态都在调度器启动前或单线程中首次触达
```

Clang 另加 `-fno-c++-static-destructors`。

## 尺寸与诊断

```text
-Os -ffunction-sections -fdata-sections
-Wl,--gc-sections -Wl,--print-memory-usage -Wl,-Map=<app>.map
-fstack-usage -Wstack-usage=<任务栈预算字节>
```

## 告警（自有代码 -Werror）

```text
-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Wold-style-cast
-Wnon-virtual-dtor -Woverloaded-virtual -Wcast-align -Wdouble-promotion
-Wnull-dereference -Wimplicit-fallthrough -Wundef
```

- C++20 默认启用 `-Wvolatile`：`volatile` 对象的 `++`、`--`、复合赋值已弃用，旧寄存器代码迁移时会报错。
- 第三方头文件（ETL、CMSIS、厂商 SDK、RTOS）必须以 `-isystem` 引入，否则严格告警会在其头文件中报错（实测 ETL 触发 `-Wold-style-cast`）。

## CMake 片段

```cmake
set(CMAKE_CXX_STANDARD 17)          # 方案：C++17 基线；模块需要时整体切到 20
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
target_compile_options(app PRIVATE
  $<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions -fno-rtti -fno-use-cxa-atexit>
  -ffunction-sections -fdata-sections -fstack-usage)
target_include_directories(app SYSTEM PRIVATE third_party/etl/include)
target_link_options(app PRIVATE -Wl,--gc-sections -Wl,--print-memory-usage -Wl,-Map=app.map)
```

## 链接脚本

把 `linker_discard.ld` 中的 `/DISCARD/` 段并入项目链接脚本，丢弃永不执行的静态析构与终结函数。

## 可选：重定向 libstdc++ 抛异常辅助函数

即使 `-fno-exceptions`，libstdc++ 预编译库中的 `std::__throw_*` 仍可能被链接，并带入 snprintf/malloc。可用 `-Wl,--wrap=<mangled>` 把它们重定向到项目故障处理函数，例如：

```text
-Wl,--wrap=_ZSt17__throw_bad_allocv
-Wl,--wrap=_ZSt20__throw_length_errorPKc
-Wl,--wrap=_ZSt20__throw_out_of_rangePKc
-Wl,--wrap=_ZSt24__throw_out_of_range_fmtPKcz
```

然后实现对应的 `extern "C" [[noreturn]] void __wrap__ZSt20__throw_length_errorPKc(const char*)`，在其中进入故障处理。完整列表见 Pigweed `docs/sphinx/size_optimizations.rst`。用 `scripts/cpp_cost.py check` 确认 `throw_helpers` 类符号已消失。

## LTO

默认关闭。LTO 会与链接脚本的段放置（TCM、RAM 函数）冲突，增加调试和崩溃栈分析难度。只在空间不足时开启，开启后完整回归并复核崩溃报告。
