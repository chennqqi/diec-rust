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
- 固定全库 2,235 个程序文件的 include 图为 56 个 literal 调用、0 缺失/动态/环；
  最大 active depth 2、每 scope 最大传递 evaluations 30。
- 固定三层 database bundle 为 2,268 entries、2,909,316 entry bytes；无
  extra/comment 的规范 `ZIP_STORED` 模型合计 3,201,508 bytes。8×/64× sizing
  已形成未准入的 database load 候选。
- Linux/Windows 都完整枚举 4,096-entry flat/nested fixture，并观察到先列举后
  reopen 的 TOCTOU；报告未测 filesystem attempt 次数。ADR 0014 因此按结构模型
  提出 524,288/8,388,608 的未准入 metadata/open attempt 候选。
- 固定 database-error 与真实 typo 报告证明 diagnostic 会追加到 stdout、破坏
  JSON，且 Qt5/Qt6 文本不同；已测 scan 每次只有一行，不能作为最大值。
  Diagnostics 候选按 work ceiling 提出 4,096/131,072。
- 固定 37-case engine contract 证明上游小输入 copy 会忽略 short/error read，
  subdevice 还可能越界多读一字节；archive sizing 的最大 root fixture 只有
  16,777,452 bytes，不能作为输入上限。Root input 候选按设计关系提出
  1 GiB/8 GiB，并明确不是上游观察最大值或 allocation 目标。
- 三次固定 affinity session 的四个产品 case 共 180 个 measured run 都有
  peak RSS，最大为 80,953,344 bytes；archive limit 的 14 个 normal case 最大
  process RSS 为 56,472 KiB、before/after 差值最大 37,572 KiB。这些是整个上游
  进程的 RSS，不是 scan-owned cumulative allocation。Total-allocation 候选按
  2× total-expanded 结构关系提出 1 GiB/8 GiB，不以观察 RSS 定值。
- QuickJS-NG spike 中 4 MiB heap、128 KiB stack 与 25 ms deadline 能触发受控
  失败并恢复同一 context，但这些数值是故障注入条件，不是生产默认候选。
- 固定 2,902,881-byte 程序源、20,947-operation Binary corpus anchor、pinned
  256 KiB VM stack 默认值和 scan deadline 已形成联合 script runtime 候选；
  三轮 Windows MSVC full Binary corpus 每轮正常 VM poll 均为 28 次，4,130 个
  lifecycle memory checkpoint 最大 observed `malloc_size` 为 654,562 bytes；
  Binary signature HostApi 每轮 native checkpoint 固定 16,439 次，并已有
  4095/4096 候选边界及单次 native search 中断测试。候选 custom allocator
  又在相同语料的三轮运行中固定最大瞬时 live heap 为 4,478,992 bytes，
  32 MiB hard limit 下 0 次拒绝，42/42 runtime drop 后归零。它不是默认
  allocator 或 production backend 的测量；计费包含对齐 payload 与 internal
  header。全部 2,235 个固定程序文件的隔离顶层 parse/eval 又连续三轮固定
  3,486,384-byte 瞬时 high-water、0 次拒绝和 drop 后归零；该实验不调用
  `detect`，不能替代各 file type 的完整生命周期。逐规则独立 runtime 复验
  进一步固定 p50/p95/p99 为 118,752/127,776/153,648 bytes，最大
  3,489,576 bytes 来自 `Binary/audio.1.sg`；2,235 个 runtime 均零拒绝、drop
  归零且各触发一次正常 poll。其余 HostApi checkpoint、完整跨格式 scaling、
  sanitizer 及三平台资源证据仍缺失，因此候选不得 admitted。
- PE/ELF/Mach-O/DEX/APK/Archive/PDF 七类代表性规则的 25-case runtime 矩阵
  已连续三轮固定为每轮 25 次正常 VM poll、75 个 lifecycle memory
  checkpoint，最大 observed `malloc_size` 为 124,485 bytes；同一矩阵的 custom
  allocator 三轮最大瞬时 high-water 为 134,792 bytes，0 次拒绝且 75/75
  runtime drop 后归零。每类仅覆盖一条短规则，不能据此宣称全部固定规则或所有
  支持格式的 scaling 已完成。

项目候选值属于设计决策，见
[`../design/resource-limit-policy.md`](../design/resource-limit-policy.md)；本页只
记录证据能证明什么、不能证明什么。

## 固定证据

