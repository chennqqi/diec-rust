# 7Z coder、RAR4、CAB Store/MSZIP 与 ISO9660 archive 解包行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 engine harness 对九个项目生成样本给出一致的正向结果：

- 7Z Copy/LZMA/LZMA2/BZip2/Deflate、RAR4 store、CAB Store/MSZIP、ISO9660 的默认
  engine 模式都不展开成员；
- 显式设置 `bIsArchivesScan` 后，九个容器都产生恰好一个 `PDF / Stream`
  child，并执行 PDF 与 HeaderComment 规则；
- 对这些单成员样本再启用 aggressive 不改变原始输出；
- 7Z 与 CAB 的顶层 `filetype` 都是 `Binary`，顶层规则检测名分别是
  `7-Zip` 与 `CAB`，但 archive adapter 仍可展开成员；不能由顶层展示类型
  直接推断内部 archive 分派失败；
- harness 默认模式与使用同一数据库的固定发布 CLI 原始 stdout/stderr
  逐字节相同。

这组结果增加了 7Z 五种 coder、RAR4 store、CAB Store/MSZIP 与 ISO9660 的
正向 corpus 证据，但不关闭
`CAP-GAP-006`。NPM 分派已由独立的直接/自动/强制实验固定，见
[`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)；通用 Archive
分派现由
[`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)
固定；archive aggressive 100000 精确边界现由
[`archive-iteration-boundary.md`](archive-iteration-boundary.md) 固定，
ZIP deflate/ZipCrypto/CRC/压缩流畸形与 1 MiB 高压缩比现由
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md) 固定；
7Z PPMd7/Deflate64/filter/AES、RAR 的压缩算法、CAB LZX/Quantum、系统化畸形矩阵及跨平台
行为仍未验证。

机器报告是
[`archive-format-engine-qt5.json`](data/archive-format-engine-qt5.json)，
SHA-256 为
`fe8361ff34099b94fac9a886c804b263d83210f23058a8c00fc6187dbd9ec3f1`。
报告中的布尔事实键保持为：

- `release_and_harness_default_outputs_are_equal`
- `archive_option_is_required_for_unpacking`
- `sevenzip_copy_member_reaches_pdf_rules`
- `sevenzip_lzma_member_reaches_pdf_rules`
- `sevenzip_lzma2_member_reaches_pdf_rules`
- `sevenzip_bzip2_member_reaches_pdf_rules`
- `sevenzip_deflate_member_reaches_pdf_rules`
- `rar4_store_member_reaches_pdf_rules`
- `cab_store_member_reaches_pdf_rules`
- `cab_mszip_member_reaches_pdf_rules`
- `iso9660_store_member_reaches_pdf_rules`
- `cab_root_dispatches_as_binary_while_archive_adapter_runs`
- `sevenzip_root_dispatches_as_binary_while_archive_adapter_runs`
- `aggressive_does_not_change_single_member_results`

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| 上游 commit | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| 镜像 | `diec-rust/upstream-archive-harness:74eaf505` |
| 镜像 ID | `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc` |
| Harness binary | `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e` |
| Release binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| Fixture manifest | `5765868cc71c283e9447b66f692bd63a70165685ac946fa7cba760588871c03b` |

Harness 只替换 console `main`，扫描、数据库加载、解包和 formatter 均复用固定
镜像中的上游对象。源码和构建入口分别为
[`archive_harness_main.cpp`](../../tools/upstream/archive_harness_main.cpp) 与
[`Dockerfile.archive-harness-qt5`](../../tools/upstream/Dockerfile.archive-harness-qt5)；
报告同时绑定它们以及两个 fixture generator 的 SHA-256。

报告还绑定固定镜像内以下上游源码，不从相邻格式外推：

