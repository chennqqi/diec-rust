# 固定 Linux Qt5 benchmark 文件页 residency 与 advisory eviction

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt5 五个 benchmark case 已对上一轮 successful regular-file
closure 建立可重复的 page-residency observation：

- 每个 case 从固定 closure 投影自己的 18—2,281 个文件；
- 完全静态的 x86_64 controller 顺序读取所有文件，使 15,231—17,869 个逻辑页
  全部由 `mincore` 观测为 resident；
- controller 对每个文件执行
  `posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)`，再逐文件重新映射并调用
  `mincore`；
- 五个 case、每个 case 两次执行，在命令启动前都观测到
  `resident_pages_after_evict=0`；
- benchmark 原始 stdout/stderr 与固定 affinity baseline 相同；两次执行的
  per-path post-run residency 也完全相同。

这把 `page_residency_observed` 和 `posix_fadvise_executed` 从缺口变为正面机器
证据，并验证 advisory call 在本固定环境、本候选文件集合上确实产生了可观察的
nonresident 状态。它仍然不是完整 cold-cache baseline：controller 为了打开、
校验、warm 和 advise 文件，必然预热 pathname、directory、dentry 和 inode；
failed lookup、overlayfs 内部状态与宿主 cache 隔离也没有闭合。因此报告仍保持
`cold_cache_controlled=false`、`cold_benchmark_collected=false`，且没有保留
任何 latency/RSS 数值。

机器报告为
[`data/upstream-benchmark-linux-qt5-page-cache.json`](data/upstream-benchmark-linux-qt5-page-cache.json)，
SHA-256 为
`081ab455705587089a03401935c8109cdc271f426e11295b2c848f4186b933eb`。
相同生成器连续三次生成的文件逐字节一致。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| benchmark image | `sha256:9f1d70a8d4513404cdc457074e00dec4a9b8a6f043a572ffc17465bbe699eb09` |
| plan suite | `f93672c9603db16050047095f15d5f5ea6d9d58663b4574ed901f819f0106e1a` |
| affinity baseline | `67e6d594a5b93e1b791c11ef89bdb12e85399964cea9bee87baf591047f5d7de` |
| successful-file report | `4edfe49fc68861bbfbb04f7b3a8309b65eb4f6eba884985b4fe08e5f5ed3f922` |
| controller source | `be86dc84568f64e8ac2bd6ee9d53e45ab15a8401186b0f34b4f9b9318f8dc2b7` |
| controller ELF | `cea2a08a79f4f276fd4ad6524f095aff0a4908957cae6372e927afdadfb97852` |
| host generator | `a4cf04fd28469b1bdf950de1d6fcdded13825f175f8d0631a0e8b8961917f331` |
| page size | 4,096 bytes |
| repetitions | 2 per case，10 processes total |
| cgroup | `cpu.max=100000 100000`；`cpuset.cpus.effective=0`；512 MiB；128 PIDs |

controller 由同一固定镜像内的
`cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` 使用
`-static -O2 -std=c11 -Wall -Wextra -Werror` 编译。host probe 解析 ELF64
program headers，并拒绝 `PT_INTERP` 或 `PT_DYNAMIC`。本轮 799,536-byte ELF
没有二者。

这个约束很重要：如果使用 Python 或动态 C controller，观察器本身会映射
benchmark closure 中的 loader、libc 等文件，使这些页无法被清成 nonresident。
静态 controller 位于 host bind mount，不属于候选 closure，运行期间也不映射
目标动态库。

## 方法

每次 case 执行严格按以下顺序进行：

1. host 从 hash-bound successful-file union 按 `cases` 字段投影 case manifest，
   并核对 file count 与 bytes；
2. controller 以 `open(O_RDONLY|O_CLOEXEC)` 和 `fstat` 核对 regular-file
   类型与长度；
3. 对每个文件完整 `pread`，随后以 `mmap(PROT_NONE|MAP_PRIVATE)` +
   `mincore` 证明全部逻辑页 resident；
4. 关闭所有 mapping/fd，再对每个文件执行 `POSIX_FADV_DONTNEED`；
5. 重新逐文件 `mmap` + `mincore`，要求每个文件而不只是总数都为 0 resident；
6. `fork`/`execv` 固定命令，stdout/stderr 写入有界 case 文件，120 秒 watchdog
   超时后 `SIGKILL`；
