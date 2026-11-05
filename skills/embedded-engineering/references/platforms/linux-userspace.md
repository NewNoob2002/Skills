# Embedded Linux userspace profile

适用于运行在嵌入式 Linux 上的守护进程、工具、HMI 后端、协议网关等。没有统一的官方 C 风格，规则来源依次为：项目既有规范 → 所在发行版/框架规范（如 systemd 风格、GNOME、Yocto recipe 风格）→ BARR-C 安全核心（[c/barr-c.md](../c/barr-c.md) §2）。

## 1. 架构

- **硬件适配层集中**：GPIO 用 `libgpiod`（字符设备 `/dev/gpiochipN`，不用已弃用的 sysfs GPIO）；SPI 用 `spidev`；I2C 用 `i2c-dev`；ADC/传感器优先 IIO（`/sys/bus/iio` 或 `libiio`）；串口用 termios。业务逻辑只依赖适配层接口，便于 host 测试。
- 需要中断级时延、确定性控制环的功能不要放在 userspace：交给内核驱动、协处理器（RPMsg/remoteproc）或 MCU，并在架构评审中说明边界。
- 进程模型：systemd 服务（`Type=notify` + `sd_notify` 看门狗、`Restart=`、资源限制、`ProtectSystem=` 等加固）；进程间用明确的协议（D-Bus、Unix socket、共享内存 + 同步）。
- 配置与持久数据：原子写（写临时文件 → `fsync` → `rename` → 目录 `fsync`），防掉电损坏；只读根文件系统时数据放专用分区。

## 2. 编码要点

- 检查每个系统调用返回值，处理 `EINTR`、部分读写（`read`/`write` 返回值小于请求长度）。
- 信号处理函数中只调用 async-signal-safe 函数；优先 `signalfd` 或 self-pipe。
- 资源释放成对：文件描述符、内存、锁；错误路径统一清理（此 profile 下可按项目惯例使用 `goto` 清理）。
- 线程共享数据用 `pthread_mutex`/`_Atomic`，不依赖 `volatile`。
- 外部输入（网络、串口、文件、环境变量）全部校验长度与范围。
- 以非 root 运行，最小权限（capabilities、udev 规则授予设备访问）。

## 3. 测试与检查

| 层 | 工具 |
| --- | --- |
| 单元测试 | 项目既有框架；无则 C 用 Ceedling/Unity（[verification/ceedling.md](../verification/ceedling.md)）或 cmocka，C++ 用 CppUTest（[verification/cpp-testing.md](../verification/cpp-testing.md)） |
| 运行期检测 | `-fsanitize=address,undefined`（host 与支持的目标），Valgrind |
| 静态检查 | 编译告警门禁、clang-tidy、cppcheck；采用 BARR-C 格式层时运行 `scripts/barrc/check.sh` |
| 集成 | QEMU 镜像、目标板 + 实际外设；记录镜像版本与内核版本 |

交叉构建使用 Yocto SDK（`source environment-setup-*`）或项目工具链文件；报告时区分 host 结果与目标板结果。
