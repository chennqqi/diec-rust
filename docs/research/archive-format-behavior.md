# 7Z coder/filter/AES、RAR4、CAB Store/MSZIP/LZX/Quantum 与 ISO9660 archive 解包行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 engine harness 对四十一个可追溯样本给出可重复结果：

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
- 7Z LZMA2+AES 在公共 engine 的 archive 与 archive+aggressive 模式均不产生
  child，并逐字节输出
  `[XAESDecoder] Password is required for AES decryption`；公共 archive
  分支向 `initUnpack` 传入空属性 map，当前 `SCAN_OPTIONS` 无密码入口；
- 同一固定归档经直接 `XSevenZip` harness 传入正确密码 `DetectItEasy` 后，
  解出 331-byte PDF；缺失密码和错误密码均返回 `unpacked=false`、0-byte
  输出；
- Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 七种基础 coder 与
  7zAES 的完整矩阵在公共 engine 路径均因无密码无 child；直接 harness
  的正确密码均还原 331-byte PDF，缺失和错误密码均返回
  `unpacked=false`。其中 Copy 与 PPMd7 的错误密码仍分别留下 331-byte
  非认证输出，SHA-256 为 `d427e6be...fb0274` 与
  `3404ad64...76f042`，其余五种错误密码输出为空；
- 官方 7-Zip 生成的 `BCJ2 + LZMA2 + 4×7zAES` archive 可由 7-Zip 自身用
  正确密码验证，但固定 DIE 即使经直接 harness 传入同一正确密码也返回
  `unpacked=false`、0-byte 输出并打印 password-required 诊断；公共 archive
  路径同样无 child；
- 官方 x86 BCJ+LZMA2+AES 与 ARM64 BCJ+LZMA2+AES archive 在公共路径同样
  因无密码无 child，但直接 harness 的正确密码均成功还原 331-byte PDF；
  缺失与错误密码失败；
- 上游 `unpackImplemented()` 声明的 x86 BCJ/ARM64 两种 filter × 七种基础
  coder × 7zAES 简单序列矩阵已全部覆盖：新增十二种组合均经官方 7-Zip
  正确密码自测并由固定 DIE 还原 canonical PDF；公共路径仍因无密码无 child。
  Copy 与 PPMd7 组合的错误密码仍留下 331-byte 非认证输出，其余组合输出为空；
- 7Z 与 CAB 的顶层 `filetype` 都是 `Binary`，顶层规则检测名分别是
  `7-Zip` 与 `CAB`，但 archive adapter 仍可展开成员；不能由顶层展示类型
  直接推断内部 archive 分派失败；
- harness 默认模式与使用同一数据库的固定发布 CLI 原始 stdout/stderr
  逐字节相同。

这组结果增加了 7Z 七种单 coder、x86 BCJ+LZMA2、BCJ2+LZMA2
无分支及 E8/E9/JCC filter 链与
ARM64-BCJ+LZMA2 BL/ADRP 分支、RAR4 store、CAB Store/MSZIP 与 ISO9660 的正向
corpus 证据，并固定 7Z 七种基础 coder+AES 及完整 x86/ARM64
filter × 七种基础 coder × AES 的成功密码契约、
BCJ2+AES 官方图的失败边界
以及 CAB
LZX/Quantum 的未实现/激进扫描 quirk，但不关闭
`CAP-GAP-006`。NPM 分派已由独立的直接/自动/强制实验固定，见
[`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)；通用 Archive
分派现由
[`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)
固定；archive aggressive 100000 精确边界现由
[`archive-iteration-boundary.md`](archive-iteration-boundary.md) 固定，
ZIP deflate/ZipCrypto/CRC/压缩流畸形与 1 MiB 高压缩比现由
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md) 固定；
7Z/RAR4/CAB/ISO9660 的 26-case EOF 前缀阶梯由
[`archive-truncation-behavior.md`](archive-truncation-behavior.md) 固定；
同四格式的 33-case CRC/size/offset/method/record-field 突变由
[`archive-structure-behavior.md`](archive-structure-behavior.md) 固定；
RAR 的压缩算法、结构字段极值/组合、资源耗尽及跨平台行为仍未验证。

