# 事实核查：`skills/embedded-engineering/references/platforms/esp-idf.md`（ESP-IDF v6.x）

核查日期：2026-11-06。只读核查，未修改仓库文件。
行号对应文件当前版本（共 104 行）。

## 归档说明与勘误

- 模型：DeepSeek-V4.1-Flash；调用方式：omp；只读事实核查；对照 ESP-IDF v6.1 `fff9895c`。下文保留原始输出（旧 pre-commit 命令示例已标记移除，避免继续传播错误顺序），行号对应核查时的文档。原始 prompt 未随报告提供，不补造。
- 原始“错误 3、存疑 6、正确 30+”仅为当时模型的统计，并非完整正确性证明。
- **L76 勘误**：E3 注释与“正确”表格中“每颗芯片可关闭加密 3 次”的结论已被后续 deep review S1 推翻。`docs/en/security/flash-encryption.rst:1019-1025` 的条件分别为 `esp32`（3 次）与 `not esp32`（1 次）；ESP32-S31 等非 ESP32 目标仅 1 次。
- **L31 措辞勘误**：“冻结 tick”已按 deep review G2 收紧为推迟 tick 处理、恢复时补算；不表示硬件 tick 中断停止。

## 0. 核查环境与依据

| 依据 | 路径/来源 | 说明 |
| --- | --- | --- |
| 本机 ESP-IDF 源码 | `/home/gtc/esp/esp-idf` | `git describe` = **v6.1**，commit `fff9895c`（2026-08-25，`change(version): Update version to 6.1.0`）——与被核查文档声称的 v6.1 一致，可作为一手证据 |
| 本机 IDF Python 环境 | `~/.espressif/python_env/idf6.1_py3.14_env` | `esp-idf-kconfig 3.14.0`、`esptool 5.6.0`、`idf-component-manager 3.1.2` |
| 官方发布信息 | GitHub Releases API | v6.0：`created_at` 2026-03-19T03:17Z，`published_at` 2026-03-20T04:17Z；v6.1 `published_at` 2026-08-27 |
| 在线文档 | `docs.espressif.com/.../en/stable/...` | 抽查 5 条来源链接均 HTTP 200；`en/stable` 当前指向 **v6.1**（页面内出现 9 次 `v6.1`） |

结论速览：**错误 3 条、存疑 6 条、正确 30+ 条**。整体准确度高，两处需改（L76 的 Flash Encryption 结论、L86 的命令写法），一处字符串精度问题（L64）。

---

## 1. 错误（必须改）

### E1 · L76 — “Release 模式下只能经 OTA 更新” 结论过强（实质错误）

原文：“Release 模式下不能再串口烧写明文固件，**只能经 OTA 更新**”。

事实：Release 模式禁止的是 **UART 下载模式下的在线加密/明文烧写**；主机侧预加密（ciphertext）镜像仍可经串口烧写。

- `docs/en/security/flash-encryption.rst:719`：*“In release mode, UART bootloader cannot perform flash encryption operations. New plaintext images can ONLY be downloaded using the over-the-air (OTA) scheme…”*
- 同文件 `:690`：*“If using release mode, then it is possible to **pre-encrypt the binaries on the host and then flash them as ciphertext**. See manual-encryption.”*
- 同文件 `:1012`：*“In release mode, if a copy of the same key stored in eFuse is available on the host then it is possible to pre-encrypt files on the host and then flash them.”*

建议改法：

> Release 模式下 UART 下载模式不再执行在线加密，**明文固件只能经 OTA 写入**；若持有 eFuse 中同一密钥的副本，可在主机侧用 `espsecure.py encrypt_flash_data` 预加密后经串口烧写密文（manual encryption）。密钥不可导出/无副本时，串口只能烧写已加密镜像。

### E2 · L86 — `pre-commit` 命令参数顺序错误

原文：`pre-commit run [旧顺序已移除，hook 位于 --files 之后]`。

