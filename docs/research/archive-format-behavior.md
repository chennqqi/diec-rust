# 7Z coder/filter、RAR4、CAB Store/MSZIP/LZX/Quantum 与 ISO9660 archive 解包行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 engine harness 对十九个可追溯样本给出可重复结果：

- 7Z Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 distance-32769、
  x86 BCJ+LZMA2、BCJ2+LZMA2 无分支/E8/E9/JCC 四流分支、
  ARM64-BCJ+LZMA2 BL/ADRP 分支、RAR4 store、CAB
  Store/MSZIP、ISO9660 的默认 engine 模式都不展开成员；
- 显式设置 `bIsArchivesScan` 后，前十七个容器都产生恰好一个 `PDF / Stream`
  child，并执行 PDF 与 HeaderComment 规则；
- 合法 CAB LZX:15 能被识别为 `Binary / CAB`，但普通 archive 模式不产生
  child；archive+aggressive 反而扫描一个 331-byte `Binary / Unknown`
  Stream，未还原其中的 PDF；
- 合法 CAB Quantum level/window 18 同样在普通 archive 模式不产生 child；
  archive+aggressive 扫描一个 59-byte `Binary / Unknown` Stream，未还原
  已由独立工具验证的明文；
- 对十七个已支持单成员样本再启用 aggressive 不改变原始输出；
- 7Z 与 CAB 的顶层 `filetype` 都是 `Binary`，顶层规则检测名分别是
  `7-Zip` 与 `CAB`，但 archive adapter 仍可展开成员；不能由顶层展示类型
  直接推断内部 archive 分派失败；
- harness 默认模式与使用同一数据库的固定发布 CLI 原始 stdout/stderr
  逐字节相同。

这组结果增加了 7Z 七种单 coder、x86 BCJ+LZMA2、BCJ2+LZMA2
无分支及 E8/E9/JCC filter 链与
ARM64-BCJ+LZMA2 BL/ADRP 分支、RAR4 store、CAB Store/MSZIP 与 ISO9660 的正向
corpus 证据，并固定 CAB LZX/Quantum 的未实现/激进扫描 quirk，但不关闭
`CAP-GAP-006`。NPM 分派已由独立的直接/自动/强制实验固定，见
[`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)；通用 Archive
分派现由
[`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)
固定；archive aggressive 100000 精确边界现由
[`archive-iteration-boundary.md`](archive-iteration-boundary.md) 固定，
ZIP deflate/ZipCrypto/CRC/压缩流畸形与 1 MiB 高压缩比现由
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md) 固定；
7Z AES、RAR 的压缩算法、
系统化畸形矩阵及跨平台行为仍未验证。

机器报告是
[`archive-format-engine-qt5.json`](data/archive-format-engine-qt5.json)，
SHA-256 为
`bf197fff978dd8f8f441da1c0b44201d63a1dda601ff460afee934c6d53705f1`。
报告中的布尔事实键保持为：

- `release_and_harness_default_outputs_are_equal`
- `archive_option_is_required_for_unpacking`
- `sevenzip_copy_member_reaches_pdf_rules`
- `sevenzip_lzma_member_reaches_pdf_rules`
- `sevenzip_lzma2_member_reaches_pdf_rules`
- `sevenzip_ppmd7_member_reaches_pdf_rules`
- `sevenzip_bzip2_member_reaches_pdf_rules`
- `sevenzip_deflate_member_reaches_pdf_rules`
- `sevenzip_deflate64_distance_32769_member_reaches_pdf_rules`
- `sevenzip_bcj_lzma2_member_reaches_pdf_rules`
- `sevenzip_bcj2_lzma2_control_reaches_pdf_rules`
- `sevenzip_bcj2_e8_lzma2_member_reaches_pdf_rules`
- `sevenzip_bcj2_e9_lzma2_member_reaches_pdf_rules`
- `sevenzip_bcj2_jcc_lzma2_member_reaches_pdf_rules`
- `sevenzip_arm64_bcj_lzma2_bl_and_adrp_reach_pdf_rules`
- `rar4_store_member_reaches_pdf_rules`
- `cab_store_member_reaches_pdf_rules`
- `cab_mszip_member_reaches_pdf_rules`
- `cab_lzx_archive_has_no_child_but_aggressive_scans_unknown_output`
- `cab_quantum_archive_has_no_child_but_aggressive_scans_unknown_output`
- `iso9660_store_member_reaches_pdf_rules`
- `cab_root_dispatches_as_binary_while_archive_adapter_runs`
- `sevenzip_root_dispatches_as_binary_while_archive_adapter_runs`
- `aggressive_does_not_change_supported_single_member_results`

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| 上游 commit | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| 镜像 | `diec-rust/upstream-archive-harness:74eaf505` |
| 镜像 ID | `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc` |
| Harness binary | `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e` |
| Release binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| Fixture manifest | `1fb0e7613ef1bb0886f5465c190d039ee3cf08eb70997375971965818173b1dd` |

