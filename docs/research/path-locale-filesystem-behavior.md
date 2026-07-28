# Linux locale 与文件系统目录顺序

Status: Draft
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 qmake/CMake 双 Oracle 的目录排序：

- `C`、`C.utf8`、`POSIX` 是两个固定镜像内 `locale -a` 的完整清单；同一文件
  系统上三者 stdout 逐字节相同，尽管 charmap 分别为
  `ANSI_X3.4-1968`、`UTF-8`、`ANSI_X3.4-1968`；
- tmpfs 与匿名 Docker volume 是两个实际不同的 mount profile，`stat -f -c %T`
  分别返回 `tmpfs` 和 `ext2/ext3`；
- 文件系统会改变大小写 tie 的顺序：tmpfs 为 `a-case.empty`、
  `A-case.empty`，volume 为 `A-case.empty`、`a-case.empty`；
- 两个 profile 的其余 15 个可见名称顺序相同；reverse-manifest 创建顺序没有
  成为输出顺序；
- 1 个 hidden 名称和 3 个非法 UTF-8 basename 在 6 个环境单元、两个 Oracle
  共 12 次执行中都被静默过滤；
- 每个环境单元的 qmake/CMake exit code、stdout、stderr 均逐字节相同，退出码
  为 `0`，stderr 为空。

因此，发布 CLI 的 Linux Qt5 目录顺序不能只由 Unicode 字符串比较推导，也不能
把一个文件系统上的 golden 外推到另一个文件系统。`CAP-GAP-003` 在固定上游
环境中的最后一个 locale/filesystem 子矩阵由本页闭合；Linux Qt6、Windows 与
macOS 仍分别由 `CAP-GAP-007`、`CAP-GAP-008` 跟踪。

## 固定证据

项目生成的原始名称计划为
[`data/path-locale-fixture.json`](data/path-locale-fixture.json)，SHA-256：

```text
b00a3c94e4a5480e82fe5b6fd266be101c70bcb78ab338e694ca779645bbaad6
```

机器报告为
[`data/path-locale-filesystem-engine-qt5.json`](data/path-locale-filesystem-engine-qt5.json)，
SHA-256：

```text
e3ba7c8b35d7aa82b215402c28e3aadf95d6ac95ab6b64af8dc68b38a439ff6a
```

报告保存：

- 两个镜像的 image ID、revision 与二进制 SHA-256；
- 两个上游源码文件的 SHA-256、必需源码模式及行号；
- 21 个实际创建 basename 的原始 byte hex 清单；
- 每个环境单元的 filesystem type、charmap、exit code、时间/RSS；
- stdout/stderr 的 zlib+base64 原始字节及内容寻址 SHA-256；
- 每个环境单元解析出的完整 filename prefix 顺序。

报告生成器
[`probe_path_locale_filesystem_behavior.py`](../../tools/upstream/probe_path_locale_filesystem_behavior.py)
在普通模式下严格校验全部 6 个 stdout hash 和两个完整 prefix profile；`--explore`
只用于首次调查，不能更新已提交基线。

## 语料矩阵

夹具由
[`generate_path_locale_fixture.py`](../../tools/corpus/generate_path_locale_fixture.py)
生成，所有文件为空，按 manifest 逆序创建。21 个 basename 包含：

- ASCII 大小写 `A/a`、`I/i`、数字、下划线、前导空格和前导 dash；
- NFC `é`、NFD `e + U+0301`；
- `ä`、`å`、土耳其 `İ/ı`；
- 中文与 emoji；
- `.hidden.empty`；
- `FF`、overlong `C0 AF`、truncated `E2 82` 三种非法 UTF-8 byte 序列。

矩阵是 3 locale × 2 filesystem × 2 Oracle：

| Locale | charmap | tmpfs stdout | volume stdout |
| --- | --- | --- | --- |
| `C` | `ANSI_X3.4-1968` | `a1e9b785…47d4b` | `6f69fc47…e4191` |
| `C.utf8` | `UTF-8` | `a1e9b785…47d4b` | `6f69fc47…e4191` |
| `POSIX` | `ANSI_X3.4-1968` | `a1e9b785…47d4b` | `6f69fc47…e4191` |

tmpfs 与 volume 的完整顺序只有第 5、6 项互换：

| 位置 | tmpfs | `ext2/ext3` volume |
| ---: | --- | --- |
| 5 | `a-case.empty` | `A-case.empty` |
| 6 | `A-case.empty` | `a-case.empty` |

其余顺序依次为：leading space、leading dash、digit、underscore、emoji、NFD、
`I`、`i`、`İ`、`z`、`ä`、`å`、NFC `é`、`ı`、中文。完整字符串保存在机器
报告中，文档摘要不替代 raw artifact。

## 上游源码约束

固定 `Formats@1151e7254.../xbinary.cpp` 的 published CLI overload：

1. `QDir dir(sDirectoryName)`；
2. 无显式 filter/sort 参数调用 `dir.entryInfoList()`；
3. 按返回的 `QFileInfoList` 顺序递归；
4. `main_console.cpp` 调用
   `XBinary::findFiles(sFileName, &listFileNames)`。

这解释了为何排序是 Qt/QDir 与底层环境共同形成的可观察行为，而不是上游明确
声明的稳定 comparator。机器报告从固定 CMake 镜像读取源码字节并校验上述模式，
不依赖工作树中未物化的 Formats gitlink。

## 可重复运行

前置条件是已按
[`upstream-build-reproduction.md`](upstream-build-reproduction.md) 构建固定
qmake/CMake Oracle 镜像。PowerShell：

```powershell
python tools/corpus/generate_path_locale_fixture.py `
  --output docs/research/data/path-locale-fixture.json
python tools/upstream/probe_path_locale_filesystem_behavior.py `
  --output docs/research/data/path-locale-filesystem-engine-qt5.json
python -m unittest discover -s tools/tests `
  -p test_probe_path_locale_filesystem_behavior.py
```

每次 container 均为 `--network none`、只读 root、1 CPU、512 MiB memory、
128 pids、core 0；tmpfs 大小限制为 16 MiB。两个文件系统都挂载到同一
`/work`，避免 mount path 本身污染 stdout 比较。匿名 volume 随 `--rm` 删除。

## 兼容与设计含义

- `LegacyCompatible` 必须按平台 profile 对目录展开顺序做差分；不能把
  `sort_by(path.as_bytes())` 当作上游等价实现。
- `SafeCanonical` 应定义项目自己的确定性 total order，并在结果中标记与 raw
  upstream 顺序的 `SafetyDeviation`/compatibility profile 差异。
- 非 UTF-8 basename 不能被 lossy decode 后当成另一个合法路径；上游 directory
  expansion 的静默过滤是 legacy observation，canonical API 应给 typed
  diagnostic。
- hidden filter、filesystem identity 与 locale/charmap 必须进入 golden metadata，
  normalizer 不得重排后隐藏真实顺序差异。

这些策略与
[`ADR 0014`](../design/decisions/0014-bounded-path-expansion.md) 的 bounded
target expansion 一致。

## 非声明范围

- `stat` 的 `ext2/ext3` 是该 Docker volume 的实际报告字符串，不表示已经覆盖
  每种 ext4 feature、网络文件系统或 FUSE 实现；
- 本实验只闭合固定 Linux Qt5 Oracle 可用的完整 locale 清单及两个明确
  filesystem profile，不外推到 Linux Qt6；
- Windows NTFS/ReFS、junction/reparse point、macOS APFS/HFS+ 的 case 与
  normalization 行为未覆盖；
- production Rust `TargetExpander` 及其跨平台 system tests 尚未实现。
