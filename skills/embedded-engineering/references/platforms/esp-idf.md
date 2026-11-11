# ESP-IDF v6.x（ESP32 Xtensa 与 RISC-V 目标）

适用 profile：`esp-idf`。本文的主要 API、配置项和关键行为已对照 ESP-IDF Programming Guide v6.1 核对（2026-11-06，链接见文末）；未覆盖项见文末。用于具体芯片前，按 `sdkconfig` / `dependencies.lock` 中的实际 IDF 版本和目标芯片的技术参考手册（TRM）再核对；查不到的写 `UNKNOWN`（`GEN-002`）。

## 1. 版本与目标

- **IDF 版本**：v6.0 于 2026-03 发布（tag 2026-03-19，Release 2026-03-20），维护期 30 个月至 2028-09；v6.1 为当前次版本。先从仓库确认版本（`idf.py --version`、`dependencies.lock` 的 `idf` 条目、CI 镜像标签），不要假设。v5.x 工程迁移见 §9。
- **架构**：同一份组件代码可能编译到两种 CPU 架构，必须同时考虑：

| 目标 | CPU | 说明 |
| --- | --- | --- |
| ESP32 | Xtensa LX6 双核 | 经典目标；ECO3 之前用 Secure Boot v1，ECO3 起支持 v2 |
| ESP32-S31 | RISC-V 双核（最高 320 MHz）+ 低功耗 RISC-V 核 | **v6.1 中为 preview 目标**（`IDF_TARGET_ESP32S31` 选择 `IDF_ENV_BRINGUP`），尚未达到量产级支持；需要 esptool ≥ 5.3 |
| 其他 RISC-V 目标（ESP32-C 系列、ESP32-P4 等） | RISC-V 单核或多核 | 核数、ISA 扩展、外设按各自 TRM 与 `soc_caps.h` 核实 |

- 用 preview 目标做产品时，在报告中写明“IDF 对该目标为 preview”，驱动可用性与 API 稳定性逐项核实，不把 ESP32 上的结论直接套用。

## 2. 工程结构与编码规范

- 工程以**组件**组织：每个组件的 `CMakeLists.txt` 调用 `idf_component_register(SRCS … INCLUDE_DIRS … REQUIRES … PRIV_REQUIRES …)`；依赖写全，不靠隐式传递。外部组件经 `idf_component.yml` 声明、由组件管理器解析并锁定在 `dependencies.lock`，该文件纳入版本控制。
- 配置：可提交的默认值写在 `sdkconfig.defaults`（可按目标分 `sdkconfig.defaults.<target>`）；组件自己的选项写在 `Kconfig` / `Kconfig.projbuild`。v6 使用 esp-idf-kconfig v3，语法有变化。代码中按 `CONFIG_*` 与 `SOC_*` 能力宏分支，不按芯片名硬编码（§6）。
- **编码规范**（ESP-IDF Style Guide，`ESP-006`）：4 空格缩进、禁止 tab；函数定义的 `{` 单独一行，控制语句的 `{` 在同一行；行宽 120；仅本文件使用的对象一律 `static` 且静态变量用 `s_` 前缀；公共符号带组件前缀；typedef 以 `_t` 结尾；头文件用 `#pragma once` + `extern "C"` 保护；只用 LF。格式化工具是 Astyle（`astyle_py`，经 pre-commit），不是 clang-format。BARR-C 的格式/命名层不用于 ESP-IDF 组件，安全核心中不冲突的部分仍适用（见 [profiles.md](../profiles.md) §3）。
- v6 默认 C 方言 `gnu23`、C++ `gnu++26`，**默认把告警当错误**（可用 `CONFIG_COMPILER_DISABLE_DEFAULT_ERRORS=y` 关闭，不建议在产品代码中关闭）；默认 libc 为 Picolibc；CMake ≥ 3.22。
- 厂商生成或第三方组件（`managed_components/`、`components/` 中的上游副本）不重排、不改格式（`GEN-007`）。