Harness 只替换 console `main`，扫描、数据库加载、解包和 formatter 均复用固定
镜像中的上游对象。源码和构建入口分别为
[`archive_harness_main.cpp`](../../tools/upstream/archive_harness_main.cpp) 与
[`Dockerfile.archive-harness-qt5`](../../tools/upstream/Dockerfile.archive-harness-qt5)；
报告同时绑定它们以及两个 fixture generator 的 SHA-256。
PPMd7 生成与 Deflate64 独立验证的工具依赖清单也由报告绑定。

报告还绑定固定镜像内以下上游源码，不从相邻格式外推：

| 组件 | 镜像内路径 | SHA-256 | 固定符号/条件 |
| --- | --- | --- | --- |
| Engine archive branch | `/opt/die-source/XScanEngine/xscanengine.cpp` | `e088bebb...61b498` | `FT_ZIP / FT_7Z / FT_RAR / FT_CAB` 条件 |
| 7Z adapter | `/opt/die-source/XArchive/xsevenzip.cpp` | `d8da44bd...8e5554` | `XSevenZip::initUnpack`、Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 method table 及 BCJ/ARM64-BCJ filter table |
| Decompress dispatch | `/opt/die-source/XArchive/xdecompress.cpp` | `4f52eefa...2728d` | `HANDLE_METHOD_DEFLATE64` → `XDeflateDecoder::decompress64` |
| Deflate decoder | `/opt/die-source/XArchive/Algos/xdeflatedecoder.cpp` | `cb74b248...627a6` | `XDeflateDecoder::decompress64` |
| BCJ2 graph | `/opt/die-source/XArchive/xsevenzip.cpp` | `d8da44bd...8e5554` | `createPMInfo(HANDLE_METHOD_BCJ2)` 与四流坐标解析 |
| BCJ2 dispatch | `/opt/die-source/XArchive/xdecompress.cpp` | `4f52eefa...2728d` | `HANDLE_METHOD_BCJ2` 专用分支 |
| BCJ2 decoder | `/opt/die-source/XArchive/Algos/xbcj2decoder.cpp` | `254d9773...3018a` | `XBCJ2Decoder::decompress` |
| RAR adapter | `/opt/die-source/XArchive/xrar.cpp` | `23721187...0ccb8` | `XRar::initUnpack` |
| CAB adapter | `/opt/die-source/XArchive/xcab.cpp` | `a0ce130f...8035b` | `XCab::initUnpack` |
| CAB method mapping | `/opt/die-source/XArchive/xcab.cpp` | `a0ce130f...8035b` | 只精确匹配 `0x0000/0x0001/0x0003`，其他完整 `typeCompress` 值映射为 `HANDLE_METHOD_UNKNOWN` |
| CAB decompress dispatch | `/opt/die-source/XArchive/xdecompress.cpp` | `4f52eefa...2728d` | CAB 分支只列 Store/MSZIP |
| ISO9660 adapter | `/opt/die-source/XArchive/xiso9660.cpp` | `d6e97c4f...98fb1` | `XISO9660::initUnpack` |

完整哈希与 required-pattern 计数保存在机器报告的 `source_contract` 中。

## 语料

