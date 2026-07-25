# 设计文档

本目录保存由调研证据支持的 diec-rust 设计。尚未完成上游调研的部分应明确标记为待定。

Phase 0 计划形成：

- `architecture.md`：workspace、模块边界、依赖方向和数据流。
- `api.md`：Rust API、CLI 契约、结果及错误模型。
- `c-abi.md`：C ABI、所有权、线程安全和静态链接。
- `testing.md`：语料、oracle、差分、fuzz、benchmark 和 CI。
- [`upstream-sync.md`](upstream-sync.md)：DIE-engine subtree 和组件锁定策略（Accepted）。
- [`decisions/`](decisions/)：重大决策的 ADR。

设计文档必须链接所依据的 `docs/research/` 文档。被后续设计取代时保留历史内容并将状态改为 `Superseded`，同时链接替代文档或 ADR。
