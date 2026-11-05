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
