# 通用 Archive 分派可达性

Status: Draft
Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254
Last updated: 2026-07-28

## 范围

本文固定 DIE-engine 的通用 `FT_ARCHIVE` 扫描分支，区分自然格式检测、
公共 CLI 分派、compact `filetypes=ARCHIVE` 强制分派和 verbose 规则执行。
实验固定以下组件：

- Detect-It-Easy `c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- Formats `1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XArchive `0fcd4e8d3e9933baac3b12246d82ac026557ffd0`
- XScanEngine `dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- die_script `5d82316c110abf0eb863b50bc679d330e05067b6`

本实验使用 ZIP、TAR、GZIP 三种项目生成归档，覆盖专用分支和两种 Binary
回退。archive aggressive 的 100000 精确边界已由
[`archive-iteration-boundary.md`](archive-iteration-boundary.md) 固定；
本实验不验证压缩/加密/畸形输入或跨平台行为，这些仍归 `CAP-GAP-006`。
ZIP 的首轮对应矩阵见
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)。

## 结论

固定版本中的 generic Archive 分支不能从普通文件自然到达：

1. Formats 对每个已识别 archive 都同时加入 `FT_ARCHIVE` 和至少一个具体
   子类型，例如 ZIP、TAR、GZIP。
2. `XScanEngine::scanProcess()` 只有在检测集合包含 `FT_ARCHIVE` 且集合大小
   恰好为 1 时才进入 generic Archive 分支。
3. 因此 ZIP 自然进入专用 ZIP 分支；TAR 与 GZIP 虽包含 `FT_ARCHIVE`，仍回退
   Binary。打开公共 `--verbose` 只影响规则结果，不改变该分派。
4. 显式设置 compact device property `filetypes=ARCHIVE` 后，检测集合被替换为
   单一 `ARCHIVE`，scanner 初始化为 `Archive`。
5. 强制 quiet 模式没有可见格式规则，三种样本均为 `Archive / Unknown`。
   强制 verbose 模式下，Archive 脚本宿主会重新检测原始设备、选择具体
   XArchive adapter，并由原样 `_Archive.0.sg` 分别报告 ZIP、tar、GZIP。

这与 generic Image 的 singleton 强制入口模式相似，但内部行为不同：generic
Archive 能为已支持的具体归档创建 adapter，而 generic Image 在固定版本中会得到
空 adapter。Rust 兼容实现必须把“自然检测集合”“scanner 选择”和“脚本宿主内部
重检测”作为三个不同阶段保存；不能看到 `FT_ARCHIVE` 就直接把顶层类型改成
Archive。

## 源码证据

报告绑定固定容器内完整源码与规则哈希。关键位置是：

- `Formats/xformats.cpp:1608-1646`：ZIP、GZIP、TAR、7Z 等自然检测均先加入
  `FT_ARCHIVE`，再加入具体子类型。
- `Formats/xformats.cpp:234-287`：`createClass()` 能为 ZIP、GZIP、TAR 及其他
  具体 archive file type 创建 XArchive 派生 adapter。
- `XScanEngine/xscanengine.cpp:2796-2798`：generic Archive 分支要求
  `stFT.contains(FT_ARCHIVE) && stFT.size() == 1`。
- `die_script/die_scriptengine.cpp:135-146`：进入 `FT_ARCHIVE` 后重新调用
  `getFileTypes(device, true)`，选 preferred file type，经
  `XFormats::createClass()` 创建 adapter，再构造 `Archive_Script`。
- `db/Archive/_Archive.0.sg`：仅在 `Archive.isVerbose()` 为真时读取格式
  name/version/options 并产生记录。
- `db/ZIP/_ZIP.0.sg`：自然 ZIP verbose 模式使用专用 ZIP 规则，不是 Archive
  规则。
- `db/Binary/archive_archives.1.sg`：自然 TAR 回退 Binary 后以 USTAR header
  规则报告 `tar`。

这些条件共同解释了为什么检测集合中出现 `ARCHIVE` 不等于 generic Archive
scanner 分支已到达。

## 夹具

[`data/generic-archive-dispatch-fixture.json`](data/generic-archive-dispatch-fixture.json)
固定三种项目生成样本：

| 样本 | Size | 自然 detected | 自然初始类型 |
| --- | ---: | --- | --- |
| `payload.zip` | 151 | `BINARY|ARCHIVE|ZIP` | `ZIP` |
| `payload.tar` | 2048 | `BINARY|ARCHIVE|TAR|TEXT|UTF8` | `Binary` |
| `payload.txt.gz` | 54 | `BINARY|ARCHIVE|GZIP` | `Binary` |

三者都只包含
`diec-rust deterministic corpus\n`，payload SHA-256 为
`22b217bfba5795d402092bf48bfb28146c0ee4dd0036fd4d0c93e25bbe65e998`。
ZIP 与 TAR 成员名为 `payload.txt`；GZIP header 不携带原始文件名。生成器复用
通用基线的确定性 builder，测试使用 Python `zipfile`、`tarfile`、`gzip`
独立解析内容、成员、时间戳及哈希。

## 观察矩阵

| 样本 | automatic quiet | automatic verbose | forced quiet | forced verbose |
| --- | --- | --- | --- | --- |
| ZIP | `ZIP / Unknown` | `ZIP / ZIP`，`_ZIP.0.sg` | `Archive / Unknown` | `Archive / ZIP` |
| TAR | `Binary / tar` | `Binary / tar` | `Archive / Unknown` | `Archive / tar` |
| GZIP | `Binary / Unknown` | `Binary / Unknown` | `Archive / Unknown` | `Archive / GZIP` |

强制 verbose 的三个结果都来自 `_Archive.0.sg`。ZIP 的格式版本为 `2.0`、
info 为 `Store`；TAR/GZIP 的 version 和 info 为空。每次扫描均加载固定
main/extra/custom database，错误数为 0，PDSTRUCT success 为 true。

## Oracle 设计

[`data/generic-archive-dispatch-engine-qt5.json`](data/generic-archive-dispatch-engine-qt5.json)
是内容寻址报告，SHA-256 为
`960fca28122af3bddb2fcd22706f5350ee8f4753a79a61cc2338aba7d1f53c04`。
它绑定：

- 固定 CMake harness 镜像和 qmake release 镜像的 ID、revision；
- harness、CMake release、qmake release 二进制的大小和 SHA-256；
- 五个组件 HEAD，以及 scanner、Formats、脚本宿主和三份规则的源码哈希；
- fixture manifest、两个 generator、harness、Dockerfile 和 probe 的哈希；
- 3 个样本 × harness/default release/verbose release 的 15 次执行；
- 每次原始 stdout/stderr 的 SHA-256、长度及 `zlib+base64` 内容；
- 无网络、1 CPU、512 MiB、128 PID、只读根和只读 fixture mount。

每个 release 模式都同时运行固定 CMake 与 qmake 二进制，quiet 和 verbose 的
stdout/stderr 均逐字节相等。release 的 root filetype 和 detection names 也与
harness 对应 automatic 模式一致。

报告固定以下机器可检验事实：

- `natural_detection_pairs_archive_with_concrete_subtype`
- `automatic_scan_never_initializes_generic_archive`
- `zip_uses_specialized_public_branch`
- `tar_and_gzip_use_binary_public_fallback`
- `automatic_verbose_does_not_force_generic_archive`
- `forced_quiet_archive_is_unknown`
- `forced_verbose_archive_redetects_all_adapters`
- `qmake_and_cmake_release_outputs_are_byte_equal`
- `release_and_harness_automatic_semantics_agree`

## 复现

```text
python tools/corpus/generate_generic_archive_dispatch_fixture.py \
  /tmp/diec-generic-archive-dispatch-fixture

docker build --provenance=false \
  --file tools/upstream/Dockerfile.generic-archive-dispatch-harness-qt5 \
  --tag diec-rust/generic-archive-dispatch-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_generic_archive_dispatch_harness.py \
  --fixture-dir /tmp/diec-generic-archive-dispatch-fixture \
  --output \
  docs/research/data/generic-archive-dispatch-engine-qt5.json
```

重新生成后必须与提交报告逐字节相等。镜像、二进制、组件、规则、工具、fixture
或任一原始输出变化都会使离线测试失败。

## 剩余缺口

generic Archive 顶层分派及其 verbose 规则入口已固定，但
`CAP-GAP-006` 仍保持开放：

- archive aggressive 的 100000 精确边界已由
  [`archive-iteration-boundary.md`](archive-iteration-boundary.md) 闭合；
- ZIP 1 MiB/843.58:1、ZipCrypto 无密码和首轮畸形已由
  [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)
  固定；其他格式/算法、更高展开量、solid/multi-volume 和系统化畸形仍缺；
- 最大深度、总展开量的安全预算与更多格式交互；
- Linux Qt6、Windows、macOS 对应行为。