| 组件 | 镜像内路径 | SHA-256 | 固定符号/条件 |
| --- | --- | --- | --- |
| Engine archive branch | `/opt/die-source/XScanEngine/xscanengine.cpp` | `e088bebb...61b498` | `FT_ZIP / FT_7Z / FT_RAR / FT_CAB` 条件 |
| 7Z adapter | `/opt/die-source/XArchive/xsevenzip.cpp` | `d8da44bd...8e5554` | `XSevenZip::initUnpack` 及 Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 method table |
| RAR adapter | `/opt/die-source/XArchive/xrar.cpp` | `23721187...0ccb8` | `XRar::initUnpack` |
| CAB adapter | `/opt/die-source/XArchive/xcab.cpp` | `a0ce130f...8035b` | `XCab::initUnpack` |
| ISO9660 adapter | `/opt/die-source/XArchive/xiso9660.cpp` | `d6e97c4f...98fb1` | `XISO9660::initUnpack` |

完整哈希与 required-pattern 计数保存在机器报告的 `source_contract` 中。

## 语料

[`generate_archive_format_fixture.py`](../../tools/corpus/generate_archive_format_fixture.py)
只使用项目生成字节，复用固定 331-byte PDF payload，不导入第三方 archive
样本。仓库保存生成器和
[`archive-format-corpus.json`](data/archive-format-corpus.json)，不保存生成出的
二进制。

| 样本 | 结构 | Size | SHA-256 |
| --- | --- | ---: | --- |
| `pdf-member.7z` | 7Z Copy coder → `payload.pdf` | 427 | `b5db3322be26f8693e15cfcd1d898e463f6ac20003274b90ffd75dd80788611d` |
| `pdf-member-lzma.7z` | 7Z LZMA coder → `payload.pdf` | 305 | `e5b9efb5cce8422bff727a336a024323595624c972a52a51bf6fa2f144e234a3` |
| `pdf-member-lzma2.7z` | 7Z LZMA2 coder → `payload.pdf` | 301 | `a75b724562911af555468ad797c2a940e3597fe3c3387d6db3bb1c0c89aeaafe` |
| `pdf-member-bzip2.7z` | 7Z BZip2 coder → `payload.pdf` | 346 | `f9b7455d5922e88c3e987b6010dbc8f90470b2fb6dc9bd2612225e87fde59c3f` |
| `pdf-member-deflate.7z` | 7Z Deflate coder → `payload.pdf` | 295 | `07185ac8131fed41933521faf48ac339270f1b15b0f63832330ea848a9dd0097` |
| `pdf-member.rar` | RAR4 store → `payload.pdf` | 401 | `1e988659f00088083708520b34d0fcd280af016d03f2d9d95b8449425bb01ab9` |
| `pdf-member.cab` | CAB store → `payload.pdf` | 411 | `9c96e5fc93766362d90940ef83606646f255eaad408677675b510eebb2434708` |
| `pdf-member-mszip.cab` | CAB MSZIP → `payload.pdf` | 279 | `88046b230fc0abb3a4ec09222879601677c9c8e8044afc9f869f15dae55aa752` |
| `pdf-member.iso` | ISO9660 → `payload.pdf` | 43008 | `d32df4410a94094ab990d9cb32fa4a2e4e168d3173756962f6889902c18bb832` |

四个成员 payload 的 SHA-256 都是
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。
生成器测试逐字节复验 size/hash，使用 Python 标准库独立解压四个压缩 stream，
并检查格式头、7Z Start/Next Header CRC、RAR header CRC、CAB size/压缩类型；
MSZIP 的 `CK` + raw deflate 数据还会由 Python `zlib` 独立还原，ISO9660 检查
sector size。

## 实验矩阵

每个样本运行四种模式：

| 模式 | 可达入口 | 预期作用 |
| --- | --- | --- |
| `default` | engine harness | archive off |
| `release_default` | 固定发布 CLI | archive off 的等价控制 |
| `archive` | engine harness `--archive` | 设置 `bIsArchivesScan` |
| `archive_aggressive` | engine harness `--archive --aggressive` | archive + aggressive |

观察摘要：

