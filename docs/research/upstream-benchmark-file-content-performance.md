# 固定 Linux Qt5 benchmark 的 warm/file-content 成对性能测量

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt5 五个 benchmark case 已完成 `warm` 与
`file-content-nonresident-metadata-warm` 的成对测量。每个 case 有 10 对，
按 pair index 交替采用 AB/BA 顺序，共 100 个直接子进程：

- 两个状态使用同一个完全静态的 x86_64 C controller、同一个
  `CLOCK_MONOTONIC` 计时边界和同一个 `wait4` direct-child peak-RSS 口径；
- 每个 warm run 在计时前逐文件证明全部 candidate content pages resident；
- 每个 file-content run 在计时前完整 warm candidate、执行逐文件
  `POSIX_FADV_DONTNEED`，再证明全部 candidate pages nonresident；
- container 创建、manifest 校验、完整 warm、fadvise 和 `mincore` 验证均在
  timed interval 之外；
- 五个 case 的 stdout/stderr 均与固定 affinity baseline 相同，两个 cache
  state 之间也完全相同；
- 10 对样本中所有 `file-content - warm` latency delta 均为正。

本轮观察到的 paired median ratio 为 1.244956—8.789222 倍。该结果只说明固定
上游 binary 在这一个连续 WSL2/Linux-vCPU session 中对指定 successful-file
content residency 的敏感性，不是 Rust/upstream 性能比较，也不构成回归阈值。

机器报告为
[`data/upstream-benchmark-linux-qt5-file-content-performance.json`](data/upstream-benchmark-linux-qt5-file-content-performance.json)，
SHA-256 为
`6370d44ca5777be3b0d2e9fbe2f3e8b07166ea404cfbba0bba627c4d1d6f5a91`。

## 固定身份与测量边界

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| benchmark image | `sha256:9f1d70a8d4513404cdc457074e00dec4a9b8a6f043a572ffc17465bbe699eb09` |
| plan suite | `f93672c9603db16050047095f15d5f5ea6d9d58663b4574ed901f819f0106e1a` |
| affinity baseline | `67e6d594a5b93e1b791c11ef89bdb12e85399964cea9bee87baf591047f5d7de` |
| successful-file closure | `4edfe49fc68861bbfbb04f7b3a8309b65eb4f6eba884985b4fe08e5f5ed3f922` |
| page-cache evidence | `081ab455705587089a03401935c8109cdc271f426e11295b2c848f4186b933eb` |
| cache-environment evidence | `77ef746852a3a05fd29b8e8a8650f0febb22d123dd3b007451265b4597c72811` |
| measurement source | `3f8cdece2ebdfd6c12572c9671d24a17be24cdd8da0b0629a5849187f5b3c906` |
| page controller source | `be86dc84568f64e8ac2bd6ee9d53e45ab15a8401186b0f34b4f9b9318f8dc2b7` |
| measurement ELF | 804,240 bytes；`3f572449ddf0330e3e1e4a9b254edb78bb45ec575abfcfb463dd37d1a02a73bf` |
| host generator | `0e2dbff928c176235759e2128b51faa2653d12987158618c1c12dfdeb11ebf24` |
| scheduling | 10 pairs/case，ABBA alternating by pair index |
| process count | 5 cases × 10 pairs × 2 states = 100 |
| cgroup | `cpu.max=100000 100000`；`cpuset.cpus.effective=0`；512 MiB；128 PIDs |

controller 在固定镜像内使用
`cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` 和
`-static -O2 -std=c11 -Wall -Wextra -Werror` 编译。host probe 解析 ELF64
program headers；该 ELF 无 `PT_INTERP` 和 `PT_DYNAMIC`，因此测量器本身不会
通过动态 loader/libc 重新 fault benchmark closure 中的候选页。

计时从 `clock_gettime(CLOCK_MONOTONIC)` 后立即 `fork` 开始，至
`wait4` 返回结束，包含 fork/exec 和目标进程完整运行时间。peak RSS 为
`wait4` 返回的 direct-child `ru_maxrss * 1024`。stdout/stderr 分别受
64 MiB `RLIMIT_FSIZE` 限制；120 秒 watchdog 超时后发送 `SIGKILL`。这些数值
不能与历史 Python `Popen`/polling runner 的 RSS 直接混用。

## 方法

每个 pair 的两个状态使用相同 manifest 和 command。偶数 pair 先 warm 后
file-content，奇数 pair 反向，用交错顺序降低单调漂移偏差：

1. 新容器加载 hash-bound manifest，打开并核对所有 regular file 的长度；
2. 完整 `pread` 所有候选文件，再以 `mmap(PROT_NONE)` + `mincore` 证明所有
   content pages resident；
3. warm 状态保持这些页 resident；file-content 状态对每个文件执行
   `POSIX_FADV_DONTNEED` 并逐文件证明 0 resident；
4. 只有 before-run page-state invariant 成立后才启动单个 timed child；
5. `wait4` 返回 latency、peak RSS 和退出状态；controller 输出严格 TSV；
6. host 拒绝未知/重复字段、状态不匹配、非十进制数、页状态不符、超时、非零
   退出或越界输出；
