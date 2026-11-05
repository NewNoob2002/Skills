# 目标机调试与故障分析

范围：Cortex-M 与 RISC-V MCU 的 fault 分析、调试器连接、日志通道、map/栈分析。寄存器地址与位定义来自 ARM 架构参考手册（ARMv7-M：ARM DDI 0403；ARMv8-M：ARM DDI 0553）和 RISC-V Privileged Specification；具体芯片的实现以其参考手册为准。

## 1. 先确认授权

连接调试器本身是只读的，但以下操作会改变硬件状态，属于 `GEN-001` / `DBG-001` 的授权范围：

- `load`、`flash write`、`monitor reset`、`monitor halt`，以及任何擦除操作；
- halt 一个正在控制电机、加热器、电源等执行器的目标（halt 后控制环停止，执行器会停在最后的输出状态）；
- 修改 option bytes、读保护（RDP）或调试端口锁定，这类操作可能不可逆。

只读排查顺序：先读取已有的故障记录（见 §5），再在不 halt 的前提下读内存（有些探针支持后台访问），最后才在授权后 halt。

提供命令示例时须同时说明影响，但不要求用户先批准才能看到方案；实际执行前，必须确认目标与授权范围。只读环境中也要解释硬件风险，不能仅以无执行权限代替风险说明。烧录会覆盖现有固件，先确认备份和恢复方式；halt 之前先让执行器进入安全状态。

