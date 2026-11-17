# readable-cpp、ABI 与平台门禁增量验证（2026-11-17）

## 1. 对象、范围与来源

仓库 `https://github.com/NewNoob2002/Skills.git`，实际 HEAD 为 `5cae6d9b5fdbec57222016c80de2701db020bbc9`。开始时 `git status --short` 为空，无未提交改动。结束时 HEAD 保持不变，`git status` 对应 19 个已跟踪文件修改、16 个新文件，本轮改动留在工作树，范围为技能、安装器、相关测试、README/design/验证报告及本页证据；不推送、不修改其他固件仓库、不烧录、不访问实机。不覆盖旧报告、`evals/RESULTS.md` 或历史 Agent 评测。结构索引为 123 行入口、135 条规则。

实际读取的固定版本如下；完整理由亦见 [来源记录](../../skills/embedded-engineering/references/sources.md)。GitHub API 返回 403，网页抓取不可用后，以临时只读 Git clone 读取源文件，没有更改网络安全配置。

| 来源 | 实际版本和路径 | 分类与采用理由 |
| --- | --- | --- |
| X-TRACK `dev_lvgl_v9` | `28b0e90898eb6fcb474c7a354459242c781d780a`；`Firmware/X-TRACK/App/App.cpp`、`App/UI/Dashboard/{Dashboard,DashboardModel,DashboardView}.{cpp,h}`、`App/Service/DataProc/DP_Backlight.cpp`，相同固件根下 `Frameworks/PageManager/{PageManager.h,PageBase.h,PageManager.cpp,PageManagerRouter.cpp,PageManagerState.cpp}` | **样例观察**：组合根、页面生命周期、显示/数据/服务分工；函数花括号换行和控制体同行仅是观察。没有读取整个 Frameworks；不把样例升格为标准，不复制实现、裸资源所有权或 void 指针事件 |
| InfiniTime `main` | `9ad16304f5fd526b781a760cf1313813d232645e`；`doc/coding-convention.md` | **上游明文规则**：2 空格、同行花括号、camelCase 变量、成员无前后缀。证明上游贡献应服从项目规则；不是本地 4 空格/成员后缀的出处 |
| Pigweed | `c9174437f47c28f60d4b1a14ad9835049b5782dc`；`docs/sphinx/style_guide.rst`、`docs/sphinx/style/cpp.rst`（网站 style guide 对应源码） | **上游明文规则**：Google 风格及其覆盖、clang-format、共享 C/C++ 头的 C 兼容、控制体花括号、生命周期/所有权说明。未将全部 Pigweed 堆限制施加给 Linux |
| 本仓库 | 本轮工作树 | **新增约定**：readable-cpp 的完整布局/命名组合、三项独立选择、显式安装和门禁清单、默认逐函数 Doxygen、原创背光分工例子。没有冒称由某上游完整规定 |

## 2. 环境与可重跑命令

工具实测：Python 3.14.10、uv 0.13.6、clang/clang-format/clang-tidy 23.1.4、GCC/G++ 16.2.1 20260810、Arm GNU 15.3.Rel2（15.3.1 20260627）、CMake 4.5.0、Ninja 1.13.2、QEMU 11.1.3、pi 1.5.2。已有用户级依赖 ETL 20.49.0、CppUTest 4.0、FreeRTOS V11.3.3；本轮没有安装工具。门禁清单校验 LLVM 主版本 23，CI 模板还要求项目工具镜像填写固定 digest；占位符需项目填实。

先完成基线：结构 32 PASS；Python 254 passed、2 skipped、150 subtests passed（未设置 ETL/CppUTest 环境变量）。系统 Python 无 pytest，随后使用仓库约定的 uv；不把第一次环境失败算通过。最终完整回归设置依赖路径：

```sh
python3 tools/validate_skill.py
ETL_INCLUDE="$HOME/.local/share/embedded-eval/etl/include" \
CPPUTEST_PREFIX="$HOME/.local/share/embedded-eval/cpputest-install" \
  uv run -q --with pytest --with pyyaml python -B -m pytest -q tests
uv run -q --with pyyaml python3 tools/run_evals.py \
  freertos-cpp mcu-baremetal-c linux-userspace --strict \
  --json /tmp/skills-engineering-evals.json \
  --report /tmp/skills-engineering-evals.md
sh -n install.sh skills/embedded-engineering/scripts/barrc/check.sh
git diff --check
```