7. 子进程退出后再次逐文件观察 residency，保存完整 per-path vector；
8. host 核对输出 hash、manifest、page invariants、device/inode 唯一性，并要求
   同 case 两次 post-run vector 完全一致。

`PROT_NONE` mapping、`mincore` 和打开文件本身不读取文件内容。第 5 步因此用于
验证 advise 后、benchmark 前的页状态；第 6 步才允许目标进程重新 fault/readahead
这些页。

## 每个 case

| Case | Files | Bytes | Logical pages | Before run resident | After run resident | Post-run vector SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qt/process control | 18 | 62,358,715 | 15,231 | 0 | 4,343 | `71b121cac78e156c44fab0742c96766e00d17d630d78d5f915fed68812ea8929` |
| database load | 2,253 | 65,261,596 | 17,831 | 0 | 7,345 | `69b6a3168d10a055fc5bb138b4d1460bebe18679ab8ccd25e456c7bfad3d573e` |
| PE32 JSON | 2,255 | 65,271,878 | 17,835 | 0 | 8,101 | `8cfcccf1e7e0360c9549087b607f6e6103c79d5254de34b998809a37e03c5a2e` |
| baseline batch JSON | 2,281 | 65,319,431 | 17,869 | 0 | 8,331 | `df94486899ae800bd409ee7eb5f365f47dce70bda02e76e7140d6958902bf71d` |
| depth-16 archive | 2,254 | 65,263,871 | 17,832 | 0 | 7,985 | `ebe6d4ab24adacb3f3b47c666ef589ff638a6237a28f79ebd470479c84858c29` |

“After run resident”不是实际读取字节数。ELF demand paging、filesystem readahead、
共享页及程序访问模式都会影响它；本报告只把它作为命令确实从已观察
nonresident 状态重新加载页面、以及两次路径向量可复现的证据。

全部 manifest path 在每次容器中映射到唯一的 `(st_dev, st_ino)`，因此 logical
page 合计没有因同一 inode 的别名路径重复计数。文件 mode/SHA-256 身份仍由上游
successful-file report 与 immutable image ID 绑定；controller 不为重新计算哈希
而在 eviction 后再次读取内容。

## Cold-cache 边界

机器 scope 精确声明：

- `successful_regular_file_page_residency_observed=true`；
- `posix_fadvise_dontneed_executed=true`；
- `all_candidate_pages_observed_nonresident_before_run=true`；
- `directory_and_metadata_cache_controlled=false`；
- `failed_lookup_cache_controlled=false`；
- `overlayfs_host_cache_isolation_proven=false`；
- `cold_cache_controlled=false`；
- `cold_benchmark_collected=false`；
- `performance_timings_collected=false`。

因此当前最多可以说“固定 successful-file candidate 的内容页在命令前被观测为
nonresident”，不能简写成“cold run”。下一阶段 controller 设计至少要选择并
评审一种口径：

1. 接受 metadata-warm/file-content-nonresident 作为单独命名的可移植层，并与
   warm baseline 配对；
2. 在具备权限的隔离 VM/裸机中使用全局 cache drop，增加前后观测并证明不会污染
   其他工作负载；
3. 为各平台定义不同但明确的 cache state，禁止把不可等价结果放入同一阈值。

任何选择都不能用一次 `fadvise` 返回 0 代替 `mincore` 后验，也不能把 container
边界自动当成独立 host page cache。

## 复现

```powershell
python tools\benchmark\probe_upstream_benchmark_page_cache.py `
  --output docs\research\data\upstream-benchmark-linux-qt5-page-cache.json
```

probe 固定 image、plan、affinity baseline、successful-file report、controller
source、静态 ELF 属性、cgroup、page size、输出 hash、manifest 投影和两次
per-path residency。Docker 始终断网并限制为单 Linux vCPU、512 MiB 与 128
PIDs。

## 尚未完成

- 评审并命名 metadata-warm/file-content-nonresident benchmark 层；
- failed lookup、directory、dentry/inode 与 overlayfs cache 口径；
- 若选择全局 cold，建立隔离 VM/裸机 controller 与前后验证；
- 三次独立 session、跨 reboot/日期与 physical-core/SMT/frequency 控制；
- Rust/upstream 随机化成对测量；
- Windows/macOS 等价或明确不可等价策略；
- 评审后的 latency/p95/RSS/size/default-limit thresholds。
