# 上游 archive/resource/overlay 嵌套扫描行为

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-25

## 结论

固定版本的发布 `diec` CLI 中，`-r` / `--recursivescan` 不负责目录递归，也
不启用 archive 成员提取。它启用单个文件内部的 resource 和 overlay 扫描：

- 默认模式不扫描 PE resource 或 overlay；
- `--recursivescan` 将可扫描的 resource 以及任何 overlay 作为 subdevice
  扫描，并在父记录的 `values` 中输出嵌套 detection；
- `--aggressivecscan` 单独使用不启用任何 file-part 扫描；
- `--recursivescan --aggressivecscan` 在本轮小语料上与单独 recursive
  逐字节相同；aggressive 只改变已启用路径的过滤和计数上限；
- 顶层 ZIP 和 ZIP overlay 均不会因 `--recursivescan` 被解包。archive 提取
  需要独立的 engine 选项 `bIsArchivesScan`，发布 CLI 没有设置它。

7 个确定性样本、4 种模式在固定 qmake/CMake 两个 oracle 上共运行 56 次。
每次退出码均为 `0`、stderr 为空，两个构建的退出码及原始 stdout/stderr
逐字节相同。

另用只替换发布 CLI `main` 的 engine harness 运行 7 个样本 × 8 种
archive/recursive/aggressive 组合，并将其中 4 个不含 archive 的模式逐字节
对照发布 CMake oracle。56 次 harness 执行及 28 次发布对照全部通过。

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
  的发布 CLI 实验确认默认输出 21 个 `Resource`，aggressive 输出 22 个；
  overlay 不受该判断约束。

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
只从项目生成的最小 PE/PDF 字节构造 7 个样本：

| Sample | 结构 | Size | SHA-256 |
| --- | --- | ---: | --- |
| `pdf-member.zip` | ZIP → PDF | 453 | `508af7b74ab36708e185da3a60c6e8307a39424b10b534e1165ad11bd0a665e0` |
| `nested-zip.zip` | ZIP → ZIP → PDF | 569 | `812f26268314d51a47dd7a9aa97d20398d48f464740f4157dd916e4d85172149` |
| `many-pdf-members.zip` | ZIP → 22 × PDF | 9548 | `65ecf2baaecc114a11c2a76cbbd0a42d909ca274a506bc1793673a3144740b9b` |
| `pe-pdf-overlay.exe` | PE → overlay → PDF | 843 | `315f3a0e55ef32aed2d03b5330602dd45cbd81c50db527a68bdd65d8a6475f7b` |
| `pe-pdf-resource.exe` | PE → RT_RCDATA resource → PDF | 1024 | `679124ef09b88eeb9edc29e2ee7165f3dbaf4e17b9d988b548c51cf8d4d1482b` |
| `pe-many-pdf-resources.exe` | PE → 22 × RT_RCDATA PDF | 9216 | `1eea60ef127f55f19a82568262ed14098972c7f50f462448eb209106592cf568` |
| `pe-zip-overlay.exe` | PE → overlay → ZIP → PDF | 965 | `5e2b2da6d29fb18b638dc696524b1a045bd1748a59944cf2f97c388e2e0c3075` |

ZIP 使用 store method、单成员、固定 DOS 时间字段，不存在高压缩比或动态元数据。
PE resource 使用标准三层 type/name/language directory，类型为 RT_RCDATA
（ID 10），PDF 位于文件 offset 608。仓库只提交生成器及
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
| 22 PDF ZIP / archive | 21 | 0 | 0 | 确认默认 off-by-one |
| 22 PDF ZIP / archive+aggressive | 22 | 0 | 0 | 全部成员 |
| 22 PDF resources / recursive | 0 | 21 | 0 | 确认默认 off-by-one |
| 22 PDF resources / recursive+aggressive | 0 | 22 | 0 | 全部 resources |
| PE→ZIP overlay→PDF / archive+recursive | 1 | 0 | 1 | Overlay 下继续 archive |

22 成员 archive 的 stdout SHA-256 分别为
`bfe44c29274a3f34e40d9656ad7d239b909d19104e95dfd80d45cb163cc87ef5`
和 aggressive 的
`fcd0bb31b05a7d3452614a63f7277cc8749858ca2b6e953b119953946a81b1b6`。

## 尚未覆盖

- ZIP/7Z/RAR/CAB/ISO9660 各自的解包错误、encrypted entry、重复名称和 metadata；
- 100000 archive、2000 resource 的 aggressive 上限边界；
- 更深的 resource/overlay/archive 链及实际最大栈深、取消、超时和内存峰值；
- 非 PE 格式的 overlay；
- XML、CSV、TSV 和文本 formatter 的嵌套表示；
- Windows/macOS 与 Qt 6 oracle。

archive 的源码限制不等于已验证的安全保证。后续 engine harness 应先使用受控、
低压缩比语料验证行为，再单独用隔离资源限制测试恶意声明长度和压缩炸弹。
