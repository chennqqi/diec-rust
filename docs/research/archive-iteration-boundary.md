# 上游 Qt5/Qt6 archive aggressive 记录边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux x86_64 Qt5 engine oracle 已观察 aggressive archive 的精确记录边界：

- 第 99999 条和第 100000 条记录中的 PDF 哨兵均被扫描；
- 第 100001 条记录中的相同 PDF 哨兵不被扫描；
- 三个样本均有 100001 条 ISO9660 archive record，差异只有 PDF 哨兵位置；
- 上游源码中的 aggressive `nLimit = 100000` 不会先于 `i < 100000` 生效：
  `nCurrentIndex` 从 0 开始，每轮最多增加 1，且 `nCurrentIndex > nLimit`
  在增加后才检查。循环最多执行 100000 轮，因此 aggressive 模式下该条件
  不可能为真；实际边界是第 100000 条记录可达、第 100001 条不可达。

这关闭了 `CAP-GAP-006` 中“archive aggressive 100000 精确边界”子项。
ZIP deflate/ZipCrypto/CRC/压缩流畸形已有
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)。该 gap
在本实验完成时仍开放，后续已由
[`archive-gap-closure.md`](archive-gap-closure.md)
以五类 engine family 闭集、成对 oracle 和 depth/total 证据关闭；其他方法、
系统化畸形与真实资源耗尽仍作为扩展/安全风险，跨平台由独立 gap 跟踪。

相同上游源码的 Qt6 engine oracle 得到不同的 ISO9660 可观察边界：

- 第 99999 条 PDF 可达，第 100000 和第 100001 条 PDF 均不可达；
- 三例均比 Qt5 多一个 Stream，它来自未被过滤的 ISO `.` directory record；
- direct Qt probe 证明 Qt 5.15.13 把单 NUL `QByteArray` 转为空 `QString`，
  Qt 6.4.2 则保留一个 NUL code unit；固定 `xiso9660.cpp` 的 dot filter 因而
  在两个 runtime 上得到不同比较结果；
- `xscanengine.cpp`、`xiso9660.cpp` 与 corpus bytes 相同，因此该差异不是
  上游 revision 或输入漂移。

机器报告：
[`archive-iteration-boundary-engine-qt5.json`](data/archive-iteration-boundary-engine-qt5.json)、
[`archive-iteration-boundary-engine-qt6.json`](data/archive-iteration-boundary-engine-qt6.json)
和
[`qt-null-filename-semantics-qt5-qt6.json`](data/qt-null-filename-semantics-qt5-qt6.json)。
完整 Qt6 闭环说明见
[`qt6-count-boundary-runtime-evidence.md`](qt6-count-boundary-runtime-evidence.md)；
原生 Windows Qt5 双轮对照见
[`windows-count-boundary-behavior.md`](windows-count-boundary-behavior.md)。

## Qt5 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| XScanEngine gitlink | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| `xscanengine.cpp` SHA-256 | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| harness binary SHA-256 | `5fba6113410416fc828c8687f9d179d4875862115b53a5a7e993e0760eb87eaa` |
| image ID | `sha256:6cfc6dfb568e1287103bbe92f31e75864153b6bf5f196a744178d9c86ae19392` |

报告还保存每例原始 stdout/stderr 及其 SHA-256、退出码、timeout/OOM 标志、
扫描耗时和进程 peak RSS。

Qt6 harness image ID 为
`sha256:a51310e8e03ada9fb907d6ea3d3d3b0a5d0c1917a3aaef971f3a07683486508f`，
binary SHA-256 为
`d13b381bc5353f8e261a741c235a825e65461d8ab38cf9f9ba71c16fb94dfbcb`。
`xiso9660.cpp` SHA-256 为
`d6e97c4ff2395b812b65da5ab480e937c6b365e6e6e8b0288ddf48b8fd398fb1`。

## 源码语义

固定
[`xscanengine.cpp`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2835-L2921)
的顺序是：

1. aggressive 模式把 `nLimit` 从 20 改为 100000；
2. `nCurrentIndex` 初始化为 0；
3. 外层循环条件包含 `i < 100000`；
4. 成员成功解包并进入扫描后，`nCurrentIndex++`；
5. 随后才检查 `nCurrentIndex > nLimit`。

因此 normal 模式会在扫描第 21 个成员后得到 `nCurrentIndex == 21` 并退出；
aggressive 模式即使每轮都成功扫描，最后一轮也只得到
`nCurrentIndex == 100000`，不会满足严格大于。该结论同时绑定完整源码 SHA-256、
关键 token 出现次数和操作顺序，不依赖“最新版”源码。

## 边界夹具

生成器
[`generate_archive_iteration_boundary_fixture.py`](../../tools/corpus/generate_archive_iteration_boundary_fixture.py)
创建三个确定性 ISO9660：

| 样本 | archive records | PDF 哨兵 one-based ordinal | SHA-256 |
| --- | ---: | ---: | --- |
| `sentinel-099999.iso` | 100001 | 99999 | `5214a3b0baadc4e29b7cade268b6e255567bf920110e6cdbae2647883e35b439` |
| `sentinel-100000.iso` | 100001 | 100000 | `a4b9e66ddf948f7fda3aa1d5ef4572e58e9262bef3f2aa90f1f6e005a2c8c449` |
| `sentinel-100001.iso` | 100001 | 100001 | `fd8bc136371dd7e6fb2e58ffd3fac0884440092fb6422bc2bd66302a99ae7819` |