机器报告是
[`archive-format-engine-qt5.json`](data/archive-format-engine-qt5.json)，
SHA-256 为
`d27ee4aa9c03be0939d495e6b9ab062f669f123eeff36ccfac16062d3089a784`。
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
- `sevenzip_aes_public_engine_has_no_password_and_no_child`
- `sevenzip_aes_direct_correct_password_reaches_payload`
- `sevenzip_aes_direct_missing_and_wrong_password_fail`
- `sevenzip_base_aes_public_engine_has_no_password_and_no_child`
- `sevenzip_base_aes_direct_correct_password_reaches_payload`
- `sevenzip_base_aes_missing_and_wrong_password_fail`
- `sevenzip_copy_and_ppmd7_aes_wrong_password_leave_output`
- `sevenzip_bcj2_aes_public_engine_has_no_password_and_no_child`
- `sevenzip_bcj2_aes_direct_correct_password_still_fails`
- `sevenzip_bcj2_aes_missing_and_wrong_password_fail`
- `sevenzip_filter_aes_public_engine_has_no_password_and_no_child`
- `sevenzip_filter_aes_direct_correct_password_reaches_payload`
- `sevenzip_filter_aes_missing_and_wrong_password_fail`
- `sevenzip_filter_base_aes_matrix_public_engine_has_no_password_and_no_child`
- `sevenzip_filter_base_aes_matrix_direct_correct_password_reaches_payload`
- `sevenzip_filter_base_aes_matrix_missing_and_wrong_password_fail`
- `sevenzip_filter_copy_and_ppmd7_aes_wrong_password_leave_output`
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
| 镜像 | `diec-rust/upstream-sevenzip-password-harness:74eaf505` |
| 镜像 ID | `sha256:adf8e09f3ed7c15a54f3486c482599e1bcb122308a0b27396de1baf2ee634daf` |
| Harness binary | `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e` |
| Direct password harness | `af3566c9c3a554f0769a3c582ebc2eb116e74560cbd6f3f3b03e4d006cc98baa` |
| Release binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| Fixture manifest | `4ba3b9e9bac2a449e603156d51b2ad32e6a8b87d48a0eb94f99581ab5325d555` |

Harness 只替换 console `main`，扫描、数据库加载、解包和 formatter 均复用固定
镜像中的上游对象。源码和构建入口分别为
[`archive_harness_main.cpp`](../../tools/upstream/archive_harness_main.cpp) 与
[`Dockerfile.archive-harness-qt5`](../../tools/upstream/Dockerfile.archive-harness-qt5)；
报告同时绑定它们以及两个 fixture generator 的 SHA-256。
PPMd7 生成与 Deflate64 独立验证的工具依赖清单也由报告绑定。
直接密码 harness 只调用同一镜像内的 `XSevenZip` public API，源码和派生镜像
入口分别为
[`sevenzip_password_harness_main.cpp`](../../tools/upstream/sevenzip_password_harness_main.cpp)
与
[`Dockerfile.sevenzip-password-harness-qt5`](../../tools/upstream/Dockerfile.sevenzip-password-harness-qt5)。

报告还绑定固定镜像内以下上游源码，不从相邻格式外推：

