# Phase 0 ADR 评审就绪性

Status: In Review

Last updated: 2026-07-27

## 结论

当前十个有效 Proposed ADR 都具备提交决策评审所需的背景、明确决策、替代方案、
后果/代价、固定证据和验收条件，因此均为 `review_ready=true`。没有任何一个
ADR 满足自身全部 acceptance conditions，因此全部为
`acceptance_ready=false`，不得自动改为 Accepted。

ADR 0007 已被 ADR 0011 Superseded，不属于当前待接受集合。机器清单见
[`data/adr-review-readiness.json`](data/adr-review-readiness.json)。

## 待评审决策

| ADR | 核心评审问题 | 仍缺的主要 acceptance evidence |
| --- | --- | --- |
| 0001 | opaque handles、paired free、JSON-first v1 | 多语言 consumer、sanitizer、最终 thread/ABI diff |
| 0002 | 向内依赖 workspace 与 ports/adapters | Cargo DAG、vertical slice、bounded queue、runtime ADR |
| 0003 | legacy raw 与 modern canonical 永久分离 | modern schema、跨 Rust/C/CLI canonical bytes、默认 profile |
| 0004 | 默认拒绝且 evidence-bound 的精确 waiver | 真实 owner workflow、modern/engine variants、release signing |
| 0005 | deterministic text facts 取代未初始化状态 | Phase 1 SafetyDeviation 与 production HostApi |
| 0006 | rquickjs/QuickJS-NG 作为首个私有 backend | 全 HostApi、正式资源测试、三平台/sanitizer、许可证/SBOM |
| 0008 | 固定 order manifest 取代非传递 comparator | 全规则 manifest、Rust loader、Windows/macOS order |
| 0009 | modern cancel 不返回 partial detections | production Rust/JSON/C mapping、race/recovery、legacy waiver |
| 0010 | include cycle 提前有界失败 | production graph/stack、边界/fuzz、SafetyDeviation |
| 0011 | 默认 Rust 1.97.1、MSRV 1.88 | Phase 1 default/MSRV CI jobs |

## 评审约束

- 评审可以接受“决策方向”，但只有 ADR 自身定义的 acceptance conditions 被机器
  证据满足后，才可把 `Status` 改成 Accepted。
- 若团队决定 acceptance conditions 是实现期门禁而非决策接受前置条件，应先修改
  ADR，明确拆分 `Decision acceptance` 与 `Implementation exit`，不能直接绕过。
- ADR 0006 的七类代表规则、全语法 inventory 和资源 spike 是重要证据，但不是
  全量规则/HostApi/平台兼容率。
- ADR 0005 与 0010 都是安全偏差，必须保留 ADR 0004 的精确 waiver 与原始上游
  证据；不能在 normalizer 中隐藏。
- ADR 0011 的本机双工具链门禁不能替代 Phase 1 CI。

## 可重复校验

[`test_adr_review_readiness.py`](../../tools/tests/test_adr_review_readiness.py)
验证：

- 十个 Proposed 与一个 Superseded ADR 的集合、状态完全匹配；
- 每份 ADR 的必要章节和 contract test 实际存在；
- 全部 active ADR `review_ready=true`、`acceptance_ready=false`，且剩余证据
  和评审问题非空；
- summary 不得声称 Phase 0 decision gate complete；
- Phase 0 总门禁仍为 `not_ready`。

该校验只证明评审输入完整，不替代评审人。
