# T1 初始化期堆护栏的范围

`assets/cpp/templates/bsp/heap_guard.cpp` 是可选的 **MCU T1** 模板，不能由编码风格选择自动链接。初始化在单线程、非 ISR 上完成；先调用全部构造/分配，再 `proj::heap_guard_lock()`，然后启动调度器。锁定不是原子同步，不能与分配并发。T0 不链接它；Linux/T3 不继承它。

## 1. 支持入口与失败策略

声明支持 GNU/Clang 的 C++17/20 replacement new ABI（包括 Arm GNU C++17 对齐分配）。不得使用 `-fno-aligned-new`、其他全局分配器替换、类专属分配器来推断已覆盖。

| 入口 | 覆盖 | 失败/锁定后 |
| --- | --- | --- |
| 普通、数组 `new` | 2 个入口 | `__builtin_trap()`，不抛异常 |
| 普通、数组 `new(nothrow)` | 2 个入口 | `nullptr` |
| aligned 普通/数组 | 2 个入口 | trap |
| aligned + nothrow 普通/数组 | 2 个入口 | `nullptr` |
| unsized/sized/nothrow/aligned/aligned+sized/aligned+nothrow delete，各普通/数组 | 12 个入口 | 非空指针 trap；空指针无操作 |
| placement new | 不拦截 | 使用调用者提供的存储，无新分配 |
| 类专属 `operator new/delete`、自定义内存池、运行库私有分配器 | 不覆盖 | 项目另行审计 |
| `malloc/calloc/realloc/free/aligned_alloc/posix_memalign` 与 RTOS 分配入口 | **不在此模板范围** | 项目通过链接 wrap、库配置或统一分配策略另设门禁 |

arena 默认 1024 字节、基址对齐 64，支持 1..64 的二次幂对齐（普通 new 使用 `max_align_t`）。更大或非法对齐请求明确失败，不回落系统堆。零长请求占用至少 1 字节并按入口对齐；数组 cookie 与 padding 同样消耗容量。容量比较先减后加，`SIZE_MAX` 请求不会因舍入溢出而获得小块。失败的请求不消耗容量。尺寸/对齐必须按实际初始化预算调整并复验。

该策略刻意不提供堆回收；禁止把会销毁动态对象的通用 host 程序直接链接本模板。故障处理应由目标项目替换成记录原因、安全态或复位路径。

## 2. 已执行与未执行

本轮复现基线 `5cae6d9b5fdbec57222016c80de2701db020bbc9`：锁定后直接调用普通 `operator new(16)` 收到 SIGILL；调用 `operator new(64, std::align_val_t{64})` 返回成功。旧模板没有 aligned replacement，运行库接管该入口。旧 `(size + alignment - 1)` 舍入还存在整数溢出风险。

`tests/test_heap_guard.py` 使用独立主机进程直接调用每个入口，避免编译器分配消除；失败必须同时匹配 `HEAP_EXPECT_TRAP:<mode>` 和 SIGILL/SIGTRAP，而非任意非零码。测试覆盖锁前/锁后、nothrow 空返回、exact-capacity、padding 边界、零长、非法/过大对齐与 `SIZE_MAX`。GNU/Clang × C++17/20 主机运行；Arm GNU × C++17/20 × M0+/M4/M7 仅编译并检查对象的 8/12 个强符号。

目标 MCU 运行 **NOT_RUN**。ARM 对象编译不证明启动顺序、实际链接选择、库内部 C 分配、故障安全态或目标多线程正确性；必须在最终 ELF/map 中核对 replacement 符号，再由获得授权的硬件验收覆盖。
