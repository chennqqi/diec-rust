# 固定 Linux Qt5 benchmark 的 runner-integrated warm/file-content 成对测量

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

通用 process benchmark runner 的 plan/report schema v2 已接入
`linux-file-content-v1` controller，并对固定 Linux Qt5 五个 benchmark case
完成 `warm` 与
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

本轮观察到的 paired median ratio 为 1.333355—8.760115 倍。该结果只说明固定
上游 binary 在这一个连续 WSL2/Linux-vCPU session 中对指定 successful-file
content residency 的敏感性，不是 Rust/upstream 性能比较，也不构成回归阈值。

机器报告为
[`data/upstream-benchmark-linux-qt5-file-content-performance.json`](data/upstream-benchmark-linux-qt5-file-content-performance.json)，
SHA-256 为
`d27775639c8b7ab4ee171ff4e0e2f0b4077ea76d185e33e11b2b80c7a26012ac`。

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
| measurement source | `056514706dfa8df76d5cb0f4fa5cb1c9e5fed4d0950d1e786d7c36be62069e51` |
| page controller source | `be86dc84568f64e8ac2bd6ee9d53e45ab15a8401186b0f34b4f9b9318f8dc2b7` |
| measurement ELF | 804,184 bytes；`2a0c02d469a7f6829c04fc356cd33e9a8ac67b21adf22213a5d9596da2550a31` |
| process runner | v2；`7a4e9e929e33e34a067360da4117051146d6101284267cbc89fc9a2e02853dbf` |
| host generator | `9d9bd9612916c4b227d78ec36e03818d6041476947af8dc981a6f55136cadaa6` |
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

每个 pair 的两个状态使用相同 manifest 和 command。每个 sample 都动态构造
严格的 plan schema v2，绑定 controller binary/manifest 的绝对路径、bytes、
SHA-256、page size、file count、logical pages、cache state 和 `/bench`
working-directory contract。偶数 pair 先 warm 后
file-content，奇数 pair 反向，用交错顺序降低单调漂移偏差：

1. Python runner 验证 plan、目标 executable、input artifacts、controller、
   manifest、host 与 finalizer 身份，把精确 preflight 写入有界 exchange；
2. runner 通过 `os.execve` **替换自身**为静态 controller，确保测量期间没有
   Python/loader/libc 映射继续 pin candidate pages；
3. controller 加载 hash-bound manifest，打开并核对所有 regular file 的长度；
4. 完整 `pread` 所有候选文件，再以 `mmap(PROT_NONE)` + `mincore` 证明所有
   content pages resident；
5. warm 状态保持这些页 resident；file-content 状态对每个文件执行
   `POSIX_FADV_DONTNEED` 并逐文件证明 0 resident；
6. 只有 before-run page-state invariant 成立后才启动单个 timed child；
7. `wait4` 返回 latency、peak RSS 和退出状态；controller 输出严格 TSV；
8. controller 完成测量后再 `execve` Python finalizer；finalizer 重新验证
   preflight、plan、executable、inputs、controller/manifest 与自身身份，生成
   report schema v2；
9. runner 拒绝未知/重复字段、状态不匹配、非十进制数、页状态不符、超时、非零
   退出或越界输出；
10. host probe 核对 stdout/stderr 与 affinity baseline，并从 10 个 raw pair 重算
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
| Qt/process control | 12.035 ms | 66.312 ms | 53.524 ms | 5.683948× | 14,090,240 / 13,369,344 B |
| database load | 97.396 ms | 933.205 ms | 813.255 ms | 8.760115× | 20,432,896 / 19,644,416 B |
| PE32 JSON | 253.032 ms | 999.514 ms | 753.471 ms | 4.114096× | 36,282,368 / 35,497,984 B |
| baseline batch JSON | 3,041.579 ms | 4,171.030 ms | 1,063.506 ms | 1.333355× | 81,139,712 / 80,273,408 B |
| depth-16 archive | 160.986 ms | 1,104.170 ms | 944.330 ms | 6.589210× | 24,813,568 / 23,953,408 B |

database load 对 file-content residency 的 paired median ratio 最大；batch case
需要较多 CPU 扫描工作，因此相同内容页扰动只表现为约 1.333 倍。这个解释是由
case 工作定义和观测比例得到的合理推断，不是 CPU/I/O profiling 证明。

RSS 两状态的 median 很接近，且 file-content 多数略低；不能据此声称 cache
state 降低内存。`ru_maxrss` 是进程地址空间 resident high-water mark，不是文件
系统 page cache 用量，也不包含 controller 或容器的总内存峰值。

## 能证明与不能证明的事项

机器 scope 固定：

- `descriptive_upstream_cache_state_spike=true`；
- `runner_plan_integration_present=true`；
- `direct_child_process_only=true`；
- `same_launcher_clock_and_rss_method_across_states=true`；
- `metadata_cache_controlled=false`；
- `system_cold_cache_controlled=false`；
- `physical_core_topology_proven=false`；
- `long_horizon_sessions_present=false`；
- `rust_paired_measurements_present=false`；
- `regression_thresholds_frozen=false`。

因此本报告填补了“同一 controller 下实际测量两个精确 cache state”的技术
证据，并将 generic process benchmark runner 从 warm-only v1 扩展为严格的
Linux file-content plan/report schema v2。它仍没有控制 failed lookup、
directory、dentry/inode
reclaim、overlayfs host cache 或 system-global cold 状态。`system-cold` 仍然
只能在得到授权的 disposable dedicated VM/裸机上采集，通用 `cold` 标签仍禁止。

本轮只有一个连续 session。ABBA 能降低顺序漂移，但不能替代跨日期、重启、频率
与 physical-core/topology 控制。短 Qt/process control 仍容易受启动噪声影响，
在更多 session 证明稳定前不具备回归阈值资格。

## 对 Phase 0 的影响

- ADR 0015 的第二层 cache-state 已从纯 residency spike 推进到 runner-integrated
  100 个成对 performance samples，且每个 measured run 都携带 plan、preflight、
  controller identity 与 before-run page evidence；
- `P0-BLOCK-006` 仍为 Open：没有 Rust 同 case 配对、dedicated system-cold、
  长期 session、跨平台 cache-state runtime/closure 或评审阈值；
- 不能把本报告与历史 warm baseline 的绝对 RSS/latency 拼接为同一 trend，因为
  launcher、计时边界、warm 定义和 RSS collector 不同；
- Phase 1/6 应把已形成的 v2 contract 纳入 Linux CI，并为 Windows/macOS 采用
  经评审的等价或明确不等价 controller。

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
- macOS `MS_INVALIDATE` + `mincore` runtime candidate 的 Darwin 执行与
  fixed-closure integration；Windows 已固定为只复用 warm；
- 经评审的 latency/p95/RSS、发行包 size 和默认资源限制阈值。
