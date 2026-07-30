# macOS root、ACL 与 ownership 路径候选

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 结论

本轮只建立 macOS x86_64/Qt 5 上游 CLI 的 root、ACL 与 ownership
候选采集基础设施，尚未在 Darwin runner 上执行，也不接纳任何 capability row。

候选由
[`collect_macos_cli_privilege_paths.py`](../../tools/upstream/collect_macos_cli_privilege_paths.py)
采集，并由
[`validate_macos_cli_privilege_paths.py`](../../tools/upstream/validate_macos_cli_privilege_paths.py)
从原始 stdout/stderr 重算。矩阵包含 6 个临时目标、runner/root 两种执行身份，
每项连续两轮，共 12 个 case、24 次 CLI 执行和 48 个 raw stream。

这关闭的是“缺少可执行候选基础设施”，不是“已经观察到 macOS 行为”。
`platform_admitted=false`、`capability_rows_admitted=0` 保持不变。

## Darwin ACL 契约

Apple 官方 `file_cmds` 的固定
[`chmod(1)` 源文件](https://github.com/apple-oss-distributions/file_cmds/blob/659a8a301e2acf0343f8b8673a154a2ca4d07084/chmod/chmod.1)
说明：

- `chmod +a ACE path` 添加 ACL entry，`chmod -N path` 移除 ACL；
- ACL entry 可用 `user:`/`group:` 明确身份类型；
- 普通文件的 `read` 表示打开读取；
- 目录的 `list` 与 `search` 分别表示列举和按名称查找；
- `readattr`、`readextattr`、`readsecurity` 是独立权限。

Apple 的
[`Shell Scripting Primer`](https://developer.apple.com/library/archive/documentation/OpenSource/Conceptual/ShellScripting/ForMoreInformation/ForMoreInformation.html)
也明确把 `chmod` 定义为同时修改 mode bits 和 ACL 的文件工具。

候选因此使用两条显式 deny ACE：

```text
user:<runner> deny read
user:<runner> deny list,search
```

collector 不把 Linux POSIX mode 结论投影成 Darwin ACL 结论，也不预设 uid 0
是否绕过 deny ACE；root 与 runner 的 detection tree/summary 关系由 raw stream
重算后原样保存。ACE 刻意不拒绝 `readattr`/`readsecurity`，使非 root
collector 仍能在每轮执行前保存 stat 与 ACL listing；这不是扩大扫描权限，
而是把“数据读取/目录查找”和“证据元数据读取”分开观察。

## Fixture 与矩阵

payload 固定为
[`baseline-corpus.json`](data/baseline-corpus.json) 中的 `minimal.pdf`：
331 bytes，SHA-256
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。

| 目标 | owner | mode | ACL | runner/root 观察 |
| --- | --- | --- | --- | --- |
| `owner_public_file` | runner | `0644` | 无 | 普通 owner 控制 |
| `root_public_file` | root | `0644` | 无 | ownership 与可读控制 |
| `root_private_file` | root | `0600` | 无 | ownership + mode denial |
| `mode_000_file` | runner | `0000` | 无 | mode denial 与 root 对照 |
| `acl_deny_read_file` | runner | `0644` | deny read | 文件 ACL |
| `acl_deny_search_directory` | runner | `0755` | deny list/search | 目录发现 ACL |

每次 CLI 执行前重新保存目标的 uid、gid、mode、size、`ls -lde` ACL listing；
first/second snapshot 必须与 fixture 顶层 snapshot 相同。validator 从 raw stream
重新计算：

- exit code、timeout 与 determinism；
- `Cannot find`、filename prefix 和 PDF root 计数；
- detection tree 与固定 minimal-PDF baseline 的关系；
- 每个目标的 runner/root detection tree 和 summary 是否相同。

ACL 两项只记录观察，不属于预期 reference control。普通公开目标、root 对
root-owned private/mode-000 的 reference 关系作为显式检查保留；即便失败，
candidate 也会记录精确 failure，不会由 normalizer 隐藏。

## 权限提升与清理边界

collector 必须由非 root 用户启动，并在任何 fixture mutation 前执行：

```text
/usr/bin/sudo -n -- /usr/bin/id -u
```

只有返回 uid 0 才继续。所有外部命令均使用 argv 调用，不经过 shell。`chown`
只对两个已解析的单文件路径执行；ACL add/remove 也只对两个已解析目标执行。
fixture 必须是已存在 parent 的一个全新直接子目录，不允许复用已有目录或文件系统
根。

runner 与 root 进程分别使用 `<fixture>/.runtime/{runner,root}-{home,tmp}`。
root 路径由 hash-bound
[`exec_macos_privilege_root.py`](../../tools/upstream/exec_macos_privilege_root.py)
包装：`sudo -n` 以 isolated Python (`-I -S`) 启动 helper，helper 在 uid 0
进程内固定 `HOME`、`TMPDIR`、Qt `PATH` 和 `umask(0000)`，随后 `execve`
上游二进制。这不依赖 sudoers 是否保留环境或重设 umask。整个 fixture 根仍是
runner-owned `0700`。报告保存 `.runtime/` 下全部对象的相对路径、类型、
uid/gid、mode 和 size；validator 拒绝绝对路径、`..`、重复/乱序或未知 owner。

不能把 `HOME` 隔离夸大为 Qt AppData 隔离。固定 Qt
`qtbase@40143c189b7c1bf3c2058b77d00ea5c4e3be8b28` 的
`src/corelib/io/qstandardpaths_mac.mm` 通过
`NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory,
NSUserDomainMask, ...)` 解析 AppDataLocation。固定 CLI 的
[`main_console.cpp`](../../upstream/DIE-engine/console_source/main_console.cpp)
把 `SCAN_OPTIONS` 零初始化，所以 `bUseCache=false`；但固定
`horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83` 的
`XScanEngine::loadDatabase` 在目录数据库分支仍可能删除已有 stale cache。

因此本候选不把三个规则目录直接传给 root CLI。collector 先在
`<fixture>/.database/` 生成三个确定性 `ZIP_STORED` 归档：成员按 POSIX 路径
排序、时间固定为 1980-01-01、mode 固定为 `0100644`，并在报告中保存成员数、
字节数和 SHA-256。固定 XScanEngine 的 file/ZIP database 分支不进入目录缓存
逻辑，从代码路径上排除这项外部 cache 读写；`HOME`/`TMPDIR` helper 只作为
其他常规用户态写入的附加隔离，不作为 macOS AppData 重定向证明。

清理顺序为：

1. 对两个 ACL 目标逐个执行 `/bin/chmod -N`；
2. 恢复 mode-000 文件的 owner write/read；
3. 用当前进程删除 collector-owned fixture。

不使用递归 `sudo chown`、递归 `chmod` 或 shell glob。报告必须保存
`fixture_removed=true` 及 ACL cleanup command records；清理失败即采集失败。

## Hash-bound workflow

手动 workflow
[`macos-qt5-oracle-candidate.yml`](../../.github/workflows/macos-qt5-oracle-candidate.yml)
在 `macos-15-intel` 上从 runner temp 创建独立 fixture，运行 collector/validator，
并上传：

- `cli-privilege-path-candidate.json`；
- `raw/cli-privilege-path/` 下 48 个 stdout/stderr；
- 汇总 `SHA256SUMS`。

机器计划
[`macos-qt5-oracle-plan.json`](data/macos-qt5-oracle-plan.json)
绑定 workflow、collector 和 validator 的 SHA-256。加入本矩阵后：

- CLI：2,132 次执行、4,264 个 raw stream；
- database-cache engine：2 次执行、4 个 raw stream；
- runtime 合计：2,134 次执行、4,268 个 raw stream；
- 两份 database-cache build log 继续单列，不计入 runtime。

## 合成回放

[`test_macos_cli_privilege_path_candidate.py`](../../tools/tests/test_macos_cli_privilege_path_candidate.py)
构造完整 synthetic bundle，验证 12 个 case/48 个 raw stream 可重放，并确认
validator 拒绝：

- raw stream 内容或 inventory 漂移；
- 确定性 ZIP database 身份漂移；
- fixture mode/ownership/ACL snapshot 漂移；
- runner/root relationship 漂移；
- admission 漂移。

合成回放只证明报告契约和 fail-closed validator，不是 Darwin runtime evidence。

## 尚未证明

- 尚未在固定 macOS x86_64 runner 上运行，所有 12 个 case 的真实结果未知；
- 尚未固定 runner APFS volume 的 ACL capability、实际用户/组和 sudo policy；
- 未覆盖 inherited ACL、group ACL、多用户、immutable flags、sandbox/TCC/SIP、
  network volume 或 ACL 与 symlink 的组合；
- 其余 engine-only 权限矩阵仍缺；
- 未经 Darwin artifact 审查和 68 行 closure 更新，不得改变 macOS
  `platform-missing` 状态。