7. host 核对 stdout/stderr 与 affinity baseline，并从 10 个 raw pair 重算
   min/median/nearest-rank p95/max/MAD、paired delta 和 scaled ratio。

`warm` 与 file-content 状态都会执行 pathname lookup、open、fstat 和完整 warm，
所以二者的 metadata 都是 warm。实验变量只是在命令启动前候选 content pages
是全部 resident，还是逐文件观测为全部 nonresident。

## 观测结果

以下 latency 为 10 个样本的 median；ratio 是每个 pair 的
`file-content duration / warm duration` 先缩放到 `1e6` 后再取 median，不是两列
median 的简单相除。

| Case | Warm median | File-content median | Paired delta median | Paired ratio median | Warm/File peak RSS median |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qt/process control | 10.748 ms | 56.135 ms | 44.738 ms | 5.212505× | 14,090,240 / 13,369,344 B |
| database load | 61.371 ms | 531.202 ms | 469.870 ms | 8.789222× | 20,496,384 / 19,709,952 B |
| PE32 JSON | 162.445 ms | 633.004 ms | 472.373 ms | 3.873532× | 36,202,496 / 35,497,984 B |
| baseline batch JSON | 1,441.800 ms | 1,792.036 ms | 330.137 ms | 1.244956× | 80,986,112 / 80,386,048 B |
| depth-16 archive | 77.289 ms | 490.358 ms | 411.421 ms | 6.624679× | 24,780,800 / 23,949,312 B |

database load 对 file-content residency 的 paired median ratio 最大；batch case
需要较多 CPU 扫描工作，因此相同内容页扰动只表现为约 1.245 倍。这个解释是由
case 工作定义和观测比例得到的合理推断，不是 CPU/I/O profiling 证明。

RSS 两状态的 median 很接近，且 file-content 多数略低；不能据此声称 cache
state 降低内存。`ru_maxrss` 是进程地址空间 resident high-water mark，不是文件
系统 page cache 用量，也不包含 controller 或容器的总内存峰值。

## 能证明与不能证明的事项

机器 scope 固定：

- `descriptive_upstream_cache_state_spike=true`；
- `direct_child_process_only=true`；
- `same_launcher_clock_and_rss_method_across_states=true`；
- `metadata_cache_controlled=false`；
- `system_cold_cache_controlled=false`；
- `physical_core_topology_proven=false`；
- `long_horizon_sessions_present=false`；
- `rust_paired_measurements_present=false`；
- `regression_thresholds_frozen=false`。

因此本报告填补了“同一 controller 下实际测量两个精确 cache state”的技术
证据，但没有把 generic process benchmark runner v1 升级为 production
file-content runner。它也没有控制 failed lookup、directory、dentry/inode
reclaim、overlayfs host cache 或 system-global cold 状态。`system-cold` 仍然
只能在得到授权的 disposable dedicated VM/裸机上采集，通用 `cold` 标签仍禁止。

本轮只有一个连续 session。ABBA 能降低顺序漂移，但不能替代跨日期、重启、频率
与 physical-core/topology 控制。短 Qt/process control 仍容易受启动噪声影响，
在更多 session 证明稳定前不具备回归阈值资格。

## 对 Phase 0 的影响

- ADR 0015 的第二层 cache-state 已从纯 residency spike 推进到 100 个成对
  performance samples，且每个 measured run 都携带 before-run page evidence；
- `P0-BLOCK-006` 仍为 Open：没有 Rust 同 case 配对、生产 runner schema 接入、
  dedicated system-cold、长期 session、跨平台 cache-state 策略或评审阈值；
- 不能把本报告与历史 warm baseline 的绝对 RSS/latency 拼接为同一 trend，因为
  launcher、计时边界、warm 定义和 RSS collector 不同；
- Phase 1/6 的正式 runner 应复用这里的 controller identity/evidence contract，
  但仍需把 orchestration 纳入统一 plan schema 和跨平台 CI。

## 复现

```powershell
python tools\benchmark\probe_upstream_benchmark_file_content_performance.py `
  --output docs\research\data\upstream-benchmark-linux-qt5-file-content-performance.json
```

该命令会重新编译静态 controller，并启动 100 个 measured child。报告包含真实
timing，因此再次执行不会要求输出逐字节相同；可重复的是固定输入/二进制身份、
调度策略、页状态与输出 invariant，统计值应作为新的独立 session 保留，不能
静默覆盖既有基线。

## 尚未完成

- 将 file-content controller/evidence 纳入正式 process benchmark plan schema；
- 对相同 case 建立 upstream/Rust 随机化或交错配对；
- 至少跨日期/重启的长期 session 与 physical-core/topology/frequency 证据；
- dedicated system-cold authority/isolation/controller；
- Windows/macOS 等价或明确不可等价的 cache-state 策略；
- 经评审的 latency/p95/RSS、发行包 size 和默认资源限制阈值。
