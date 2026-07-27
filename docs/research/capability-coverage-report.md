# Phase 0 能力覆盖报告

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 目的

本报告把 [`capability-traceability.json`](data/capability-traceability.json)
中的 68 个稳定 `CAP-*` 投影为能力 × 平台闭集，回答三个不同问题：

1. 每个能力是否都有分类，避免遗漏未测试能力；
2. Linux Qt5 证据是 runtime observation 还是 source-only；
3. 哪些缺口属于语料边界，哪些属于平台基线缺失。

机器报告为
[`data/capability-coverage.json`](data/capability-coverage.json)，由
[`build_capability_coverage.py`](../../tools/research/build_capability_coverage.py)
确定性生成。报告绑定 traceability 原始文件 SHA-256、上游 commit 和规则 commit。

## 2. 目标平台闭集

Phase 0 报告固定四个平台：

- `linux-x86_64-qt5`
- `linux-x86_64-qt6`
- `windows-x86_64-qt5`
- `macos-x86_64-qt5`

当前只有 Linux x86_64 Qt5 被 traceability manifest 接纳为完整 runtime baseline
平台。已有 Linux Qt6 spot differential 不等于 68 项能力基线，因此在本报告中
仍统一分类为 `platform_missing`。Windows 与 macOS 同理。

## 3. 分类语义

| 分类 | 含义 |
| --- | --- |
| `runtime_observed` | 固定 oracle 对 hash-bound 输入观察到命名行为 |
| `runtime_observed_with_corpus_gaps` | 有 runtime observation，但明确边界语料仍缺失 |
| `source_only_runtime_corpus_missing` | 只有固定源码证据，缺少 runtime corpus |
| `source_only_with_corpus_gaps` | 只有源码证据，且另有明确边界缺口 |
| `platform_missing` | 该平台未接纳完整能力基线 |

`source_only` 不能提升为 runtime compatibility；一项能力有某个正例，也不能消除
其 negative、boundary、resource 或 encoding 缺口。

## 4. 当前结果

报告包含 68 行、4 个平台、272 个 cell：

| 平台 | Runtime observed | Observed + corpus gaps | Source-only | Source-only + gaps | Platform missing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Linux x86_64 Qt5 | 64 | 4 | 0 | 0 | 0 |
| Linux x86_64 Qt6 | 0 | 0 | 0 | 0 | 68 |
| Windows x86_64 Qt5 | 0 | 0 | 0 | 0 | 68 |
| macOS x86_64 Qt5 | 0 | 0 | 0 | 0 | 68 |

所有 68 个能力行和 272 个平台 cell 都已分类，未分类计数为 0。这只证明审计
清单没有“消失的行”，**不表示覆盖完成**：

- Linux Qt5 source-only 能力已清零；
- 8 行至少关联一个已命名 corpus gap；
- 三个尚未接纳的平台各有 68 个 `platform_missing`；
- `phase_0_coverage_complete` 必须保持 `false`。

## 5. 缺口映射

traceability 中四个开放 `CAP-GAP-*` 现在显式映射到受影响能力；

| Gap | 类型 | 能力行数 | 范围 |
| --- | --- | ---: | --- |
| `CAP-GAP-003` | corpus | 4 | Unicode、特殊路径和枚举 |
| `CAP-GAP-006` | corpus | 4 | archive 格式、深度和总解压限制 |
| `CAP-GAP-007` | platform | 68 | 完整 Qt5/Qt6 capability matrix |
| `CAP-GAP-008` | platform | 8 | Windows/macOS path 与 encoding |
映射是保守的审计范围，不是“这些能力除此之外都已完备”的声明。

`CAP-GAP-006` 已新增 RAR4/CAB/ISO9660 store-only 单 PDF 的固定 engine
正例：默认模式与发布 CLI 相同，显式 archive 后各产生一个 PDF Stream child。
该增量见 [`archive-format-behavior.md`](archive-format-behavior.md)，但 7Z、
NPM/通用 Archive、100000 边界、压缩/加密/畸形和跨平台仍缺，因此 gap 行数与
状态均不变。

