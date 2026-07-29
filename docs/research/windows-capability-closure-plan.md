# Windows Qt5 68 行能力闭合报告

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 目的

本文把 [`capability-traceability.json`](data/capability-traceability.json)
中的 68 个稳定能力 ID 逐行映射到 Windows Qt5 runtime 证据。机器报告为
[`data/windows-capability-closure-plan.json`](data/windows-capability-closure-plan.json)，
由
[`build_windows_closure_plan.py`](../../tools/research/build_windows_closure_plan.py)
确定性生成。

生成器绑定：

- 固定上游、规则和 68 行 traceability；
- [`windows-qt5-build-baseline.json`](data/windows-qt5-build-baseline.json)；
- 23 份 Windows runtime 报告的完整 SHA-256；
- 每份报告的 source/platform 身份和命名 summary facts；
- 2,438 次 Windows 进程执行，其中 legacy/archive dispatch 86 次执行、
  72 次 case observation，debug-data paired harness 2 次执行、6 次 case
  observation，archive-option matrix 128 次执行、128 次 case observation，
  count-boundary 22 次执行、22 次 case observation，archive-limit
  30 次执行、30 次 case observation，以及最终 path closure 46 次执行、
  46 次 case observation。

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
| Evidence complete | 68 |
| Partial | 0 |
| Missing | 0 |
| Total | 68 |

所有行均恰好分类一次，`closure_required=0` 且
`windows_baseline_admitted=true`。总覆盖生成器已 hash-bind 本报告，并把
Windows 68 行接纳为 `runtime_observed`。

68 个已闭合行主要来自：

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
- resource/debug paired harness 的 Formats 枚举、resource 正分派、
  public debug 不分派和 direct debug 规则正例。
- 64-case archive-option engine matrix、32 个 Windows release 控制以及
  nested ZIP option 传播边界。
- archive 99999/100000/100001 和 resource inclusive 21/2001 精确计数边界。
- archive depth 64、累计展开量 33,554,546 bytes 和 root-only cancellation
  prefix。
- 23-case path closure 固定 4096-entry 顺序、dangling/cyclic reparse、
  同步 TOCTOU、WSL UNC/extended-UNC 以及本地/redirector access denial。

这些行仍受各自报告中已经写明的全局平台限制约束，但没有把其他能力行的缺口
反向扩散到本行。

## 3. Partial：0 行

最后一行 `CAP-CLI-IN-003` 已由
[`windows-path-closure-behavior.md`](windows-path-closure-behavior.md)
闭合。机器报告仍为每行保留 `observed_scope` 和 evidence paths，并要求
complete 行的 `missing_scope`、`proposed_experiment` 均为 null。

## 4. Missing：0 行

最后一个 archive nested engine 缺口 `CAP-NEST-009` 已由
[`windows-archive-limit-behavior.md`](windows-archive-limit-behavior.md)
闭合：相同 14-case corpus 和取消 control 各双运行，达到 depth 64 与
33,554,546 bytes，确定性投影与 Linux Qt5 相等。

## 5. 后续维护

新增或变更能力时，接纳条件仍为：固定 source/rules/toolchain/binary 或 object identity；
项目生成的 hash-bound 输入；至少双轮确定性；保留 raw 与结构化投影；差异逐项
分类；报告和 generator hash 进入本 closure manifest。

## 6. 与 Phase 0 门禁的关系

Windows closure 已达到 68 `evidence_complete`，coverage 生成器已接纳
`windows-x86_64-qt5`，并把 `CAP-GAP-008` 的 Windows 部分标为 closed。
macOS 仍需独立 fixed oracle 和同样的 68 行审计。Windows closure 本身也不
替代 Phase 0 的设计文档评审、许可证审计或规则运行时/C ABI 技术验证。