事实：`--files` 是可变长选项，会把其后的 `astyle_py` 当作文件名一并吞掉，导致 hook 名缺失（`pre-commit` 报 “No hook with id …” 或直接对所有文件跑默认 hook 集）。仓库配置见 `.pre-commit-config.yaml:212-217`（`repo: espressif/astyle_py`，`id: astyle_py`，`args: ['--astyle-version=3.4.7', '--rules=tools/ci/astyle-rules.yml']`）。

建议改法（二选一）：

```bash
pre-commit run astyle_py --files <files>
pre-commit run --hook-stage manual astyle_py --files <files>   # 需要显式阶段的场景
```

### E3 · L76 相邻细节 — “只能进行一次”措辞与旧芯片差异

原文：“Flash Encryption 密钥写入 eFuse‘只能进行一次’”。

事实：对 ESP32 及多数目标成立（key block 一次性烧写 + 写保护）；但对支持 **Key Manager** 的目标（`esp32c5`、`esp32h4`、`esp32p4`、`esp32s31`，见 `docs/en/api-guides/bootloader.rst:153`），密钥可在 eFuse 之外由 Key Manager 部署，措辞“只能进行一次”不再普遍成立。

建议改法：把“写入 eFuse 只能进行一次”限定为“传统 eFuse key block 方案（ESP32/S2/S3/C3/C6/H2 等）；支持 Key Manager 的目标按该目标安全文档核对密钥部署方式”。

> 注：同段“Development 模式最多关闭加密 3 次”**正确** —— `flash-encryption.rst:1021`：*“It can only be done three times per chip”*。

---

## 2. 存疑（需补充/收紧措辞，或证据链不足）

### Q1 · L7 — v6.0 发布日 2026-03-19（差 1 天，取决于“发布”定义）

GitHub API：tag/`created_at` = **2026-03-19T03:17Z**，`published_at` = **2026-03-20T04:17Z**。文档写 03-19 有据（tag 日期），但“发布”通常指 published。维护期“至 2028-09”与 `SUPPORT_POLICY.md`（每版本 30 个月）自洽。

建议：写作 “v6.0 于 2026-03 发布（tag 2026-03-19 / release 2026-03-20），维护至 2028-09”，或直接标注“30 个月支持期”。

### Q2 · L28 — FreeRTOS 基线 v10.5.1（默认成立，但仓库内同时存在 V11.1.0 内核）

- 默认实现 `FreeRTOS-Kernel`：`include/freertos/task.h:62` → `tskKERNEL_VERSION_NUMBER "V10.5.1"`；`docs/en/api-reference/system/freertos_idf.rst:18` 亦如此表述。
- 但 v6.1 仓库同时提供 `FreeRTOS-Kernel-SMP`：`include/freertos/task.h:60` → **`"V11.1.0"`**，由 `CONFIG_FREERTOS_SMP` 选择（`components/freertos/CMakeLists.txt:33-36`），该选项 `default n` 且 `depends on IDF_TARGET_ESP32`，help 明确标注 “FEATURE UNDER DEVELOPMENT”（`components/freertos/Kconfig:7-19`）。

结论：文档在**默认配置**下正确；建议补一句“若启用实验性 `CONFIG_FREERTOS_SMP`（仅 esp32），内核切换为 Amazon SMP V11.1.0，行为与 API 细节需按该内核核对”。

### Q3 · L64 — RISC-V 异常名大小写与合并，不利于日志检索

v6.1 实际打印字符串（`components/esp_system/port/arch/riscv/panic_arch.c:272-286`）：

```
Instruction address misaligned / Instruction access fault / Illegal instruction /
Breakpoint / Load address misaligned / Load access fault /
Store address misaligned / Store access fault / ... / Store page fault
```

文档写 “Illegal instruction”、“Load Access Fault”、“Store Access Fault”、“Load/Store Address Misaligned”：
- `Illegal instruction` ✓ 与实现一致；
- `Load Access Fault`、`Store Access Fault` 实际为小写 `Load access fault`、`Store access fault`；
- `Load/Store Address Misaligned` 实际是两条独立原因（`Load address misaligned` / `Store address misaligned`），文档用合并写法会被误读成一条。

