# RISC-V MCU 要点（与 Cortex-M 的差异）

适用于 `mcu-baremetal` / `mcu-rtos` 中的 RISC-V 目标。分层、ISR、RTOS 的通用规则不变，见 [rtos/mcu-isr-rtos.md](../rtos/mcu-isr-rtos.md)。RISC-V 的中断控制器、cache 和部分 CSR 由各厂商实现，**一切以芯片参考手册为准**（`GEN-002`）。架构依据：RISC-V Unprivileged / Privileged Specification。

## 1. 中断模型

| 组件 | 作用 | 说明 |
| --- | --- | --- |
| CLINT 或 ACLINT | 机器定时器（`mtime`/`mtimecmp`）与软件中断 | 地址由平台决定 |
| PLIC | 平台级外部中断，带优先级与阈值 | 进入 trap 后需要 claim、处理完再 complete |
| CLIC | 核内中断控制器：向量化、按级别抢占 | 规范版本与实现差异较大，按手册确认 |
| 厂商控制器 | 如部分国产 MCU 的私有控制器 | 只按手册使用 |

- 默认情况下进入 trap 时硬件清除 `mstatus.MIE`，中断不嵌套。需要嵌套时，要么由 CLIC 的硬件抢占级别支持，要么在 handler 中保存 `mepc`/`mstatus` 后显式重新开中断；后者容易出错，需要评审。
- GCC 的 `__attribute__((interrupt))` 会生成保存所用寄存器并以 `mret` 返回的入口；使用 RTOS 时改用其移植层提供的 trap 入口，不要混用。
- 与 Cortex-M 的 NVIC 不同，不存在“数值越小优先级越高”的通用约定，优先级语义按控制器手册确认。

## 2. FreeRTOS RISC-V 移植

- 在 `FreeRTOSConfig.h` 中配置 `configMTIME_BASE_ADDRESS` 与 `configMTIMECMP_BASE_ADDRESS`（使用 CLINT 时），值取自芯片手册。
- trap 入口使用移植层的 `freertos_risc_v_trap_handler`；外部中断通过移植层的钩子分发给应用。
- ISR 中只用 `FromISR` API（`ISR-004`）；RISC-V 移植层没有 Cortex-M 那样的 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 屏蔽机制，是否支持中断嵌套取决于移植层与控制器。

## 3. 原子操作与内存序（`RV-001`）

- 原子指令属于 A 扩展（`LR/SC`、`AMO*`）。工具链 `-march` 不含 `a`（例如 `rv32imc`）时，`std::atomic` 与 C11 `_Atomic` 的读-改-写会变成 libatomic 调用或链接失败，与 ARMv6-M 的情况相同（[cpp/coding.md](../cpp/coding.md) §7），这时改用关中断临界区。
- 与 C++ 规则相同，共享原子类型加 `static_assert(std::atomic<T>::is_always_lock_free)`，并用 `scripts/cpp_cost.py check` 检查 `atomic_libcall`。
- RISC-V 采用弱内存模型（RVWMO）。MMIO 与 DMA 描述符的访问顺序需要显式 `fence`（如 `fence iorw, iorw`），不能只依赖 `volatile`；厂商 HAL 的寄存器访问宏是否包含 fence，要查看其实现。
- cache 维护（DMA 前 clean、后 invalidate）由厂商扩展或 Zicbom 扩展提供，指令和 CSR 以手册为准（`DMA-001`）。

## 4. ABI 与工具链

- psABI 要求栈 16 字节对齐；自写的启动代码与上下文切换必须保持对齐。
- 编译选项中的 `-march`/`-mabi` 必须与芯片实际支持的扩展一致（例如有没有 `f`/`d`、`c`），否则会出现非法指令异常（mcause 2）。
- 使用 `cpp_cost.py` 时通过 `--prefix riscv32-unknown-elf-`（或项目工具链前缀）指定 `nm`/`size`。
- trap 分析方法见 [verification/debugging.md](../verification/debugging.md) §3。