最终完整回归为 **267 passed、178 subtests passed、无跳过（135.71s）**；结构为 **32 PASS、0 FAIL、0 NOT_RUN、0 BLOCKED**；shell 语法与 `git diff --check` 通过。期间曾出现一次 **265 passed + 1 failed**：`bad_brightness.hpp` 被格式化后失去无花括号控制体，导致 `CPPF-001` 预期失败；恢复该负例并增加主头优先包含用例后重跑通过。最终日志本地路径为 `/tmp/skills-final-structure.log`、`/tmp/skills-final-pytest.log`，核心结果已在本页归档，不要求临时文件长期存在。

工程验证本轮重跑 **3 个工程、27 个变体**：25 MATCH、2 KNOWN_GAP、0 MISMATCH、0 NOT_RUN。3 个 good 通过，22 个负例按预期检出；已知漏报为 MCU ISR 工作量和 Linux signal printf（均依赖人工/运行上下文评审）。没有声称全部 6 工程/50 变体在本轮重跑。C++ 模板完整测试包含 18 次 ARM C++17/20 × M0+/M4/M7 编译、4 个预期失败、格式/tidy/分层与 CppUTest；MCU C 工程运行 QEMU，Linux C 工程运行 CMock/ASan/UBSan，FreeRTOS 工程运行 POSIX 集成。

## 3. 新增工程与失败诊断

`tests/test_readable_cpp.py` 每次生成临时工程，使用真实 CMake/Ninja 编译数据库，并执行构建、CTest、风格门禁。没有伪造数据库，也不依赖临时目录永久存在。

| 验收 | 实际结果与证明范围 |
| --- | --- |
| G474 风格混编 | `.ioc` 表达 G474 工程背景；C 使用 BARR-C，C++ 目录显式 readable-cpp；同一 ABI 头由 C 与 C++ 独立包含、C 调用/C++ 实现、真实链接并在主机运行。不是 G474 HAL 或板上测试 |
| 正例与反例 | `brightness.hpp` 独立包含通过；坏样例布局和命名分别匹配 CPPF-001、readability-identifier-naming；没有把语法错误当命名检出 |
| 缺文档负例 | 删除方法的 Doxygen 后保持可编译；exit 1 且命中 `DOC-001 ... missing Doxygen block for setLevel`；加类注释或普通注释仍失败。声明/定义择一可通过；内部链接同名函数不能跨 TU 借用文档 |
| RK3588 风格 Linux C++ | 最小 SocketCAN socket + epoll 主机程序；profile 为 linux-userspace/T3，项目 2 空格/snake 风格优先。异常/RTTI 路径实际编译运行；检查编译/链接命令无 MCU `-fno-exceptions/-fno-rtti` 或 linker_discard。没有绑定 CAN 接口或访问板卡 |
| 识别回归 | `.c/.cpp/.cc/.cxx` × epoll/can/can-raw 共 12 组，另验证带 MCU 子树的混合仓库仍保留 Linux 候选 |
| 安装/配置 | 两种 C++ 配置显式选用；已有配置（含祖先）保留；目录越界、vendor 路径/别名拒绝；空文件范围无工具也 PASS EMPTY，不全仓回退；缺工具 exit 3 TOOL_MISSING，坏配置/缺数据库 exit 2 CONFIG_ERROR |
| readable-cpp 分层示例 | `examples/g474-backlight`：C ABI 入口、页面/业务服务/端口/假适配器分层；CMake+Ninja 构建、CTest 1/1、`style_gate` PASS。主机示例，不是 G474 HAL 或板上运行证据 |

独立复现的精确负例摘要（临时路径归一化）：

```text
naming exit 1
CPPF-002 clang-tidy:
<TEMP>/cpp/brightness.hpp:10:10: error: invalid case style for method 'set_level' [readability-identifier-naming,-warnings-as-errors]
missing-doc exit 1
DOC-001 cpp/brightness.hpp:8: missing Doxygen block for setLevel
```

