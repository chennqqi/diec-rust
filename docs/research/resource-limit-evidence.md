# 资源限制证据边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 结论

现有证据足以说明固定上游在若干路径上没有适合作为 Rust 静态库安全边界的全局
限制，也足以固定部分 legacy 兼容临界值；它不足以直接给出项目全部生产默认值。

- archive 递归实验到达 64 层，累计展开实验到达 `33,554,546` bytes；固定源码块
  没有独立 depth 或全 scan 累计展开量计数。
- normal resource 扫描第 21 个 child 可达、第 22 个不可达；aggressive 第
  2001 个可达、第 2002 个不可达。
- aggressive archive 循环的第 100000 条 record 可达，第 100001 条不可达。
- QuickJS-NG spike 中 4 MiB heap、128 KiB stack 与 25 ms deadline 能触发受控
  失败并恢复同一 context，但这些数值是故障注入条件，不是生产默认候选。

项目候选值属于设计决策，见
[`../design/resource-limit-policy.md`](../design/resource-limit-policy.md)；本页只
记录证据能证明什么、不能证明什么。

## 固定证据

| 能力 | 固定报告 | 可使用的结论 |
| --- | --- | --- |
| archive depth/累计展开 | [`data/archive-limit-engine-qt5.json`](data/archive-limit-engine-qt5.json) | 64 层和 33,554,546 bytes 都可达；未观察到上游独立全局 cutoff |
| aggressive archive record | [`data/archive-iteration-boundary-engine-qt5.json`](data/archive-iteration-boundary-engine-qt5.json) | ordinal 100000 可达，100001 不可达 |
| PE resource child count | [`data/scan-option-boundaries-linux-qt5.json`](data/scan-option-boundaries-linux-qt5.json) | normal 21、aggressive 2001 为 inclusive 边界 |
| runtime hard-stop wiring | [`data/rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json) | heap/stack/deadline 能被 runtime 拒绝且 context 可恢复 |

四份报告均固定到同一 DIE-engine commit。生成器
[`build_resource_limit_policy.py`](../../tools/research/build_resource_limit_policy.py)
会严格验证 commit、关键断言、临界 case 和文件 SHA-256；任一证据漂移都会拒绝
重新生成候选策略。

## 不能从现有实验推出的结论

### 最大已测值不是安全默认值

“到达 64 层”只证明固定上游在该输入上继续扫描，不证明 64 是安全、足够或性能
合理的默认值。同理，`33,554,546` bytes 不是建议的累计展开预算。项目候选必须
同时考虑静态库嵌入进程的内存、延迟和可恢复性。

### container 限额不是库内限额

上游实验使用的 10/30/60 秒 timeout、256/512 MiB container memory 和 PID 上限
保护 oracle 进程。它们不会自动约束被 C、Go 或 Python 静态链接调用的 Rust 库，
不能复制为 `ScanLimits`。

### spike 限额不是 runtime profile

4 MiB heap、128 KiB stack 和 25 ms deadline 的目的，是证明 rquickjs/
QuickJS-NG 的 limit 与 interrupt 接线能够触发和恢复。完整固定规则加载量、真实
HostApi、不同格式输入、并发 scanner 和三平台峰值内存尚未用这些数值验证，因此
机器策略将它们放在 `runtime_spike_only`，并强制
`production_default_candidate=false`。

### 上游无界不等于 Rust 应当无界

未观察到上游独立 cutoff 是安全偏差的依据，不是无界 API 的授权。任何 exact
compatibility case 超过 Rust hard ceiling 时，都必须保留两侧 raw evidence，并按
ADR 0004/0010/0012/0014 记录精确 `SafetyDeviation`。

## 可重复检查

```powershell
python tools\research\build_resource_limit_policy.py --check
python -m unittest discover -s tools\tests -p "test_resource_limit_policy.py"
```

生成器只读取版本化文本和 JSON，不运行上游、不物化语料，也不修改任何系统资源
限制。输出为
[`../design/data/resource-limit-policy-candidate.json`](../design/data/resource-limit-policy-candidate.json)。

## 剩余证据

- 为 input、diagnostic、total allocation、metadata/open attempts、include、
  script 和 database budgets 建立数值候选及边界依据；
- 在 production `ScanBudget`/`TraversalBudget`/runtime adapter 出现后执行每项
  `limit-1/exact/+1`；
- 对 modern default 和显式 legacy-high profile 采集 CPU/peak-memory 成对报告；
- 补齐 Windows/macOS path/runtime 边界和 C/Go/Python 静态链接生命周期测试；
- 获得 ADR 0010、0012、0014 及统一策略的明确评审结论。
