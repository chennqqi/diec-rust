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
| Linux x86_64 Qt5 | 47 | 21 | 0 | 0 | 0 |
| Linux x86_64 Qt6 | 0 | 0 | 0 | 0 | 68 |
| Windows x86_64 Qt5 | 0 | 0 | 0 | 0 | 68 |
| macOS x86_64 Qt5 | 0 | 0 | 0 | 0 | 68 |

所有 68 个能力行和 272 个平台 cell 都已分类，未分类计数为 0。这只证明审计
清单没有“消失的行”，**不表示覆盖完成**：

- Linux Qt5 source-only 能力已清零；
- 30 行至少关联一个已命名 corpus gap；
- 三个尚未接纳的平台各有 68 个 `platform_missing`；
- `phase_0_coverage_complete` 必须保持 `false`。

## 5. 缺口映射

原 traceability 中十二个 `CAP-GAP-*` 现在显式映射到受影响能力：

| Gap | 类型 | 能力行数 | 范围 |
| --- | --- | ---: | --- |
| `CAP-GAP-001` | corpus | 5 | CLI/script profiling 与 entropy/info/struct 边界 |
| `CAP-GAP-002` | corpus | 4 | database header/write/permission/concurrency |
| `CAP-GAP-003` | corpus | 4 | Unicode、特殊路径和枚举 |
| `CAP-GAP-004` | corpus | 6 | structured-output escaping 与 nested ordering |
| `CAP-GAP-005` | corpus | 5 | deep/aggressive resource filtering 与计数 |
| `CAP-GAP-006` | corpus | 4 | archive 格式、深度和总解压限制 |
| `CAP-GAP-007` | platform | 68 | 完整 Qt5/Qt6 capability matrix |
| `CAP-GAP-008` | platform | 8 | Windows/macOS path 与 encoding |
| `CAP-GAP-009` | corpus | 1 | device/subdevice short-read、range、seek 与 I/O |
| `CAP-GAP-010` | corpus | 1 | equal-priority、cross-layer 与 comparator ordering |
| `CAP-GAP-011` | corpus | 1 | mid-callback、async stop 与 cancellation race |
| `CAP-GAP-012` | corpus | 1 | generic Image 与非 JPEG/PNG image variants |

映射是保守的审计范围，不是“这些能力除此之外都已完备”的声明。

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
相等；全部平台 cell 有已知状态；Linux 四类计数保持 47/21/0/0；其他三个平台
各保持 68 个 `platform_missing`；十二个 gap 均映射到已知能力；所有
`with_corpus_gaps` 状态都至少关联一个具名 corpus gap。

## 7. 对 Phase 0 门禁的影响

该报告关闭了 `P0-BLOCK-005` 中“没有完整 coverage report”的审计缺口，但没有
关闭 blocker 本身。要关闭 `P0-BLOCK-005`，仍须：

1. 保持
   [`source-only-closure-plan.md`](source-only-closure-plan.md)
   的 Linux source-only 闭集为空，新增或降级能力必须重新进入 closure catalog；
2. 逐项收敛十二类 corpus gap，而不是只增加 happy-path 样本；
3. 固定 Windows、macOS 和完整 Linux Qt6 oracle；
4. 重新生成报告，且经评审确认 Phase 0 所需行不再为 source-only、
   corpus-missing 或 platform-missing。
