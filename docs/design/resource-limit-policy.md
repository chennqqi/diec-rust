# 资源限制候选策略

Status: In Review

Last updated: 2026-07-30

## 1. 状态

本文把 API 与 ADR 中分散的资源限制整理为一个可评审候选。它不是已冻结的发布
默认值，也不允许 Phase 0 提前实现 production `ScanBudget`。机器可读契约为
[`data/resource-limit-policy-candidate.json`](data/resource-limit-policy-candidate.json)，
当前结果必须保持 `review_candidate_incomplete`、`admitted=false`。

候选依赖：

- [资源限制证据边界](../research/resource-limit-evidence.md)；
- [ADR 0010](decisions/0010-bounded-include-graph.md)；
- [ADR 0012](decisions/0012-bounded-nested-scan-budget.md)；
- [ADR 0014](decisions/0014-bounded-path-expansion.md)；
- [数据库加载规模](../research/database-load-sizing.md)；
- [Traversal attempt 候选](data/traversal-attempt-budget-candidate.json)；
- [`api.md` 的 `ScanLimits`](api.md#8-scanlimits)。

## 2. 共同不变量

所有 profile 都必须满足：

- 数值 limit 非零；`0`、整数最大值或 missing 不表示无限；
- 调用方可以降低限额，不能关闭 hard limit；
- root、child、include、extractor 与 path expansion 共享父 scan 累计事实，
  child 不重置预算；
- read、allocation、decompression 和 enqueue 前先原子 reserve；
- legacy-high 只能显式 opt in，任何 adapter 都不得默认选择；
- 因安全 hard stop 与固定上游产生的差异必须使用证据绑定的
  `SafetyDeviation`，normalizer 不得隐藏。

## 3. Modern default 候选

### Scan

| Counter | 候选值 |
| --- | ---: |
| wall deadline | 30,000 ms |
| maximum nested depth | 32 |
| total archive entries considered | 4,096 |
| maximum queued items | 4,096 |
| maximum result nodes | 100,000 |
| maximum single expanded object/allocation | 134,217,728 bytes |
| total expanded bytes | 536,870,912 bytes |
| total source bytes read/mapped | 1,073,741,824 bytes |

### Traversal

| Counter | 候选值 |
| --- | ---: |
| wall deadline | 30,000 ms |
| maximum directory depth | 64 |
| maximum entries considered | 100,000 |
| maximum files emitted | 100,000 |
| maximum native path bytes | 67,108,864 bytes |
| maximum metadata/open attempts | 524,288 |

### Include

| Counter | 候选值 |
| --- | ---: |
| maximum active include depth | 16 |
| maximum total include evaluations | 256 |

固定全库观察最大值为 depth 2/evaluations 30；候选使用 8× headroom，并将
`30 × 8 = 240` 向上取 2 次幂。证据见
[`include-graph-sizing.md`](../research/include-graph-sizing.md)。

### Database load

| Counter | 候选值 |
| --- | ---: |
| maximum sources | 32 |
| maximum entries/cache records | 32,768 |
| maximum single entry | 8,388,608 bytes |
| maximum total entry bytes | 33,554,432 bytes |
| maximum single/total container | 33,554,432 bytes |
| maximum single logical path | 512 bytes |
| maximum total logical path bytes | 524,288 bytes |
| maximum cache bytes | 67,108,864 bytes |

固定 bundle 有 3 个 source、2,268 个文件、2,909,316 bytes；规范
`ZIP_STORED` 三层合计 3,201,508 bytes。候选使用观察值 8× 后向上取二次幂，
cache bytes 再保留一倍 record metadata 空间。该推导和 archive/cache 行为绑定
见 [`database-load-sizing.md`](../research/database-load-sizing.md)。

Scan/traversal 值来自 ADR 0012/0014 的 Proposed 表；database 值来自固定
bundle sizing。两类都只是评审候选。

## 4. Legacy-high 候选

该 profile 只用于受控差分或调用方明确选择的高资源扫描，不是 CLI、C ABI 或 Rust
library 默认。

### Scan

| Counter | 候选值 |
| --- | ---: |
| wall deadline | 120,000 ms |
| maximum nested depth | 64 |
| total archive entries considered | 100,001 |
| maximum single expanded object | 536,870,912 bytes |
| total expanded bytes | 4,294,967,296 bytes |
| total source bytes read/mapped | 8,589,934,592 bytes |

### Traversal

| Counter | 候选值 |
| --- | ---: |
| wall deadline | 120,000 ms |
| maximum directory depth | 256 |
| maximum entries considered | 1,000,000 |
| maximum files emitted | 1,000,000 |
| maximum native path bytes | 1,073,741,824 bytes |
| maximum metadata/open attempts | 8,388,608 |

### Include

| Counter | 候选值 |
| --- | ---: |
| maximum active include depth | 64 |
| maximum total include evaluations | 4,096 |

### Database load

| Counter | 候选值 |
| --- | ---: |
| maximum sources | 256 |
| maximum entries/cache records | 262,144 |
| maximum single entry | 67,108,864 bytes |
| maximum total entry bytes | 268,435,456 bytes |
| maximum single/total container | 268,435,456 bytes |
| maximum single logical path | 4,096 bytes |
| maximum total logical path bytes | 4,194,304 bytes |
| maximum cache bytes | 536,870,912 bytes |

profile 的 global archive-entry budget 不改变固定 upstream 的局部兼容语义：
normal resource child inclusive 边界为 21，aggressive resource child 为 2001；
aggressive archive 只让 ordinal 100000 可达，ordinal 100001 不可达。

## 5. 尚未定值的必需预算

当前策略有 7 个明确 unresolved 项，因此不得 admitted：

1. root `maximum_input_bytes`；
2. `maximum_diagnostics`；
3. `maximum_total_allocated_bytes`；
4. script maximum heap bytes；
5. script maximum stack bytes；
6. script maximum instruction/fuel；
7. script runtime deadline。

QuickJS spike 的 4 MiB heap、128 KiB stack 和 25 ms deadline 只在机器契约的
`runtime_spike_only` 中保存；它们不能填充第 4—7 项。include 两项已有
16/256 与 64/4096 候选，但仍需 ADR 0010 评审、dynamic/custom database 和
production 边界测试。database load 的 10 个字段已有非零候选，但仍保持
`review_candidate_not_admitted`，并需要完整 cache overhead、ZIP64/compression
ratio 和跨平台 benchmark。

## 6. 统一计数语义

每个 reserve 失败必须产生：

```text
LimitReached {
  kind,
  limit,
  requested,
  consumed,
  node,
  stage
}
```

`requested` 是本次操作在执行前申请的增量，`consumed` 是申请前已提交用量。
counter 使用 checked integer；失败不改变 `consumed`，不执行部分 allocation，
不产生未完成 child。确定性边界可以返回带稳定前缀的
`Completion::Limited`；cancel/deadline 仍按 ADR 0009 返回 typed termination。

scan 与 traversal 当前都提出 30/120 秒 deadline，但它们不是两个互不相关的
计时器。最终实现必须从同一绝对 deadline 派生 remaining duration，不能让进入
path expansion 或 child scan 时重新获得完整时长。

## 7. 生成与漂移门禁

```powershell
python tools\research\build_traversal_attempt_budget.py --check
python tools\research\build_resource_limit_policy.py --check
```

生成器验证：

- 固定上游 commit；
- ADR 0010/0012/0014 与 API 的精确契约片段；
- archive depth/expanded、archive iteration、resource count 和 runtime spike
  报告的关键断言；
- 全部 source SHA-256；
- strict JSON、无 duplicate key、无非有限数。

生成器不是评审机器人。即使 `--check` 通过，ADRs 仍为 Proposed、本文仍为
In Review，候选仍不得 admitted。

## 8. 接受条件

- ADR 0010、0012、0014 获得明确 review disposition；
- 7 个 unresolved 项都有非零候选与证据；
- 每个 production counter 有 `limit-1/exact/+1`；
- 所有 archive backend 使用同一 reserve API；
- modern/legacy-high 的 CPU 和 peak-memory benchmark 通过；
- Rust、CLI、JSON、C、Go、Python 观察同一 limit/usage/completion；
- Windows/macOS path 与 runtime limit 证据完成。
