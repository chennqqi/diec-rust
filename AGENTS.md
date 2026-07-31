# 项目协作约定

开始工作前先阅读 [README.md](README.md)、[ROADMAP.md](ROADMAP.md) 和 [docs/README.md](docs/README.md)。

## 当前阶段

项目目前处于 Roadmap Phase 1。Phase 0 设计门禁已于 2026-07-31 评审通过并关闭，
五份调研正文、五份设计正文和十四个有效 ADR 全部 Accepted；`P0-BLOCK-005`（macOS
运行时基线采集）deferred 至 Phase 1 与 Rust 实现并行完成。Phase 1 建立工程骨架、
跨平台 CI、规则同步、差分测试基础设施并冻结首版内部结果模型；公共 ABI 仍保持
实验状态。调研正文写入 `docs/research/`，设计正文写入 `docs/design/`，不要堆积在
本文件或 `README.md` 中。

## 兼容基线

- 上游为 `https://github.com/horsicq/DIE-engine`。
- 所有结论和差分测试固定到确切 commit SHA，不使用“最新版”作为基线。
- 能力结论必须附上游源码位置、固定版本文档或可重复实验。
- 上游规则原样保存，不格式化或手工修改；同步时记录来源路径、commit、哈希和时间。
- Rust 与上游的可观察差异默认视为缺陷。确认需要偏离时，必须用 ADR 记录理由并增加回归测试。
- 导入代码、规则、submodule 或样本前核对许可证并保留归属信息。

## 架构与安全

- CLI 和 FFI 是核心库的薄适配层，核心层不得依赖它们或 GUI 框架。
- 优先纯 Rust、跨平台依赖。引入大型依赖、native 依赖或系统库必须记录权衡。
- 默认不使用 `unsafe`；确有必要时限制在最小模块，记录安全不变量并覆盖边界测试。
- 所有二进制输入均不可信。偏移、长度、整数运算和分配必须受控；畸形输入不得导致 panic、越界、无限循环或无界分配。
- 扫描结果使用统一结构化模型并保持确定性；CLI、JSON 和 FFI 不得各自实现检测逻辑。
- 性能变更以可重复 benchmark 或 profiling 为依据。

## 规则、ABI 与测试

- 规则解析不得静默忽略未知语法；不支持项必须产生明确诊断并计入兼容性失败。
- C ABI 只使用固定布局 C 类型和不透明句柄；不得暴露 Rust 类型。
- FFI 必须明确所有权、释放函数、线程安全和 ABI 版本，且 panic 不得跨越边界。
- 每项能力包含单元/集成测试，并按风险补充差分、FFI、fuzz、性能和跨平台测试。
- 差分测试保留原始及规范化输出；规范化不得隐藏有语义的差异。
- 不直接提交恶意或来源不明样本；使用可重复生成器、哈希清单或隔离语料库。

## 完成与提交

- 新行为有测试，缺陷修复有回归用例。
- Rust workspace 建立后，提交前运行：
  - `cargo fmt --check`
  - `cargo clippy --workspace --all-targets --all-features -- -D warnings`
  - `cargo test --workspace --all-features`
- 兼容行为运行固定上游版本的对应差分测试；ABI 变更运行 C 链接和生命周期测试。
- 更新相关调研/设计文档、能力矩阵和基线记录。
- 规则同步、实现、FFI 和 CLI 变更尽量分别提交。
- 不提交构建产物、临时扫描输出、私有样本或本机路径。

