# diec-rust

使用 Rust 重新实现 [horsicq/DIE-engine](https://github.com/horsicq/DIE-engine)。

项目目标是在保持上游检测能力和规则语义兼容的前提下，改善架构、代码质量、性能、依赖规模与可移植性。“Rust 重写”不表示逐行翻译 C++：兼容的是能力、规则语义、输入输出和边界行为，内部设计采用清晰、安全、可测试的 Rust 架构。

## 目标

- 与固定版本 DIE-engine 的检测能力及可观察行为一致。
- 原样复用上游检测规则，并保持来源、版本和内容可追溯。
- 提供无 GUI 的命令行程序，包括适合自动化使用的结构化输出。
- 提供稳定 C ABI，可构建静态 `.a`（Windows 对应 `.lib`），供 C、Go 和 Python 调用。
- 通过单元、集成、差分、FFI、模糊、性能及跨平台测试证明兼容性和可靠性。

## 当前范围

Phase 0 设计门禁已通过，Phase 1 工程骨架与兼容测试基础设施已关闭。项目现处于
Phase 2，实现受控字节读取、通用扫描上下文和格式探测与解析，按能力矩阵逐步交付
并与上游逐格式差分验证。公共 C ABI 仍保持实验状态。

GUI 不在当前交付范围内，作为未来计划保留。

## 设计方向

计划采用 Cargo workspace，分离以下职责：

- 核心扫描编排和公共数据模型。
- PE、ELF、Mach-O、DEX、archive 等格式解析。
- 上游规则加载、解析、编译与执行。
- C ABI 和内存生命周期管理。
- CLI 表示层。
- 规则同步、基线采集和差分测试工具。

最终 crate 划分将在上游调研和架构评审后确定，不以本节作为未经验证的实现承诺。

## 项目文档

- [ROADMAP.md](ROADMAP.md)：调研门禁、阶段计划、交付物和未来方向。
- [AGENTS.md](AGENTS.md)：开发和评审必须遵守的工程约束。
- `docs/research/`：上游事实与实验结果。
- `docs/design/`：架构、API、ABI、测试方案与决策记录。
- `upstream/DIE-engine/`：固定 SHA 的上游主仓库 subtree，仅用于参考和变更跟踪。
- `upstream/Detect-It-Easy/`：与主仓库 gitlink 一致的规则/发布数据 sibling subtree。
- `upstream/components.lock.toml`：主仓库与关键组件的 SHA、角色和物化方式。

## 上游与许可证

- 上游项目：<https://github.com/horsicq/DIE-engine>
- DIE-engine 仓库当前标注为 MIT License。

导入上游代码、规则、子模块或测试样本前，仍需逐项核对来源和许可证，并保留归属信息。规则同步必须固定到具体 commit，不使用含义不明确的“最新版”作为兼容基线。
