# 设计文档

本目录保存由调研证据支持的 diec-rust 设计。尚未完成上游调研的部分应明确标记为待定。

- [`schemas/`](schemas/)：raw execution/framing、legacy CLI semantic result、
  normalization、双侧 semantic comparison、差分输入、精确 waiver registry 和
  audit 的版本化 machine-readable schema 与 synthetic examples。

Phase 0 计划形成：

- [`architecture.md`](architecture.md)：workspace、模块边界、依赖方向和数据流（In Review）。
- [`api.md`](api.md)：Rust API、CLI 契约、结果及错误模型（In Review）。
- [`c-abi.md`](c-abi.md)：C ABI、所有权、线程安全和静态链接（In Review）。
- [`testing.md`](testing.md)：语料、oracle、差分、fuzz、benchmark 和 CI（In Review）。
- [`risks.md`](risks.md)：Phase 0 风险、触发条件、缓解和关闭证据（In Review）。
- [`phase-0-gate-review.md`](phase-0-gate-review.md)：Phase 0 退出条件、阻塞项及
  关闭证据的审计总账（In Review）。
- [`design-review-readiness.md`](design-review-readiness.md)：五份必需设计从
  Draft 进入 In Review 的结构证据、开放阻塞项和防误报约束（In Review）。
- [`upstream-sync.md`](upstream-sync.md)：DIE-engine subtree 和组件锁定策略（Accepted）。
- [`decisions/`](decisions/)：重大决策的 ADR。

设计文档必须链接所依据的 `docs/research/` 文档。被后续设计取代时保留历史内容并将状态改为 `Superseded`，同时链接替代文档或 ADR。
