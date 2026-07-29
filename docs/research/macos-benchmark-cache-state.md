# macOS benchmark 缓存态策略与预执行计划

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 结论

macOS 当前只允许复用 `warm`。Apple 的公开契约提供了一个可在 Darwin 上验证的
第二层 runtime candidate，但本机不是 Darwin，尚无运行报告，因此
`file-content-nonresident-metadata-warm` 和 `system-cold` 都未获准：

- `F_NOCACHE` 只切换当前 fd 的 data-caching 策略；`F_GLOBAL_NOCACHE` 切换
  vnode 对应文件的全局 caching 策略。固定 XNU 实现只设置/清除 flag，没有
  eviction 或 residency 后验，不能单独证明候选页 nonresident；
- `madvise(MADV_DONTNEED)` 只声明近期不准备访问，是 advice，不是驱逐完成证明；
- `msync(MS_INVALIDATE)` 的公开手册语义是使映射范围 cached data invalid；
  `mincore` 可以逐页返回当前 in-core residency。因此
  “完整 warm → `MS_SYNC|MS_INVALIDATE` → 每页 `mincore=0`”是值得运行验证的
  per-file candidate；
- 该 candidate 即使在临时文件上成功，也不能自动升级为 benchmark 状态。仍需
  对 2,283-file 固定闭包逐路径验证、接入 runner/controller、证明不改变上游
  输出，并完成成对测量；
- 未找到并评审能够由普通进程证明 file data、dentry/inode metadata 和整机
  cache 全部 cold 的公开契约。macOS `system-cold` 因此只接受 disposable
  dedicated host 的 reboot boundary，当前仍未建立。

机器计划为
[`data/macos-benchmark-cache-state-plan.json`](data/macos-benchmark-cache-state-plan.json)，
SHA-256 为
`df1f42ceea6d59c5885d33fabbc2760b4d5a003f7308dd3b8bd33459341c458f`。
计划状态是 `infrastructure_ready_runtime_missing`；它不是 macOS runtime
observation，也没有提升任何性能 baseline。

## 固定 Apple/Darwin 契约

### XNU 源码

