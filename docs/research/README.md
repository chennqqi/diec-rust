# 调研文档

本目录只记录上游事实、实验结果和证据，不提前写入本项目的实现决策。

Phase 0 计划形成：

- [`upstream-baseline.md`](upstream-baseline.md)：版本、构建、submodule、依赖和许可证（Draft）。
- [`capability-matrix.md`](capability-matrix.md)：CLI/engine 能力与证据索引（Draft）。
- [`source-analysis.md`](source-analysis.md)：模块关系及扫描/规则调用链（Draft）。
- [`rule-compatibility.md`](rule-compatibility.md)：规则语法、内建函数和宿主 API（Draft）。
- [`cli-dependency-and-license.md`](cli-dependency-and-license.md)：CLI 源码/链接依赖闭包与许可证初审（Draft）。
- [`upstream-build-baseline.md`](upstream-build-baseline.md)：固定 Linux Qt5/qmake CLI 构建与行为实验（Draft）。
- [`upstream-cmake-differential.md`](upstream-cmake-differential.md)：官方 CMake CLI 构建及与 qmake 的原始输出差分（Draft）。
- [`behavior-baseline.md`](behavior-baseline.md)：确定性安全语料、原始输出哈希和多格式行为（Draft）。
- [`cli-special-modes.md`](cli-special-modes.md)：entropy/info/struct 的 schema、优先级和边界行为（Draft）。
- [`cli-path-behavior.md`](cli-path-behavior.md)：多目标、目录递归、输出聚合和错误顺序（Draft）。
- [`data/cli-dependencies.toml`](data/cli-dependencies.toml)：固定组件依赖边、LICENSE blob 和 bundled code 证据。
- [`data/baseline-corpus.json`](data/baseline-corpus.json)：生成语料的文件名、意图、大小和 SHA-256。
- [`data/path-corpus.json`](data/path-corpus.json)：由基线字节组成的确定性嵌套目录树。

每份文档遵守 [`../README.md`](../README.md) 的证据和状态约定。实验附件如需版本化，应使用文本格式并放入主题对应的子目录。
