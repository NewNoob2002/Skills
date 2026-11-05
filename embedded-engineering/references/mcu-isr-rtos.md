# ISR、RTOS 与 DMA 设计（`mcu-baremetal` / `mcu-rtos`）

基于 rovinax/embedded-skills（MIT）的 `embedded-isr-design` 与 `embedded-rtos-design`，结合 brunofbloq 的并发护栏与 BARR-C 6.4/6.5 修订。修订点见 §6。

## 1. ISR：只捕获事件，不处理业务

**允许**：读状态寄存器、清中断标志、取时间戳、把少量有界数据写入环形缓冲/双缓冲、启动 DMA、`FromISR` 方式通知任务、有界计数器自增。

**禁止**：协议解析（JSON/protobuf/NMEA/MAVLink/自定义帧）、姿态估计、PID/Kalman 等控制计算、文件系统、Flash 擦写、网络协议处理、显示刷新、日志/`printf`、`malloc`/`free`、阻塞调用（`HAL_Delay`、轮询等待、带超时的 `HAL_*_Transmit`）、非常量上界的循环、非 `FromISR` 的 RTOS API。

**时间预算**：不存在通用的“UART ISR < 10 µs”之类的数字。每个项目按最短截止期限与中断负载，为每个 ISR 设定预算，并用 GPIO 翻转 + 示波器/逻辑分析仪、DWT `CYCCNT` 或 trace 实测；未测量记为 `NOT_RUN`。

**BARR-C 6.5**：

- 自写 ISR 命名以 `_isr` 结尾（6.5.b），声明为 `static` 或用编译器机制防止被普通代码调用（6.5.c）。
- 向量表要求的固定名（`USART1_IRQHandler`）属于记录在案的例外：放在 `platform/`/`bsp/`，只做一行转发到 `static` 的 `*_isr` 函数，或在偏离记录中说明。
- 未使用的向量安装默认 stub ISR（6.5.d），stub 进入安全态并记录故障，而不是空返回。

## 2. 清标志与共享数据

- **写 1 清除（W1C）寄存器不要用 `|=`**：`EXTI->PR1 |= mask` 会把其他已挂起位一起写 1 清掉。直接写：`EXTI->PR1 = mask;`。
- **清标志的时机**：在 Cortex-M 上，若清标志的写操作在 ISR 返回前尚未到达外设（总线写缓冲），中断会被再次挂起导致重入。必要时在清标志后读回该寄存器或使用 `__DSB()`，依据芯片参考手册/ARM 应用笔记，并在注释中写明来源。
- **ISR 与任务共享**按优先顺序：队列 → 双缓冲/环形缓冲（单生产者单消费者，索引宽度不超过 CPU 原子访问宽度）→ 任务通知/事件标志。
- `volatile` 只保证每次访问都真实发生，**不提供原子性与内存序**。多字节结构、读-改-写、多核共享必须用临界区、RTOS 原语或 C11 `_Atomic`（BARR-C:2018 1.8.c.ii 关于线程共享数据的 `volatile` 用法已由 Barr Group 撤回）。

```c
/* 反例：ISR 写结构体，任务读到的可能是半更新的数据。 */
volatile imu_sample_t g_imu_sample;

/* 正例：ISR 只投递，任务侧完整拷贝。 */
static void
imu_drdy_isr (void)
{
    BaseType_t b_woken = pdFALSE;

    vTaskNotifyGiveFromISR(gh_imu_task, &b_woken);
    portYIELD_FROM_ISR(b_woken);
}
```

## 3. RTOS 集成