## 3. FreeRTOS（IDF SMP 版本）与并发

IDF 默认的 FreeRTOS 基于 Vanilla v10.5.1 并加入 SMP 支持（实验性的 `CONFIG_FREERTOS_SMP` 仅限 `esp32`，会改用 Amazon SMP 内核 V11.1.0，细节按该内核核对），与原版有几处会导致错误代码的差异：

- **临界区是自旋锁**（`ESP-001`）：用 `portMUX_TYPE` 定义（静态初始化 `portMUX_INITIALIZER_UNLOCKED`，动态 `portMUX_INITIALIZE()`），任务中 `taskENTER_CRITICAL(&mux)` / `taskEXIT_CRITICAL(&mux)`，ISR 中 `taskENTER_CRITICAL_ISR(&mux)` / `taskEXIT_CRITICAL_ISR(&mux)`。临界区要短，不在其中调用 FreeRTOS API 或任何会阻塞、让出的函数；嵌套须配对，交叉使用不同自旋锁可能死锁。
- `taskDISABLE_INTERRUPTS()` 只作用于当前核，**不能**作为 SMP 互斥手段；`vTaskSuspendAll()` 只暂停调用核的调度，另一核上未绑核的任务照常运行，同样不是互斥手段（在 Core 0 上调用会推迟 tick 计数、延时任务处理与调度，恢复时补处理 pended ticks；硬件 tick 中断仍会发生）。
- **任务创建**：`xTaskCreatePinnedToCore()` / `xTaskCreateStaticPinnedToCore()` 的 `xCoreID` 取 `0`、`1` 或 `tskNO_AFFINITY`；`xTaskCreate()` 等价于 `tskNO_AFFINITY`。单核配置下该参数被忽略。对时序敏感或与绑核外设中断交互的任务显式绑核，并在设计中写明理由（`ESP-003`）。
- **栈深度单位是字节**（原版是字），`uxTaskGetStackHighWaterMark()` 也返回字节；从其他 FreeRTOS 工程移植时不要照搬数值（`RTOS-002`）。
- ISR 中只用 `FromISR` API 并以 `portYIELD_FROM_ISR()` 结束（`ISR-004`）；任务优先级数值语义与原版相同（数值越大越高）。
- 双核共享数据不能只靠 `volatile`（`C-001`）；原子类型按目标核实是否 lock-free，RISC-V 目标见 [riscv.md](riscv.md)（`RV-001`）。

## 4. 中断、IRAM 与 Flash cache

- 中断用 `esp_intr_alloc()`（或驱动提供的注册接口）分配，标志位决定级别与放置；不要直接写中断矩阵或 CPU 中断寄存器。
- **Flash cache 关闭窗口**（`ESP-002`）：任何经 SPI1 的 Flash 写、擦除或非加密读都会自动关闭 cache；期间其他任务挂起、另一核自旋，未标记 IRAM 安全的中断被屏蔽，对应硬件事件在 cache 恢复前不会得到处理。
  - 必须在该窗口内运行的中断用 `ESP_INTR_FLAG_IRAM` 注册；处理函数及其调用的所有函数放入 IRAM（`IRAM_ATTR`），访问的数据放入 DRAM（`DRAM_ATTR`）。
  - 违反时：从 Flash 取指会导致 Illegal Instruction 异常；读放在 Flash 的常量会得到错误值。ISR 中的日志用 `ESP_DRAM_LOGE()` 等宏，`TAG` 与格式串也必须在 DRAM。
  - IRAM 容量有限：只把确有低延迟需求的路径放入 IRAM，并在报告中给出 `idf.py size` / `size-components` 的变化。
