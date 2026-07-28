# 上游 archive/resource/overlay 嵌套扫描行为

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-28

## 结论

固定版本的发布 `diec` CLI 中，`-r` / `--recursivescan` 不负责目录递归，也
不启用 archive 成员提取。它启用单个文件内部的 resource 和 overlay 扫描：

- 默认模式不扫描 PE resource 或 overlay；
- `--recursivescan` 将可扫描的 resource 以及任何 overlay 作为 subdevice
  扫描，并在父记录的 `values` 中输出嵌套 detection；
- `--aggressivecscan` 单独使用不启用任何 file-part 扫描；
- `--recursivescan --aggressivecscan` 对可识别 resource 与单独 recursive
  相同；对无法被格式探测器识别的 resource，aggressive 会越过
  `isScanable()` 过滤并按 `Binary` 扫描；
- 顶层 ZIP 和 ZIP overlay 均不会因 `--recursivescan` 被解包。archive 提取
  需要独立的 engine 选项 `bIsArchivesScan`，发布 CLI 没有设置它。

8 个确定性样本、4 种模式在固定 qmake/CMake 两个 oracle 上共运行 64 次。
每次退出码均为 `0`、stderr 为空，两个构建的退出码及原始 stdout/stderr
逐字节相同。

其中 `RT_MANIFEST` 样本另以专用 probe 保存固定 CMake Qt 5 CLI 的完整 raw
stdout 与规范化树；通用双 oracle 报告确认 qmake 输出逐字节相同。它把
resource type ID、子设备 file-part、scan ID、重新探测和原样 Binary 规则连接成
一条端到端证据链：仅 recursive+aggressive 产生 `Binary / Resource` 子记录，
并由 `win_resources.1.sg` 输出 `Format: Manifest[Resources]`。

另用只替换发布 CLI `main` 的 engine harness 运行 7 个样本 × 8 种
archive/recursive/aggressive 组合，并将其中 4 个不含 archive 的模式逐字节
对照发布 CMake oracle。56 次 harness 执行及 28 次发布对照全部通过。

同一固定 harness 的补充格式实验还运行七种 7Z 单 coder、x86/ARM64
BCJ+LZMA2、BCJ2+LZMA2 no-branch/E8/E9/JCC filter 链、RAR4 store、CAB
Store/MSZIP 与 ISO9660 共十七个项目生成的单 PDF 样本。十七者 default 均与发布
CLI 原始输出相同且不展开；
显式 archive 后各产生一个 PDF Stream child，archive+aggressive 与 archive
逐字节相同。7Z/CAB 顶层仍分别为 `Binary / 7-Zip` 和 `Binary / CAB`，不能把
展示 filetype 当作 adapter 选择条件。完整报告见
[`archive-format-behavior.md`](archive-format-behavior.md)。
同一实验中的第十八个 CAB LZX:15 样本在普通 archive 下无 child，
archive+aggressive 下产生 331-byte `Binary / Unknown` Stream，不能归入上述
正向解包集合。第十九个 CAB Quantum 18 样本具有相同模式边界，但 aggressive
child 为 59-byte `Binary / Unknown`；独立解码器已证明其合法明文。
第二十个 7Z LZMA2+AES 样本在公共 archive 与 archive+aggressive 下均因
没有密码入口而不产生 child；直接 `XSevenZip` harness 的正确密码能还原
331-byte PDF，缺失与错误密码都返回 0-byte 失败输出。
第二十一个官方 BCJ2+LZMA2+4×AES 样本也在公共路径无 child；直接 harness
即使传入正确密码仍返回 `unpacked=false` 和 0-byte 输出，而固定 7-Zip
26.02 对同一归档验证成功。
第二十二、二十三个 x86 BCJ+LZMA2+AES 与 ARM64 BCJ+LZMA2+AES 样本在
公共路径同样无 child；直接 harness 的正确密码均还原 331-byte PDF，
缺失/错误密码失败。
第二十四至二十九个 Copy/LZMA/PPMd7/BZip2/Deflate/Deflate64+AES 样本
补齐七种基础 coder+AES 矩阵：公共路径均无 child，直接正确密码均还原
331-byte PDF，缺失/错误密码均报告失败；Copy 与 PPMd7 的错误密码仍分别
留下 331-byte 非认证输出。

