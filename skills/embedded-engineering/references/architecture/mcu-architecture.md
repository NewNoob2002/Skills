# MCU 固件架构（`mcu-baremetal` / `mcu-rtos`）

基于 rovinax/embedded-skills（MIT）的 `embedded-architecture` 与 `embedded-driver-design`，按 BARR-C 与实际工程做了修订，修订点见 §7。Zephyr 与 Linux profile **不适用**本文件的目录结构，见 §6。

## 1. 原则

单一职责、低耦合、高内聚、显式接口、硬件抽象、可移植、可测试、确定性。业务逻辑不得依赖 MCU 厂商库、CMSIS、RTOS 内部 API 或外设寄存器。

## 2. 目录分层

```text
project/
├── app/          # 组合根：启动顺序、状态机编排、任务创建、接口实例绑定
├── module/       # 业务逻辑：motor/ imu/ control/ telemetry/ storage/
├── interface/    # 硬件服务契约：uart_if.h spi_if.h gpio_if.h（只有声明）
├── driver/
│   ├── bus/      # 总线驱动：实现 interface/ 中的总线契约（可用 platform/）
│   └── device/   # 器件驱动：icm42688/ w25q/，只依赖总线接口
├── bsp/          # 板级映射：把接口绑定到具体外设/引脚
├── platform/     # 厂商代码：platform/<target>/{core,hal,cmsis,startup,linker}
├── middleware/   # 第三方：freertos/ lwip/ fatfs/ usb/
├── docs/
├── tools/
└── tests/        # Ceedling 测试与 support/
```

厂商生成的 `Core/`、`Drivers/` 不得留在仓库根目录，放入 `platform/<target>/`。已有项目迁移目录属于大规模变更，需要用户授权；未授权时只对新增代码执行分层规则。

## 3. 依赖规则

允许的 `#include` 方向（`scripts/arch_lint.py` 的默认配置 `assets/arch_layers.json` 与此一致）：

| 层 | 可以依赖 | 禁止 |
| --- | --- | --- |
| `app` | module, interface, bsp, driver, middleware | HAL、寄存器、厂商设备头 |
| `module` | interface, 其他 module 的公共头 | HAL、CMSIS、寄存器、RTOS 头、bsp、platform |
| `interface` | interface, 标准头 | 一切实现 |
| `driver/device` | interface | HAL、platform、寄存器 |
| `driver/bus`、`bsp` | interface, platform, middleware | app, module |
| `platform` | platform | 其他所有层 |
| `middleware` | middleware, platform | app, module |

说明：

- `bsp/`、`driver/bus/` 包含 `interface/` 头是为了**实现**契约（依赖倒置），不是反向依赖。
- `app/` 是组合根，可以包含 bsp 头以取得接口实例，但不得调用 HAL。
- 模块间依赖只经公共头，禁止循环依赖。
- RTOS：任务创建在 `app/`；任务函数调用 module API。module 需要同步原语时，通过 `interface/osal_if.h` 之类的 OS 抽象，而不是直接包含 `FreeRTOS.h`。

```text
TASK (app) → MODULE API → INTERFACE → BUS/DEVICE DRIVER → PLATFORM
```

## 4. 接口与驱动设计

接口是带上下文指针的函数表，使同一器件驱动能挂在不同总线实例上，也能在 Ceedling 中被 CMock 替换：

```c
typedef struct
{
    proj_err_t (*p_write)(void * p_ctx, uint8_t const * p_data, size_t len);
    proj_err_t (*p_read)(void * p_ctx, uint8_t * p_data, size_t len);
    void * p_ctx;
} spi_if_t;
```

器件驱动规则：

- 设备上下文结构体持有总线接口指针与器件状态，不使用文件级全局状态（便于多实例与测试）。
- 寄存器地址与位定义放 `<device>_reg.h`，全部命名常量，无魔数。
- 初始化显式分阶段：参数校验 → 读 ID 校验 → 软复位 → 配置；每步检查返回值。
- 驱动不直接调用 RTOS；需要等待/延时时通过注入的 OSAL 或回调。
- 每个阻塞操作都有超时并返回明确错误码。
- 驱动的 host 测试 mock 的是**总线接口头**，不是 HAL。

## 5. 架构检查清单

- [ ] 新代码落在正确层；app/module 无 HAL 调用、无寄存器访问（`arch_lint.py` 通过）
- [ ] 厂商/CubeMX 代码只在 `platform/`
- [ ] 每个硬件服务都有接口；接口头只有声明
- [ ] 无循环依赖；模块单一职责，无 `misc`/`utility`/`system_manager` 式上帝模块
- [ ] BSP 与 platform 中无业务逻辑
- [ ] 器件驱动可以只用 mock 总线在 host 上测试

发现违规时：报告违规 → 说明危害 → 给出正确结构 → 在授权范围内重构。

## 6. 非 MCU profile 的对应关系

- **Zephyr**：设备模型（`DEVICE_DT_DEFINE`、`DEVICE_API`）、devicetree 与 Kconfig 已经提供接口/BSP 层。不要在 Zephyr 设备 API 之上再造一层 `spi_if_t`；业务模块直接依赖 Zephyr 驱动 API 或子系统 API，板级差异放在 overlay 与 Kconfig。
- **Linux kernel**：遵循子系统框架（platform driver、regmap、IIO、input、net 等），不发明私有抽象层。
- **Linux userspace**：硬件访问集中在一个适配层（字符设备、`libgpiod`、`spidev`、`i2c-dev`、sysfs/IIO），业务逻辑与之隔离以便 host 测试。

## 7. C++ 实现

同样的分层用 C++ 表达：

- 构建期绑定的接口用 Concept/模板注入，运行期选择的接口用纯虚接口。
- 驱动是以总线 Concept 为模板参数的类模板。
- 组合根在 `app/` 中用 `constinit` 对象搭建。

示例与模板见 [cpp/patterns.md](../cpp/patterns.md) 与 `assets/cpp/templates/`。`arch_lint.py` 同时检查 `.cpp/.hpp`。

## 8. 相对 rovinax 原版的修订

| 原版 | 问题 | 修订 |
| --- | --- | --- |
| 头文件可用 `#pragma once` | BARR-C 4.2.b 要求预处理 guard，1.1.c 限制 `#pragma` | 统一 `#ifndef MODULE_H` guard |
| 禁止所有 `int` | BARR-C 5.2.a 只要求“宽度重要时”用定宽类型；与 SDK/标准库接口冲突 | 宽度重要时必须定宽；`short`/`long` 禁止（5.2.b） |
| 全局错误类型名 `error_t` | 与 glibc `<errno.h>` 的 `error_t`（GNU 扩展）冲突，Ceedling host 构建可能报重定义；BARR-C 5.1.c 要求公共类型带模块前缀 | 使用 `<proj>_err_t` |
| 接口函数表无上下文指针 | 无法多实例，难以 mock | 增加 `p_ctx` |
| 未提及变量前缀 | BARR-C 7.1.j–n 要求 `g_`、`p_`、`pp_`、`b_`、`h_` | 加入 [c/barr-c.md](../c/barr-c.md) |
| `TASK → MODULE` 但 module 可能直接用 RTOS | 破坏可测性 | module 通过 OSAL 接口 |