[`generate_archive_format_fixture.py`](../../tools/corpus/generate_archive_format_fixture.py)
使用项目生成结构并复用固定 331-byte PDF payload；唯一外部输入是下述
48-byte Quantum 压缩流，仓库不保存原始第三方 archive。仓库保存生成器和
[`archive-format-corpus.json`](data/archive-format-corpus.json)，不保存生成出的
二进制。PPMd7 stream 由 tool-only 的 `pyppmd==1.3.1`
生成；Deflate64 stream 由生成器直接写 fixed-Huffman bits，并由
`inflate64==1.0.4` 独立解码验证。两个工具的版本与 LGPL-2.1-or-later
标识保存在 manifest，安装入口固定于
[`requirements-archive-format.txt`](../../tools/corpus/requirements-archive-format.txt)。
它们不是 Rust/runtime 依赖。Quantum stream 固定来自
`kyz/libmspack@55d501976171397ccd5d5a7a1ca7da065b1d9a06` 的
`libmspack/test/test_files/cabd/mszip_lzx_qtm.cab`：源文件 379 bytes、
SHA-256
`0ce0b55fe705b744d41bb361170c0467db30da0c7f9bdd386d5dade71a78e171`，
切片位于 offset 331、长度 48、SHA-256
`6131acbaf1867209d537751a567e4c0a72756e7731a166395433c65d1543c04d`，
许可证为 LGPL-2.1-only。commit、路径、源/切片哈希均保存在 manifest
`third_party_inputs`，不依赖浮动分支或下载时的“最新版”。

| 样本 | 结构 | Size | SHA-256 |
| --- | --- | ---: | --- |
| `pdf-member.7z` | 7Z Copy coder → `payload.pdf` | 427 | `b5db3322be26f8693e15cfcd1d898e463f6ac20003274b90ffd75dd80788611d` |
| `pdf-member-lzma.7z` | 7Z LZMA coder → `payload.pdf` | 305 | `e5b9efb5cce8422bff727a336a024323595624c972a52a51bf6fa2f144e234a3` |
| `pdf-member-lzma2.7z` | 7Z LZMA2 coder → `payload.pdf` | 301 | `a75b724562911af555468ad797c2a940e3597fe3c3387d6db3bb1c0c89aeaafe` |
| `pdf-member-ppmd7.7z` | 7Z PPMd7 coder → `payload.pdf` | 277 | `77045232118f35db87b75404c943dff0535cbfef1194e66866818729a9571269` |
| `pdf-member-bzip2.7z` | 7Z BZip2 coder → `payload.pdf` | 346 | `f9b7455d5922e88c3e987b6010dbc8f90470b2fb6dc9bd2612225e87fde59c3f` |
| `pdf-member-deflate.7z` | 7Z Deflate coder → `payload.pdf` | 295 | `07185ac8131fed41933521faf48ac339270f1b15b0f63832330ea848a9dd0097` |
| `pdf-member-deflate64.7z` | 7Z Deflate64 distance 32769 → `payload.pdf` | 32874 | `e2c1afb79650bf9c59d3e36e20eb725c08b65d8ae4456c743fd3ddf6a23247a3` |
| `pdf-member-bcj-lzma2.7z` | 7Z LZMA2 → x86 BCJ → `payload.pdf` | 310 | `bf72e9c4b7adb71bfadc63abab107948357a21412a84fc12ac57daee8005cbe5` |
| `pdf-member-bcj2-lzma2.7z` | 7Z LZMA2 → BCJ2 no-branch control → `payload.pdf` | 320 | `224fbc30dd083fbc0b4cb23a38a8feef4f3dcb54da3b86c134f297814f2e6f95` |
| `pdf-member-bcj2-e8-lzma2.7z` | 7Z LZMA2 → BCJ2 E8 call-stream → `payload.pdf` | 325 | `64037802411734a3ee759d0bd5d7e8f3155f028d963947f101fd5cfb9971baa1` |
| `pdf-member-bcj2-e9-lzma2.7z` | 7Z LZMA2 → BCJ2 E9 jump-stream → `payload.pdf` | 325 | `c9019677df0e36103ce047eaec5cc4927dfaaba50a958323dee4c5e6433e11d4` |
| `pdf-member-bcj2-jcc-lzma2.7z` | 7Z LZMA2 → BCJ2 JCC jump-stream → `payload.pdf` | 326 | `b325bccbf764b40309f0156ad5a46b20cd78824f1a3b6866b3123fe451d0cd6c` |
| `pdf-member-arm64-bcj-lzma2.7z` | 7Z LZMA2 → ARM64 BCJ BL/ADRP → `payload.pdf` | 338 | `08021c16bc18fcd492ddad0dfcbbdf31d56f509193e4c1c052a0b4ff38b51d0c` |
| `pdf-member.rar` | RAR4 store → `payload.pdf` | 401 | `1e988659f00088083708520b34d0fcd280af016d03f2d9d95b8449425bb01ab9` |
| `pdf-member.cab` | CAB store → `payload.pdf` | 411 | `9c96e5fc93766362d90940ef83606646f255eaad408677675b510eebb2434708` |
| `pdf-member-mszip.cab` | CAB MSZIP → `payload.pdf` | 279 | `88046b230fc0abb3a4ec09222879601677c9c8e8044afc9f869f15dae55aa752` |
| `pdf-member-lzx.cab` | CAB LZX:15 → `payload.pdf` | 330 | `9fa90ae102f325edc1aaa127216f76a01e393c61b1878098b7179d4db00fa633` |
| `text-member-quantum.cab` | CAB Quantum 18 → `qtm.txt` | 124 | `2c24e38765939ee6003125244650f32e46a1af760f98c28c79699fc88319945e` |
| `pdf-member.iso` | ISO9660 → `payload.pdf` | 43008 | `d32df4410a94094ab990d9cb32fa4a2e4e168d3173756962f6889902c18bb832` |