原 `CAP-GAP-005` 已由
[`scan-option-boundaries.md`](scan-option-boundaries.md)
闭合：项目生成的最小规则与 1/22/2002-resource PE 在 16 次双 Qt5 执行中固定
deep 的 `DS`/`EP` 增量、aggressive/recursive gate、默认 21 与 aggressive
2001 的精确 child count、枚举顺序，以及 PE parser 每目录 1000 项的前置限制。

原 `CAP-GAP-004` 已由
[`cli-output-boundaries.md`](cli-output-boundaries.md)
闭合：10-case 双 Qt5 oracle 固定 Unicode、控制字符、分隔符和 XML 特殊字符，
并验证 JSON 树与顺序、flat XML escaping、nested XML 非良构、CSV/TSV 无引用
导致的歧义、嵌套 leaf flattening，以及 plain text 层级和断行行为。

原 `CAP-GAP-002` 已由
[`database-archive-cache.md`](database-archive-cache.md)
闭合：固定非特权 Qt5 engine harness 覆盖 bad version、0/4/8-byte header、
record 中部/尾部截断、cache 写失败与恢复、不可读 database file/directory，
以及 8 个同输入同步并发 writer；十九个 case 两次运行的原始输出逐字节相同。

原 `CAP-GAP-001` 已由
[`cli-special-modes.md`](cli-special-modes.md)
闭合：28-case 双 oracle 固定临界 entropy、通用及 PE/ELF/Mach-O/DEX struct
方法、层级 filter 和多目标 framing；既有 profiling oracle 固定 292 条真实规则
顺序，并证明 messages gate。

原 `CAP-GAP-011` 已由
[`engine-contract-behavior.md`](engine-contract-behavior.md)
闭合：首条/中间/末条 callback false、同步跨线程 stop、预停止、规则内
`_breakScan()` 及 fresh-state engine 恢复均有固定证据；未同步跨线程读写因上游
plain `bool` 数据竞争而明确排除在可移植 compatibility golden 之外。

原 `CAP-GAP-012` 已由
[`image-dispatch-behavior.md`](image-dispatch-behavior.md)
闭合：七种非 JPEG/PNG variant 的自然 Binary fallback、强制 generic Image
分支及其 null-adapter error 均有固定机器证据。

原 `CAP-GAP-010` 已由
[`rule-orchestration.md`](rule-orchestration.md)
闭合：同 priority、字符串 priority、缺失/空 priority 段、跨层 append 与
`_init` 比较环均有固定双 Qt5 oracle 证据。

原 `CAP-GAP-009` 已由
[`engine-contract-behavior.md`](engine-contract-behavior.md)
闭合：direct/subdevice 的 chunked、EOF、read/seek error、sequential、position
和合法/非法 range 均有固定 37-case Qt5 engine 证据；不安全的 silent success
由 ADR 0013 管理，不被 normalizer 隐藏。

## 6. 可重复验证

生成：

```text
python tools/research/build_capability_coverage.py
```

验证：

```text
python tools/tests/test_capability_coverage.py
```

测试要求 committed report 与生成结果逐字节一致；68 个 ID 与 traceability 完全
相等；全部平台 cell 有已知状态；Linux 四类计数保持 64/4/0/0；其他三个平台
各保持 68 个 `platform_missing`；四个开放 gap 均映射到已知能力；所有
`with_corpus_gaps` 状态都至少关联一个具名 corpus gap。

## 7. 对 Phase 0 门禁的影响

该报告关闭了 `P0-BLOCK-005` 中“没有完整 coverage report”的审计缺口，但没有
关闭 blocker 本身。要关闭 `P0-BLOCK-005`，仍须：

1. 保持
   [`source-only-closure-plan.md`](source-only-closure-plan.md)
   的 Linux source-only 闭集为空，新增或降级能力必须重新进入 closure catalog；
2. 逐项收敛剩余四个 corpus/platform gap，而不是只增加 happy-path 样本；
3. 固定 Windows、macOS 和完整 Linux Qt6 oracle；
4. 重新生成报告，且经评审确认 Phase 0 所需行不再为 source-only、
   corpus-missing 或 platform-missing。
