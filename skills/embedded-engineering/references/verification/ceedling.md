# Ceedling 测试基线（MCU host 单元测试）

Ceedling = Unity（断言）+ CMock（从头文件自动生成 mock）+ 构建编排。基线版本 **1.x**（核实时最新为 1.2.2）；0.31 → 1.0 有破坏性变更，旧项目先读官方 `docs/BreakingChanges.md`。

## 1. 安装与创建

```sh
gem install ceedling           # 需要 Ruby；或使用官方 Docker 镜像 throwtheswitch/madsciencelab
ceedling new --local --gitsupport <name>   # --local 把 Unity/CMock/Ceedling 放进 vendor/，锁定版本
ceedling upgrade <project>     # 已 vendor 的项目随 gem 升级
```

已有固件仓库：把 `assets/ceedling/project.yml` 复制到仓库根并按目录调整 `:paths:`；不要为此重排生产代码目录。

## 2. 关键命令

| 命令 | 用途 |
| --- | --- |
| `ceedling test:all` | 运行全部测试 |
| `ceedling test:<name>` | 运行单个测试（如 `test:motor`、同名时 `test:foo/motor`） |
| `ceedling gcov:all` | 覆盖率（需 `gcov` 插件和 gcovr） |
| `ceedling files:source` / `files:test` | 列出 Ceedling 看到的文件集合，排查“找不到源文件” |
| `ceedling clobber` | 清理构建目录 |
| `ceedling help` | 列出当前配置下的全部任务 |

## 3. 1.x 配置要点

- `:project:` ↳ `:use_test_preprocessor:` 取 `:none`（默认）/`:mocks`/`:tests`/`:all`，不再是布尔值。头文件中有 `#ifdef` 或宏生成的声明时用 `:mocks` 或 `:all`（需要 `gcc`/`cpp` 在 PATH）。
- `:project:` ↳ `:compile_threads:`、`:test_threads:` 可设 `:auto`。
- `:import:` 已被 `:mixins:` 取代，用于“同一代码库多个目标变体”。
- `:use_deep_dependencies` 等旧选项已无效。
- 1.1+ 支持 Partials（在同一测试中混用模块的真实函数与 mock，含 `static`/`inline`）；1.2+ 恢复增量构建并新增 Sanitize 插件（ASan/UBSan/LSan）。
- 测试文件内的构建指令：`TEST_SOURCE_FILE("path/file.c")` 额外编译链接一个源文件；`TEST_INCLUDE_PATH("path")` 追加头文件搜索路径（相对于运行 `ceedling` 的目录）。

## 4. 测什么、怎么 mock

| 对象 | 方式 |
| --- | --- |
| `module/` 业务逻辑、状态机、协议解析、滤波/控制算法 | 直接测试，mock 其依赖的 `interface/` 头 |
| `driver/device/` 器件驱动 | `#include "mock_spi_if.h"`，断言寄存器读写序列、错误码传播、超时 |
| `interface/` 契约 | 不单独测试（只有声明） |
| `platform/` 厂商代码 | 不测试 |
| ISR 时序、DMA/cache、抢占 | **Ceedling 无法证明**，交给目标机/HIL；ISR 中的纯逻辑可抽成函数在 host 测试 |

常用 CMock 生成函数（以 `int32_t spi_write(uint8_t const * p_data, size_t len)` 为例）：

- `spi_write_ExpectAndReturn(p_data, len, 0)`：期望调用并比较参数。
- `spi_write_ExpectWithArrayAndReturn(p_data, 3, len, 0)`：按数组内容比较指针参数（`:array` 插件）。
- `spi_write_IgnoreAndReturn(0)`：忽略调用（`:ignore` 插件）。
- `spi_read_ReturnArrayThruPtr_p_data(buf, n)`：通过指针参数回填数据（`:return_thru_ptr` 插件）。
- `spi_write_StubWithCallback(fake)`：自定义行为（`:callback` 插件）。

函数表式接口（`spi_if_t` 结构体中的函数指针）：CMock 只 mock 自由函数。做法是在 `tests/support/` 写一个把函数表指向 CMock 生成的自由函数的适配器，或直接在测试中写 fake 函数赋给函数表。

## 5. 测试编写约定

- 一个生产模块对应 `tests/test_<module>.c`；`setUp()`/`tearDown()` 重置状态。
- 测试名描述行为：`test_motor_set_speed_rejects_value_above_max`。
- 每个公共函数至少覆盖：正常路径、参数校验失败（`NULL`、越界）、依赖返回错误时的传播、边界值（0、最大值、回绕）。
- 期望值来自规格/数据手册/测试向量，不复制实现的计算结果。
- 测试代码本身不需满足 BARR-C 格式层，也不纳入 `check.sh`（文件名前缀 `test_` 会触发 4.1.b）。
- host 编译器（gcc/clang，64 位）与目标（arm-none-eabi，32 位）的差异：`int`/指针宽度、对齐、`char` 符号性、字节序。依赖这些的代码，测试中用定宽类型并在目标上补充验证。

## 6. 覆盖率与 CI

```yaml
:plugins:
  :enabled:
    - report_tests_pretty_stdout
    - gcov
:gcov:
  :utilities: [gcovr]
  :reports: [HtmlDetailed, Cobertura]
```

- CI 中运行 `ceedling test:all` 与 `ceedling gcov:all`，覆盖率阈值由项目定（gcovr 支持 `--fail-under-line` 等，经 `:gcov:` ↳ `:gcovr:` 配置传入）。
- 报告时写明：测试数量、通过/失败/忽略、覆盖率数值与报告路径；Ceedling 未安装或未运行时写 `NOT_RUN` 及原因。
