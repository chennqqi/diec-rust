# 固定 Linux Qt5 上游单 vCPU affinity 复验

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 结论

固定 Linux Qt5 上游 benchmark 已完成一次单 Linux vCPU affinity 复验：

- 五个既有 warm plans、语料、上游二进制和资源 quota 不变；
- 每个 probe container 都增加 `--cpuset-cpus 0`；
- container 内回读并验证 `cpuset.cpus.effective=0`；
- 17 次 warmup、90 次 measured 全部 exit 0，stderr 为空，输出 hash 稳定；
- database、PE32 JSON、baseline batch JSON 和 depth-16 archive 的 peak RSS 均为
  15/15 完整样本；
- 约 4 ms 的 Qt/process control 只获得 9/30 个 RSS 样本，原始空值保留，且明确
  不作为产品 RSS 证据。

机器报告为
[`upstream-benchmark-linux-qt5-affinity.json`](data/upstream-benchmark-linux-qt5-affinity.json)，
SHA-256 为
`67e6d594a5b93e1b791c11ef89bdb12e85399964cea9bee87baf591047f5d7de`。

本实验只证明 Docker/WSL2 Linux scheduler 将容器约束到一个可见 vCPU；它**不是物理核心证明**，
也没有控制宿主 power governor、频率、SMT sibling 或后台负载。因此报告仍是
`descriptive_upstream_only`、`targets_frozen=false`，不能用于声称 Rust 性能改善。

## 2. 固定身份与执行约束

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| rules/database | `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| release `diec` SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| benchmark image | `sha256:9f1d70a8d4513404cdc457074e00dec4a9b8a6f043a572ffc17465bbe699eb09` |
| benchmark report | `67e6d594a5b93e1b791c11ef89bdb12e85399964cea9bee87baf591047f5d7de` |
| affinity scope | 单个 WSL2/Linux vCPU `0` |

实际 Docker 约束为：

```text
--network none --cpus 1 --cpuset-cpus 0 --memory 512m --pids-limit 128
```

报告验证：

```text
cpu.max=100000 100000
cpuset.cpus.effective=0
memory.max=536870912
pids.max=128
```

镜像 ID 与早先 quota-only 报告不同，是因为 benchmark runner 增加了 `Popen` 后的
有界同步 RSS 首采样；上游 `diec`、harness、语料、plans 和工作定义未改变。首采样最多
尝试 16 次，每次只用 `sleep(0)` 让出调度片，不设置固定等待，也不改变 cache 声明。

## 3. 原始统计摘要

下表仅把报告中的整数纳秒和 bytes 换算为 ms/MiB：

| Case | Median | p95 nearest-rank | MAD | Peak RSS samples | Peak RSS median | Peak RSS max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qt/process control | 3.974 ms | 5.033 ms | 0.559 ms | 9/30 | 8.12 MiB | 11.38 MiB |
| database load | 68.003 ms | 68.201 ms | 0.063 ms | 15/15 | 18.46 MiB | 18.96 MiB |
| PE32 JSON end-to-end | 167.141 ms | 170.943 ms | 3.803 ms | 15/15 | 34.11 MiB | 34.35 MiB |
| baseline batch JSON | 1,373.345 ms | 2,228.018 ms | 53.233 ms | 15/15 | 76.92 MiB | 77.05 MiB |
| depth-16 archive | 120.415 ms | 123.824 ms | 1.339 ms | 15/15 | 23.29 MiB | 23.46 MiB |

control 的 MAD/median 为 `0.14065761019178033`，p95/median 为
`1.2665495897611139`。虽然通过灾难性噪声 guardrail，但它仍小于 50 ms 候选下限，
不具备 regression eligibility。

单 vCPU 复验的 PE、archive 和 batch 出现明显 scheduler/tail 变化。它与早先
quota-only 报告不是同一次成对随机化实验，不能把两个报告的差值解释为 affinity
收益或损失；后续同一 affinity 条件的三次独立 invocation 见
[`upstream-performance-repeated-sessions.md`](upstream-performance-repeated-sessions.md)，
它进一步证明冻结阈值前仍需专用 benchmark host 和更强的长期重复 session。

## 4. control RSS 的审计口径

在 `--cpuset-cpus 0` 下，runner、被测子进程和 Docker 容器任务竞争同一个 Linux
vCPU。约 4 ms 的 control 可能在父进程重新获得调度前已经退出，此时
`/proc/PID/status` 不再存在，polling 无法补回该次 peak RSS。

probe 只对 affinity 报告作以下窄例外：

- 仅 `upstream.qt-process-control.v1` 可保留部分 RSS；
- 至少需要 3 个有效样本；
- 样本数和每次 `null` 原样进入机器报告；
- `control_peak_rss_product_evidence=false`；
- 其余四个 case 任意一次 RSS 缺失仍使报告失败。

该例外不影响 duration、exit code、stdout/stderr hash 或 case 数量校验，也不放宽
quota-only 历史报告的完整 RSS 要求。

## 5. 可重复执行

```powershell
docker build -f tools\upstream\Dockerfile.upstream-benchmark-qt5 `
  -t diec-rust/upstream-benchmark-qt5:74eaf505 tools
python tools\benchmark\probe_upstream_benchmark.py `
  --image diec-rust/upstream-benchmark-qt5:74eaf505 `
  --cpuset-cpus 0 `
  --output docs\research\data\upstream-benchmark-linux-qt5-affinity.json
```

`--cpuset-cpus` 只接受一个非负十进制 CPU 编号；range、list、负数、Unicode 数字和
超出 32-bit signed 范围的输入均拒绝。probe 会把同一约束应用到 cgroup observation、
语料校验和全部五个 case，而不是只约束其中某一次运行。

## 6. 剩余门禁

这次实验把“完全没有 affinity 数据”收窄为“已有单 Linux vCPU 的首轮复验”，但
`P0-BLOCK-006` 仍保持 Open。仍需：

- 可审计的 cold-cache controller 和 cold baseline；
- 裸机或可证明 topology 的 physical-core/SMT/频率控制，以及跨 reboot/日期的
  长期重复 session；
- Windows、macOS 的相同上游 case 与发行包口径；
- Phase 1 Rust 相同 bytes/options 的成对 latency/p95/RSS/size；
- 人工评审后的 regression thresholds 和默认资源限制。
