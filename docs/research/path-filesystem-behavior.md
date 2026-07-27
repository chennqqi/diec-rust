# Linux symlink、权限与目录深度行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 qmake/CMake 两个 Oracle 对 9 个 case、共 18 次执行给出
逐字节一致结果：

- 显式文件 symlink 与目录 symlink 都被跟随，输出与直接扫描目标 PDF 逐字节相同；
- 枚举同时含真实文件/目录及其 symlink 的目录时，两个目标各被扫描两次，不做
  inode/canonical-path 去重；
- dangling symlink 被当作不存在，向 stdout 写 `Cannot find:`、exit `1`，
  stderr 为空；
- mode 000 目录由 root 扫描时到达 PDF；由 `nobody` 扫描时静默返回 exit `0`、
  空 stdout/stderr，不产生权限诊断；
- 64 层、最终路径 672 bytes 的目录链到达 leaf PDF，输出与直接扫描逐字节相同；
- 自循环 `loop -> .` 没有 visited-set。固定 Linux 的 symlink resolution 上限
  使递归在 40 层停止，随后按深度 40→0 扫描同一个 `root.pdf` 共 41 次，
  exit `0`、stderr 为空；终止来自当前 OS 路径解析边界，不是 engine 安全预算。

机器报告：
[`path-filesystem-engine-qt5.json`](data/path-filesystem-engine-qt5.json)，SHA-256
为 `97549da236a57cc5502b43a8157f81865fa6d9a0ab626035ebcf63df97792dbb`。
报告保存所有原始 stdout/stderr，并以 SHA-256、`zlib+base64` content-addressed
artifact 去重。

这批证据闭合 `CAP-GAP-003` 的 Linux Qt5 首轮 symlink、permission 与 depth
子矩阵，但不关闭整个 gap。超大目录、取消/预算、locale/filesystem 排序以及
Windows junction/reparse point、macOS alias/normalization 仍缺。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| qmake image | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| CMake image | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| fixture TAR | `c5b2e170e7032afd1e6297c7a9f501ec395f72cae2718a3fbbf91340c704037b` |
| fixture manifest | `a763d4a3270f299f0bfb983cc5a204a4e0fd4247b74fabe247756d5bd962dedb` |
| `Formats/xbinary.cpp` | `d82bd21326bb7ba07eb343020d50af0ae2cf7e8e534d8e08d07ffa8129913c34` |

报告绑定两个原始 `diec` binary 的 size/SHA-256、两个 image ID/revision、本地
fixture/baseline generator，以及固定 `xbinary.cpp` 的完整字节。源码契约要求：

1. 目录使用无参数 `QDir::entryInfoList()`；
2. 每个 entry 的 absolute path 直接递归传给 `findFiles()`；
3. 该 overload 没有 visited set、depth 参数或 symlink policy。

具体 follow/filter/重复次数以本轮运行结果为准，不能只从缺少关键词推断。

## 确定性文件系统 fixture

[`generate_path_filesystem_fixture.py`](../../tools/corpus/generate_path_filesystem_fixture.py)
生成 112,640-byte deterministic GNU tar。之所以使用 GNU longname extension，
是 64 层 leaf path 超过 USTAR 的 255-byte 上限。所有 metadata 固定：

- uid/gid/mtime 均为 0；
- directory/file/symlink mode 明确；
- 普通文件全部复用项目生成的 331-byte 最小 PDF；
- 不提交 TAR，只提交
  [`path-filesystem-fixture.json`](data/path-filesystem-fixture.json)。

79 个 manifest entry 包含：

```text
paths/symlink/
├── target.pdf
├── file-link.pdf -> target.pdf
├── dir-target/child.pdf
├── dir-link -> dir-target
└── dangling.pdf -> missing.pdf
paths/cycle/
├── root.pdf
└── loop -> .
paths/denied/                 mode 000
└── secret.pdf
paths/deep/
└── level-000/.../level-063/leaf.pdf
```

独立测试通过 Python `tarfile` 复验 member 顺序、type、mode、link target、64 层
和所有 payload hash。Oracle probe 在运行前又于 container 内使用 `lstat()`、
`readlink()` 与 path component 计数复验实际展开状态，避免把 TAR metadata
误当成已物化文件系统事实。

## 结果矩阵