本调研固定 Apple 官方
[`apple-oss-distributions/xnu`](https://github.com/apple-oss-distributions/xnu)
commit `f6217f891ac0bb64f3d375211650a4c1ff8ca1ea`：

| 文件 | SHA-256 | 相关事实 |
| --- | --- | --- |
| [`bsd/sys/fcntl.h`](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/sys/fcntl.h#L301-L308) | `0f93c8918a70ffafe20bfe9c72e671fde67438cbee9f9de8c2f87b5c704c9a9e` | `F_NOCACHE` 是 “for this fd”；`F_GLOBAL_NOCACHE` 是 “globally for this file” |
| [`bsd/kern/kern_descrip.c`](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/kern_descrip.c#L3600-L3662) | `480cfed4e987be874bd71fb6933c254adf9fb1f36de8496dee8f351b18da13b1` | 前者切换 fileglob `FNOCACHE`，后者切换 vnode nocache；两个 case 都没有 eviction/residency 调用 |

XNU main 会继续变化，因此计划绑定 exact commit 与两个完整文件 hash，不以
“最新版源码”作为证据。实际 Darwin 运行还必须记录 macOS product/build、
Darwin release、Apple clang 和临时卷 filesystem；公开 XNU commit 不能替代
运行内核身份。

### Apple 手册

- [`fcntl(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fcntl.2.html)
  将 `F_NOCACHE` 定义为关闭/开启 data caching；
- [`mincore(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/mincore.2.html)
  返回映射页当前是否 core resident；
- [`msync(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/msync.2.html)
  将 `MS_INVALIDATE` 定义为 invalidate cached data；
- [`madvise(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/madvise.2.html)
  将 `MADV_DONTNEED` 定义为应用预计近期不访问该范围。

这些页面位于 Apple archive，因此 runtime collector 必须用当前 SDK 编译固定
C probe，并记录实际系统身份。手册支持候选实验的接口语义，不证明具体 APFS/
macOS build 上执行后必然得到零 resident pages。

## 三层 taxonomy 的 macOS 映射

| ADR 0015 状态 | 当前状态 | 证据/下一门禁 |
| --- | --- | --- |
| `warm` | `portable_name_allowed` | 固定 warmup、输入、命令和输出，不执行 eviction |
| `file-content-nonresident-metadata-warm` | `runtime_candidate_not_admitted` | 双轮临时文件实验成功后，再对固定 benchmark closure 建立逐路径 controller |
| `system-cold` | `dedicated_reboot_only_not_admitted` | disposable dedicated host、reboot identity、无关负载隔离和操作后证据 |
| `cold` | `forbidden` | 无例外 |

明确拒绝以下替代：

- 只看 `F_NOCACHE`/`F_GLOBAL_NOCACHE` 返回成功；
- 只调用 `MADV_DONTNEED` 而没有 `mincore` 后验；
- 只证明一个映射或总页数，而不验证每个 fixed closure path；
- 运行 `purge` 命令后直接标记 system-cold；
- 把临时 fixture capability 当成 DIE-engine performance baseline。

## Darwin 候选实验

[`probe_macos_file_content_cache.c`](../../tools/benchmark/probe_macos_file_content_cache.c)
只操作一个 16 MiB deterministic regular-file fixture：

1. 在 collector 创建的临时目录中 `mkstemp`，立即 unlink；
2. 写满并 `fsync`，以 `MAP_SHARED` 映射后逐页 touch；
3. 用 `mincore` 要求全部页 resident；
4. 切换 fd-local `F_NOCACHE`，立即记录 residency，再恢复；
5. 调用 `msync(MS_SYNC|MS_INVALIDATE)`，再次记录逐页 residency；
6. 释放映射并关闭已 unlink 的 fixture。

probe 不接触 benchmark binary、rules、corpus 或 manifest，不执行 `purge`、
reboot、sudo 或任何 system-wide cache flush。collector 用固定
`-std=c11 -O2 -Wall -Wextra -Werror` 编译，每次创建独立 fixture，连续执行两
轮并要求结构化 observation 完全相同。

候选报告 validator 接受两种诚实结果：

- 两轮 `after_msync_invalidate_resident_pages=0`：只把它标成 Linux 第二层的
  semantic candidate，仍保持 `cache_state_admitted=false`；
- 任一轮非零：候选不等价，必须保持 unsupported，不得用重试筛选出“成功”结果。

任何 duplicate JSON key、non-finite value、页几何漂移、fixture 未完全 warm、
两轮差异、触碰 benchmark file、system flush 或 admission=true 都 fail closed。

## 在 macOS x86_64 上执行

将输出写到仓库外部证据目录：

```text
python3 tools/benchmark/collect_macos_cache_state_candidate.py \
  --output /private/tmp/diec-macos-cache-state-candidate.json

python3 tools/benchmark/validate_macos_cache_state_candidate.py \
  /private/tmp/diec-macos-cache-state-candidate.json
```

运行前还应先执行已固定的 macOS Qt5 oracle bootstrap，并让两份报告记录同一
host/toolchain identity。候选报告通过评审和去路径审计后，才能决定是否提交
sanitized runtime evidence。

## 本机可执行验证

```powershell
python tools\research\build_macos_cache_state_plan.py --check
python -m unittest discover -s tools\tests `
  -p "test_macos_benchmark_cache_state.py"
```

当前 Windows 主机只能验证生成器、hash、parser、validator 和 fail-closed
边界，不能编译运行 Darwin C probe。

## 尚未完成

- 在固定 Darwin x86_64/APFS 主机生成双轮候选报告；
- 若 candidate 成立，将同一控制器接入 2,283-file closure 与通用 runner；
- 若 candidate 不成立，固定 unsupported 运行证据并调查不改变被测 I/O 语义的
  其他公开接口；
- dedicated reboot 型 macOS system-cold infrastructure；
- Rust/upstream 成对、长期 session、physical-core/topology 与阈值评审。
