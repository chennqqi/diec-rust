# 固定 Linux Qt5 benchmark 成功文件访问闭包

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt5 五个 benchmark case 已建立 successful regular-file access
closure：

- 每个 case 在相同断网镜像、512 MiB/128 PID、单 Linux vCPU `0` 下独立 trace
  两次；
- parent-child `ptrace(PTRACE_SYSCALL)` 记录成功的 `open`/`openat`/`openat2`，
  exec trap 的 `/proc/<pid>/maps` 补入内核按 ELF `PT_INTERP` 映射的动态加载器；
- 两次 closure、volatile path 和基线 stdout/stderr 对每个 case 完全相同；
- 五个 case 的 unique union 为 2,283 个 regular files、73,560,058 bytes，
  包括两个 ELF、16 个系统动态依赖、loader cache、28 个 corpus 文件、时区文件
  和本轮实际打开的规则文件；
- main `db` 2,124 个资产中成功打开 2,097 个，`db_extra` 142 个中成功打开
  138 个，`db_custom` 两个中成功打开 0 个；未打开的 33 个资产全部不是 `.sg`
  脚本，而是 22 个 `_icons` PNG、6 个 `.vscode` 文件、3 个 `about.txt` 和
  2 个 `info.ini`。

这关闭的是“这五个固定 case 成功打开哪些 persistent regular files”的技术清单，
不是完整 cold-cache controller。它把 future advisory eviction 的候选 file set
从推测变为 hash-bound observation，但 failed lookup、目录、dentry/inode cache、
descendant、page residency 和实际 eviction 仍未闭合。

机器报告为
[`data/upstream-benchmark-linux-qt5-file-access.json`](data/upstream-benchmark-linux-qt5-file-access.json)，
SHA-256 为
`4edfe49fc68861bbfbb04f7b3a8309b65eb4f6eba884985b4fe08e5f5ed3f922`。

## 固定身份与方法

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| benchmark image | `sha256:9f1d70a8d4513404cdc457074e00dec4a9b8a6f043a572ffc17465bbe699eb09` |
| plan suite | `f93672c9603db16050047095f15d5f5ea6d9d58663b4574ed901f819f0106e1a` |
| affinity baseline | `67e6d594a5b93e1b791c11ef89bdb12e85399964cea9bee87baf591047f5d7de` |
| tracer | `6300c7e23fad559a6ff7dcd72f5cfbf6e74e869eb659e976e28c0c6203ab0c84` |
| host probe | `ac72cf9e7194790a594ba0c234f2d541a68b043a4fdc67e09ba159e6ff1119c7` |
| trace repetitions | 2 per case，10 processes total |
| cgroup | `cpu.max=100000 100000`；`cpuset.cpus.effective=0`；512 MiB；128 PIDs |

镜像没有 `strace` 或 `perf`。项目内 tracer 仅支持 Linux x86_64，并使用
`PTRACE_TRACEME` 的 parent-child 模型，不要求 `CAP_SYS_PTRACE`。Docker/WSL2 的
`kernel.yama.ptrace_scope=1` 允许该关系。

每次执行：

1. tracee 在 exec 前 `SIGSTOP`，parent 设置
   `PTRACE_O_TRACESYSGOOD|PTRACE_O_EXITKILL`；
2. syscall exit 时读取成功返回的 fd，经 `/proc/<pid>/fd/<fd>` 解析路径，只保留
   regular files；
3. exec trap 读取 maps，补入 kernel-opened `PT_INTERP`。否则仅按用户态
   `openat` 会少掉
   `/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2`；
4. tracee stdout/stderr 重定向到有界文件并与既有 affinity baseline hash 对照；
5. 进程结束后重新读取每个 persistent file 的 bytes、mode、SHA-256；
6. host probe 要求同 case 两次 records 和 volatile paths 完全一致，再生成全局
   union。

tracer 使用独立 watchdog。即使 tracee 在 CPU 自旋中不再产生 syscall，也会在
timeout 后被 `SIGKILL`，不会让 parent 永久阻塞。trace duration 被刻意丢弃：
ptrace 观察会改变时序，本报告不是性能测量。

## 每个 case