| Case | User | Exit | PDF roots | 关键行为 |
| --- | --- | ---: | ---: | --- |
| direct control | root | 0 | 1 | 普通 PDF |
| file symlink | root | 0 | 1 | 跟随到 target |
| directory symlink | root | 0 | 1 | 跟随并枚举 child |
| symlink tree | root | 0 | 4 | file/dir target 各重复一次 |
| dangling symlink | root | 1 | 0 | stdout `Cannot find:` |
| deep 64 | root | 0 | 1 | 到达 leaf |
| denied directory | root | 0 | 1 | root 可读取 |
| denied directory | nobody | 0 | 0 | 静默空结果 |
| self cycle | root | 0 | 41 | depth 40→0 重复扫描 |

除 symlink tree/self-cycle 多目标外，成功 PDF case 的 stdout SHA-256 都是固定单
PDF 基线 `5a475aa450326d3096db01352fe524bbda579173a645f0f502a74bba27a32e35`。
非特权 denied case 的 stdout/stderr 均为空内容哈希。

### Symlink tree 顺序

四个 prefix 的精确顺序是：

```text
/work/paths/symlink/dir-link/child.pdf
/work/paths/symlink/dir-target/child.pdf
/work/paths/symlink/file-link.pdf
/work/paths/symlink/target.pdf
```

stdout SHA-256：
`79d30fa46318c587e501b67afea27364710cae5ac10f09dd1b4eda33c5792617`。
输出使用 symlink 路径本身，不 canonicalize 成 target path。

### Self-cycle

`loop -> .` 的 prefix 序列含 41 项。第一项含 40 个 `/loop` component，之后每项
减少一个，最后是 `/work/paths/cycle/root.pdf`。stdout SHA-256：
`66f7fb7535dcdd248ff2ee053bcd528a009c277f598044540e3c86506b0b8bf6`。

这是 Linux 运行结果；“40”与内核/VFS symlink resolution 限制一致，是从运行
序列与无 visited-set 源码作出的解释。Rust 实现不得把 41 当作可移植或安全的
产品上限。

## 受限执行

每个 case 使用全新 container：

```text
network=none
cpus=1
memory=512 MiB
pids=128
root filesystem=read-only
fixture mount=read-only
work tmpfs=64 MiB
core size=0
normal in-container timeout=30 seconds
self-cycle in-container timeout=10 seconds
host safety timeout=in-container timeout + 20 seconds
```

mode 000 case 先由 root 展开 TAR，再用 `runuser -u nobody` 启动同一固定 binary。
self-cycle 实际约 0.6 秒完成，未触发 timeout；报告仍保存 timeout 和 core
限制，防止上游/环境变化造成无界运行或 core artifact。

复现：

```powershell
$baseline = Join-Path $env:TEMP diec-path-fs-baseline
$fixture = Join-Path $env:TEMP diec-path-fs-fixture
$report = Join-Path $env:TEMP path-filesystem-engine-qt5.json

python tools\corpus\generate_baseline_corpus.py $baseline
python tools\corpus\generate_path_filesystem_fixture.py `
  $baseline $fixture
python tools\upstream\probe_path_filesystem_behavior.py `
  --fixture-dir $fixture `
  --output $report
```

## 兼容与安全要求

- legacy-compatible 路径必须保留 follow、symlink-path prefix、重复顺序和
  dangling/permission 的可观察结果；canonical profile 不应继承这些缺陷。
- `TargetExpander` 默认不得跟随 directory symlink，且必须使用 stable file
  identity/visited set 识别 cycle，而不是等待 OS 的 symlink 上限。
- depth、entry count、total path bytes、wall time 与 cancellation 都必须有共享
  budget；达到限制时返回明确 partial/limit diagnostic，不能静默截断。
- 权限错误必须与合法 empty directory 区分。上游两者都返回 exit 0/空输出，
  canonical API 必须提供类型化 I/O diagnostic。
- symlink target 与扫描时打开之间存在 TOCTOU；Rust 应使用受控 open/metadata
  策略，并在测试中覆盖 target swap。
- 安全偏离需由 ADR/compatibility profile 明确，不得把“比上游更安全”写成逐字
  兼容。

## 剩余缺口

- 大目录 entry/count/time/memory 边界与 cooperative cancellation；
- symlink target 在枚举/打开之间变化的 TOCTOU；
- locale 改变、case/normalization 不同的 filesystem 排序；
- Windows symlink/junction/reparse point、reserved path 与权限语义；
- macOS symlink、case-sensitive/case-insensitive volume 与 normalization；
- Linux Qt6 完整平台基线。

因此 `CAP-GAP-003`、`CAP-GAP-007` 与 `CAP-GAP-008` 仍保持开放；本页只闭合固定
Linux Qt5 的具名子矩阵。
