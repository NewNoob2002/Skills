# 可选 readable-cpp v1 与显式门禁

平台 profile、资源等级、编码风格是三个独立选择。例如 G474 可为 `mcu-rtos / T1 / readable-cpp`，RK3588 可为 `linux-userspace / T3 / project`。风格不启用或关闭异常、RTTI、堆或链接裁剪。默认方案 A 保持不变；readable-cpp 仅对项目或指定自有 C++ 目录显式选用。目标上游贡献按上游规则，既有配置优先，第三方、生成代码和厂商 SDK 不应用此风格。

## 1. 本仓库新增约定

| 项目 | readable-cpp v1 | 证明范围 |
| --- | --- | --- |
| 缩进/列宽 | 4 空格，100 列目标（不可断的字符串等可超过） | clang-format |
| 花括号 | 函数定义左括号换行，控制语句同行；单语句控制体也加括号 | clang-format + clang-tidy；宏内人工审查 |
| 类型 | `PascalCase` | clang-tidy `CamelCase` |
| 函数、方法、局部变量、参数 | `lowerCamelCase` | clang-tidy `camelBack`；C ABI 名称人工核对并窄范围 NOLINT |
| 私有成员 | `lowerCamelCase_` | clang-tidy |
| 常量（含枚举值） | `kPascalCase` | clang-tidy；模板依赖名人工审查 |
| 命名空间 | 小写下划线 | clang-tidy |
| include | 同名实现头优先，头文件能独立包含 | clang-format 部分排序；独立包含须编译测试，宏条件/间接依赖人工审查 |

工具文件是 `assets/cpp/readable-cpp/.clang-format` 和 `.clang-tidy`。命名工具不是 C++ 语义规范的完整证明；公共 C API 必须保留平台 C 命名，若在 C++ TU 中触发命名告警，在 ABI 声明处写具理由的 `NOLINTNEXTLINE(readability-identifier-naming)`，不得给整个目录关闭检查。共享 `.h` 只含 C 构造，用 `#ifdef __cplusplus` 保护 linkage；不是所有 `.h` 都是 C。参考可编译的 [ABI 样例](../../assets/cpp/abi/backlight.h)。

正例（与 `assets/cpp/readable-cpp/examples/brightness.hpp` 相同，所有函数文档在声明/定义之一）：

```cpp
namespace display_ui {
class Brightness
{
  public:
    /// @brief Set the requested level. Thread context only; owns no resources.
    /// @param requestedLevel Desired percent; values above 100 are clamped.
    void setLevel(unsigned requestedLevel)
    {
        if (requestedLevel > kMaxLevel) {
            requestedLevel = kMaxLevel;
        }
        level_ = requestedLevel;
    }

  private:
    static constexpr unsigned kMaxLevel = 100;
    unsigned level_ = 0;
};
} // namespace display_ui
```

反例见 `assets/cpp/readable-cpp/examples/bad_brightness.hpp`：`set_level`、`requested_level`、`level` 私有成员缺后缀，以及无花括号控制体。反例必须分别由命名/布局规则检出，不能把编译失败当成功。该文件是故意未格式化的测试夹具，**不要对它运行 `clang-format -i`**；否则 `InsertBraces` 会插入花括号，布局负例失效。

## 2. 选择与安装

```sh
# 安装技能，并在已存在的自有 C++ 子目录放置选定配置；已有本级/祖先配置逐项跳过。
sh install.sh --agent codex --scope project --project-dir /path/to/project \
  --cpp-style readable-cpp --cpp-dir app_cpp
# 默认方案也须显式选择配置安装：--cpp-style default-cpp --cpp-dir app_cpp
```

安装不会替换既有配置，即使指定 `--overwrite`（该参数仅替换技能副本）。已有配置需要人工合并，不能用读取技能目录的 `--style=file:...` 偷偷覆盖。混编目录的 C 与 C++ 布局不同，应以显式文件清单分流。可在无配置的自有范围中使用门禁 `style=readable-cpp` fallback；有项目配置时须使用 `style=project`，按每个文件最近配置查找。

清单示例（所有路径相对项目根；`.h` 的角色由清单显式指定，`doc_headers` 只检查文档，不施加 C++ 布局）：

```json
{
  "version": 1,
  "llvm_major": 23,
  "style": "project",
  "compile_commands": "build/compile_commands.json",
  "cpp": ["app_cpp/*.cpp", "app_cpp/*.cc", "app_cpp/*.cxx"],
  "cpp_headers": ["app_cpp/*.hpp"],
  "c": ["module/*.c", "module/*.h"],
  "doc_headers": ["interface/*.h"],
  "doxygen": true
}
```

以下假设 `SKILL_DIR` 指向本技能目录；仓库内为 `skills/embedded-engineering`，安装后为对应 Agent 的技能目录。

```sh
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build
python3 "$SKILL_DIR/scripts/style_gate.py" --root . --manifest style-gate.json
```

`cpp` 只放编译单元，头文件通过 TU 的真实编译选项检查。独立包含测试另行构建；未被任何 TU 包含的头不在命名/文档语义覆盖内。C 范围只适用于采用 BARR-C 的自有 C 代码；Zephyr/ESP-IDF 使用其平台门禁。C++ 命名用真实 compilation database，不以裸 `-- -std=c++17` 代替；交叉 GCC 特有参数若 Clang 不接受，生成可供 Clang 使用且保留目标/宏/include 的数据库，失败标 CONFIG_ERROR，不能算规则检出。

退出码：0 PASS（空集显示 `PASS EMPTY`，不调用工具）；1 真实违规；2 CONFIG_ERROR（无效配置、缺编译项或解析失败）；3 TOOL_MISSING。LLVM major 由清单固定并校验，默认 23；升级须重新跑正反例，不自动使用任意版本。GitHub/GitLab 模板都在构建生成数据库后调用同一门禁；CI 工具镜像须锁版本。

## 3. 默认逐函数 Doxygen 规则

**默认启用**：所有新增自有 C/C++ 函数与方法（含私有方法、构造、析构、模板和重载）必须有 Doxygen，声明或定义择一，不重复。**类级注释不能替代逐函数说明**。默认英文；项目在 `AGENTS.md` 指定其他注释语言时按项目，上游贡献仍按上游规则。按接口需要解释参数、返回值、错误语义、ISR/线程上下文和所有权；`void` 函数无须虚构返回值。C API 保留 C 命名。

`style-gate.json` 的 `doxygen` 默认 `true`；只有显式写 `false` 才关闭，且应仅用于遗留基线、第三方或生成代码，并在项目规则中记录原因。`doxygen=true` 使用 Clang AST 只检查被选范围中显式函数关联的 Doxygen 块是否存在，声明和定义可跨 TU 合并；不验证英文质量、标签完整性、语义或重复内容。普通 `//`、文件级块或类级块不算逐函数文档。宏生成的声明、未实例化模板特殊路径、条件编译未选分支以及未被 TU 触达的头留给评审。门禁是范围检查，不自行猜测 git 中哪些行“新增”：迁移项目选定新增目录/文件，既有代码按团队基线处理。报告必须同时写这些覆盖限制。
