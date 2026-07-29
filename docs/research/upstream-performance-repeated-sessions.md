# 固定 Linux Qt5 上游单 vCPU 重复 session

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt5 affinity benchmark 已完成三次独立 probe invocation：

- 固定同一 OCI image、五个 plans、语料、上游 ELF 和 `cpuset=0`；
- 每个 session 有 17 次 warmup、90 次 measured，合计 51 warmup、270 measured；
- 三个 session 全部通过原 probe semantic verifier，stderr 为空，五个 case 的
  stdout/stderr hash 跨 session 一致；
- 四个产品 case 的 225 个 measured run 全部取得 peak RSS；短 control 分别只有
  9/30、12/30、12/30，原始缺失值没有插补；
- database median 的跨 session max/min 只有 1.0008，但 PE32 与 depth-16 archive
  median 分别达到 1.3940 和 1.7704；batch median 为 1.0406，p95 却达到
  1.6848。

因此单次 affinity session 不足以冻结 regression threshold。当前结果继续保持
`descriptive_upstream_only` 与 `targets_frozen=false`；它证明了连续 session
之间存在显著 scheduler/host-state 漂移，但不能把漂移归因于某个具体机制，也不能
用于声称 Rust 更快或更慢。

机器汇总为
[`data/upstream-benchmark-linux-qt5-affinity-repeated.json`](data/upstream-benchmark-linux-qt5-affinity-repeated.json)，
SHA-256 为
`c7e8acbc0d78f2576c94f0d1a578a3436224205e3bdb2a29809dd75d790f6584`。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| rules | `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| image ID | `sha256:9f1d70a8d4513404cdc457074e00dec4a9b8a6f043a572ffc17465bbe699eb09` |
| plan suite SHA-256 | `f93672c9603db16050047095f15d5f5ea6d9d58663b4574ed901f819f0106e1a` |
| cgroup | `cpu.max=100000 100000`；`cpuset.cpus.effective=0`；512 MiB；128 PIDs |
| session 1 | `67e6d594a5b93e1b791c11ef89bdb12e85399964cea9bee87baf591047f5d7de` |
| session 2 | `3329d85989efec599b8621013f644aa3933ecacf86bdd3fb737c831010f5f011` |
| session 3 | `c6c171899b7366e3858f2ac039ed9346b48b9ba154ef4beee3607dcb4b376128` |

三个 source report 均原样保留。汇总器重新调用
[`probe_upstream_benchmark.py`](../../tools/benchmark/probe_upstream_benchmark.py)
的 semantic verifier，并拒绝 image、revision、plan、完整 environment、cpuset、
case set、输出 hash、RSS 口径或 target 状态漂移。

## 跨 session 结果

下表把报告中的整数纳秒转换为毫秒；比值仍来自未舍入整数：

| Case | Session 1 median | Session 2 median | Session 3 median | Median max/min | p95 max/min |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qt/process control | 3.974 ms | 3.962 ms | 3.759 ms | 1.0571 | 1.3141 |
| database load | 68.003 ms | 67.949 ms | 67.994 ms | 1.0008 | 1.0038 |
| PE32 JSON | 167.141 ms | 119.921 ms | 119.901 ms | 1.3940 | 1.4223 |
| baseline batch JSON | 1,373.345 ms | 1,320.092 ms | 1,319.808 ms | 1.0406 | 1.6848 |
| depth-16 archive | 120.415 ms | 68.040 ms | 68.017 ms | 1.7704 | 1.7583 |

PE 与 archive 的 session 2/3 median 很接近，session 1 明显更慢；database 三次
几乎一致；batch 的 median 较接近但 session 1 出现 2,228.018 ms p95。由于三个
session 是同一 host 上的连续 invocation，本实验不能区分 page cache、WSL2/Docker
scheduler、CPU frequency、SMT sibling、宿主后台负载或其他状态影响。把 session 2/3
当作“正确值”、删除 session 1 或用三者最小值冻结阈值都没有证据基础。

产品 case 的 peak RSS median 跨 session max/min 为：

- database：1.0133；
- PE32：1.0037；
- batch：1.0003；
- archive：1.0000。

短 control 的 RSS median 比值为 1.7475，但只有部分采样且明确不是产品 RSS 证据。

## 范围边界

机器报告保持：

- `physical_core_topology_proven=false`；
- `cold_cache_controlled=false`；
- `power_and_frequency_controlled=false`；
- `long_horizon_variability_measured=false`；
- `regression_thresholds_approved=false`。

`cpuset.cpus.effective=0` 只证明 Linux scheduler 可见的单 vCPU 约束，**不是物理核心**
或 SMT sibling 证明。三个 session 没有跨 reboot、日期、主机或随机化实现顺序；
plans 仍声明 warm cache，不能据此回答 cold baseline。

## 复现

在已有 session 1 的基础上，顺序运行两次：

```powershell
python tools\benchmark\probe_upstream_benchmark.py `
  --image diec-rust/upstream-benchmark-qt5:74eaf505 `
  --cpuset-cpus 0 `
  --output docs\research\data\upstream-benchmark-linux-qt5-affinity-session-2.json

python tools\benchmark\probe_upstream_benchmark.py `
  --image diec-rust/upstream-benchmark-qt5:74eaf505 `
  --cpuset-cpus 0 `
  --output docs\research\data\upstream-benchmark-linux-qt5-affinity-session-3.json
```

然后生成汇总：

```powershell
python tools\benchmark\summarize_upstream_benchmark_sessions.py `
  --session docs\research\data\upstream-benchmark-linux-qt5-affinity.json `
  --session docs\research\data\upstream-benchmark-linux-qt5-affinity-session-2.json `
  --session docs\research\data\upstream-benchmark-linux-qt5-affinity-session-3.json `
  --output docs\research\data\upstream-benchmark-linux-qt5-affinity-repeated.json
```

重新采集的 duration/RSS 数值预期会变化；复现要求是固定身份、执行计数、输出、
scope 和 verifier 关系保持有效，不要求新 observation 与本报告逐字节相同。

## 尚未完成

- 定义完整 file-access closure 后实现可审计 cold-cache controller 与 cold baseline；
- 在裸机或可证明 topology 的环境控制 physical core、SMT、frequency/governor，
  并跨 reboot/日期重复 session；
- Windows、macOS 的相同 case 和最终发行包口径；
- Phase 1 Rust 与 upstream 的随机化成对 session；
- 人工评审并冻结 latency/p95/RSS/size thresholds 和默认资源限制。
