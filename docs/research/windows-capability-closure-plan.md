# Windows Qt5 68 行能力闭合计划

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 目的

本文把 [`capability-traceability.json`](data/capability-traceability.json)
中的 68 个稳定能力 ID 逐行映射到现有 Windows Qt5 runtime 证据，避免把
“已有很多实验”误写成“平台能力已闭合”。机器报告为
[`data/windows-capability-closure-plan.json`](data/windows-capability-closure-plan.json)，
由
[`build_windows_closure_plan.py`](../../tools/research/build_windows_closure_plan.py)
确定性生成。

生成器绑定：

- 固定上游、规则和 68 行 traceability；
- [`windows-qt5-build-baseline.json`](data/windows-qt5-build-baseline.json)；
- 18 份 Windows runtime 报告的完整 SHA-256；
- 每份报告的 source/platform 身份和命名 summary facts；
- 2,210 次 Windows 进程执行，其中新增 legacy/archive dispatch 86 次执行、
  72 次 case observation。

报告只接受三种状态：

| 状态 | 含义 |
| --- | --- |
| `evidence_complete` | 当前 Windows 证据执行了该行在 Linux Qt5 定义的完整边界 |
| `partial` | 已有命名观察，但仍缺该行的一部分边界 |
| `missing` | 没有足以支持该 Windows runtime 行的直接实验 |

源码相同、Linux 已完成、CLI 有相邻正例，均不能单独把 Windows 行提升为
`evidence_complete`。

## 2. 当前结论

| 分类 | 行数 |
| --- | ---: |
| Evidence complete | 63 |
| Partial | 1 |
| Missing | 4 |
| Total | 68 |

所有行均恰好分类一次，但仍有 5 行需要 closure，因此
`windows_baseline_admitted=false`。现有
[`capability-coverage.json`](data/capability-coverage.json) 继续把 Windows
68 行标记为 `platform_missing` 是正确的保守行为；本计划提供逐行升级路径，
不直接改变平台接纳状态。

63 个已闭合行主要来自：

- 26 样本的 single-target、scan option、output、entropy/info/struct；
- help/version/show-structs；
- multi-target 与 empty/single-directory 基础行为；
- main/extra/custom/show-database 与 17-case ZIP database；
- Unknown fallback、parse/runtime error collection；
- PE/ELF/Mach-O、DEX/Java/PYC、PDF/CFBF、image、binary fallback dispatch；
- directory/internal recursion、resource/overlay gates 与 nested result tree。
- engine file/memory/device/subdevice 入口、I/O/range 边界、signature-name
  filter、record sort 和 cancellation。
- verbose、profiling/messages channel、test/create-test no-op 及完整
  292-rule Windows profiling order。
- main/extra/custom 层顺序、global/type init、priority 边界、四模式
  deep/entry-point/heuristic gate 和 wrong-file-type 排除。
- private signature-path 的空、精确、缺失、大小写、点段和 basename 边界。
- scalar、四类列表、flags、IDs、enums 以及 version/info/rule/priority
  result-model 边界。
- DOS/COM/BW、Amiga Hunk/Atari ST 以及 NPM/通用 Archive 的公共或
  property-only dispatch 边界。
- manifest resource 的 default/recursive/aggressive/combined 四模式上下文
  传播边界。

这些行仍受各自报告中已经写明的全局平台限制约束，但没有把其他能力行的缺口
反向扩散到本行。

## 3. Partial：1 行

| ID | 已观察范围 | 仍缺 |
| --- | --- | --- |
| `CAP-CLI-IN-003` | Unicode/特殊名、Junction alias/chain、ADS、324/325-code-unit path | UNC、reparse cycle、4096-entry ordering、TOCTOU、domain/network ACL |

Partial 行不能计入 Windows runtime baseline。机器报告为每行保存
`observed_scope`、`missing_scope`、`proposed_experiment` 和 evidence paths。

## 4. Missing：4 行

### 4.1 Nested engine boundaries：4 行

- `CAP-NEST-003`
- `CAP-NEST-004`
- `CAP-NEST-007`
- `CAP-NEST-009`

分别需要 direct archive option、archive/resource count sentinel、
debug-data direct control 以及 depth/cumulative
expansion limit。它们不能由 release CLI aggressive/recursive case 替代。

## 5. 执行顺序

按“每次固定构建关闭最多能力行”的原则：

1. Windows nested engine harnesses：处理 4 个 missing；
2. Windows path closure：最后处理 `CAP-CLI-IN-003`，其中 domain/UNC 等需要
   明确环境能力，不把无法在当前主机合法构造的 profile 写成已观察。

每批的接纳条件相同：固定 source/rules/toolchain/binary 或 object identity；
项目生成的 hash-bound 输入；至少双轮确定性；保留 raw 与结构化投影；差异逐项
分类；报告和 generator hash 进入本 closure manifest。

## 6. 与 Phase 0 门禁的关系

Windows closure 达到 68 `evidence_complete` 后，coverage 生成器才可以接纳
`windows-x86_64-qt5`，并把 `CAP-GAP-008` 的 Windows 部分标为 closed。
macOS 仍需独立 fixed oracle 和同样的 68 行审计。Windows closure 本身也不
替代 Phase 0 的设计文档评审、许可证审计或规则运行时/C ABI 技术验证。