每个镜像为 4,306,944 bytes。PDF 是项目生成的最小良性样本；其余记录不含
第三方或恶意字节。完整清单见
[`archive-iteration-boundary-corpus.json`](data/archive-iteration-boundary-corpus.json)。
生成器测试验证：

- 两次生成的文件和 manifest 逐字节相同；
- ISO9660 PVD、root directory、记录数量和哨兵 ordinal 一致；
- 只有哨兵 extent/size 完整落在镜像内，且内容以 `%PDF-1.4` 开头。

## 受控分配失败

aggressive 模式会尝试扫描每个成功创建 buffer 的成员。为了隔离记录索引边界，
占位记录声明 16 MiB 大小并指向镜像外；该大小使固定
`XBinary::createFileBuffer()` 选择 `QTemporaryFile`。实验把
`TMPDIR=/proc`，使占位记录的临时文件创建确定性失败，于是原始 engine 循环继续
移动到下一条记录，但不解包或递归扫描占位内容。小于 16 MiB 的合法 PDF 哨兵仍
使用内存 `QBuffer`，行为未被屏蔽。

这是明确记录的故障注入，不代表正常可写临时目录下扫描 10 万个真实成员的性能。
它验证的是：

- archive adapter 确实枚举 100001 条记录；
- 原始 `XScanEngine` 循环是否到达指定 ordinal；
- 到达时同一个合法 PDF 能否形成 `PDF / Stream` child。

## 运行结果

每例在独立容器中使用：

```text
--network none --cpus 1 --memory 512m --pids-limit 128
TMPDIR=/proc
wall timeout: 30 seconds
```

| 哨兵 ordinal | exit | PDF nodes | Stream nodes | elapsed | peak RSS after |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 99999 | 0 | 1 | 1 | 814 ms | 86,588 KiB |
| 100000 | 0 | 1 | 1 | 838 ms | 87,184 KiB |
| 100001 | 0 | 0 | 0 | 817 ms | 86,788 KiB |

三例 stderr 为空、无 engine error、未停止、未 timeout、未以 137 退出。
elapsed/RSS 是本次环境描述值，只断言有效及 high-watermark 不倒退，不作为
跨机器性能 golden。

Qt6 使用相同 corpus 和故障注入，两次独立执行的稳定语义相同：

| 哨兵 ordinal | PDF nodes | Stream nodes | record count |
| ---: | ---: | ---: | ---: |
| 99999 | 1 | 2 | 4 |
| 100000 | 0 | 1 | 2 |
| 100001 | 0 | 1 | 2 |

Qt6 三例 stderr 同样为空。报告中的 timing/RSS 是描述性观测，不作为逐字节
golden；node/PDF/record/Stream count、exit code 和 stderr hash 才是闭环断言。

## 复现

```powershell
$corpusDir = Join-Path $env:TEMP diec-archive-iteration-boundary
python tools\corpus\generate_archive_iteration_boundary_fixture.py $corpusDir
docker build `
  -f tools\upstream\Dockerfile.archive-iteration-boundary-harness-qt5 `
  -t diec-rust/upstream-archive-iteration-boundary-harness:74eaf505 `
  tools\upstream
python tools\upstream\probe_archive_iteration_boundary_harness.py `
  --platform qt5 `
  --image diec-rust/upstream-archive-iteration-boundary-harness:74eaf505 `
  --corpus-dir $corpusDir

python tools\upstream\probe_archive_iteration_boundary_harness.py `
  --platform qt6 `
  --image diec-rust/archive-iteration-boundary-harness-qt6:74eaf505 `
  --corpus-dir $corpusDir `
  --output docs\research\data\archive-iteration-boundary-engine-qt6.json

python tools\upstream\probe_qt_null_filename_semantics.py `
  --output docs\research\data\qt-null-filename-semantics-qt5-qt6.json
```

## Rust 兼容要求

- 若 legacy compatibility profile 选择 Qt5 基线，必须把单层 archive 的记录
  迭代硬上限定义为 100000，使用 one-based 语义描述为“第 100000 条可达，
  第 100001 条不可达”；若选择 Qt6 基线，还必须重现 ISO dot-entry 保留造成
  的一条提前量；
- 不应把 aggressive 的 `nLimit=100000` 实现成另一个会提前拒绝第 100000 条的
  scanable-member 上限；
- 兼容测试需要保留 99999/100000/100001 三点哨兵，而不是只测一个大样本；
- 安全 profile 可以增加累计展开量、时间、内存和成员大小预算，但必须通过 ADR
  和结构化诊断与 legacy profile 区分。

## 限制与剩余缺口

- 只验证 Linux x86_64 Qt 5.15.13/Qt 6.4.2、ISO9660 record enumeration 和
  一个 PDF 哨兵；
- 故障注入刻意不测 10 万个成功解包成员的吞吐、结果树大小或真实磁盘耗尽；
- 未验证 ZIP64、7Z/RAR/CAB 大记录数，以及压缩、加密、CRC/size 欺骗和截断；
- 未验证 Windows、macOS 或其他 Qt minor 的临时文件与 archive backend 差异。