| 样本 | 顶层 filetype / detection | default / release | archive / archive+aggressive |
| --- | --- | --- | --- |
| 7Z Copy/LZMA/LZMA2/BZip2/Deflate | `Binary / 7-Zip` | 0 Stream | 1 × `PDF / Stream` |
| RAR4 store | `RAR / Unknown` | 0 Stream | 1 × `PDF / Stream` |
| CAB Store/MSZIP | `Binary / CAB` | 0 Stream | 1 × `PDF / Stream` |
| ISO9660 | `ISO 9660 / Unknown` | 0 Stream | 1 × `PDF / Stream` |

每个 archive child 的 size 是字符串 `"331"`，规则检测名严格为
`["PDF", "HeaderComment"]`。每个样本的 `default == release_default`，
`archive == archive_aggressive`，比较对象是未经规范化的 stdout/stderr
原始字节，不只是摘要。

完整 36 次执行的原始 stream 以 SHA-256 为键，经 `zlib+base64` 去重嵌入报告；
离线测试会解压每个 artifact、复验长度/hash，并验证每个 case 的引用。扫描容器
禁用网络，限制为 1 CPU、512 MiB、128 PIDs、只读根和只读 fixture mount，
每次执行超时 60 秒。

## 7Z 与 CAB 顶层 quirk

7Z 与 CAB 是这组样本中必须保留的兼容性反例。固定发布 CLI 与 harness 默认
模式都输出顶层 `filetype = Binary`；规则结果分别为
`Archive: 7-Zip(0.4)` 与 `Archive: CAB(1.03)[102.4%, 1 file]`。显式 archive
后同一顶层下面仍出现 PDF Stream child。

因此 Rust 结果模型和差分测试必须分别保留：

1. 顶层展示 `filetype`；
2. 顶层规则 detection；
3. archive adapter 的内部选择；
4. child 的 `parentfilepart` 与父子关系。

把 detection 名 `7-Zip`/`CAB` 规范化成对应顶层 archive `filetype`，或因顶层
是 `Binary` 而跳过解包，都会产生可观察差异。

## 复现

```sh
python3 tools/corpus/generate_archive_format_fixture.py \
  /tmp/diec-archive-format-fixture

python3 tools/upstream/probe_archive_format_harness.py \
  --fixture-dir /tmp/diec-archive-format-fixture \
  --output docs/research/data/archive-format-engine-qt5.json

python3 tools/tests/test_generate_archive_format_fixture.py
python3 tools/tests/test_probe_archive_format_harness.py
```

探针先验证 manifest inventory、size/hash 和无额外文件，再验证镜像 revision、
binary/source/local tool identity，最后运行全部 case。报告生成器变化会改变
`generator_sha256` 和报告 SHA，必须重新采集并同步严格测试中的固定报告哈希。

## 剩余边界

本实验只证明五种 7Z coder、RAR4 store、CAB Store/MSZIP 与 ISO9660 的合法
单成员正例，不证明：

- 通用 Archive 的自动/强制分派见
  [`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)；
  NPM 的直接检测、公共自动回退和强制分支见
  [`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)；
- 7Z 的 PPMd7、Deflate64、BCJ/ARM64-BCJ/BCJ2 filter 与 AES 组合；
- RAR 的压缩方法、CAB LZX/Quantum、ISO9660 扩展，以及
  solid/multi-volume/encrypted entry；
- 截断 header、错误 size/CRC、重复名称、目录、链接和路径穿越 metadata；
- 空 archive、多成员顺序、不可扫描成员与错误/partial-result 行为；
- aggressive 100000 精确边界见
  [`archive-iteration-boundary.md`](archive-iteration-boundary.md)；ZIP
  1 MiB/843.58:1 已由
  [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md) 固定，
  更高展开量和真实资源耗尽仍未验证；
- Windows、macOS、Qt6，以及平台 archive backend 差异。

`CAP-GAP-006` 因此保持开放。已有 ZIP 深度、累计展开量、取消与 20/21 边界
证据见 [`archive-limit-behavior.md`](archive-limit-behavior.md)，100000
记录边界见
[`archive-iteration-boundary.md`](archive-iteration-boundary.md)；这些证据应
与 [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)
共同约束后续 Rust archive 层，但不能替代剩余格式和压力边界实验。