## 三层能力边界

必须区分发布 CLI、`XScanEngine` 的通用 console 包装器和 engine API：

| 层 | recursive | resource | overlay | archive |
| --- | --- | --- | --- | --- |
| 发布 `src/console/main_console.cpp` | 暴露 `-r` | 由 recursive 间接启用 | 由 recursive 间接启用 | 不可达 |
| `XScanEngineConsole` 辅助类 | 暴露 | 独立选项 | 独立选项 | 独立选项 |
| `SCAN_OPTIONS` | `bIsRecursiveScan` | `bIsResourcesScan` | `bIsOverlayScan` | `bIsArchivesScan` |

发布入口只在
[`main_console.cpp#L299`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp#L299)
设置 `bIsRecursiveScan`，没有注册或赋值后三个独立选项。组件内的
[`xscanengineconsole.cpp#L149-L156`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengineconsole.cpp#L149-L156)
不能当作发布 `diec` 的参数契约。

因此 Rust 项目若同时追求 CLI 兼容与完整 engine 能力，必须分别定义：

- 上游 CLI 的可达行为；
- 核心 API 中 archive/resource/overlay 的独立控制；
- 将来是否为 Rust CLI 增加上游发布 CLI 没有的显式选项。后者属于产品设计
  决策，不是本调研结论。

## 上游递归流程

所有嵌套路径都位于
[`XScanEngine::scanProcess()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2832)
中，并被 `!bCollection` 包围。

### Archive

archive 分支只在 `bIsArchivesScan` 为真时进入，且只将 ZIP、7Z、RAR、CAB 和
ISO9660 视为可解包类型。流程为：

1. `initUnpack()`；
2. 从 entry 声明的 uncompressed size 创建完整 file buffer；
3. `unpackCurrent()`；
4. aggressive 时无条件扫描，否则先探测成员类型并只扫描
   `isScanable()` 的成员；
5. 将成员标记为 `FILEPART_STREAM`，保留 stream offset、size、original name
   和 handler info，再递归调用 `scanProcess()`。

源码中的 `nLimit` 默认值为 20，aggressive 时为 100000；循环本身还有
`i < 100000` 上限。默认分支在扫描后用 `nCurrentIndex > nLimit` 判断。22
个 PDF 成员的运行实验确认默认实际输出 21 个 `Stream`，aggressive 输出全部
22 个。aggressive 的更高边界仍受循环硬上限限制，最多访问 100000 个 entry。

分配发生在成员类型过滤之前，且按 archive 声明的解压后大小创建 buffer。
此处没有观察到总解压字节数、单成员大小或压缩比限制，是后续安全设计必须
处理的压缩炸弹和内存耗尽风险。

### Resource 与 overlay

[`xscanengine.cpp#L2932-L3014`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2932-L3014)
先收集最多 10000 个 resource，再收集最多 1 个 overlay：

- resource 条件是 `bIsResourcesScan || bIsRecursiveScan`；
- overlay 条件是 `bIsOverlayScan || bIsRecursiveScan`；
- 每个合法 file part 以原文件 offset/size 创建 `SubDevice`；
- overlay 始终扫描；
- resource 在 aggressive 下始终扫描，否则只扫描 `isScanable()` 类型；
- resource 的 `nLimit` 默认 20、aggressive 为 2000。条件使用
  `nCurrentIndex <= nLimit`，且计数只在实际扫描后增加。22 个 PDF resource
  的发布 CLI 实验确认默认输出 21 个 `Resource`；三组合法 resource directory
  的 2002 项实验确认 aggressive 精确输出 2001 个。PE parser 本身要求每层
  directory 不超过 1000 项。overlay 不受该判断约束。详见
  [`scan-option-boundaries.md`](scan-option-boundaries.md)。

PE 的 resource 由
[`XPE::getFileParts()`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/exec/xpe.cpp#L11205-L11288)
枚举，记录文件 offset、size、virtual address 和 resource ID。overlay 从
header/section 的最大文件末端到文件末尾，本轮 PE 样本因此得到精确 offset
512。

递归调用复制完整 `SCAN_OPTIONS`，所以 resource/overlay 内还可继续寻找新的
resource/overlay，archive 选项在 engine 调用中也会继续传播。当前源码路径
未见独立的最大嵌套深度计数；终止依赖结构不再产生 file part、各层记录限制
或外部取消状态。

## 确定性语料

[`tools/corpus/generate_nested_corpus.py`](../../tools/corpus/generate_nested_corpus.py)
只从项目生成的最小 PE/PDF 字节构造 8 个样本：

| Sample | 结构 | Size | SHA-256 |
| --- | --- | ---: | --- |
| `pdf-member.zip` | ZIP → PDF | 453 | `508af7b74ab36708e185da3a60c6e8307a39424b10b534e1165ad11bd0a665e0` |
| `nested-zip.zip` | ZIP → ZIP → PDF | 569 | `812f26268314d51a47dd7a9aa97d20398d48f464740f4157dd916e4d85172149` |
| `many-pdf-members.zip` | ZIP → 22 × PDF | 9548 | `65ecf2baaecc114a11c2a76cbbd0a42d909ca274a506bc1793673a3144740b9b` |
| `pe-pdf-overlay.exe` | PE → overlay → PDF | 843 | `315f3a0e55ef32aed2d03b5330602dd45cbd81c50db527a68bdd65d8a6475f7b` |
| `pe-pdf-resource.exe` | PE → RT_RCDATA resource → PDF | 1024 | `679124ef09b88eeb9edc29e2ee7165f3dbaf4e17b9d988b548c51cf8d4d1482b` |
| `pe-many-pdf-resources.exe` | PE → 22 × RT_RCDATA PDF | 9216 | `1eea60ef127f55f19a82568262ed14098972c7f50f462448eb209106592cf568` |
| `pe-manifest-resource.exe` | PE → RT_MANIFEST → unclassified binary | 1024 | `0a973cbde2f520bdbd6e1b75304e4a412462113d4de9a8139cdf997af16641ee` |
| `pe-zip-overlay.exe` | PE → overlay → ZIP → PDF | 965 | `5e2b2da6d29fb18b638dc696524b1a045bd1748a59944cf2f97c388e2e0c3075` |

ZIP 使用 store method、单成员、固定 DOS 时间字段，不存在高压缩比或动态元数据。
PE resource 使用标准三层 type/name/language directory。PDF resource 类型为
RT_RCDATA（ID 10）；Manifest resource 类型为 RT_MANIFEST（ID 24），内容是
20 字节项目生成的未分类二进制；两者 payload 均位于文件 offset 608。仓库只提交生成器及
[`data/nested-corpus.json`](data/nested-corpus.json)，不提交二进制。

生成命令：

```sh
python3 tools/corpus/generate_nested_corpus.py /tmp/diec-nested-corpus
```

## 运行结果

| Sample | 默认/仅 aggressive | recursive/recursive+aggressive |
| --- | --- | --- |
| `pdf-member.zip` | 顶层 ZIP Unknown | 完全相同；不提取 PDF |
| `nested-zip.zip` | 顶层 ZIP Unknown | 完全相同；不提取 inner ZIP |
| `many-pdf-members.zip` | 顶层 ZIP Unknown | 完全相同；不提取 22 个 PDF |
| `pe-pdf-overlay.exe` | PE32 Unknown | 增加 PDF Overlay，offset 512、size 331 |
| `pe-pdf-resource.exe` | PE32 Unknown | 增加 PDF Resource，offset 608、size 331 |
| `pe-many-pdf-resources.exe` | PE32 Unknown | recursive 增加 21 个 PDF Resource；recursive+aggressive 增加 22 个 |
| `pe-manifest-resource.exe` | PE32 Unknown | recursive 因内容不可识别而跳过；recursive+aggressive 增加 Binary Resource，并报告 Manifest |
| `pe-zip-overlay.exe` | PE32，顶层规则报告 Zip archive | 增加 ZIP Overlay，offset 512、size 453；不提取 PDF |

嵌套 detection 直接放在父 detection 的 `values` 数组中。PDF 子记录保留其
两条规则结果：`Format: PDF(1.4)` 和上游拼写
`Complier: HeaderComment(e2e3cfd3)`。这不是平铺列表，差分规范化不得丢弃
父子关系、`parentfilepart`、offset 或 size。

原始 stdout 哈希如下。每个样本的“仅 aggressive”与 default 相同，
“recursive+aggressive”与 recursive 相同；所有 stderr SHA-256 都是空内容
哈希 `e3b0c442...b855`。

| Sample | default stdout SHA-256 | recursive stdout SHA-256 |
| --- | --- | --- |
| `pdf-member.zip` | `c44a38d6ce556ea5566f31cbc79383b496c94e7de2b94f9f91b39a84333cca8a` | 同 default |
| `nested-zip.zip` | `799ea3bf745faaa98eded46e38a72b7071b71ac7fec67743b4ce1f8e1b132e64` | 同 default |
| `many-pdf-members.zip` | `04898e9f7aaeed9c80690882fc0930f53327575d2a4b633e9227a1c15caa1a53` | 同 default |
| `pe-pdf-overlay.exe` | `971925ae03163e822dd574e2375344a2b666c43527ec65cc1ad8448787b6529d` | `5da6c91da7dec687207781d752f538c7bf7a546c5167ff0b82c8cc5a0c55310d` |
| `pe-pdf-resource.exe` | `94941d54fe62e2c43a0709062c7628eb2fa26d7fda825dc366547a4dc85a8f8b` | `4707bde3cda1f7d47d7f7b7e34b4af90a97f11abdc0f6fac5dfbd1a5edde7db4` |
| `pe-many-pdf-resources.exe` | `f184ce3c75aa41d215fc29eec8ded6c3fb24fe178f3ad647232b65502fa7a52a` | `093ee24d820d55662090bda88088f08c52ff5af66b01619d9569cc9b1097753b`；aggressive 为 `60eec7e0c60d5cf85dfc5129e5c821bc6c8137af7a4f9cf8a8ae8cef4349b530` |
| `pe-manifest-resource.exe` | `94941d54fe62e2c43a0709062c7628eb2fa26d7fda825dc366547a4dc85a8f8b` | 同 default；recursive+aggressive 为 `c9e8a5c7f3eab49f1f8b533917aba24abebc9f1f05128bf4a359bedbeffab7fa` |
| `pe-zip-overlay.exe` | `2df1e81416610a0e4d678b7b816358cf4b2fc8dbd7b6a379a6ed54bc6ec440dd` | `a9bb31663ca8aca9669dcd97298265cd07d76a86ea91f7c986a3d7ad7b0cd012` |

## 复现

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --nested-corpus-dir /tmp/diec-nested-corpus
```

工具先验证 manifest 的 size/SHA-256 和 generator identity，再将目录只读挂载
为 `/nested`。报告保留每次运行的原始字节哈希、双 oracle 差分、相对 default
变化以及只抽取稳定字段的 detection tree；稳定字段摘要不参与相等判定。

Manifest 端到端链使用专用 probe，并同时保存完整 raw stdout 与规范化树：

```sh
python3 tools/upstream/probe_resource_context_chain.py \
  --image diec-rust/upstream-oracle-cmake:74eaf505 \
  --binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --nested-corpus-dir /tmp/diec-nested-corpus \
  --baseline docs/research/data/resource-context-chain-qt5.json
```

基线 SHA-256 为
`56090cee25f736eeb1c1fbb90a1619199f0fc2a93c7c318c0731ddffb585de64`。
它固定 child offset `608`、size `20`、file type `Binary`、
parent file-part `Resource` 以及 `format / Manifest / "" / Resources` 的完整
可观察输出。

## Engine archive harness

[`archive_harness_main.cpp`](../../tools/upstream/archive_harness_main.cpp)
直接实例化上游 `DiE_Script`，设置与发布 CLI 相同的规则路径、显示字段、排序
和 JSON formatter，仅增加 `--archive` 到 `bIsArchivesScan` 的映射。
[`Dockerfile.archive-harness-qt5`](../../tools/upstream/Dockerfile.archive-harness-qt5)
基于固定 CMake oracle image，复用同一 target 已编译的所有上游对象和链接命令，
只用该 harness object 替换 `main_console.cpp.o`。它不修改上游 subtree，也不
复制扫描、解包或渲染实现。

| Provenance | SHA-256 / value |
| --- | --- |
| Parent image | `diec-rust/upstream-oracle-cmake:74eaf505` |
| Dockerfile | `2ae4695c9e63857c263dc2d35978dbccc3d4d5f7b65dc20c7424472a1728bf8f` |
| Harness source | `bd67e06915809d5f9a8065f1d3471a1c9f44d614e1f7d5f176a691088dc6e86d` |
| Local image ID | `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc` |
| Harness binary | `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e` |
| Reused release binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| OCI revision label | `74eaf505c250ab47e709024e9dc41657cd8f2254` |

构建命令：

```sh
docker build \
  --provenance=false \
  --file tools/upstream/Dockerfile.archive-harness-qt5 \
  --tag diec-rust/upstream-archive-harness:74eaf505 \
  tools/upstream
```

自动探针：

```sh
python3 tools/upstream/probe_archive_harness.py \
  --harness-image diec-rust/upstream-archive-harness:74eaf505 \
  --harness-binary /opt/die-build/src/console/diec-archive-harness \
  --release-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --release-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --nested-corpus-dir /tmp/diec-nested-corpus
```

探针对每个样本运行 default、archive、aggressive、archive+aggressive、
recursive、recursive+aggressive、archive+recursive 及三者组合。所有不含
archive 的 28 次 harness 输出都与发布 CMake CLI 对应模式逐字节相同。

关键 engine 结果：

| 输入/模式 | Stream | Resource | Overlay | 结果 |
| --- | ---: | ---: | ---: | --- |
| ZIP→PDF / archive | 1 | 0 | 0 | PDF 成为 Stream |
| ZIP→ZIP→PDF / archive | 2 | 0 | 0 | archive flag 跨层传播 |
| 7Z Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64/x86 BCJ+LZMA2/BCJ2+LZMA2 no-branch/E8/E9/JCC/ARM64-BCJ+LZMA2 BL/ADRP、RAR4 store、CAB Store/MSZIP、ISO→PDF / archive | 1 | 0 | 0 | 十七个 coder/container 样本各产生一个 PDF Stream |
| CAB LZX:15 / archive | 0 | 0 | 0 | 合法成员未解包 |
| CAB LZX:15 / archive+aggressive | 1 | 0 | 0 | 331-byte Binary/Unknown Stream |
| CAB Quantum 18 / archive | 0 | 0 | 0 | 合法成员未解包 |
| CAB Quantum 18 / archive+aggressive | 1 | 0 | 0 | 59-byte Binary/Unknown Stream |
| 22 PDF ZIP / archive | 21 | 0 | 0 | 确认默认 off-by-one |
| 22 PDF ZIP / archive+aggressive | 22 | 0 | 0 | 全部成员 |
| 22 PDF resources / recursive | 0 | 21 | 0 | 确认默认 off-by-one |
| 22 PDF resources / recursive+aggressive | 0 | 22 | 0 | 全部 resources |
| PE→ZIP overlay→PDF / archive+recursive | 1 | 0 | 1 | Overlay 下继续 archive |

22 成员 archive 的 stdout SHA-256 分别为
`bfe44c29274a3f34e40d9656ad7d239b909d19104e95dfd80d45cb163cc87ef5`
和 aggressive 的
`fcd0bb31b05a7d3452614a63f7277cc8749858ca2b6e953b119953946a81b1b6`。

独立 context-rule oracle 又证明：当 scanner 已经提供
`FILEPART_RESOURCE + scan ID 24` 或 `FILEPART_DEBUGDATA + RSDS bytes` 时，
固定 `win_resources.1.sg` 与 `debug_data_debugData.1.sg` 分别产生 Manifest
resource 和 PDB link detection，Rust 规则 spike 与 Qt5 8/8 一致。该实验只验证
“subdevice context → 规则结果”；本页 engine/CLI harness 才验证父对象枚举与
层级输出。两者尚未合并为同一条端到端 Rust 扫描链。

Manifest 专用 CLI oracle 已把上述两段的 resource 路径合并为单一上游端到端
链。固定源码审计进一步区分 debug-data 的“格式层可枚举”和“普通 engine
不调度”：

- `Formats@1151e725...` 的 `XPE::getFileParts()` 在
  `xpe.cpp:11244-11261` 可生成 `FILEPART_DEBUGDATA`；
- `XScanEngine@dfe4a419...` 的完整 `xscanengine.cpp` SHA-256 为
  `e088bebb...61b498`，其中 `FILEPART_DEBUGDATA` 出现次数为 `0`；
- 普通 `scanProcess()` 在 `xscanengine.cpp:2935,2939` 只请求 resource 和
  overlay；resource ID 在 `:2990` 写入 `sScanID`，并在 `:2995` 调度 child。

可重复审计由
[`probe_subdevice_source_audit.py`](../../tools/upstream/probe_subdevice_source_audit.py)
生成 [`subdevice-source-audit.json`](data/subdevice-source-audit.json)，基线
SHA-256 为
`9e521017baeb15ae8331c931b30ad6905e932aa6b69556b81566b5e09e9a3652`。
因此不能把 `debug_data_debugData.1.sg` 的直接 context 正例误写成发布 scanner
可达性；若 Rust legacy-compatible 默认扫描额外调度 debug-data，会形成上游
没有的 detection，属于可观察兼容差异。

后续 paired oracle 已用同一项目生成 PE 闭合这条负向链：Formats 同时枚举
offset 608 的 Manifest resource 与 offset 1088 的 RSDS debug data；public
recursive+aggressive 对前者产生 Manifest child，对后者不建 child；把后者的
原始 38 bytes 直接置于 `FILEPART_DEBUGDATA` context 时，原样 debug rule 产生
`PDB file link / 7.0`。完整证据见
[`debug-data-dispatch-behavior.md`](debug-data-dispatch-behavior.md) 和
[`debug-dispatch-engine-qt5.json`](data/debug-dispatch-engine-qt5.json)。

## 尚未覆盖

- ZIP deflate/ZipCrypto 无密码、CRC/压缩流/offset/method 畸形、local fallback
  和 path metadata 首轮矩阵见
  [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)；
  7Z/RAR/CAB/ISO9660 解包错误、其他 encrypted entry、重复名称和系统化
  metadata 仍缺；
- archive aggressive 第 100000 条可达、第 100001 条不可达，见
  [`archive-iteration-boundary.md`](archive-iteration-boundary.md)；
  resource aggressive 2001 实际 child 边界也已固定；
- 更深的 resource/overlay/archive 链及实际最大栈深、取消、超时和内存峰值；
- 非 PE 格式的 overlay；
- Rust scanner 从父格式枚举 resource、生成 scan ID、调度规则并形成与 Qt5
  一致的结果树；本页已固定 debug-data 的 legacy 默认不调度契约，但 Rust
  实现尚未开始；
- formatter 的嵌套表示已由
  [`cli-output-boundaries.md`](cli-output-boundaries.md) 固定：JSON/text
  保留树或缩进，CSV/TSV 仅深度优先输出 leaf，nested XML 会生成非法动态标签；
- Windows/macOS 与 Qt 6 oracle。

archive 的源码限制不等于已验证的安全保证。后续 engine harness 应先使用受控、
低压缩比语料验证行为，再单独用隔离资源限制测试恶意声明长度和压缩炸弹。
