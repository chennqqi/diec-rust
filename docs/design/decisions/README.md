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
