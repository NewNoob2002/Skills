# Third-party notices

## rovinax/embedded-skills

references/mcu-architecture.md 与 references/mcu-isr-rtos.md 改编自 <https://github.com/rovinax/embedded-skills>（已修订，见各文件“相对 rovinax 原版的修订”一节）。

```text
MIT License

Copyright (c) 2026 rovinax

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.```

## Barr Group BARR-C enforcement kit

assets/barr-c/ 与 scripts/barrc/check.sh 原样复制自 <https://github.com/netrinomike/barr-c>（2018/，commit 75bcc16）。许可证全文见 assets/barr-c/LICENSE。BARR-C 标准本身版权归 Barr Group 所有，本技能只引用规则编号并意译要点。

## brunofbloq/embedded-agent-skills

references/workflow.md 借鉴其工作流结构（角色分工、两阶段架构门、证据级别、任务契约），为独立改写，未复制原文。该仓库未声明许可证。

## Modern Embedded C++ 模块的参考来源

`references/cpp-*.md`、`assets/cpp/` 与 `scripts/cpp_cost.py`、`scripts/bench/` 为本技能独立编写。以下项目只作为规则与设计的参考，**未复制其源代码或文档原文**；规则编号与要点为意译，实测数据由 `scripts/bench/` 在本地生成。

| 项目 | 许可 | 参考内容 |
| --- | --- | --- |
| Pigweed <https://github.com/google/pigweed> | Apache-2.0 | 嵌入式 C++ 指南、尺寸优化、C++ 风格（标准库头文件分级、无异常/无堆策略、ISR/线程安全标注、`--wrap` 抛异常辅助函数、丢弃 `.fini_array`） |
| modm <https://github.com/modm-io/modm> | MPL-2.0 | 静态类型外设与编译期波特率校验的设计思路 |
| ETL <https://github.com/ETLCPP/etl> | MIT | 模板通过公开 API 使用 ETL（`etl::span`、`etl::expected`、`etl::queue_spsc_isr`）；ETL 本身不随本技能分发 |
| C++ Core Guidelines <https://github.com/isocpp/CppCoreGuidelines> | Standard C++ Foundation 许可 | 规则编号与要点 |
| CppUTest <https://github.com/cpputest/cpputest> | BSD 风格 | 测试模板通过公开 API 使用 CppUTest/CppUMock；CppUTest 本身不随本技能分发 |

`assets/cpp/.clang-format` 派生自上文 Barr Group BARR-C enforcement kit 的 `.clang-format`（MIT），仅修改列宽并增加 C++ 选项。