建议：按上面 8 条原样列出（区分大小写），便于 grep UART 日志。寄存器名（`MEPC`/`MCAUSE`/`MTVAL`/`RA`/`SP`）与 `MTVAL` 承载出错地址**正确**（`fatal-errors.rst:156-164, 389`）。

### Q4 · L97 — DHCP 不再下发 DNS 的表述过度简化

原文：“DHCP 服务器不再自动下发 DNS，需要 `esp_netif_dhcps_option()` 与 `esp_netif_set_dns_info()`。”

事实（`docs/en/migration-guides/release-6.x/6.0/networking.rst:160-179`）：`LWIP_DHCPS_ADD_DNS` 宏被移除；此后**只有**在显式用 `esp_netif_dhcps_option(ESP_NETIF_DOMAIN_NAME_SERVER)` 启用时，才把配置的 DNS 地址放进 offer；**未启用时 DHCP 服务器仍把自己的 IP 作为 DNS 下发**（保留旧默认行为）。即“不再自动携带配置的 DNS”，而非“不再下发 DNS”。

建议：改为“不再自动把已配置的 DNS 放进 DHCP offer；需显式启用 `ESP_NETIF_DOMAIN_NAME_SERVER`，并用 `esp_netif_set_dns_info()` 设置地址；未启用时客户端拿到的是 AP 自身 IP”。

### Q5 · L83 — `linux` 目标不是受支持目标

`tools/idf_py_actions/constants.py`：`SUPPORTED_TARGETS` 不含 `linux`；`PREVIEW_TARGETS = ['linux', 'esp32h21', 'esp32h4', 'esp32s31']`。用它做 host 单元测试可行，但属 preview，组件支持面不全（例如部分驱动/无线组件不可用）。

建议：句中补 “（`linux` 属 preview 目标，仅可用于不依赖硬件的逻辑测试）”。

### Q6 · L3 / L104 — 自相矛盾的范围声明

L3 声明“API 名称、配置项与行为均对照 Programming Guide v6.1（2026-11-06 核实）”，L104 又列出“未逐条核对原文的点：Xtensa panic 寄存器名称……”。本次核查已确认：Xtensa panic 寄存器 `PC`/`EXCCAUSE`/`EXCVADDR` 与原因串 `LoadProhibited`/`StoreProhibited`/`IllegalInstruction` 均与 `components/esp_system/port/arch/xtensa/panic_arch.c:229-236` 一致；`esp_check.h` 宏名 `ESP_RETURN_ON_ERROR`/`ESP_GOTO_ON_ERROR`/`ESP_RETURN_ON_FALSE`（`:19,65,90`）一致；Xtensa 高优先级中断确需汇编实现（`docs/en/api-guides/hlinterrupts.rst:9` + `xt_highint4/5`、`xt_nmi` 符号表）；QEMU 支持目标为 esp32/esp32c3/esp32s3（`tools/idf_py_actions/qemu_ext.py:69,105,…`）。

建议：删除 L104 的“未核对”项或就地标注“已核对（v6.1 源码）”，避免读者重复核查。

---

## 3. 正确（已逐条比对，可直接保留）

