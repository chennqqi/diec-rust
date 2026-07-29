# Phase 0 设计评审就绪性

Status: In Review

Last updated: 2026-07-30

## 结论

Roadmap 点名的五份设计正文已经从 Draft 进入 In Review：

- [`architecture.md`](architecture.md)
- [`api.md`](api.md)
- [`c-abi.md`](c-abi.md)
- [`testing.md`](testing.md)
- [`risks.md`](risks.md)

这只表示每份文档都已有目标/非目标、证据、核心契约、开放门禁和可验证验收条件，
可以提交评审。五份文档的 `acceptance_ready` 全部为 false；Phase 0 仍是
`IN PROGRESS`，不得开始正式功能实现。

机器清单为
[`data/design-review-readiness.json`](data/design-review-readiness.json)。

## 状态语义

- `Draft`：正文、证据或开放问题清单尚不足以接受系统性评审。
- `In Review`：评审输入完整，但可以且通常仍包含必须由评审决定或后续证据关闭的
  blocking items。
- `Accepted`：评审结论已经记录，所有该文档声明的 acceptance gate 已满足，或
  residual risk 已由 Accepted ADR 明确接受。

因此不能因为状态从 Draft 变为 In Review 就：

- 将 `ROADMAP.md` Phase 0 改为 DONE；
- 将 Proposed ADR 自动改为 Accepted；
- 冻结尚未决定的公共 Rust API、C ABI 数值或默认资源限制；
- 把 Linux-only、source-only 或 spike 证据外推为完整兼容；
- 将 spike 代码直接搬入正式 workspace。

## 文档评审焦点

| 文档 | 已具备的评审输入 | 仍阻止 Accepted |
| --- | --- | --- |
| Architecture | workspace/DAG、checked input、queue、runtime port、结果与 adapter 边界 | ADR 0002/0006、canonical result、limits、许可证和平台门禁 |
| API | source/request/limits/cancel/report/diagnostic、legacy/modern 分离；scan/traversal/include 候选已统一并列出 9 个 unresolved budget | ADR 0003、modern schema、未决 limits、thread/path policy |
| C ABI | opaque handle、布局、状态、所有权、panic、thread/static link | ADR 0001、runtime thread model、三平台和 Go/Python 验证 |
| Testing | capability/raw/semantic/waiver、fuzz、FFI、performance、CI/release；limit 候选具备 hash-bound 机器契约 | ADR 0004、Windows/macOS oracle、Rust 成对/cold/size benchmark、9 个未决 limits、release integration |
| Risks | 20 项完整风险、owner、触发/缓解/验证/关闭、Phase 0 gate | 设计/ADR 评审结论及 runtime/license/platform/performance blocker |

## 可重复校验

[`test_design_review_readiness.py`](../../tools/tests/test_design_review_readiness.py)
要求：

- 五份文档集合、状态和 contract test 完全匹配；
- 每份 required heading 实际存在；
- 每份 `review_ready=true`、`acceptance_ready=false` 且 blocking items 非空；
- Phase 0 gate 仍为 `not_ready`，Roadmap 仍为 `IN PROGRESS`；
- summary 不得声称获准退出 Phase 0。

该测试证明评审包没有结构漂移，不替代人的评审结论。