Doxygen 自动化只证明编译可达、显式自有范围里的函数关联了文档块，不能证明英文质量、参数/返回/错误/上下文/所有权语义，也不强制重复文档。类注释不能替代逐函数注释；宏、未实例化模板、未编译条件分支、未包含头仍需评审。C ABI 命名豁免只在必要声明处给理由，不关闭整个目录。共享 `.h` 不被笼统视作 C；Zephyr 应用 C++、ESP-IDF 与 Linux 保留项目/平台风格，BARR-C 范围只用于已采用该规则的自有 C。

## 4. 真正写入 Agent 的补丁验收

使用 pi-subagents 的 `worker`，同步脚本驱动、一个 writer，工作目录为新建临时仓库 `/tmp/skills-agent-g474.5ybl_82v`。通过本仓库安装器装入本轮技能并提供 AGENTS.md；仅允许编辑 `c/backlight.h`、`c/main.c`、`cpp/backlight.cpp`。未触及任何现有固件仓库，也没有提交或推送。

实际新增 `uint32_t backlight_step(uint32_t current_percent, uint32_t requested_percent)`，C 声明、C++ 实现、C 调用。先 clamp 到 100，再向目标移动不超过 5，覆盖六个独立期望值：`(0,100)->5`、`(40,10)->35`、`(98,120)->100`、`(5,0)->0`、`(25,25)->25`、`(UINT32_MAX,0)->95`。Agent 首轮因常量局部变量命名触发 tidy，修正源代码后通过，没有放宽配置。父会话独立重跑以下全部通过：

```sh
cmake --build /tmp/skills-agent-g474.5ybl_82v/build
ctest --test-dir /tmp/skills-agent-g474.5ybl_82v/build --output-on-failure
python3 skills/embedded-engineering/scripts/style_gate.py \
  --root /tmp/skills-agent-g474.5ybl_82v \
  --manifest /tmp/skills-agent-g474.5ybl_82v/style-gate.json
```

构建成功、CTest 1/1、BARR-C/CPPF/DOC 门禁成功。完整三文件 diff 留存为 [Agent 补丁](readable-cpp-2026-11-17-agent.patch)，SHA256 `4b1c13cec98a0aca01a3f2fe60ef61ff7b1b9b9e1645db7bb368dc20b86453a2`。这是单次验收，不是历史多 Agent 成功率评测的替代。

额外交叉构建同一补丁：C 使用 `arm-none-eabi-gcc -std=c11 -mcpu=cortex-m4 -mthumb -Os -ffreestanding -Wall -Wextra -Werror -I c -c c/main.c`；C++ 使用 `arm-none-eabi-g++ -std=c++17` 同组目标选项，加 `-fno-exceptions -fno-rtti`。链接使用 `-nostdlib -Wl,-e,main -Wl,-Ttext=0x08000000 ... -lc -lgcc`，`nm` 确认 `main/backlight_clamp/backlight_step` 为未改名强符号。首次纯 `-nostdlib` 链接因 C 测试表初始化需要 `memcpy` 失败；正确链接 newlib 后通过，未修改业务实现或伪造 libc。此 ELF 仅用于 ABI 链接验证，没有 G474 启动代码/向量表，不能烧录运行。目标运行 NOT_RUN。

## 5. 初始化堆保护

从本地 HEAD 取原始 guard，在主机真实复现：锁后普通 `operator new` 收到 SIGILL（exit -4），aligned new 返回成功（exit 0）；旧模板没有 aligned replacement。修复覆盖 8 个 new/12 个 delete，包括数组、aligned、nothrow、sized delete。普通失败 trap，nothrow 返回 nullptr；null delete 无操作，非空 delete trap。

`tests/test_heap_guard.py` 对 GCC/Clang × C++17/20 运行独立进程：每组 11 个正常模式和 17 个预期 trap 模式；要求 trap 标记和 SIGILL/SIGTRAP 同时匹配。覆盖锁定前后、64 字节对齐、exact capacity、padding、零长、SIZE_MAX、过大/非二次幂对齐及失败不耗容量。Arm GNU C++17/20 × M0+/M4/M7 编译并核对强符号。规则、1024/64 容量/对齐边界与不支持项见 [堆护栏说明](../../skills/embedded-engineering/references/cpp/heap-guard.md)。

