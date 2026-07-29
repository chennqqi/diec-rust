# Windows benchmark 缓存态能力边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 结论

原生 Windows 可以继续复用 `warm` 名称，但当前没有证据允许把 Linux 的
`file-content-nonresident-metadata-warm` 原名移植到 Windows，也没有建立
`system-cold`：

- `SetSystemFileCacheSize(-1, -1, 0)` 是 system file cache 的全局 flush，
  调用进程必须启用 `SeIncreaseQuotaPrivilege`；本机普通 token 不持有也未启用
  该 privilege；
- `FILE_FLAG_NO_BUFFERING` 改变的是打开该 handle 时的 I/O 路径和对齐契约，
  不能替另一个保持默认打开方式的 `diec.exe` 逐文件驱逐缓存，更没有提供
  “命令前所有候选页 nonresident”的观测；
- `FlushFileBuffers` 把缓冲数据写向设备，语义不是驱逐 clean read cache；
- `EmptyWorkingSet` 只从指定进程 working set 尽可能移除页面，不是 system
  file cache controller；
- API 存在不等于状态等价。没有 per-file eviction + residency 后验时，不得用
  Linux 第二层名称；没有 dedicated machine、全局授权和操作后证据时，不得用
  `system-cold`。

因此 ADR 0015 的 Windows 策略是：`warm` 可跨平台；第二层暂记
`unsupported`，而不是用 `NO_BUFFERING` 冒充；system-cold 只能在 disposable
dedicated Windows VM/裸机上另建特权 controller 并评审。通用 `cold` 仍永久
禁止。

机器报告为
[`data/upstream-benchmark-windows-cache-environment.json`](data/upstream-benchmark-windows-cache-environment.json)，
SHA-256 为
`bc58d9de0ee32e7aa55dd8f2bea7436ee8fdb6e2626eda83e9c41c2fc01abce7`。
同一只读 observer 连续运行两次，原始 JSON 逐字节相同。

## 官方 API 契约

结论固定到 Microsoft Learn 的公开 Win32 契约：

- [`GetSystemFileCacheSize`](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-getsystemfilecachesize)
  读取 system cache working-set 的当前最小/最大限制及 hard-limit flags；
- [`SetSystemFileCacheSize`](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-setsystemfilecachesize)
  改变 system file cache working set，`-1/-1` 表示 flush，调用方必须启用
  `SE_INCREASE_QUOTA_NAME`；
- [File buffering](https://learn.microsoft.com/en-us/windows/win32/fileio/file-buffering)
  将 `FILE_FLAG_NO_BUFFERING` 定义为该 handle 的 uncached I/O，并要求访问长度、
  offset 和 buffer 满足 sector alignment；
- [`FlushFileBuffers`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
  将指定 handle 的 buffered information 写向文件或设备；
- [Working Set Information](https://learn.microsoft.com/en-us/windows/win32/psapi/working-set-information)
  明确 `EmptyWorkingSet` 的对象是指定 process working set。

这些文档支持“接口各自控制什么”的结论，但没有公开承诺把任意文件的所有
Cache Manager 页面逐路径驱逐后再提供等价于 Linux `mincore` 的 residency
证明。因此报告把未证明的等价关系固定为 `false`，而不是从 API 名称推断成功。

## 固定只读观察

| 字段 | 观察值 |
| --- | --- |
| OS | Windows build 26100，AMD64，64-bit |
| logical processors | 22 |
| page/allocation granularity | 4,096 / 65,536 bytes |
| target filesystem | NTFS，fixed volume |
| filesystem geometry | 512-byte sector，8 sectors/cluster |
| system cache hard limits | min/max 均未启用，flags `0` |
| process elevation | limited、not elevated |
| `SeIncreaseQuotaPrivilege` | token 中不存在，未启用 |
| relevant API exports | 四项均存在 |
| cache-changing call | none |

报告不保存 drive letter、absolute path、volume serial 或 machine name。读取
`GetSystemFileCacheSize` 只观察限制；observer 没有调用
`SetSystemFileCacheSize`、`EmptyWorkingSet`、`FlushFileBuffers`，也没有打开
`FILE_FLAG_NO_BUFFERING` handle 或启动 benchmark。

## 与三层 taxonomy 的映射

| ADR 0015 状态 | Windows 当前结论 | 进入测量前的门禁 |
| --- | --- | --- |
| `warm` | 可复用 | 固定 warmup、命令、输入和输出；不执行 eviction |
| `file-content-nonresident-metadata-warm` | 不可复用 | 需找到不改变被测 handle 语义的 per-file eviction，并逐文件证明 pre-run nonresident |
| `system-cold` | 尚未建立 | disposable dedicated host、明确特权授权、全局 flush/reboot controller、隔离及操作后证据 |
| `cold` | 禁止 | 无例外 |

Windows 与 Linux 可以比较各自的 warm baseline。其他状态只有在 controller
语义和证据等价时才能共享阈值；否则必须使用平台限定名称和独立阈值。

## 复现

```powershell
python tools\benchmark\probe_windows_benchmark_cache_environment.py `
  --output docs\research\data\upstream-benchmark-windows-cache-environment.json
```

probe 固定 generator/observer SHA-256，连续启动两个 native Windows observer，
要求输出逐字节相同。任何 API 查询失败、token 数据异常、重复 JSON key、
non-finite JSON 或 scope 发生变化都 fail closed。

## 尚未完成

- dedicated Windows VM/裸机的 system-cold authority、isolation、controller 与
  post-state 实验；
- Windows 第二层是否存在可审计的 per-file eviction/residency 组合；在找到前
  保持 unsupported；
- macOS 已固定的 `MS_INVALIDATE` + `mincore` candidate 的 Darwin runtime；
- Rust/upstream 成对、跨 reboot/日期长期 session、physical-core/topology 和
  评审阈值。