| 行 | 断言 | 证据 |
| --- | --- | --- |
| L12 | ESP32 = Xtensa LX6 双核；Secure Boot v2 需 ECO3（chip rev v3.0） | `components/soc/esp32/include/soc/soc_caps.h:168`（2 核）；`docs/en/security/secure-boot-v2.rst:16,38,44`（v3.0 onwards 才有 v2） |
| L13a | ESP32-S31 = RISC-V 双核 + LP RISC-V 核 | `components/soc/esp32s31/include/soc/soc_caps.h:175`（`SOC_CPU_CORES_NUM (2U)`）、`:57`（`SOC_LP_CORE_SUPPORTED`）、`:609`（LP core 为 RISC-V） |
| L13b | 最高 320 MHz | `components/soc/esp32s31/include/soc/clk_tree_defs.h:44,88`（CPLL 320 MHz 作 CPU 源；另有 240 MHz 档） |
| L13c | v6.1 中为 preview 目标；`IDF_TARGET_ESP32S31` 会 `select IDF_ENV_BRINGUP` | `Kconfig:149-153`；`tools/idf_py_actions/constants.py`（`PREVIEW_TARGETS` 含 `esp32s31`）；`Kconfig:23`（`IDF_ENV_BRINGUP` 仅用于新芯片 bring-up） |
| L13d | 需要 esptool ≥ 5.3 | esptool v5.3.0 release notes：“ESP32-S31: Add support…”；本机安装 5.6.0 已含 `targets/esp32s31.py` |
| L20 | `idf_component_register(SRCS … INCLUDE_DIRS … REQUIRES … PRIV_REQUIRES …)`；`idf_component.yml` + `dependencies.lock` | `tools/cmake/component.cmake:428-449`（多值参数列表含 SRCS/SRC_DIRS/EXCLUDE_SRCS/INCLUDE_DIRS/PRIV_INCLUDE_DIRS/LDFRAGMENTS/REQUIRES/PRIV_REQUIRES）；`docs/en/api-guides/build-system.rst:193-195` |
| L21 | `sdkconfig.defaults.<target>`；`Kconfig`/`Kconfig.projbuild`；v6 用 esp-idf-kconfig **v3** | `build-system.rst:1104-1109`（仅当 `sdkconfig.defaults` 存在才加载目标专属文件）；`build-system.rst:744-747`；`migration-guides/release-6.x/6.0/build-system.rst:81`（“v6 uses esp-idf-kconfig v3 … 语法有变化”）；本机 `esp-idf-kconfig 3.14.0` |
| L22 | 4 空格/禁 tab、函数 `{` 独行、控制语句 `{` 同行、120 列、`static` + `s_` 前缀、公共符号组件前缀、`_t` 后缀、`#pragma once` + `extern "C"`、astyle（非 clang-format） | `docs/en/contribute/style-guide.rst:27-29,35,60,228,301-316`；`.pre-commit-config.yaml:212-217`；仓库无 `.clang-format` |
| L23a | 默认 `gnu23` / `gnu++26` | `tools/cmake/build.cmake:207-208`；v6.0 release notes（同项） |
| L23b | 默认告警即错误，`CONFIG_COMPILER_DISABLE_DEFAULT_ERRORS` 可关闭（默认 n） | `build.cmake:182`（`-Werror` 在默认编译选项里）；`Kconfig:679`；`CMakeLists.txt:232`（启用后 `-Werror` → `-Werror=all`，即只把默认告警当错误——比“关闭全部”更精确） |
| L23c | 默认 libc = Picolibc | `components/esp_libc/Kconfig:4-7`（`default LIBC_PICOLIBC`，例外：`IDF_TOOLCHAIN_CLANG` 时 newlib） |
| L23d | CMake ≥ 3.22 | `CMakeLists.txt:1`、`tools/cmake/project.cmake:2` |
| L30 | `portMUX_TYPE` + `portMUX_INITIALIZER_UNLOCKED` + `portMUX_INITIALIZE()`；任务/ISR 各用 `taskENTER_CRITICAL(&mux)` / `taskENTER_CRITICAL_ISR(&mux)` | `FreeRTOS-Kernel/portable/xtensa/include/freertos/portmacro.h`（SMP：`:85-90`，`portENTER_CRITICAL_ISR(lock)` `:346`；单核内核同样接收 mux 形参） |
| L31 | `taskDISABLE_INTERRUPTS()` 仅当前核；`vTaskSuspendAll()` 只挂起本核调度，Core 0 上调用冻结 tick | `docs/en/api-reference/system/freertos_idf.rst:257-264,287-293` |
| L32 | `xTaskCreatePinnedToCore` / `xTaskCreateStaticPinnedToCore`，`xCoreID` ∈ {0,1,`tskNO_AFFINITY`}；`xTaskCreate` ≡ `tskNO_AFFINITY`；单核下该参数被忽略 | `FreeRTOS-Kernel/include/freertos/task.h:206,381-399`（`xTaskCreate` 内联转调 PinnedToCore + `tskNO_AFFINITY`）；`freertos_idf.rst:82-88,487-491` |
| L33 | 栈深度单位字节；`uxTaskGetStackHighWaterMark()` 返回字节 | `freertos_idf.rst:92`；`task.h`（`usStackDepth … NUMBER OF BYTES`）；HWM 实现除以 `sizeof(StackType_t)`，而 IDF port 定义 `portSTACK_TYPE uint8_t`（`portmacro.h:47`）→ 结果即字节 |
| L34 | ISR 只用 `FromISR` API，以 `portYIELD_FROM_ISR()` 结束；优先级数值大者高 | `portmacro.h:227`（SMP 版含 GET_FROM_ISR 变体宏）；`task.h` 优先级语义不变 |
| L39 | `esp_intr_alloc()` 分配中断 | `components/esp_hw_support/include/esp_intr_alloc.h` |
| L40-42 | SPI1 操作自动关 cache；期间他核忙等、非 IRAM 安全中断屏蔽；`ESP_INTR_FLAG_IRAM` + `IRAM_ATTR`/`DRAM_ATTR`；ISR 日志用 `ESP_DRAM_LOGE()`，TAG/格式串需在 DRAM | `docs/.../spi_flash_concurrency.rst:66-95`；`esp_intr_alloc.h:42,145`；`esp_log.h:84,136-143`（`DRAM_STR()` 用法） |
| L44 | Xtensa 高优先级中断（level 4+）需汇编处理函数，不能调 FreeRTOS API | `docs/en/api-guides/hlinterrupts.rst:9,18-40`（`xt_highint4/5`、`xt_nmi` 符号，`.S` 文件定义） |
| L49 | `esp_check.h` 的 `ESP_RETURN_ON_ERROR` / `ESP_GOTO_ON_ERROR` | `components/esp_common/include/esp_check.h:19,65`（另有 `*_ISR`、`ESP_RETURN_ON_FALSE` 变体） |
| L49 | `ESP_ERROR_CHECK()` 在 `NDEBUG` 下只求值不检查 | `components/esp_common/include/esp_err.h:97-106`（`#ifdef NDEBUG` 分支仅 `(void) sizeof(err_rc_)`）；建议顺带补一句：`ASSERTIONS_SILENT` 下会 `abort()` 但不打印（`:107-113`） |
| L50 | `esp_wifi_init()` 重复初始化返回错误 | `components/esp_wifi/src/wifi_init.c:372-377` → `ESP_ERR_INVALID_STATE`（可写明错误码） |
| L50 | I2C master NACK → `ESP_ERR_INVALID_RESPONSE` | `components/esp_driver_i2c/i2c_master.c:726`；v6.0 release notes 同项 |
| L51 | `COMPILER_ASSERT_NDEBUG_EVALUATE` 默认 `n` | `Kconfig:497-509`（`default n`），并说明 NDEBUG 下按标准替换为 `((void)0)` |
| L53 | IWDT 超时致命（走 panic handler，panic 失败则硬复位）；TWDT 仅在 `CONFIG_ESP_TASK_WDT_PANIC` 时 panic | `docs/en/api-reference/system/wdts.rst:71-77`；`components/esp_system/Kconfig:271-279,324` |
| L59 | `CONFIG_IDF_TARGET_ARCH_XTENSA` / `_RISCV`；`soc/soc_caps.h`；`esp_cpu.h`；`esp_intr_alloc.h` | `Kconfig:52-60`；`components/esp_hw_support/include/esp_cpu.h` 存在 |
| L60 | `portNUM_PROCESSORS` / `CONFIG_FREERTOS_UNICORE` 决定核数 | `components/freertos/config/include/freertos/FreeRTOSConfig.h:301`（`#define portNUM_PROCESSORS configNUMBER_OF_CORES`）；`Kconfig` 中 `FREERTOS_UNICORE` 被各单核目标 `select` |
| L63 | Xtensa：`PC`/`EXCCAUSE`/`EXCVADDR`，原因串 `LoadProhibited`/`StoreProhibited`/`IllegalInstruction` | `components/esp_system/port/arch/xtensa/panic_arch.c:229-236`；`fatal-errors.rst:173` |
| L64（寄存器部分） | RISC-V：`MEPC`/`MCAUSE`/`MTVAL`/`RA`/`SP`，访问类故障地址在 `MTVAL` | `fatal-errors.rst:156,164,389` |
| L65 | “Cache error” / Flash 中代码触发 Illegal Instruction → 查 IRAM/cache | `fatal-errors.rst:49,102,545`（`Cache error` 原因串） |
| L66 | `idf.py monitor` 解码；`riscv32-esp-elf-addr2line` / `xtensa-esp32-elf-addr2line`；core dump 到 Flash 或 UART；OCD 感知 + 已连调试器时 panic 提前返回（不进 core dump） | 工具链前缀见 `tools/cmake/toolchain-esp32.cmake` / `toolchain-esp32c6.cmake` / `toolchain-esp32s31.cmake`；`components/esp_system/panic.c:380-406`（`CONFIG_ESP_DEBUG_OCDAWARE` + `esp_cpu_dbgr_is_attached()` 时设断点返回），coredump 写入在其后的 `:447` |
| L67 | panic 行为由 `CONFIG_ESP_SYSTEM_PANIC_*` 选择，默认 PRINT_REBOOT，`PRINT_HALT` 停住 | `components/esp_system/Kconfig:30-64`（`default ESP_SYSTEM_PANIC_PRINT_REBOOT`，含 PRINT_HALT / SILENT_REBOOT / GDBSTUB） |
| L68 | `esp_reset_reason()` | `components/esp_system/include/esp_system.h:85` |
| L72 | 两个 OTA 分区 + `otadata`（2 扇区，0x2000） | `docs/en/api-guides/partition-tables.rst:45,65`（`otadata, data, ota, 0xd000, 0x2000`） |
| L73 | `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`；`ESP_OTA_IMG_PENDING_VERIFY`；两 API；不确认则复位后回滚；新镜像仅一次机会；factory 不参与回滚 | `components/bootloader/Kconfig.app_rollback:3-12`；`components/app_update/include/esp_ota_ops.h:358,382`；`docs/en/api-reference/system/ota.rst:41-45,96,107-113,122` |
| L74 | `CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK` 写 eFuse 安全版本；ESP32 最多 32 位 | `Kconfig.app_rollback:15-52`（`range 1 32 if IDF_TARGET_ESP32`，`default 32`） |
| L76 | Development 模式每芯片最多关闭加密 3 次 | `flash-encryption.rst:1021`（见 E1/E3 的修正） |
| L78 | v6 中 `idf.py efuse*` 必须显式给 `--port`（或 `ESPPORT`），否则报错 | `docs/en/migration-guides/release-6.x/6.0/tools.rst:27-32`；`tools/idf_py_actions/serial_ext.py:513-515`（"Port is required for espefuse…"） |
| L79 | v6 TLS/密码学为 MbedTLS 4.x、PSA 为主；早于正常启动的代码需自行 `psa_crypto_init()` | `migration-guides/.../security.rst:20-28`；`components/mbedtls/mbedtls/include/mbedtls/build_info.h:39`（**4.1.0**，可写实数） |
| L83 | Unity 组件测试放 `test_apps/`；host 测试可用 `linux` 目标 | `components/unity/` 存在；`linux` 在 `PREVIEW_TARGETS`（见 Q5） |
| L84 | `pytest-embedded` 驱动目标测试；QEMU 仅部分目标 | `docs/en/api-guides/tools/qemu.rst`；`qemu_ext.py` 映射 esp32/esp32c3/esp32s3 |
| L85 | `idf.py set-target` / `build` / `size` / `size-components` | `tools/idf_py_actions/core_ext.py` 中 `size`、`size-components`、`set-target` 目标均存在 |
| L87 | `idf.py flash monitor` | 同上（`flash`、`monitor` 目标） |
| L93 | v6.0 移除 legacy ADC/DAC/I2S/Timer Group/PCNT/MCPWM/RMT/Temperature Sensor/I2C slave v1/SDM 驱动 | `migration-guides/.../peripherals.rst:60-63,211-214,244-247,251-254,259-262,271-274,290-295,297-302,304-309`（逐项均有移除段落） |
| L94 | 移除 `intr_types.h`→`esp_intr_types.h`、`esp_spi_flash.h`、`esp_spiram.h`、`esp_interface.h`、lwIP `ping.h`/`esp_ping.h`；移除 `esp_dma_capable_malloc/calloc`；`esp_log_buffer_hex` → `ESP_LOG_BUFFER_HEX` | `migration-guides/.../system.rst:187,352`；`networking.rst:204-205`；`peripherals.rst:371,377`；`wifi.rst:28`；`esp_log_buffer.h:134`；文件在组件树中确已不存在（仅 `esp_intr_types.h` 保留） |
| L95 | 迁出：wifi_provisioning→network_provisioning、esp-mqtt、cJSON、USB Host（`espressif/usb`）、gcov（`espressif/esp_gcov`）、部分以太网 PHY/SPI 与 LCD（NT35510）驱动 | `provisioning.rst:9-21`；`protocols.rst:12,236`；`peripherals.rst:327,429`；`system.rst:394`；`networking.rst:46-49`（组件树中已无 `esp_wifi_provisioning`/`mqtt`/`json`/`usb`/`gcov`，`esp_lcd` 本体仍在） |
| L96 | MbedTLS 4.x：移除多数 `mbedtls_*` 旧 API；去掉无前向保密的 DHE/RSA 密钥交换与 <250 位曲线 | `security.rst:27,31-32`（原文即 “<250 bits; e.g., secp192r1/secp224r1”，另有 static ECDH 被移除——可补充） |
| L98 | 默认告警即错误、默认 Picolibc、`gnu23`/`gnu++26` | 见 L23 各行证据 |
| L102-103 | 来源链接可用 | 抽查 5 条均 HTTP 200；`en/stable` = v6.1 |