- **RDP/option bytes**：先确认完整芯片型号、参考手册、工具及版本，再生成可复核命令。RDP Level 2 默认按不可逆处理，要求用户明确接受调试/回退受限的后果；不能把“核对型号”当成接受后果。部分 STM32 系列可在预置 OEM 密钥等条件下回退，必须按型号核实，不能泛化（[ST AN5156 的 RDP 说明](https://www.st.com/content/st_com/en/technical-documents/an5156-introduction-to-security-for-stm32-mcus-stmicroelectronics_asset/chunk-006-topic-an5156-sec-feat-read-out-protection-rdp-.html)）。
- 保护升级、降级与擦除副作用分别按参考手册确认，不能把 RDP1→0 的 mass erase 泛化成“升到 RDP2 会整片擦除”；锁定前完成固件、数据与升级通道验证（[STM32F469/479 RM0386](https://www.stmicroelectronics.com/resource/en/reference_manual/dm00127514.pdf)）。
- **烧录文件格式**：使用前核对工具的输入格式；`st-flash` 不直接接收 ELF（[官方手册](https://github.com/stlink-org/stlink/blob/testing/doc/man/st-flash.md)）。先用目标工具链的 objcopy 转换为 binary/ihex，并从链接脚本或 ELF 段确认写入地址，不能给未知板子套用固定地址。

## 2. Cortex-M fault 分析（ARMv7-M / ARMv8-M Mainline）

ARMv6-M（Cortex-M0/M0+）没有可配置的 fault 状态寄存器，所有 fault 都进入 HardFault，只能依靠栈帧和反汇编分析。

| 寄存器 | 地址 | 用途 |
| --- | --- | --- |
| CFSR | `0xE000ED28` | 可配置 fault 状态：MMFSR（字节 0）、BFSR（字节 1）、UFSR（半字 2） |
| HFSR | `0xE000ED2C` | `FORCED`（bit 30）：可配置 fault 升级为 HardFault；`VECTTBL`（bit 1）：读向量表失败 |
| MMFAR | `0xE000ED34` | `MMARVALID` 置位时为出错地址 |
| BFAR | `0xE000ED38` | `BFARVALID` 置位时为出错地址 |

常见 CFSR 位：

| 位 | 名称 | 典型原因 |
| --- | --- | --- |
| 0 / 1 | `IACCVIOL` / `DACCVIOL` | MPU 违规：执行或访问受保护区域、空指针 |
| 4 / 12 | `MSTKERR` / `STKERR` | 进入异常时压栈失败，多为栈溢出 |
| 9 | `PRECISERR` | 精确总线错误，BFAR 中是出错地址 |
| 10 | `IMPRECISERR` | 非精确总线错误：出错写操作已经离开 CPU，PC 不指向出错指令 |
| 16 | `UNDEFINSTR` | 执行了未定义指令，多为跳转到数据区或函数指针损坏 |
| 17 | `INVSTATE` | 试图进入 ARM 状态：函数指针最低位为 0 |
| 18 | `INVPC` | 异常返回时 EXC_RETURN 非法，多为栈被破坏 |
| 19 | `NOCP` | 访问未使能的协处理器（FPU 未在 CPACR 中使能） |
| 20 | `STKOF` | 栈越过栈界限寄存器（仅 ARMv8-M） |
| 24 / 25 | `UNALIGNED` / `DIVBYZERO` | 只有在 CCR 中使能对应的 trap 后才会报告 |

栈帧：进入异常时硬件压栈 `R0, R1, R2, R3, R12, LR, PC, xPSR`（8 个字），FPU 上下文活动时追加扩展帧。EXC_RETURN（进入 handler 时的 LR）bit 2 为 0 表示使用 MSP、为 1 表示使用 PSP，bit 4 为 0 表示带扩展的 FP 帧。

分析步骤：

1. 读 CFSR、HFSR，以及有效的 MMFAR/BFAR；HFSR.FORCED 置位时再看 CFSR 中的原始原因。
2. 按 EXC_RETURN 选择 MSP 或 PSP，取出栈帧中的 PC 和 LR。
3. `arm-none-eabi-addr2line -e app.elf -f -C <pc> <lr>` 定位源码行；结合 `arm-none-eabi-objdump -d -S` 查看出错指令。
4. 遇到 `IMPRECISERR`（仅调试构建）：Cortex-M3/M4 上可设置 ACTLR.DISDEFWBUF 关闭写缓冲，使总线错误变为精确错误；这会降低性能，不得留在发布构建中。其他内核按其技术参考手册确认。

fault handler 的写法：用汇编入口判断 EXC_RETURN 并取得栈帧指针，再交给 C 函数记录现场（§5）；随后进入安全态，或由看门狗复位。不要在 fault handler 中调用 RTOS API 或格式化日志。

## 3. RISC-V trap 分析

M 模式下读取 `mcause`、`mepc`、`mtval`、`mstatus`。`mcause` 的最高位为 1 表示中断，为 0 表示异常。常见异常码：

| 码 | 含义 | `mtval` |
| --- | --- | --- |
| 0 / 1 / 2 | 取指地址未对齐 / 取指访问错误 / 非法指令 | 出错地址；非法指令时可能是指令编码（取决于实现） |
| 4 / 5 | 读地址未对齐 / 读访问错误 | 出错地址 |
| 6 / 7 | 写或 AMO 地址未对齐 / 写或 AMO 访问错误 | 出错地址 |
| 8 / 11 | U 模式 / M 模式的环境调用（`ecall`） | 0 |

`mepc` 指向出错指令，用 `addr2line` 定位。`mtval` 是否写入、写入什么内容取决于实现，以芯片手册为准。其他架构差异见 [platforms/riscv.md](../platforms/riscv.md)。

## 4. 调试器与日志通道

| 工具 | 启动方式（示例） | GDB 连接 |
| --- | --- | --- |
| OpenOCD | `openocd -f interface/stlink.cfg -f target/stm32f4x.cfg` | `target extended-remote localhost:3333` |
| pyOCD | `pyocd gdbserver --target <target>` | 默认端口 3333 |
| SEGGER J-Link | `JLinkGDBServer -device <device> -if SWD` | 默认端口 2331 |

- 接口和目标配置文件的名称以所用工具版本附带的文件为准；不要猜测文件名。
- RTOS 感知：OpenOCD 可以对目标启用 `-rtos FreeRTOS` 等 RTOS 支持，从而在 GDB 中查看各任务的栈；Zephyr 提供 `west debug` / `west attach`。
- 日志通道：SEGGER RTT 与 SWO/ITM 不占用 UART，适合 ISR 附近的诊断；ISR 中仍然不做格式化（`ISR-001`），只写入令牌或原始数据。
- 半主机（semihosting）在没有连接调试器时会触发断点异常导致目标停住，只能用于测试构建。

## 5. 故障记录与复位原因（`FAULT-001`）

- 启动时读取并保存复位原因寄存器（看门狗、掉电、软件复位、引脚复位等；位定义见芯片手册），然后按手册要求清除。
- fault handler 把 CFSR/HFSR/BFAR/MMFAR（或 `mcause`/`mepc`/`mtval`）、PC、LR 和当前任务 ID 写入 no-init RAM（链接脚本中不清零的段）或预留的 Flash 区，并附魔数与 CRC；下次启动时检查并上报。
- 断言失败同样写入这份记录（见 [architecture/state-protocol-fault.md](../architecture/state-protocol-fault.md) §4）。
- Zephyr：使用 `k_sys_fatal_error_handler` 与 coredump（`CONFIG_DEBUG_COREDUMP`）；Linux 用户态：使用 core dump（systemd-coredump）与 `gdbserver`。

## 6. map 与栈分析

- 体积：`arm-none-eabi-size -A app.elf`；`arm-none-eabi-nm -C -S --size-sort app.elf | tail -n 20`；A/B 比较用 `scripts/cpp_cost.py diff`。
- map 文件：链接时加 `-Wl,-Map=app.map,--cref`，用于确认每个符号放在哪个段、由哪个目标文件引入（例如 `malloc` 是被谁拉进来的）。
- 栈：`-fstack-usage` 生成每个函数的 `.su` 文件（`static` / `dynamic` / `bounded`）；GCC 的 `-fcallgraph-info=su` 输出调用图，两者结合估算最坏栈深。递归、函数指针和虚调用无法静态确定，必须标为 `UNKNOWN`，并用运行时水位线复核（`RTOS-002`）。
