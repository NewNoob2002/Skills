# Eclipse ThreadX 要点（与 FreeRTOS 的差异）

ThreadX 现为 Eclipse ThreadX（MIT 许可）。适用 `mcu-rtos`；ISR、任务设计与看门狗的通用规则见 [rtos/mcu-isr-rtos.md](mcu-isr-rtos.md)。API 以目标版本的 ThreadX 用户手册与 `tx_api.h` 为准。

## 1. 与 FreeRTOS 的关键差异（`TX-002`）

| 主题 | ThreadX | FreeRTOS | 移植时的风险 |
| --- | --- | --- | --- |
| 优先级 | 数值越小优先级越高，0 最高 | 数值越大优先级越高 | 直接照搬数值会让优先级完全颠倒 |
| 抢占阈值 | 每个线程有 preemption-threshold，只有优先级高于阈值的线程才能抢占它 | 无对应机制 | 用于减少上下文切换，但会推迟高优先级线程，需要计入时序分析 |
| 启动 | `tx_kernel_enter()` 不返回，在 `tx_application_define()` 中创建对象 | `vTaskStartScheduler()` | 对象创建位置不同 |
| 内存池 | block pool 定长、确定性；byte pool 变长、非确定性 | heap_1…heap_5 | RT 路径只用 block pool |
| 队列消息 | 消息大小以 32 位字为单位（1、2、4、8、16 个字） | 以字节为单位 | 大消息改为传递指针或索引 |

## 2. ISR 中的服务调用（`TX-001`）

- ISR 中只能调用允许在中断中使用的服务，等待选项必须是 `TX_NO_WAIT`。
- 不得在 ISR 中调用会挂起的服务，例如 `tx_thread_sleep`，或使用非零等待选项的 `tx_queue_receive`、`tx_semaphore_get`。
- ISR 只投递事件（`ISR-001`）：`tx_semaphore_put`、`tx_queue_send(..., TX_NO_WAIT)`、`tx_event_flags_set`。

## 3. 线程与同步

- 线程用静态栈创建：`tx_thread_create(&thread, "name", entry, input, stack, stack_size, priority, preempt_threshold, time_slice, TX_AUTO_START)`，栈数组为静态存储期（`RTOS-003`）。
- 互斥量需要优先级继承时，创建时使用 `TX_INHERIT`。
- 定时器回调默认在系统定时器线程中执行，不在 ISR 中；只有定义 `TX_TIMER_PROCESS_IN_ISR` 时才在 ISR 中执行，此时回调必须遵守 ISR 规则。
- 栈检查：定义 `TX_ENABLE_STACK_CHECKING`，并用 `tx_thread_stack_error_notify` 注册溢出回调；实测余量同样记录到报告中（`RTOS-002`）。

## 4. C++ 与 CMSIS-RTOS2

- C++ 包装规则与 FreeRTOS 相同：线程入口用静态成员蹦床，互斥量包装成 BasicLockable（[cpp/coding.md](../cpp/coding.md) §7）。
- 通过 CMSIS-RTOS2 适配层使用 ThreadX 时，ISR 中的超时同样必须为 0（`ISR-004`），且适配层自身的内存分配策略需要核实。
