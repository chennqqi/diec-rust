# Phase 0 ADR 评审就绪性

Status: Accepted

Last updated: 2026-07-31

## 结论

当前十四个有效 ADR 全部通过评审并获得 Accepted 状态。每个 ADR 的
`## Decision acceptance` 章节记录 Phase 0 评审批准的决策方向，
`## Implementation exit` 章节列出 Phase 1+ 实现期门禁。

ADR 0007 已被 ADR 0011 Superseded，不属于当前待接受集合。机器清单见
[`data/adr-review-readiness.json`](data/adr-review-readiness.json)。

## 已接受决策

| ADR | 核心决策 | 实现期门禁 |
| --- | --- | --- |
| 0001 | opaque handles、paired free、JSON-first v1 | 多语言 consumer、sanitizer、最终 thread/ABI diff |
| 0002 | 向内依赖 workspace 与 ports/adapters | Cargo DAG、vertical slice、bounded queue |
| 0003 | legacy raw 与 modern canonical 永久分离 | modern schema、跨 Rust/C/CLI canonical bytes、默认 profile |
| 0004 | 默认拒绝且 evidence-bound 的精确 waiver | 真实 owner workflow、modern/engine variants、release signing |
| 0005 | deterministic text facts 取代未初始化状态 | Phase 1 SafetyDeviation 与 production HostApi |
| 0006 | rquickjs/QuickJS-NG 作为首个私有 backend | 全量 HostApi、跨平台 static archive、许可证/SBOM |
| 0008 | 固定 order manifest 取代非传递 comparator | 全规则 manifest、Rust loader、Windows/macOS order |
| 0009 | modern cancel 不返回 partial detections | production Rust/JSON/C mapping、race/recovery、legacy waiver |
| 0010 | include cycle 提前有界失败 | dynamic/custom database、production graph/stack、边界/fuzz |
| 0011 | 默认 Rust 1.97.1、MSRV 1.88 | Phase 1 default/MSRV CI jobs |
| 0012 | 全 scan 嵌套预算有限，legacy high-resource 仍有 hard ceiling | production budget、Rust 全 limit 边界、跨平台资源与 waiver |
| 0013 | short read/I/O/seek/range fail closed | production ByteSource、跨 adapter typed error、fuzz/sanitizer |
| 0014 | safe canonical 不跟随枚举 link；legacy alias 仍受 hard stop | production TargetExpander、边界/TOCTOU/root confinement |
| 0015 | warm、file-content-nonresident-metadata-warm、dedicated system-cold 三层 | dedicated authority/isolation、macOS runtime closure |

## 评审约束

- ADR 的 `Accepted` 状态表示决策方向获批准；Implementation exit 中的条件在
  Phase 1+ 满足后才视为完整交付。
- ADR 0006 的七类代表规则、全语法 inventory 和资源 spike 是重要证据，但不是
  全量规则/HostApi/平台兼容率。
- ADR 0005、0010、0013 与 0014 都是安全偏差，必须保留 ADR 0004 的精确
  waiver 与原始上游证据；不能在 normalizer 中隐藏。
- ADR 0011 的本机双工具链门禁不能替代 Phase 1 CI。
- ADR 0015 的 per-file `mincore=0` 不能外推为 system-cold。

## 可重复校验

[`test_adr_review_readiness.py`](../../tools/tests/test_adr_review_readiness.py)
验证：

- 十四个 Accepted 与一个 Superseded ADR 的集合、状态完全匹配；
- 每份 ADR 的必要章节和 contract test 实际存在；
- 全部 active ADR `review_ready=true`、`acceptance_ready=true`；
- summary 反映 decision gate complete；
- Phase 0 总门禁仍为 `not_ready`。

该校验只证明评审输入完整，不替代评审人。