除 ARM64、Deflate64 与 BCJ2 E8/E9/JCC 五个特殊 case 外的十三个成员使用
331-byte payload，
SHA-256 都是
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。
ARM64 case 在 PDF EOF 后追加 offset 332 的对齐 BL、零填充及 offset 4096 的
ADRP 指令，payload 为 4100 bytes，SHA-256 是
`2b3bc0f871ac98ea53d0e0e8188594882876ad1a8f4b8d7c83e18865a47695cd`。
Deflate64 case 把 PDF 以 NUL 扩展到 32769 bytes，再用 distance code 30、
distance 32769 回引开头 3 bytes，得到 32772-byte payload，SHA-256 是
`01025f0bcf2f53ace11f1a0a01f4f3e69c2311c861c3148c6756f79c46be62df`。
标准 raw Deflate `zlib` 以 invalid distance code 拒绝同一 stream，因此该
fixture 不是仅更换 7Z method ID 的普通 Deflate 子集。
BCJ2 control 使用 canonical `LZMA2 coder 0 → BCJ2 main input 1` graph，
call/jump 为空，range 初始化为五个 NUL。E8 case 在 PDF 后追加
`e8 c0 fe ff ff`，其 `rel32=-320` 指向 offset 16；编码后 main 只保留 E8，
call stream 为大端绝对地址 `00000010`，range stream 为
`007ffffc00`，解码得到 336-byte payload，SHA-256 为
`572bbf54c1bccee4fea930eb674e1f7d7df5e21406d64590a6c83f98d09e96eb`。
E9 case 同样追加 `e9 c0 fe ff ff`，地址进入 jump stream，解码得到
336-byte payload，SHA-256 为
`23b2153ff0e57d3ce794b843dc0daf7b1ddc69654364e72a2dc3aac2a2287052`。
JCC case 追加 `0f 85 bf fe ff ff`，其 `rel32=-321` 同样指向 offset 16；
main 保留 `0f85`，jump stream 为 `00000010`，解码得到 337-byte payload，
SHA-256 为
`8b7323a3472d060dede7dc1a9097d95f0d81a16b8e5bb668dc27dbf228057533`。
官方 7-Zip 26.02 Linux x64 console
`7z2602-linux-x64.tar.xz`（SHA-256
`41aaba7b1235304ab5aa0624530c67ae829496cd29e875925271efdccc28c03e`）
对四个 BCJ2 archive 和 CAB LZX 执行 `7zz t` 均报告 `Everything is Ok`；
该工具只用于
fixture 独立验证，不是运行时或仓库构建依赖。
LZX 的 250-byte 压缩流来自 Windows `makecab` LZX:15，对固定时间
`2020-01-02 03:04:06` 的同一 `payload.pdf` 连续生成两次均得到上述 archive
哈希；生成器输出又与 `makecab` 产物逐字节相同。临时工具身份为
`makecab.exe` SHA-256
`070a98b4f7c03f99048a10f490d5916a9a98417e0d0de2c414c76b3dd00cb35e`
及 `expand.exe` SHA-256
`e5cd2d9536b0729ce90368dce9d923dccfa6f75f2996e31bb349e6a75a2aa897`；
`expand` 还原结果为 331 bytes、SHA-256
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。
同一 `expand.exe` 也将生成的 124-byte Quantum CAB 还原为 59-byte
`If you can read this, the Quantum decompressor is working!\n`，SHA-256
为 `bdcfdaf09e54d61f950b165b201d4ad5f5acfdecff1fc5641e382aa382c74b45`；
该值还与固定 libmspack 回归测试中的 MD5
`98fcfa4962a0f169a3c7fdbcb445cf17` 对应。
两者只用于一次性生成/独立验证，不是测试或运行时依赖。
生成器测试逐字节复验 size/hash，使用 Python 标准库及固定 `pyppmd`
与 `inflate64` 独立解压既有压缩 stream，并独立检查 BCJ2 coder graph、
LZMA2 main、call/jump/range stream 与 E8/E9/JCC 地址逆变换，
并检查格式头、7Z Start/Next Header CRC、RAR header CRC、CAB size/压缩类型；
LZX case 还逐字节固定 archive 哈希、`0x0f03` method/window、CFDATA checksum
和 250-byte 压缩流；
Quantum case 固定 `0x1222` method/level/window、48-byte 来源切片、生成 archive
哈希及明文 MD5；
BCJ+LZMA2 使用同一标准 filter 链独立还原，MSZIP 的 `CK` + raw deflate 数据
由 Python `zlib` 独立还原。ARM64 case 的 BL 正向/逆向向量固定为
`0x94000002 → 0x94000055 → 0x94000002`，ADRP 向量固定为
`0x90000001 → 0xB0000001 → 0x90000001`，并证明 LZMA2 解压后得到已转换字节；
ISO9660 检查 sector size。

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
| 7Z Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/x86 BCJ+LZMA2 | `Binary / 7-Zip` | 0 Stream | 1 × 331-byte `PDF / Stream` |
| 7Z BCJ2+LZMA2 no-branch | `Binary / 7-Zip` | 0 Stream | 1 × 331-byte `PDF / Stream` |
| 7Z BCJ2 E8+LZMA2 | `Binary / 7-Zip` | 0 Stream | 1 × 336-byte `PDF / Stream` |
| 7Z BCJ2 E9+LZMA2 | `Binary / 7-Zip` | 0 Stream | 1 × 336-byte `PDF / Stream` |
| 7Z BCJ2 JCC+LZMA2 | `Binary / 7-Zip` | 0 Stream | 1 × 337-byte `PDF / Stream` |
| 7Z Deflate64 distance-32769 | `Binary / 7-Zip` | 0 Stream | 1 × 32772-byte `PDF / Stream` |
| 7Z ARM64-BCJ+LZMA2 BL/ADRP | `Binary / 7-Zip` | 0 Stream | 1 × 4100-byte `PDF / Stream` |
| RAR4 store | `RAR / Unknown` | 0 Stream | 1 × `PDF / Stream` |
| CAB Store/MSZIP | `Binary / CAB` | 0 Stream | 1 × `PDF / Stream` |
| CAB LZX:15 | `Binary / CAB` | 0 Stream | archive: 0；aggressive: 1 × 331-byte `Binary / Unknown` |
| CAB Quantum 18 | `Binary / CAB` | 0 Stream | archive: 0；aggressive: 1 × 59-byte `Binary / Unknown` |
| ISO9660 | `ISO 9660 / Unknown` | 0 Stream | 1 × `PDF / Stream` |