- **Xtensa 高优先级中断**：高于 FreeRTOS 可屏蔽级别的中断（Xtensa 目标的高级别中断）不能调用 FreeRTOS API，处理方式按官方 “High Priority Interrupts” 指南（Xtensa 上需汇编处理函数）；RISC-V 目标的中断模型不同，按该目标文档处理，不互相套用。
- ISR 只做事件捕获（`ISR-001`）；W1C 状态寄存器直接赋值（`ISR-002`），优先使用驱动 API 而不是直接访问寄存器。

## 5. 错误处理、日志与看门狗

- 所有返回 `esp_err_t` 的调用都检查（`ESP-004`）。可恢复错误（外部输入、总线 NACK、超时、资源不足）返回给调用者：用 `esp_check.h` 的 `ESP_RETURN_ON_ERROR` / `ESP_GOTO_ON_ERROR` 等宏传播并附带日志。`ESP_ERROR_CHECK()` 只用于“失败即为程序错误、继续运行无意义”的场合，它在失败时会中止；但定义了 `NDEBUG`（断言被禁用）时它只求值、**不检查也不中止**，错误被静默丢弃（`esp_err.h`），因此不能用它处理发布构建中仍可能发生的错误。返回 `esp_err_t` 的调用也不要用 `(void)` 丢弃结果（如 `esp_ota_mark_app_valid_cancel_rollback()` 失败意味着下次复位会回滚），至少记录日志。
- v6 注意：`esp_wifi_init()` 在已初始化时返回错误，包在 `ESP_ERROR_CHECK` 中会导致重复初始化的路径直接中止；I2C master 收到 NACK 返回 `ESP_ERR_INVALID_RESPONSE`。
- `assert()` 只用于内部逻辑错误；断言可被配置关闭，表达式不能有副作用（v6 中 `COMPILER_ASSERT_NDEBUG_EVALUATE` 默认 `n`，`NDEBUG` 下断言表达式不再求值）（`ERR-001`）。
- 日志用 `ESP_LOGx(TAG, …)`，每个组件一个 `TAG`；不在 ISR 或临界区中调用普通日志。
- 看门狗：中断看门狗（IWDT）超时总是致命错误；任务看门狗（TWDT）只有在 `CONFIG_ESP_TASK_WDT_PANIC` 时才触发 panic。业务任务订阅 TWDT 时，只在本周期确有进展后才喂狗（`RTOS-005`）。

## 6. Xtensa / RISC-V 兼容与故障分析

组件代码默认要在两种架构上都能编译和正确运行（`ESP-008`）：

- 芯片差异按 `CONFIG_IDF_TARGET_*`、`SOC_*` 能力宏（`soc/soc_caps.h`）以及 `esp_cpu.h`、`esp_intr_alloc.h` 等抽象处理；架构专属代码（内联汇编、特殊寄存器、Xtensa 窗口寄存器相关代码）集中放在按 `CONFIG_IDF_TARGET_ARCH_XTENSA` / `CONFIG_IDF_TARGET_ARCH_RISCV` 区分的文件中，其他代码不引用。
- 不假设核数：单核目标上 `xCoreID` 被忽略，`portNUM_PROCESSORS` / `CONFIG_FREERTOS_UNICORE` 决定实际核数；绑核到 Core 1 的设计在单核目标上要有降级方案。
- 不假设非对齐访问、原子宽度或 cache 行大小跨目标一致；按 TRM 与 `SOC_*` 宏确认（`PROTO-002`、`DMA-001`）。
- **故障分析**（panic 输出以 “Guru Meditation Error” 开头）：
  - Xtensa：看 `PC`、`EXCCAUSE`、`EXCVADDR`（异常类型如 `LoadProhibited`、`StoreProhibited`、`IllegalInstruction`）。
  - RISC-V：看 `MEPC`、`MCAUSE`、`MTVAL`、`RA`、`SP`（异常原因串区分大小写，如 “Illegal instruction”、“Instruction access fault”、“Load access fault”、“Store access fault”、“Load address misaligned”、“Store address misaligned”）；访问类故障的出错地址在 `MTVAL`。
  - “Cache error” 或 Flash 中代码引起的 Illegal Instruction，优先怀疑 §4 的 IRAM/cache 问题。
  - 用 `idf.py monitor` 的地址解码或 `riscv32-esp-elf-addr2line` / `xtensa-esp32-elf-addr2line`（按目标）配合 ELF 定位；需要完整现场时启用 core dump（存 Flash 或 UART），连接 JTAG 且开启 OCD 感知模式时 core dump 会跳过。
  - panic 行为由 `CONFIG_ESP_SYSTEM_PANIC_*` 选择（默认打印后重启；`PRINT_HALT` 会停住，正在驱动执行器的设备不要用，见 `DBG-001`）。
