# Phase 0 设计门禁审计

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 结论

Phase 0 当前为 **not ready**，`ROADMAP.md` 必须继续保持 `IN PROGRESS`。这不是
因为调研数量不足：三项技术验证已经有可重复证据，风险清单和后续阶段门禁也已
形成。稳定 capability traceability 已在本轮闭合；其余阻塞点是现有证据还没有
闭合为可评审的 Phase 0 决策。

机器可读结论保存在
[`data/phase-0-gate-review.json`](data/phase-0-gate-review.json)。该清单只判断
Phase 0 设计门禁，不把 Phase 2—6 的实现期风险误当成当前必须关闭的功能。

## Roadmap 退出条件

| ID | 退出条件 | 当前判断 | 证据或缺口 |
| --- | --- | --- | --- |
| `P0-EXIT-001` | 能力矩阵每项有源码或可重复实验 | Not ready | 68 个稳定 `CAP-*` 已绑定固定源码/实验；8 个 coverage gap 仍使 Phase 0 coverage 不完整 |
| `P0-EXIT-002` | 基线覆盖主要格式和代表规则语法 | Not ready | 26 个安全格式样本、七类专用规则差分已存在；`testing.md` 和能力矩阵仍明确声明格式覆盖不足 |
| `P0-EXIT-003` | 三项技术验证完成或记录替代 | Ready for review | rquickjs runtime、C static link 和固定 Linux upstream oracle 均有可重复证据及边界 |
| `P0-EXIT-004` | 架构、规则 runtime、ABI、测试方案完成评审 | Not ready | 五份必需设计已进入 In Review、但未获得评审结论；十个有效 ADR 均为 Proposed |
| `P0-EXIT-005` | 风险清单完整 | Ready for review | 20 项风险均含触发、缓解、验证和关闭条件，但文档仍需评审 |
| `P0-EXIT-006` | 后续阶段有可测完成条件 | Ready for review | `ROADMAP.md` 与 `testing.md` 已给出 Phase 1—6 的量化门禁 |
| `P0-EXIT-007` | 性能基线与资源目标得到回答 | Not ready | benchmark 方法已设计，但 runner、环境、上游基线、阈值和默认资源限制未冻结 |

`Ready for review` 不等于 `Accepted`，也不允许把 Roadmap 状态改为 `DONE`。

## 必需交付物

Roadmap 点名的五份调研正文和五份设计正文均已存在。调研正文仍为 Draft；设计中
只有 subtree 同步方案已经 Accepted，以下五份门禁正文已进入 In Review：

- [`architecture.md`](architecture.md)
- [`api.md`](api.md)
- [`c-abi.md`](c-abi.md)
- [`testing.md`](testing.md)
- [`risks.md`](risks.md)

这表示正文已具备评审输入，不表示 Accepted，证据见
[`design-review-readiness.md`](design-review-readiness.md)。当前有效决策中，
ADR 0001—0006 与 0008—0011 共十份仍为 Proposed；ADR 0007 已被 0011
Superseded，不计作待接受决策。不能仅因对应 spike 通过就自动把 ADR 改为
Accepted。

## 三项技术验证

1. 规则 runtime：固定规则、生命周期、语法/HostApi inventory、资源限制和七类
   专用规则差分已有证据；ADR 0006 的全量 HostApi、跨平台 static archive、
   许可证和正式 backend 门禁尚未满足。
2. C static link：Windows/Linux x64 的首轮 `.lib`/`.a`、C 调用、所有权、
   panic containment 和依赖证据已存在；它不是最终 C ABI 或三平台发布证明。
3. upstream oracle：固定 SHA 的 Linux Qt5 qmake/CMake oracle、生成语料和原始
   输出哈希可重复；Windows/macOS oracle 尚未固定。

因此这三项可进入评审，但其受限范围必须原样保留。

## 阻塞项与关闭证据

| ID | 阻塞项 | 要求的关闭证据 |
| --- | --- | --- |
| `P0-BLOCK-001` | Closed | 68 个稳定 CAP ID、四级验证状态、证据路径和 8 个 gap 已写入 manifest，并由测试与上游 lock 绑定 |
| `P0-BLOCK-002` | Open | 五份设计已 review-ready/In Review；仍缺 architecture、API、C ABI、testing、risks 的明确评审结论 |
| `P0-BLOCK-003` | Open | 每份 ADR 进入 Accepted、Rejected 或 Superseded，并保存评审证据 |
| `P0-BLOCK-004` | Open | runtime `db*` 2,268 文件身份及根 MIT/marker 已闭合；仍需 PNG/历史贡献、其余 source closure 和发布责任人书面评审 |
| `P0-BLOCK-005` | Open | 固定平台基线及无 Phase 0 missing row 的 coverage report |
| `P0-BLOCK-006` | Open | 固定环境的上游 benchmark、可测 latency/memory/size 目标和默认资源限制 |

## 下一步顺序

1. `P0-BLOCK-001` 已关闭；后续能力增删必须同时修改 matrix/manifest，validator
   会拒绝 ID、固定 commit、证据路径或汇总计数漂移。
2. 继续把当前 Linux 证据映射到 coverage report，精确拆分已覆盖、source-only、
   platform-missing 和 corpus-missing，收敛 `P0-BLOCK-005`。
3. 并行准备许可证和 benchmark 评审材料；不得用技术可行性替代许可证结论，
   也不得在没有固定环境时声称性能改善。
4. 技术 blocker 清零后提交设计/ADR 评审；只有评审结论落盘后才能更新
   `ROADMAP.md` 并进入 Phase 1。

## 防误报约束

[`test_phase0_gate_review.py`](../../tools/tests/test_phase0_gate_review.py) 校验：

- Roadmap 仍为 Phase 0 `IN PROGRESS`；
- 清单中的每个文档和证据路径真实存在，且记录状态与 front matter 一致；
- 必需研究、设计、spike、退出条件和 blocker ID 完整且唯一；
- 存在 blocker 时结果只能是 `not_ready`；
- 本文列出的 blocker 状态和有效 Proposed ADR 数不发生静默漂移。

该测试不替代评审，也不会自动接受 ADR。
