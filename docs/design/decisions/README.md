# Architecture Decision Records

使用顺序编号，例如 `0001-rule-runtime-strategy.md`。每份 ADR 至少包含：

- Status
- Context
- Decision
- Alternatives considered
- Consequences
- Evidence

已接受的 ADR 不直接改写历史；需要改变决策时新增 ADR，并将旧 ADR 标记为 `Superseded`。

当前 ADR：

- [`0001-c-abi-opaque-ownership.md`](0001-c-abi-opaque-ownership.md)：
  C ABI 不透明句柄、配对释放、one-shot 与 reusable scanner（Proposed）。
- [`0002-layered-workspace.md`](0002-layered-workspace.md)：
  向内依赖 workspace、ports/adapters 与有界嵌套队列（Proposed）。
- [`0003-dual-output-contract.md`](0003-dual-output-contract.md)：
  分离上游兼容输出与 canonical API/CLI 输出（Proposed）。
- [`0004-evidence-bound-difference-waivers.md`](0004-evidence-bound-difference-waivers.md)：
  默认拒绝、精确 fingerprint 且有期限的兼容差异 waiver（Proposed）。
- [`0005-deterministic-text-classification.md`](0005-deterministic-text-classification.md)：
  显式初始化文本事实，不复制 `Binary_Script` 的未初始化状态（Proposed）。
- [`0006-rquickjs-rule-runtime.md`](0006-rquickjs-rule-runtime.md)：
  以私有 rquickjs/QuickJS-NG backend 作为首个规则运行时，保留严格兼容层、
  资源和 static-link 门禁（Proposed）。
- [`0007-rust-toolchain-baseline.md`](0007-rust-toolchain-baseline.md)：
  固定 Rust 1.88 作为当前默认工具链与显式 MSRV，并将后续升级绑定到可重复证据
  （Proposed）。
- [`0008-pinned-rule-order-manifest.md`](0008-pinned-rule-order-manifest.md)：
  不在 Rust runtime 复刻非传递 comparator，以 source/target/oracle 绑定的显式
  顺序清单驱动 legacy 规则执行（Proposed）。
- [`0009-cancellation-result-contract.md`](0009-cancellation-result-contract.md)：
  modern API 用类型化取消代替上游部分成功结果，legacy 保留原始证据（Proposed）。