| Case | Successful files | Unique bytes | Records SHA-256 |
| --- | ---: | ---: | --- |
| Qt/process control | 18 | 62,358,715 | `e9a17c43d2be07ef371d7eadcea86b938dae3a39e9c60846810a8e15a5f660ef` |
| database load | 2,253 | 65,261,596 | `ee4ddca31895f7e63b704301ab427cd1b49136099ec981715b607801f7c230a6` |
| PE32 JSON | 2,255 | 65,271,878 | `f477a3df05173f4b6317f38895045542f9bcfa0e8bf80d5329fd3d1b1d6d3389` |
| baseline batch JSON | 2,281 | 65,319,431 | `f665d589922f583701086ad32746b58e8a3f526bbb8456cb71ff01781ed05ece` |
| depth-16 archive | 2,254 | 65,263,871 | `4fca0bb3fb4ae4ca11c91471ca0fc6b661f0b1207c027b8879a175d6e220150c` |

control 的 18 个文件是 harness ELF、16 个系统库和 `/etc/ld.so.cache`。需要加载
database 的四个 case 都成功打开相同的 2,097 个 main `.sg` 与 138 个 extra
`.sg`。PE/batch 还成功打开 `/usr/share/zoneinfo/Etc/UTC` 和规范化 volatile
`/proc/self/maps`；后者不进入 persistent union。报告不推断访问它们的业务目的。

全局 union records SHA-256 为
`bbe42686c5708e441cacd3188a4c3252ec89ff973f85050bb77898d58ac7ef15`。
16 个 system-library records 与既有 deployment closure 的 realpath 数量一致；
本报告额外绑定“哪些 case 实际成功打开/映射它们”，不替代 ELF dependency
解析。

## 规则资产与成功打开集合

| Tree | Asset files | Successfully opened | Missing | Missing bytes |
| --- | ---: | ---: | ---: | ---: |
| `db` | 2,124 | 2,097 | 27 | 5,735 |
| `db_extra` | 142 | 138 | 4 | 504 |
| `db_custom` | 2 | 0 | 2 | 196 |
| 合计 | 2,268 | 2,235 | 33 | 6,435 |

三个资产树仍须原样同步；“本 benchmark 没有打开”不是删除资产的授权。`_icons`
可能被 GUI 消费，`about.txt`/`info.ini`/`.vscode` 也具有来源或维护信息。本结果只
说明固定 CLI/harness 的 database load 路径成功打开全部 2,235 个 `.sg`，没有
成功打开这些 33 个非脚本资产。

因此后续必须区分：

- rule distribution manifest：原样保存固定上游三树和完整 provenance；
- runtime compiled-script closure：CLI 实际解析/编译的 `.sg`；
- GUI/display assets：未来 GUI 范围单独决定；
- benchmark eviction candidate：本 case 的 persistent regular-file union。

## Cold-cache 边界

机器 scope 明确保留：

- `failed_lookup_closure=false`；
- `directory_and_metadata_cache_closure=false`；
- `descendant_process_access_closure=false`；
- `page_residency_observed=false`；
- `posix_fadvise_executed=false`；
- `cold_cache_controlled=false`；
- `cold_benchmark_collected=false`；
- `performance_timings_from_ptrace=false`。

`posix_fadvise(POSIX_FADV_DONTNEED)` 是 advisory，不等于驱逐成功。下一步至少要在
相同 union 上设计 page-residency observation，验证每次 advisory eviction 的
前后状态，并把 directory/dentry/inode、failed lookup、overlayfs 和共享 host page
cache 边界继续留在报告中。在这些证据存在前，runner 继续拒绝 `cache_state=cold`。

## 复现

```powershell
python tools\benchmark\probe_upstream_benchmark_file_access.py `
  --output docs\research\data\upstream-benchmark-linux-qt5-file-access.json
```

host probe 只读 bind-mount 当前 tracer，运行前后由报告绑定 tracer SHA-256；容器
始终 `--network none --cpus 1 --cpuset-cpus 0 --memory 512m
--pids-limit 128`。生成器拒绝镜像、计划、affinity baseline、cgroup、输出 hash、
文件身份、重复 closure、规则 subtree 或 scope 漂移。

## 尚未完成

- page residency observation 与可验证的 advisory regular-file eviction；
- failed lookup、目录和 dentry/inode cache 的可控口径；
- controlled-cold plans、三次 session 和 upstream/Rust 随机化配对；
- physical-core/SMT/frequency/governor 与跨 reboot/日期环境；
- Windows/macOS 对应 cold controller 或明确不可等价策略；
- 评审后的 latency/p95/RSS/size/default-limit thresholds。
