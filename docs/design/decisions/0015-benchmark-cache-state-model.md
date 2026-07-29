# ADR 0015：显式区分 benchmark 的 warm、file-content 与 system-cold 状态

Status: Proposed

Last updated: 2026-07-29

## Context

process benchmark runner v1 只接受 `cache_state="warm"`，并显式拒绝含混的
`cold`。后续 Phase 0 调研已经固定五个 case 的 successful regular-file closure，
又用完全静态 controller 证明这些候选文件在每次命令前可以逐路径达到
`mincore=0`。

这个结果没有控制 pathname lookup、negative dentry、directory/inode cache 或
整个 Linux kernel 的 cache。固定 Docker Desktop/WSL2 环境根文件系统是
overlayfs，`/proc/sys` 只读，容器没有 `CAP_SYS_ADMIN`；Linux 没有 page-cache
namespace，Docker overlay2 还可能在容器间共享同一文件的 page-cache entry。

因此仅使用 `warm`/`cold` 二元标签会把三种不同实验错误地混为一谈：

1. 进程和文件内容都已预热；
2. 指定文件内容页 nonresident，但 metadata/path lookup 已预热；
3. dedicated system 的 page cache 与 reclaimable dentry/inode slab 都被控制。

证据见
[`upstream-benchmark-file-access.md`](../../research/upstream-benchmark-file-access.md)、
[`upstream-benchmark-page-cache.md`](../../research/upstream-benchmark-page-cache.md)
和
[`upstream-benchmark-cache-environment.md`](../../research/upstream-benchmark-cache-environment.md)。

## Decision

benchmark cache-state vocabulary 固定为三个互斥值：

- `warm`
  - 由 plan 声明 warmup 数量和顺序；
  - measured runs 不执行 eviction；
  - 继续作为 runner v1 唯一可执行状态。
- `file-content-nonresident-metadata-warm`
  - manifest 必须绑定 exact successful-file closure；
  - 每个 measured command 前完整 warm candidate，执行 per-file advisory
    eviction，再逐文件证明所有目标页 nonresident；
  - pathname/dentry/inode/failed lookup 明确视为 warm 或 uncontrolled；
  - controller/observation 失败必须终止，不能退化为 `warm`；
  - 未接入 runner 前，Phase 0 page-cache probe 只作为 controller 技术证据，
    不保留 timing/RSS。
- `system-cold`
  - 只允许 disposable、dedicated VM 或裸机；
  - 必须固定 kernel/filesystem/device/mount/machine identity，获得明确的
    root/cache-drop 授权，并证明无无关工作负载；
  - 每次 measured run 前执行经评审的 sync/drop/reboot controller，并记录
    page 与 dentry/inode 的前后证据；
  - upstream 与 Rust 必须共用同一 controller 并随机化或交错顺序。

通用字符串 `cold` 永久禁止。三种状态拥有独立 baseline、trend 和 threshold；
不能把一个状态的结果用于另一个状态的回归结论。

runner 的 future schema 增加非 warm 状态时，必须同时增加结构化
`cache_controller` identity/evidence，而不是只放一个字符串。至少包含：

- controller implementation、source/binary SHA-256；
- target platform/kernel/filesystem；
- candidate manifest 或 system controller identity；
- before/after observations；
- authority/isolation declaration；
- controller failure 与 timeout。

Windows/macOS 只有在语义和证据等价时才能复用同名状态；否则使用平台限定的
新状态并禁止跨状态阈值比较。

## Alternatives considered

### 把 fadvise/mincore 结果称为 cold

优点是标签短。缺点是已知 metadata/path lookup 为 warm，且 overlayfs/host
isolation 未证明；标签会支持错误的跨实验比较。

结论：拒绝。

### 在当前容器增加 `--privileged` 并写 `drop_caches`

privilege 不会创建 page-cache namespace。操作会影响 Docker Desktop WSL2 VM
kernel 的共享 cache，可能干扰其他容器/任务，也不提供 dedicated-host 证明。

结论：拒绝。

### 只保留 warm，不建立第二层

最简单，但丢弃已经可重复验证的 file-content eviction 能力，也无法区分 database
load 对内容 I/O 的敏感性。

结论：拒绝；保留 warm，同时增加精确命名的第二层。

### 用内存压力替代明确 eviction

结果依赖 kernel reclaim、cgroup accounting 和并发负载，不能证明指定路径在命令
前 nonresident，也难以跨 session 复现。

结论：拒绝。

## Consequences

正面：

- cache state 成为可审计实验条件，不再是口头的“冷/热”；
- 当前 Docker 环境可以安全测量 file-content 层，无需 host-global mutation；
- future system-cold 有明确授权、隔离和后验门禁；
- upstream/Rust 不会因使用不同 cache controller 产生虚假性能结论。

代价：

- runner schema 与 controller orchestration 更复杂；
- file-content 和 system-cold 必须维护独立报告与阈值；
- system-cold 需要 dedicated infrastructure，不能在普通共享 CI runner 上执行；
- 其他平台可能无法提供语义完全相同的状态。

## Security boundary

- 当前仓库工具不得自动启动 privileged container、添加 `CAP_SYS_ADMIN` 或写
  `/proc/sys/vm/drop_caches`。
- system-global cache mutation 必须有针对 exact dedicated environment 的显式
  用户/运维授权。
- controller 输入、manifest 和输出仍视为不可信；解析必须有界、拒绝重复字段和
  非有限值。
- cache controller 不授权更改 benchmark binary、rules、corpus 或输出规范化。

## Evidence

- [`upstream-benchmark-linux-qt5-file-access.json`](../../research/data/upstream-benchmark-linux-qt5-file-access.json)
- [`upstream-benchmark-linux-qt5-page-cache.json`](../../research/data/upstream-benchmark-linux-qt5-page-cache.json)
- [`upstream-benchmark-linux-qt5-cache-environment.json`](../../research/data/upstream-benchmark-linux-qt5-cache-environment.json)
- Linux kernel `drop_caches`、Linux man-pages namespaces/fadvise 与 Docker
  overlay2 page-cache 官方文档，链接见调研正文。

## Acceptance conditions

- cache-environment 报告在两个独立容器中逐字节重复；
- runner 继续拒绝通用 `cold`；
- future file-content plan 必须逐 measured run 绑定 manifest、controller 和
  before-run 0-resident 证明；
- future system-cold job 必须验证 dedicated authority/isolation；
- testing design、风险和 Phase 0 gate 使用相同 taxonomy；
- Windows/macOS 策略完成明确评审；
- 本 ADR 获得 Accepted/Rejected/Superseded 评审结论。
