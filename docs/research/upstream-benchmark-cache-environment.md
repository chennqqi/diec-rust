# 固定 Linux Qt5 benchmark 缓存控制环境边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt5 benchmark 容器不能安全、独立地建立 system-wide cold cache：

- 容器运行在 `6.6.87.2-microsoft-standard-WSL2` 内核，根文件系统是 overlayfs；
- `/proc/sys` 是只读 proc submount；
- effective capabilities 为 `00000000a80425fb`，不含 bit 21
  `CAP_SYS_ADMIN`；
- `/proc/sys/vm/drop_caches` 权限为 `0200`，`os.access` 不可读/写；仅尝试
  `open(O_WRONLY)`、不写入任何字节，即返回 `EROFS`；
- 当前进程可见 Linux 标准 cgroup/IPC/mount/network/PID/time/user/UTS
  namespaces，没有 page-cache namespace；
- user namespace uid map 是 initial mapping；mount namespace 隔离的是 mount
  view，不是独立 VM/kernel cache。

Docker 官方同时明确 overlay2 对同一文件共享 page-cache entry。因此增加
`--privileged`、`--cap-add SYS_ADMIN` 或把 `/proc/sys` 改为可写，不会把当前容器
变成独立 cache domain；写 `drop_caches` 将作用于承载 Docker 的 WSL2 Linux
kernel，并可能干扰其他容器/任务。本调研没有启动 privileged container、没有
增加 capability、没有执行 `sync`，也没有写 `drop_caches`。

机器报告为
[`data/upstream-benchmark-linux-qt5-cache-environment.json`](data/upstream-benchmark-linux-qt5-cache-environment.json)。
相同只读观察连续两次相同；报告 SHA-256 为
`77ef746852a3a05fd29b8e8a8650f0febb22d123dd3b007451265b4597c72811`。

## 官方契约

本结论使用以下上游接口文档，而不是从一次权限错误推断全部语义：

- Linux kernel
  [`drop_caches`](https://docs.kernel.org/6.6/admin-guide/sysctl/vm.html#drop-caches)
  文档规定：`1` 回收 clean page cache，`2` 回收包括 dentries/inodes 的
  reclaimable slab，`3` 同时执行两者；它还警告该操作可能造成显著 I/O/CPU
  代价，不建议在测试/调试环境外使用。
- Linux man-pages
  [`posix_fadvise(2)`](https://man7.org/linux/man-pages/man2/posix_fadvise.2.html)
  说明 `POSIX_FADV_DONTNEED` 只是尝试释放指定文件范围的 cached pages，并推荐
  用 `mmap` + `mincore` 观察文件页 residency。
- Linux man-pages
  [`namespaces(7)`](https://man7.org/linux/man-pages/man7/namespaces.7.html)
  列出可用 namespace 类型；不存在 page-cache namespace。namespace 只隔离其
  点名的全局资源。
- Docker
  [`overlay2 page caching`](https://docs.docker.com/engine/storage/drivers/overlayfs-driver/#page-caching)
  明确多个容器访问同一文件时共享单一 page-cache entry。
- Linux VFS
  [`Overview of the Linux Virtual File System`](https://docs.kernel.org/filesystems/vfs.html)
  说明 dentries 位于内存并用于 pathname lookup，inode lookup 通过 parent
  directory inode 完成。

因此：

- per-file fadvise/mincore 可以证明指定内容页的状态；
- 它不能证明 dentry、inode、negative lookup 或全 kernel cache 的状态；
- cgroup memory accounting 也不能等同于独立 page cache；
- privileged container 不是 system-cold 隔离方案。

## 固定观察

| 字段 | 观察值 |
| --- | --- |
| image | `sha256:9f1d70a8d4513404cdc457074e00dec4a9b8a6f043a572ffc17465bbe699eb09` |
| kernel | Linux `6.6.87.2-microsoft-standard-WSL2` x86_64 |
| root filesystem | `overlay`，rw；存在 lowerdir/upperdir/workdir |
| `/proc/sys` | `proc`，ro |
| `/sys/fs/cgroup` | `cgroup2`，ro |
| effective capabilities | `00000000a80425fb` |
| `CAP_SYS_ADMIN` | false |
| seccomp | mode 2 |
| user namespace | initial uid map |
| page-cache namespace | 不存在 |
| `drop_caches` open | `EROFS` |
| `vfs_cache_pressure` | 100 |
| cache-changing operation | none |

observer 对 mountinfo 只保留稳定 filesystem/source/options 以及
lowerdir/upperdir/workdir 的存在性，不保存 Docker 的 volatile overlay 路径。
namespace inode 和 container hostname 同样不进入报告。因此相同环境的两次报告
可逐字节比较。

## 与 page-residency 证据的关系

[`upstream-benchmark-page-cache.md`](upstream-benchmark-page-cache.md) 已证明：

- static controller 不映射 benchmark closure 的动态库；
- 每个 case 的所有候选内容页可被完整 warm；
- 每次命令前，fadvise 后逐文件 `mincore` 均为 0 resident；
- 双次 post-run per-path vector 和 stdout/stderr 相同。

本报告不否定该证据。它限定正确名称：

`file-content-nonresident-metadata-warm`

其中：

- `file-content-nonresident` 由每次命令前 per-path `mincore=0` 证明；
- `metadata-warm` 是保守且真实的描述，因为 manifest projection、`open`、
  `fstat`、warm、fadvise 和再次 open 都已解析 pathname 并接触 inode；
- overlay2 page-cache sharing 已由后验 observation 控制到“命令前目标页为 0”，
  但没有证明 container/host cache isolation。

不能把这个层缩写为 `cold` 或与 future `system-cold` 放入同一阈值组。

## System-cold 的安全门禁

只有满足以下条件才能声明 `system-cold`：

1. disposable、dedicated VM 或裸机，不承载无关工作负载；
2. exact kernel、filesystem、block device、mount options 和 machine identity
   固定；
3. 获得对该 dedicated environment 的明确 root/cache-drop 授权；
4. 每个 measured run 前执行经评审的 sync/drop/reboot controller；
5. 记录操作前后 page cache、dentry/inode 或可用的替代观测；
6. controller 失败时 fail closed，不退化为 warm 或 file-only；
7. upstream 与 Rust 的执行顺序随机化/交错，且两者使用同一 cache-state
   controller；
8. 不与 `warm` 或 `file-content-nonresident-metadata-warm` 共享回归阈值。

当前 Docker Desktop/WSL2 环境不满足第 1、3、5 项，不应请求 privileged
container 来绕过这些门禁。

## 复现

```powershell
python tools\benchmark\probe_upstream_benchmark_cache_environment.py `
  --output docs\research\data\upstream-benchmark-linux-qt5-cache-environment.json
```

probe 固定 image、resource limits、cpuset、page-cache evidence 与 observer
SHA-256；在两个独立断网容器中执行只读观察，要求结果完全相同。observer 只尝试
打开 `drop_caches` 的 write endpoint 来记录权限错误，不调用 `write`，也不执行
任何 cache-changing syscall。

## 尚未完成

- 对 cache-state taxonomy 的 ADR 评审；
- dedicated VM/裸机的 `system-cold` 实验；
- macOS 的等价或明确不可等价 cache-state contract；Windows 已由
  [`windows-benchmark-cache-state.md`](windows-benchmark-cache-state.md)
  固定为 warm 可复用、第二层 unsupported、system-cold 待 dedicated
  infrastructure；
- Rust/upstream 成对、长期 session、physical-core/topology 与评审阈值。