- 启动时读取复位原因（`esp_reset_reason()`）并记录，满足 `FAULT-001`。

## 7. OTA、安全与不可逆操作

- **OTA 分区**：至少两个 OTA 应用分区（`ota_0`、`ota_1`）加 `otadata`（2 个扇区，抵御写 otadata 时掉电）。应用分区的 OTA 是掉电安全的；bootloader、分区表、NVS/FAT 等的更新不是，掉电可能导致无法启动，必须单独设计并说明风险（`BOOT-002`）。
- **回滚**（`ESP-007`）：启用 `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`。新镜像首次启动处于 `ESP_OTA_IMG_PENDING_VERIFY`，自检通过后调用 `esp_ota_mark_app_valid_cancel_rollback()`，失败调用 `esp_ota_mark_app_invalid_rollback_and_reboot()`；两者都不调用就复位会回滚。新镜像只有一次启动机会，自检要尽早完成，避免掉电被误判为失败。factory 分区不参与回滚。
- **防回滚**：`CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK` 把安全版本写入 eFuse，镜像版本低于 eFuse 记录值时拒绝启动；eFuse 位数有限（ESP32 上最多 32 次），发布流程要规划版本号的使用（`BOOT-003`）。
- **不可逆硬件动作**（`ESP-005`，同 `GEN-001`）：烧写 eFuse（包括密钥、安全版本、JTAG/下载模式禁用）、启用 Secure Boot、启用 Flash Encryption 都不能撤销或只能有限次撤销：
  - 传统 eFuse key block 方案中 Flash Encryption 密钥写入 eFuse“只能进行一次”（支持 Key Manager 的目标如 `esp32c5`/`esp32p4` 按该目标安全文档核对密钥部署方式）；Release 模式下 UART 下载模式不再执行加密，明文固件只能经 OTA 写入，持有同一密钥副本时才能在主机预加密后经串口烧写密文；Development 模式下 ESP32 每颗芯片最多关闭加密 3 次，非 ESP32 目标每颗芯片仅 1 次（包括 ESP32-S31，不能套用 ESP32 的次数）。误启用加密后烧写明文数据会使芯片软变砖。
  - 禁用 ROM 下载模式后 `esptool` 无法再连接芯片。
  - 处理流程：先确认完整芯片型号与版本（含 ECO 版本）、IDF 版本、密钥保管与产线流程；先在 Development 模式或 QEMU 中验证；给出命令时说明后果，并要求用户在执行前确认具体设备并接受不可逆后果。型号、版本或密钥方案未知时不写可直接执行的 eFuse/安全启用命令。v6 中 `idf.py` 的 eFuse 命令需要显式指定端口。
- v6 的 TLS/密码学基于 MbedTLS 4.x（v6.1 为 4.1.0），以 PSA Crypto API 为主；在正常启动流程之前运行的代码需要自行调用 `psa_crypto_init()`。

## 8. 测试与验证