| 组件 | 镜像内路径 | SHA-256 | 固定符号/条件 |
| --- | --- | --- | --- |
| Engine archive branch | `/opt/die-source/XScanEngine/xscanengine.cpp` | `e088bebb...61b498` | `FT_ZIP / FT_7Z / FT_RAR / FT_CAB` 条件 |
| 7Z adapter | `/opt/die-source/XArchive/xsevenzip.cpp` | `d8da44bd...8e5554` | `XSevenZip::initUnpack`、Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 method table 及 BCJ/ARM64-BCJ filter table |
| 7Z AES mapping/sequences | `/opt/die-source/XArchive/xsevenzip.cpp` | `d8da44bd...8e5554` | codec `06 F1 07 01` → `HANDLE_METHOD_7Z_AES`，并注册 method/filter/BCJ2 + AES 序列 |
| 7Z AES decrypt | `/opt/die-source/XArchive/xdecompress.cpp` | `4f52eefa...2728d` | 读取 `UNPACK_PROP_PASSWORD` 并调用 `XAESDecoder::decrypt` |
| Engine unpack properties | `/opt/die-source/XScanEngine/xscanengine.cpp` | `e088bebb...61b498` | 公共 archive 分支构造空 `mapProperties` 后传给 `initUnpack` |
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
使用项目生成结构并复用固定 331-byte PDF payload；外部内容输入只有下述
48-byte Quantum 压缩流，AES archive 则由固定工具生成后以常量冻结。仓库不保存
原始第三方 archive。仓库保存生成器和
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
| `pdf-member-lzma2-aes.7z` | 7Z LZMA2 → 7zAES → `payload.pdf` | 338 | `07c1603dde5df154731333c94f8eba472f792a036bbb1cac566b2a9233afa21e` |
| `pdf-member-copy-aes.7z` | 7Z Copy → 7zAES → `payload.pdf` | 466 | `6af39a3f4d30d461b3f64ee62f21437b17c114a6a21c542b09c92c6f31388ff1` |
| `pdf-member-lzma-aes.7z` | 7Z LZMA → 7zAES → `payload.pdf` | 354 | `24f4b82d99ccf45ce6360ed6597c1dafd8f650f373a1fad8aa8585d463b9e886` |
| `pdf-member-ppmd7-aes.7z` | 7Z PPMd7 → 7zAES → `payload.pdf` | 322 | `a853a9866a5a04dc76ece82557a8f1cab8b64db1b0365347736272366e632c07` |
| `pdf-member-bzip2-aes.7z` | 7Z BZip2 → 7zAES → `payload.pdf` | 370 | `6a5368372ea5432c083f28bba92afaf29435ef9e5a2d2b9e6cbc3c0a79ea2ddd` |
| `pdf-member-deflate-aes.7z` | 7Z Deflate → 7zAES → `payload.pdf` | 338 | `79d2717de13d0c8c546aa38d8c5d078021416830bf288fb20ca5b93f347bcf11` |
| `pdf-member-deflate64-aes.7z` | 7Z Deflate64 → 7zAES → `payload.pdf` | 338 | `4bfd81b77656f041ddf260bc09387965e4fdd2090bc659a605fa6d0c28cc416e` |
| `pdf-member-bcj2-lzma2-aes.7z` | 7Z BCJ2 + LZMA2 + 4×7zAES → `payload.pdf` | 466 | `65acd90a7e2bc019e328d3084821bdcbaaa75404084773b1ac94b07c7989bd50` |
| `pdf-member-bcj-lzma2-aes.7z` | 7Z x86 BCJ + LZMA2 + 7zAES → `payload.pdf` | 354 | `7eed6f558d94ee89eba36b8e486d094583c31f1227d434af81a47d8c9c1ce857` |
| `pdf-member-arm64-lzma2-aes.7z` | 7Z ARM64 + LZMA2 + 7zAES → `payload.pdf` | 354 | `dcc122a6019de6e1ea0d07bd853a88069f88b5e709da684eb0647bdec43434ea` |
| `pdf-member-bcj-copy-aes.7z` | 7Z x86 BCJ + Copy + 7zAES → `payload.pdf` | 482 | `84c55e8a47336b7f53d5c91e53f367b23f18527e8630e9cabb4fd6f56be33102` |
| `pdf-member-bcj-lzma-aes.7z` | 7Z x86 BCJ + LZMA + 7zAES → `payload.pdf` | 370 | `1894b48a5c0ce50aff6dcb0ca02b94b90277cf93e9ccee2463d2346558300f6d` |
| `pdf-member-bcj-ppmd7-aes.7z` | 7Z x86 BCJ + PPMd7 + 7zAES → `payload.pdf` | 338 | `405279f0dceabf34c131c81c5070c96e7c08c49ebfe440cffaa4fef35187132d` |
| `pdf-member-bcj-bzip2-aes.7z` | 7Z x86 BCJ + BZip2 + 7zAES → `payload.pdf` | 386 | `80e596eae5083e61c04a9bec2384268a75a4566c2cec872ad464ef326341e31c` |
| `pdf-member-bcj-deflate-aes.7z` | 7Z x86 BCJ + Deflate + 7zAES → `payload.pdf` | 354 | `e18f65a20a4adaa63a87b21206e859ac5dfcb13ae701849472d0f209374c739f` |
| `pdf-member-bcj-deflate64-aes.7z` | 7Z x86 BCJ + Deflate64 + 7zAES → `payload.pdf` | 354 | `831e6ab83f7330b72ec9a0d48f9b5d2ce2d5c8a982b38901bcabeb137d7b9dcc` |
| `pdf-member-arm64-copy-aes.7z` | 7Z ARM64 + Copy + 7zAES → `payload.pdf` | 482 | `a25254ee79d5eb8d496eefa6bc6a7179f654d5c951120e6198906a0ea718ac4f` |
| `pdf-member-arm64-lzma-aes.7z` | 7Z ARM64 + LZMA + 7zAES → `payload.pdf` | 354 | `843feea12554d69312240a45ad756c30089678cace1594e9acfae50fc53badce` |
| `pdf-member-arm64-ppmd7-aes.7z` | 7Z ARM64 + PPMd7 + 7zAES → `payload.pdf` | 322 | `31212640b730a062fff0a855e050842810bf9a76b837aea53bcb0019ab87a759` |
| `pdf-member-arm64-bzip2-aes.7z` | 7Z ARM64 + BZip2 + 7zAES → `payload.pdf` | 386 | `e95ffcaea1b94cd592b461d077d60e8377717f84809eced64cd0c7bbca69c482` |
| `pdf-member-arm64-deflate-aes.7z` | 7Z ARM64 + Deflate + 7zAES → `payload.pdf` | 354 | `5e7586388553f33fd2d8d1ac8d25d8c2380ab218b9ae2d09325990e6c858bcc9` |
| `pdf-member-arm64-deflate64-aes.7z` | 7Z ARM64 + Deflate64 + 7zAES → `payload.pdf` | 354 | `a1fd70039a0a3fbb2ec6df78694ec6e44c1337666282a87088abc1d1fb7b4e09` |
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

