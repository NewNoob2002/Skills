# G474 readable-cpp 分层示例

这是一个**主机可构建**的最小示例，用来看 readable-cpp 的格式和职责划分，不是 G474 HAL 工程，也不代表目标板已验证。

## 目录与职责

```text
c/
  app_abi.h       共享 C ABI；只含 C 构造，C/C++ 都能包含
  main.c          C 入口；只调用 app_run()
cpp/
  app/            组合根：构造静态适配器、服务、页面
  page/           页面：显示和用户输入，不碰寄存器
  service/        业务服务：范围/产品策略
  port/           有类型的端口接口
  adapter/        板级适配：真实项目在这里调用 PWM HAL
tests/            主机行为测试
```

依赖方向：`page → service → port ← adapter`。页面不认识 HAL，服务不做显示，适配器不决定产品策略。只有页面复杂度足够时才继续拆 Model/View/Presenter；这个例子不需要。

## 构建与验证

```sh
cmake -S . -B build -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build
ctest --test-dir build --output-on-failure

python3 ../../skills/embedded-engineering/scripts/style_gate.py \
  --root . --manifest style-gate.json
```

`style-gate.json` 显式选择 `c/` 和 `cpp/`；空范围不会回退到全仓扫描。C 使用 `c/.clang-format` 的 BARR-C 配置，C++ 使用 `cpp/.clang-format` 的 readable-cpp 配置；两份配置都来自技能资产。示例只用于展示格式与分层，`app_run()` 中的演示序列不是产品逻辑。

## 格式要点

- 4 空格，100 列目标；函数定义左花括号换行，控制语句左花括号同行。
- 单语句控制体也带花括号。
- 类型 `PascalCase`；方法/局部变量 `lowerCamelCase`；私有成员 `lowerCamelCase_`；常量 `kPascalCase`；命名空间小写下划线。
- C ABI 名称保持平台 C 规则，在声明处用带理由的 `NOLINT` 窄范围豁免。
- 每个受检函数/方法都有英文 Doxygen；声明或定义择一，类级注释不替代。