---

## 4. 建议的最小修订清单

1. **L76** 按 E1 改写 Flash Encryption 结论，并删除“只能经 OTA 更新”的绝对表述；顺带在 E3 限缩“只能写入一次”。
2. **L86** 改为 `pre-commit run astyle_py --files <files>`。
3. **L64** 换成与 `panic_arch.c` 完全一致的小写原因串，并把对不齐访问拆成两条。
4. **L28** 补一行：`CONFIG_FREERTOS_SMP=y`（仅 esp32、实验性）时内核为 Amazon SMP **V11.1.0**。
5. **L97** 按 Q4 精确化 DNS 行为（未启用选项时下发 AP 自身 IP）。
6. **L83** 标注 `linux` 为 preview 目标。
7. **L79** 可把 “MbedTLS 4.x” 收紧为 “MbedTLS 4.1.0”（v6.1 实测）。
8. **L104** 删除已核实的“未核对”项（Xtensa panic 寄存器、`esp_check.h` 宏名、Xtensa 高优先级中断汇编、QEMU 目标列表），其余（`linux` 目标组件支持范围）保留为待核。

## 5. 未能确证的点（已尽力，仍缺一手证据）

- L103 引用的 `platform-espressif32#1777` 未逐条打开核对；S31 的 esptool 版本要求已用 esptool v5.3.0 release notes 独立验证，故该引用可保留但不必作为唯一依据。
- L13 “尚未达到量产级支持”：`PREVIEW_TARGETS` 与 `IDF_ENV_BRINGUP` 可证 IDF 支持级别为 preview，但 Espressif 产品侧的量产状态属商务信息，未核。
