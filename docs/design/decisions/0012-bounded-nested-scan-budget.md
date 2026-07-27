# ADR 0012：嵌套扫描采用全局有限资源预算

Status: Proposed
Last updated: 2026-07-28

## 背景

固定上游 archive scanner 有每层 entry 数量边界，却没有独立嵌套 depth 或全 scan
累计展开字节计数。固定 Linux Qt5 oracle 已观察到单成员 ZIP 到达 16 层、固定两层
累计展开 2,097,266 bytes，并证明取消返回部分 record。详见
[`archive-limit-behavior.md`](../../research/archive-limit-behavior.md)。

复制上游的直接递归和完整成员分配，会把终止条件交给 native stack、allocator、
decompressor 或宿主进程。二进制输入不可信，因此“没有上游上限”不能成为 Rust
实现允许无界资源使用的理由。

## 决策

Proposed：

1. 所有 root/child 共用一个 checked `ScanBudget`，child 不重置额度；嵌套调度采用
   ADR 0002 的显式 work queue，不递归调用公共入口。
2. 在读取、分配、解压或入队之前原子 reserve；失败不执行部分 allocation，并返回
   `LimitReached { kind, limit, requested, consumed, node, stage }`。
3. 初始 modern default profile 固定为：

   | 预算 | 默认值 |
   | --- | ---: |
   | wall deadline | 30 s |
   | maximum nested depth | 32 |
   | total archive entries considered | 4,096 |
   | maximum queued items | 4,096 |
   | maximum result nodes | 100,000 |
   | maximum single expanded object/allocation | 128 MiB |
   | total expanded bytes | 512 MiB |
   | total source bytes read/mapped | 1 GiB |

4. 上述值是 Proposed API/profile 契约，不是已证明的性能目标；ADR 未 Accepted 前仍可
   经评审修改，但实现不得以 `0`、`u64::MAX` 或“未配置”表示无界。
5. legacy normal 保留上游“每 container 最多 21 个 scanable members”的语义，
   同时受 modern 全局 hard budget 限制。legacy aggressive 是显式高资源 opt-in：
   每 container 最多 100,001 个 scanable members，但全 scan 仍须有有限、调用方
   可见的 global budget；默认不得静默升级到 aggressive ceiling。
6. 为差分测试可提供 `LegacyHighResource` profile，但 hard ceilings 仍有限：depth
   64、total entries 100,001、single object 512 MiB、total expanded 4 GiB、
   total source read 8 GiB、deadline 120 s。它需要显式构造，不是 CLI、C ABI 或
   library 默认。
7. 在 exact upstream 行为超出 hard ceiling 时，结果分类为 `SafetyDeviation`，
   绑定 upstream/case/limit/ADR 0012 的精确 waiver；normalizer 不得隐藏差异。
8. 到达确定性预算边界使用 `Completion::Limited` 并保留已完成的稳定前缀；外部
   cancel/deadline 仍按 ADR 0009 返回 typed termination，不把不稳定 detection
   前缀作为成功 report。
9. checked cumulative counter、allocator reservation、decompressor output sink 和
   result arena 使用同一预算事实来源；CLI/JSON/FFI 不得各自实现或覆盖计数。

## 考虑过的替代方案

### 完全复制上游无独立上限

对小样本最接近 upstream，但深链或高展开量会造成 stack overflow、OOM、hang 或
宿主不可控退出，不满足项目安全边界。

### 只复制每层 20/100000 entry limit

无法限制“每层一个成员”的深链，也无法限制多层累计展开量。当前语料正是该方案的
反例。

### 只依赖进程/container 隔离

适合 oracle 研究，但静态 `.a` 会嵌入 C/Go/Python 进程，不能假设存在容器或
subprocess。进程隔离可作为服务部署的第二层防线，不能替代 library budget。

### 所有限额都由调用方提供

缺少参数的调用方会恢复无界行为，也让 C ABI/CLI 默认不安全。允许调用方降低限额，
但必须有项目默认值和不可关闭的 hard ceiling。

## 后果

- 恶意或偶然的深链、高 entry count 和高展开量在分配前确定性终止。
- Rust legacy 模式在资源极端输入上不可能与 upstream raw exact；差异必须公开为
  safety deviation。
- `ScanLimits`、usage accounting、extractor sink、queue 和 result model 必须共享
  checked counters，增加实现与边界测试成本。
- 默认数值是可评审的兼容/安全/性能权衡；修改任一公开 profile 值需要新 ADR 或
  本 ADR 的 Superseding decision，不得在 patch release 静默变化。

## 证据

- [`archive-limit-behavior.md`](../../research/archive-limit-behavior.md)
- [`archive-limit-engine-qt5.json`](../../research/data/archive-limit-engine-qt5.json)
- [`archive-limit-corpus.json`](../../research/data/archive-limit-corpus.json)
- [`upstream-performance-baseline.md`](../../research/upstream-performance-baseline.md)
- `XScanEngine@dfe4a419.../xscanengine.cpp::scanProcess`
- [`architecture.md` §11](../architecture.md#11-嵌套扫描-work-queue)
- [`api.md` §8—10](../api.md#8-scanlimits)
- [`risks.md` R-005](../risks.md#r-005嵌套和解压资源耗尽)

## 验收条件

- production `ScanBudget` 对每个表列预算有 `limit-1/exact/+1` unit/property tests；
- 每个 archive backend 通过相同的 cumulative reserve API，不能先分配后记账；
- depth、entry、single object、total expanded、queue、node 和 deadline 触发点有
  system tests，结果包含稳定 `LimitReached` 字段；
- generated high-ratio、declared-size mismatch、deep chain 和 malformed archive
  在 sanitizer/fuzz 下无 panic、stack overflow、OOM 或 hang；
- modern default 与 `LegacyHighResource` 的 CPU/peak-memory benchmark 在目标平台
  完成，评审确认或调整具体数值；
- legacy normal 的 21 boundary 和 aggressive 的 100,001 boundary 在预算允许时
  与固定 upstream 差分一致；
- 超出 hard ceiling 的差异有 ADR 0004 machine-readable SafetyDeviation waiver；
- Rust、CLI、JSON、C、Go 和 Python 看到相同 completion/usage/limit contract。