| 能力 | 固定报告 | 可使用的结论 |
| --- | --- | --- |
| archive depth/累计展开 | [`data/archive-limit-engine-qt5.json`](data/archive-limit-engine-qt5.json) | 64 层和 33,554,546 bytes 都可达；未观察到上游独立全局 cutoff |
| aggressive archive record | [`data/archive-iteration-boundary-engine-qt5.json`](data/archive-iteration-boundary-engine-qt5.json) | ordinal 100000 可达，100001 不可达 |
| PE resource child count | [`data/scan-option-boundaries-linux-qt5.json`](data/scan-option-boundaries-linux-qt5.json) | normal 21、aggressive 2001 为 inclusive 边界 |
| include graph sizing | [`data/include-graph-sizing.json`](data/include-graph-sizing.json) | 30 scope 的最大 depth 2/evaluations 30，Binary 静态 30 与动态 trace 相同 |
| database load sizing | [`data/database-load-sizing.json`](data/database-load-sizing.json) | 完整固定 bundle 的 source/entry/path/container 观察量和非零候选；不证明 production 适用性 |
| traversal metadata/open | [`../design/data/traversal-attempt-budget-candidate.json`](../design/data/traversal-attempt-budget-candidate.json) | 绑定 Linux/Windows 4,096-entry、cycle 与 TOCTOU 报告；明确 attempt 数不是上游实测 |
| scan diagnostics | [`../design/data/diagnostic-budget-candidate.json`](../design/data/diagnostic-budget-candidate.json) | typed fact 计数、overflow completion、profile 字段闭包及 Qt5/Qt6 文本差异 |
| root input bytes | [`../design/data/input-budget-candidate.json`](../design/data/input-budget-candidate.json) | root logical length、入口触发时机、1 GiB/8 GiB 候选及与累计 I/O/分配的独立关系 |
| total allocation bytes | [`../design/data/allocation-budget-candidate.json`](../design/data/allocation-budget-candidate.json) | scan-owned capacity 单调累计、two-phase reserve、1 GiB/8 GiB 候选与 whole-process RSS 证据边界 |
| script runtime | [`../design/data/script-runtime-budget-candidate.json`](../design/data/script-runtime-budget-candidate.json) | heap/JS stack/fuel/deadline 的联合候选、共享/不重置语义及真实 runtime 测量缺口 |
| runtime hard-stop wiring | [`data/rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json) | 默认/custom heap、stack、deadline 能受控拒绝并恢复；custom allocator 另记录完整 Binary detect、全规则共享 runtime 顶层 eval 及逐规则独立 runtime 的瞬时 high-water 与 drop 归零 |

这些报告均固定到同一 DIE-engine commit。生成器
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
QuickJS-NG 的 limit 与 interrupt 接线能够触发和恢复。32 MiB custom-allocator
完整 Binary 语料、全部 2,235 个规则顶层 eval 及逐规则独立 runtime 分布实验
是候选 backend 的真实 high-water 证据，但完整固定规则的有效输入 detect、
不同格式全生命周期、并发 scanner、sanitizer 和三平台峰值内存尚未验证，因此
机器策略继续保持
`review_candidate_not_admitted`；4 MiB fault 条件仍为
`runtime_spike_only.production_default_candidate=false`。

### 上游无界不等于 Rust 应当无界

未观察到上游独立 cutoff 是安全偏差的依据，不是无界 API 的授权。任何 exact
compatibility case 超过 Rust hard ceiling 时，都必须保留两侧 raw evidence，并按
ADR 0004/0010/0012/0014 记录精确 `SafetyDeviation`。

## 可重复检查

```powershell
python tools\research\build_traversal_attempt_budget.py --check
python tools\research\build_diagnostic_budget.py --check
python tools\research\build_input_budget.py --check
python tools\research\build_allocation_budget.py --check
python tools\research\build_script_runtime_budget.py --check
python tools\research\build_resource_limit_policy.py --check
python -m unittest discover -s tools\tests -p "test_resource_limit_policy.py"
```

生成器只读取版本化文本和 JSON，不运行上游、不物化语料，也不修改任何系统资源
限制。输出为
[`../design/data/resource-limit-policy-candidate.json`](../design/data/resource-limit-policy-candidate.json)。

## 剩余证据

- 对 script 候选把当前 Windows Binary 与七类代表性规则的 custom-allocator
  high-water 扩展到 production backend、全部格式正反例和三平台；补齐
  sanitizer、native HostApi cooperative checkpoint、VM poll scaling 与
  `limit-1/exact/+1`；
- 对 root input 候选补齐 production `Bytes`/`ByteSource`/`Path`/FFI
  `limit-1/exact/+1`、并发 truncate/grow 和 CPU/peak-memory；
- 对 total allocation 候选补齐 production budgeted containers/decompressor
  sinks、mock allocator、`limit-1/exact/+1`、allocation trace 与 peak-RSS；
- 对 diagnostic 候选补齐真实多错误放大 corpus、typed fact
  `limit-1/exact/+1` 和 production memory/latency；
- 对 traversal metadata/open 候选补齐 mock adapter `limit-1/exact/+1`、
  三平台 handle-relative system test 和 production CPU/latency；
- 对 database load 候选补齐完整 cache overhead、ZIP64/compression ratio、
  `limit-1/exact/+1` 和 production CPU/peak-memory；
- 对 include 16/256 与 64/4096 候选补齐 dynamic/custom database、
  `limit-1/exact/+1` 和 production CPU/peak-memory；
- 在 production `ScanBudget`/`TraversalBudget`/runtime adapter 出现后执行每项
  `limit-1/exact/+1`；
- 对 modern default 和显式 legacy-high profile 采集 CPU/peak-memory 成对报告；
- 补齐 Windows/macOS path/runtime 边界和 C/Go/Python 静态链接生命周期测试；
- 获得 ADR 0010、0012、0014 及统一策略的明确评审结论。