- **单元测试**：组件测试用 IDF 集成的 Unity，放在 `test_apps/` 中构建为测试应用；纯逻辑部分可在 host 上测试（IDF 的 `linux` 目标——属 preview，仅适合不依赖硬件的逻辑，或把不依赖 IDF 的代码交给 Ceedling / CppUTest）。测试 oracle 来自接口与需求（`GEN-006`、`TEST-002`）。
- **目标测试**：`pytest-embedded` 驱动测试应用在开发板上运行；没有开发板时记 `NOT_RUN`。QEMU 可用于部分目标（以官方 QEMU 指南支持列表为准），仿真通过不等于硬件通过（`GEN-003`）。
- **构建门禁**：`idf.py set-target <target>` 后 `idf.py build`（v6 默认告警即错误）；`idf.py size` / `size-components` 报告 Flash、IRAM、DRAM 变化（`TEST-004`）。两种架构都要编译：至少构建一个 Xtensa 目标（如 `esp32`）和一个 RISC-V 目标（如 `esp32s31`，注意其 preview 状态）。
- **格式**：`pre-commit run astyle_py --files <files>`（项目已配置时）。
- 烧录与监视（`idf.py flash monitor`）是硬件动作，需要授权（`GEN-001`、`DBG-001`）。

## 9. 从 v5.x 迁移到 v6.x 的要点

以官方 v6.0 Migration Guide 为准，常见问题：

- 旧版驱动已移除（ADC、DAC、I2S、Timer Group、PCNT、MCPWM、RMT、温度传感器、I2C slave v1、SDM 的 legacy 接口），改用新驱动 API。
- 头文件移除：`intr_types.h`（改用 `esp_intr_types.h`）、`esp_spi_flash.h`、`esp_spiram.h`、`esp_interface.h`、lwIP `ping.h` / `esp_ping.h`；`esp_dma_capable_malloc`/`calloc` 已移除；`esp_log_buffer_hex` 改用 `ESP_LOG_BUFFER_HEX`。
- 迁出核心、改为组件管理器组件：wifi_provisioning（改为 network_provisioning）、esp-mqtt、cJSON、USB Host、gcov（esp-gcov）及部分以太网/LCD 驱动；需要在 `idf_component.yml` 中声明。
- MbedTLS 4.x：大量旧 `mbedtls_*` API 被移除，去除无前向保密的 DHE/RSA 密钥交换与 250 位以下曲线。
- DHCP 服务器不再自动把已配置的 DNS 放进 offer：需用 `esp_netif_dhcps_option()` 显式启用 `ESP_NETIF_DOMAIN_NAME_SERVER` 并用 `esp_netif_set_dns_info()` 设置地址；未启用时客户端拿到的 DNS 是 AP 自身 IP。
- 默认告警即错误、默认 Picolibc、`gnu23` / `gnu++26`：先在 CI 中开启这些默认值修正告警，不要以关闭 `-Werror` 代替修复。

## 来源

- ESP-IDF Programming Guide v6.1：[FreeRTOS (IDF)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_idf.html)、[Flash 并发约束](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/spi_flash/spi_flash_concurrency.html)、[Fatal Errors（RISC-V 目标页）](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-guides/fatal-errors.html)、[Style Guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/contribute/style-guide.html)、[OTA](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/ota.html)、[Flash Encryption](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/security/flash-encryption.html)、[Security Overview](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/security/security.html)。
- [ESP-IDF v6.0 发布说明](https://github.com/espressif/esp-idf/releases/tag/v6.0)，[ESP32-S31 产品页](https://www.espressif.com/en/products/socs/esp32-s31)；S31 的 preview 状态与 esptool 要求见 [platform-espressif32 #1777](https://github.com/platformio/platform-espressif32/issues/1777)。
- 2026-11-06 另对照 ESP-IDF v6.1 源码（`fff9895c`）核对了 Xtensa/RISC-V panic 原因串、`esp_check.h` 宏名、Xtensa 高优先级中断、QEMU 目标（esp32/esp32c3/esp32s3）与 `linux` preview 状态。仍未核对：IDF `linux` 目标的组件支持范围。
