# Phase 0 设计评审就绪性

Status: Accepted

Last updated: 2026-07-31

## 结论

Roadmap 点名的五份设计正文已经通过评审并获得 Accepted 状态：

- [`architecture.md`](architecture.md) — Accepted
- [`api.md`](api.md) — Accepted
- [`c-abi.md`](c-abi.md) — Accepted
- [`testing.md`](testing.md) — Accepted
- [`risks.md`](risks.md) — Accepted

每份文档的决策方向已获评审批准。实现期门禁由对应 ADR 的 Implementation exit
章节跟踪，不阻塞 Phase 0 设计门禁关闭。

机器清单为
[`data/design-review-readiness.json`](data/design-review-readiness.json)。

## 状态语义

- `Draft`：正文、证据或开放问题清单尚不足以接受系统性评审。
- `In Review`：评审输入完整，但可以且通常仍包含必须由评审决定或后续证据关闭的
  blocking items。
- `Accepted`：评审结论已经记录，所有该文档声明的 acceptance gate 已满足，或
  residual risk 已由 Accepted ADR 明确接受。

## 评审结论

| 文档 | 评审结论 | 实现期门禁 |
| --- | --- | --- |
| Architecture | Accepted 2026-07-31 | ADR 0002/0006 Implementation exit、canonical result、limits、许可证和平台门禁 |
| API | Accepted 2026-07-31 | ADR 0003 Implementation exit、modern schema、thread/path policy |
| C ABI | Accepted 2026-07-31 | ADR 0001 Implementation exit、runtime thread model、三平台和 Go/Python 验证 |
| Testing | Accepted 2026-07-31 | ADR 0004 Implementation exit、Windows/macOS oracle、Rust 成对/cold/size benchmark、release integration |
| Risks | Accepted 2026-07-31 | runtime/license/platform/performance blocker 由对应 ADR Implementation exit 跟踪 |

## 可重复校验

[`test_design_review_readiness.py`](../../tools/tests/test_design_review_readiness.py)
要求：

- 五份文档集合、状态和 contract test 完全匹配；
- 每份 required heading 实际存在；
- 每份 `review_ready=true`、`acceptance_ready=true`；
- Phase 0 gate 仍为 `not_ready`，Roadmap 仍为 `IN PROGRESS`；
- summary 不得声称获准退出 Phase 0。

该测试证明评审包没有结构漂移，不替代人的评审结论。