- ISR 中只用 `FromISR` API：`xQueueSendFromISR`、`xSemaphoreGiveFromISR`、`vTaskNotifyGiveFromISR`、`xTaskNotifyFromISR`，结束时 `portYIELD_FROM_ISR(woken)`。
- CMSIS-RTOS2 中 `osMessageQueuePut`、`osSemaphoreRelease`、`osEventFlagsSet`、`osThreadFlagsSet` 可在 ISR 调用，但**超时参数必须为 0**。
- **FreeRTOS + Cortex-M 优先级**：数值越小优先级越高。调用任何 FreeRTOS API 的 ISR，其优先级数值必须 **≥** `configMAX_SYSCALL_INTERRUPT_PRIORITY`（即逻辑上不高于它）。优先级高于此阈值的中断（如数值 0 的控制环定时器）**不能调用任何 FreeRTOS API**，只能通过寄存器级机制（如挂起一个较低优先级的软件中断）把事件传递出去。开启 `configASSERT` 让移植层检查这一点。
- 中断优先级按实时关键性分配：控制环时基 > 传感器数据就绪/DMA > 通信 > 人机交互。通信突发不得推迟控制环。

## 4. 任务设计

- 一个任务一个职责：采集、控制、通信、服务（日志、存储、看门狗）分开。
- 周期任务用绝对时间：`vTaskDelayUntil`/`xTaskDelayUntil` 或 `osDelayUntil`，不要用 `vTaskDelay` 累积漂移。处理 tick 回绕（用无符号差值比较）。
- 控制环周期与通信时序解耦；控制任务优先级最高，通信不阻塞控制。
- IPC 选择：数据流 → 队列；状态通知 → 事件标志/任务通知；共享资源 → 互斥量（支持优先级继承，ISR 不可用）。
- 资源所有权：每个外设/总线只有一个所有者任务，其他任务经所有者的 API/队列访问。
- 栈：为每个任务记录栈预算，开启栈溢出检测（`configCHECK_FOR_STACK_OVERFLOW`），用 `uxTaskGetStackHighWaterMark` 实测余量。
- 静态分配优先：`xTaskCreateStatic`、`xQueueCreateStatic`；初始化完成后不再动态分配。

## 5. 看门狗与 DMA

- 看门狗只在**验证了各子系统的实际进展**后喂狗（例如每个关键任务在本周期置位“存活位”，监控任务检查全部置位后才喂狗），不要在定时器 ISR 里无条件喂狗。
- DMA 完成中断只通知任务；数据处理在任务中进行。
- 有 D-cache 的内核（如 Cortex-M7）：DMA 缓冲区对齐到 cache line，发送前 clean、接收后 invalidate，或放在 non-cacheable 区域（MPU 配置）；缓冲区生命周期必须覆盖整个传输。
- 双缓冲/半传输中断：明确哪一半当前由 DMA 拥有。

## 6. C++ 对应

C++ 版本的模式见 [cpp-patterns.md](cpp-patterns.md) §4、§6：`IrqLock`、`OsMutex` + `std::lock_guard`、`SpscRing`、`etl::queue_spsc_isr`、`DmaRxLease`。

原子操作的链接与 lock-free 限制（ARMv6-M 上 32 位 RMW 链接失败，32 位 MCU 上 64 位原子链接失败）见 [cpp-coding.md](cpp-coding.md) §7。

## 7. 相对 rovinax 原版的修订

| 原版 | 问题 | 修订 |
| --- | --- | --- |
| 固定 ISR 时间表（GPIO < 5 µs 等） | 无依据的通用数字，与实际时钟/负载无关 | 按项目设定预算并实测 |
| `EXTI->PR1 \|= (1U << 0);` | W1C 寄存器读-改-写会误清其他挂起位 | 直接赋值写 1 |
| 控制环定时器设为优先级 0 且调用 `FromISR` | 违反 FreeRTOS Cortex-M 的 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 约束 | 见 §3 |
| CMSIS-RTOS2 `osMessageQueuePut(..., timeout)` 既列为允许又列为禁止 | 自相矛盾 | ISR 中超时必须为 0 |
| `volatile` 可用于 ISR 共享变量即可 | 不提供原子性 | 见 §2 |
| 无 ISR 命名与默认向量规则 | 缺少 BARR-C 6.5 | 见 §1 |
