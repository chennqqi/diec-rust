# 调研文档

本目录只记录上游事实、实验结果和证据，不提前写入本项目的实现决策。

Phase 0 计划形成：

- [`upstream-baseline.md`](upstream-baseline.md)：版本、构建、submodule、依赖和许可证（Draft）。
- [`capability-matrix.md`](capability-matrix.md)：CLI/engine 能力与证据索引（Draft）。
- [`source-analysis.md`](source-analysis.md)：模块关系及扫描/规则调用链（Draft）。
- [`rule-compatibility.md`](rule-compatibility.md)：规则语法、内建函数和宿主 API（Draft）。
- [`rule-runtime-spike.md`](rule-runtime-spike.md)：Boa 全库解析、真实复杂规则、宿主绑定和资源限制验证（Draft）。
- [`rquickjs-rule-runtime-spike.md`](rquickjs-rule-runtime-spike.md)：rquickjs/QuickJS-NG 全库执行、sloppy 语义、native 构建和资源限制验证（Draft）。
- [`nintendo-certified-rule.md`](nintendo-certified-rule.md)：唯一 legacy 规则的项目生成语料与真实 detect 基线（Draft）。
- [`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)：Binary 数据库分层、init/include 选择、共享引擎生命周期和排序缺陷（Draft）。
- [`signature-language.md`](signature-language.md)：signature 文法、固定 oracle、静态/动态调用清单和边界行为（Draft）。
- [`rule-syntax-inventory.md`](rule-syntax-inventory.md)：全规则 AST 语法、全局引用和宿主调用形状清单（Draft）。
- [`host-api-inventory.md`](host-api-inventory.md)：XScanEngine C++ slot、继承、默认参数与规则调用覆盖（Draft）。
- [`global-host-api-inventory.md`](global-host-api-inventory.md)：die_script 非格式 native globals、规则顶层函数与直接调用分类（Draft）。
- [`script-scope-semantics.md`](script-scope-semantics.md)：Qt Script 跨规则 lexical 环境与 QuickJS 差分（Draft）。
- [`script-state-semantics.md`](script-state-semantics.md)：Qt Script 跨规则 var/function/global 持久状态与 wrapper 风险（Draft）。
- [`c-static-link-spike.md`](c-static-link-spike.md)：Windows/Linux C staticlib、所有权、panic/CRT 和系统依赖验证（Draft）。
- [`cli-dependency-and-license.md`](cli-dependency-and-license.md)：CLI 源码/链接依赖闭包与许可证初审（Draft）。
- [`upstream-build-baseline.md`](upstream-build-baseline.md)：固定 Linux Qt5/qmake CLI 构建与行为实验（Draft）。
- [`upstream-cmake-differential.md`](upstream-cmake-differential.md)：官方 CMake CLI 构建及与 qmake 的原始输出差分（Draft）。
- [`behavior-baseline.md`](behavior-baseline.md)：确定性安全语料、原始输出哈希和多格式行为（Draft）。
- [`cli-special-modes.md`](cli-special-modes.md)：entropy/info/struct 的 schema、优先级和边界行为（Draft）。
- [`cli-path-behavior.md`](cli-path-behavior.md)：多目标、目录递归、输出聚合和错误顺序（Draft）。
- [`database-error-behavior.md`](database-error-behavior.md)：数据库缺失/损坏、规则错误和不可读输入（Draft）。
- [`nested-scan-behavior.md`](nested-scan-behavior.md)：archive/resource/overlay 的选项可达性、结果树和资源限制（Draft）。
- [`data/cli-dependencies.toml`](data/cli-dependencies.toml)：固定组件依赖边、LICENSE blob 和 bundled code 证据。
- [`data/baseline-corpus.json`](data/baseline-corpus.json)：生成语料的文件名、意图、大小和 SHA-256。
- [`data/path-corpus.json`](data/path-corpus.json)：由基线字节组成的确定性嵌套目录树。
- [`data/database-fixture.json`](data/database-fixture.json)：项目生成的数据库成功/故障 fixture。
- [`data/nested-corpus.json`](data/nested-corpus.json)：安全的 archive/resource/overlay 嵌套语料清单。
- [`data/boa-rule-runtime.json`](data/boa-rule-runtime.json)：Boa spike 输入哈希、固定版本和稳定结果摘要。
- [`data/rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json)：rquickjs spike 输入哈希、固定版本和稳定结果摘要。
- [`data/nintendo-certified-corpus.json`](data/nintendo-certified-corpus.json)：PS3/PS Vita Certified File 分支语料清单。
- [`data/nintendo-certified-baseline.json`](data/nintendo-certified-baseline.json)：双 oracle 原始输出哈希和 detection 摘要。
- [`data/binary-rule-lifecycle.json`](data/binary-rule-lifecycle.json)：固定 Binary records、helper 解析、源码 hash 和比较器环证据。
- [`data/binary-rule-order-linux-qt5.json`](data/binary-rule-order-linux-qt5.json)：固定 qmake/CMake oracle 的 292 条 Binary profiling 执行顺序。
- [`data/script-scope-fixture.json`](data/script-scope-fixture.json)：项目生成的跨规则作用域 fixture 清单。
- [`data/script-scope-qt5.json`](data/script-scope-qt5.json)：固定 qmake/CMake oracle 的作用域行为基线。
- [`data/script-state-fixture.json`](data/script-state-fixture.json)：项目生成的跨规则持久状态 fixture 清单。
- [`data/script-state-qt5.json`](data/script-state-qt5.json)：固定 qmake/CMake oracle 的持久状态行为基线。
- [`data/binary-cross-rule-state.json`](data/binary-cross-rule-state.json)：固定 Binary 顺序的跨规则状态静态审计摘要。
- [`data/signature-static-inventory.json`](data/signature-static-inventory.json)：全规则具名 signature API 调用点和保守静态值清单。
- [`data/net-bytecode-patterns.json`](data/net-bytecode-patterns.json)：固定 PE Generic 规则的 .NET bytecode pattern 有限值域。
- [`data/rule-syntax-inventory.json`](data/rule-syntax-inventory.json)：2235 个规则脚本的 AST、运算符、global 和宿主调用机器清单。
- [`data/host-api-inventory.json`](data/host-api-inventory.json)：固定 XScanEngine 宿主声明、继承和规则 arity 覆盖清单。
- [`data/host-api-arity-qt5.json`](data/host-api-arity-qt5.json)：固定 Qt 5 QObject wrapper 的额外实参与缺失方法异常基线。
- [`data/global-host-api-inventory.json`](data/global-host-api-inventory.json)：固定 die_script global 注册面、规则函数和 undeclared direct-call 分类。
- [`data/global-host-api-qt5.json`](data/global-host-api-qt5.json)：真实 `DiE_ScriptEngine` 的 Qt 5 native global 转换与副作用基线。
- [`data/c-static-link.json`](data/c-static-link.json)：C static-link spike 输入哈希、ABI 符号、平台依赖和稳定结果摘要。

每份文档遵守 [`../README.md`](../README.md) 的证据和状态约定。实验附件如需版本化，应使用文本格式并放入主题对应的子目录。