Deflate64、ARM64 与 BCJ2 E8/E9/JCC case 的 child size 分别为字符串
`"32772"`、`"4100"`、`"336"`、`"336"` 和 `"337"`，
其余已支持正例都是 `"331"`；
规则检测名严格为
`["PDF", "HeaderComment"]`。每个样本的 `default == release_default`，
除 LZX/Quantum 外均有 `archive == archive_aggressive`；这两个 CAB case 的
两种 archive 模式明确不相等。比较对象是未经规范化的 stdout/stderr 原始
字节，不只是摘要。

完整 76 次执行的原始 stream 以 SHA-256 为键，经 `zlib+base64` 去重嵌入报告；
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

本实验只证明七种 7Z 单 coder、x86 BCJ+LZMA2、BCJ2+LZMA2
无分支/E8/E9/JCC filter 链、ARM64-BCJ+LZMA2
的 BL/ADRP 分支、RAR4 store、CAB Store/MSZIP 与 ISO9660 的合法单成员正例，
以及 CAB LZX/Quantum 普通/激进模式的失败边界，
不证明：

- 通用 Archive 的自动/强制分派见
  [`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)；
  NPM 的直接检测、公共自动回退和强制分支见
  [`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)；
- 7Z AES 及 BCJ2 与 AES 的组合；
- RAR 的压缩方法、ISO9660 扩展，以及
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