除 ARM64、Deflate64、BCJ2 E8/E9/JCC 与 Quantum 六个特殊 case 外的三十五个成员使用
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
对四个 BCJ2 archive、CAB LZX 与二十二个 AES archive（密码 `DetectItEasy`）执行
`7zz t` 均报告 `Everything is Ok`。AES archive 由同一工具以固定命令生成；
7zAES 的随机 salt 使重新创建的 archive 字节不确定，因此仓库生成器保存一次
已验证产物的精确 322/338/354/370/386/466/482-byte 常量，而 manifest
固定各自命令、密码、
payload hash、
工具 tarball hash
`41aaba7b1235304ab5aa0624530c67ae829496cd29e875925271efdccc28c03e`
和 binary hash
`1676a968815b92e865bc0ffeecee3fa284ba4402bf23dc2bec2412c4b502e922`。
工具许可证记录为 LGPL-2.1-or-later，并保留其 unRAR 限制与 BSD 组件说明。
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
AES cases 还固定 archive size/hash、AES coder ID 数量、成员名，且断言归档内不出现
PDF 明文字节；
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
| 7Z LZMA2+AES | `Binary / 7-Zip` | 0 Stream | 0 Stream；stderr 明确要求密码 |
| 7Z Copy/LZMA/PPMd7/BZip2/Deflate/Deflate64+AES | `Binary / 7-Zip` | 0 Stream | 0 Stream；stderr 明确要求密码 |
| 7Z BCJ2+LZMA2+4×AES | `Binary / 7-Zip` | 0 Stream | 0 Stream；stderr 明确要求密码 |
| 7Z x86/ARM64 BCJ+LZMA2+AES | `Binary / 7-Zip` | 0 Stream | 0 Stream；stderr 明确要求密码 |
| 7Z x86/ARM64 BCJ × Copy/LZMA/PPMd7/BZip2/Deflate/Deflate64+AES | `Binary / 7-Zip` | 0 Stream | 0 Stream；stderr 明确要求密码 |
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

此外，直接密码 harness 对二十二个 AES archive 各运行缺失、正确与错误密码
三种 case。完整 164 次公共扫描及 66 次直接密码实验的原始 stream 以 SHA-256
为键，经 `zlib+base64` 去重嵌入报告；
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
7Z 七种基础 coder+AES 和完整 x86/ARM64 filter × 七种基础 coder × AES
矩阵的公共无密码与直接正确/缺失/错误密码
边界、官方 BCJ2+LZMA2+4×AES 图在正确密码下仍失败的边界，以及 CAB
LZX/Quantum 普通/激进模式的失败边界，
不证明：

- 通用 Archive 的自动/强制分派见
  [`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)；
  NPM 的直接检测、公共自动回退和强制分支见
  [`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)；
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
与 [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)、
[`archive-truncation-behavior.md`](archive-truncation-behavior.md)、
[`archive-structure-behavior.md`](archive-structure-behavior.md)
共同约束后续 Rust archive 层，但不能替代剩余格式和压力边界实验。