模板仅覆盖单线程初始化期的全局 C++ replacement ABI；placement、类专属分配器、C malloc/calloc/realloc/aligned_alloc、RTOS/库内部入口不在范围。没有目标运行证据；最终 MCU ELF 链接选择、初始化顺序、并发和故障安全态仍需目标项目验收。

## 6. 未执行与剩余风险

- **NOT_RUN**：G474/RK3588 实板、真实 CAN 收发、目标堆护栏运行和时间/栈/ISR 指标；用户本轮禁止实机操作。
- **NOT_RUN**：GitHub Actions/GitLab 托管平台。只执行本地 YAML/结构校验和同一门禁；模板镜像/preset 占位符必须由使用项目填写。
- **NOT_RUN**：本轮没有重跑 Zephyr、ESP-IDF、Linux kernel 工程及历史 28 用例多 Agent 批次；历史证据保留其原日期。
- **NOT_RUN**：IAR/ARM Compiler replacement ABI；Clang 裸机目标缺完整 sysroot，不能从 host Clang 推断支持。
- 编辑器 LSP 的新样例探测有超时，不能声称 LSP 全绿；真实编译、显式 format/tidy、回归测试才是上述判断依据。故意负例与共享 C ABI/C 文件误继承默认 C++ 风格的诊断均按语境记录，不为编辑器关闭真实门禁。
- 风格工具不能完整证明列宽、头独立性、同名头优先的所有边界以及接口语义；需保持文档所列人工审查。Clang 对 GCC 目标特有参数不能解析时应生成可信分析数据库，标配置失败，不能计作规则检出。

## 7. 2026-11-17 补充：逐函数 Doxygen 默认化

对象：`5cae6d9b5fdbec57222016c80de2701db020bbc9` 上的同一工作树。审计前已有的未提交改动全部保留；本轮没有 reset、stash、commit 或 push，没有修改其他固件仓库，没有烧录或实机操作。

变更：`style_gate.py` 的 `doxygen` 从选择性开关改为默认 `true`；`DOC-001` 改为默认强制，覆盖新增自有的 C/C++ 函数、方法与成员函数（含私有、构造、析构、模板和重载），声明或定义择一，类级注释不能替代。默认英文，项目可在 `AGENTS.md` 指定语言；第三方、生成代码、遗留基线不选入清单，显式 `doxygen:false` 须记录原因。同步更新 `SKILL.md`、`rules.yaml`、`coding.md`、`barr-c.md`、`readable-cpp.md`、`profiles.md`、`review-checklist.md`、`AGENTS.md.template`、README 与来源/证据措辞。

验证：
- `python3 -B tools/validate_skill.py`：32 PASS、0 FAIL、0 NOT_RUN、0 BLOCKED。
- `python3 -B -m unittest tests.test_readable_cpp -v`：8 项通过。新增 `test_doxygen_defaults_to_enabled`，在不写 `doxygen` 键时分别删除 C++ 方法文档和 C `main` 文档，均得到预期 `DOC-001` 缺失诊断；原有 G474 混编、RK3588 SocketCAN/epoll、默认风格优先级和失败诊断用例同时通过。
- 工具链：Python 3.14.10、clang-format/clang-tidy 23.1.4、GCC/G++ 16.2.1、CMake 4.5.0、Ninja 1.13.2、Arm GNU 工具链可用；ETL 与 CppUTest 使用 `/home/gtc/.local/share/embedded-eval/` 下的本地安装。
- 完整 Python 回归：`ETL_INCLUDE=/home/gtc/.local/share/embedded-eval/etl/include CPPUTEST_PREFIX=/home/gtc/.local/share/embedded-eval/cpputest-install python3 -B -m unittest discover -s tests -v`，**268 项通过、0 跳过**（142.305s，最终改动后完整运行）。C++ 集成依赖 ETL 与 CppUTest，非跳过。

边界：`DOC-001` 自动检查只证明编译可达且显式自有范围内存在关联文档块；英文质量、参数/返回值/错误/ISR/线程上下文/所有权语义、宏生成、未实例化模板、未编译条件分支和未被 TU 触达的头仍需人工评审。目标 MCU/RK3588 板上运行与 GitHub/GitLab 托管 CI 仍为 **NOT_RUN**。
