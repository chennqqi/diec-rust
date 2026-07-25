# 上游 CLI 专用模式行为

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-25

## 范围

本文记录 `diec` 的 `--entropy`、`--info`、`--struct` 和 `--showstructs`
行为。这些选项不经过普通 DIE 规则扫描和 `ScanItemModel` formatter，不能从
普通扫描的 JSON/schema 或输出开关优先级外推。

运行基线为 Linux amd64、Qt 5.15.13 的固定 qmake 与 CMake oracle，来源和构建
环境见
[`upstream-cmake-differential.md`](upstream-cmake-differential.md)。
输入使用
[`data/baseline-corpus.json`](data/baseline-corpus.json)
中的 5 个安全确定性样本：

- `empty.bin`
- `minimal.exe`
- `minimal.pdf`
- `payload.zip`
- `plain.txt`

## 源码调用链

固定上游
[`src/console/main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)
在 `ScanFiles()` 中按以下顺序分派：

```text
--entropy
  -> EntropyProcess::processRegionsFile()
else --info or non-empty --struct
  -> XFileInfo::processFile()
else
  -> DiE_Script::scanFile()
```

因此模式优先级为 `entropy > struct > info > normal scan`。同时给出
`--info --struct Hash` 时，`XFileInfo::OPTIONS.sString` 使用 `Hash` 而不是
`Info`。

专用模式的 formatter 优先级为：

```text
JSON > XML > CSV > TSV > formatted/plain text
```

`--plaintext` 没有专用分支，单独传入时与不传输出格式开关逐字节相同。这与普通
扫描的 `CSV > JSON > TSV > XML > plain text > colored text` 明确不同。

相关组件源码：

- [`EntropyProcess`](https://github.com/horsicq/XEntropyWidget/blob/d2bf95b1019e21e5a5ae71f55fcd6c12349c3030/entropyprocess.cpp)
- [`XFileInfo`](https://github.com/horsicq/XFileInfo/blob/88b8e2821f86d309f141b38c4d46fa0b000aa74b/xfileinfo.cpp)
- [`XFileInfoModel`](https://github.com/horsicq/XFileInfo/blob/88b8e2821f86d309f141b38c4d46fa0b000aa74b/xfileinfomodel.cpp)

## 可重复实验

生成语料后运行：

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --corpus-dir /tmp/diec-baseline-corpus \
  --matrix-kind special \
  --matrix-sample empty.bin \
  --matrix-sample minimal.exe \
  --matrix-sample minimal.pdf \
  --matrix-sample payload.zip \
  --matrix-sample plain.txt
```

每个样本覆盖 entropy 和 info 的 text/plaintext/JSON/XML/CSV/TSV、全部输出
开关组合、`Hash`、`Hash#MD5`、未知 struct，以及两组模式优先级组合。专用矩阵
共 95 种输入/模式组合、190 次 oracle 执行。两侧退出码、原始 stdout 和原始
stderr 均逐字节相同；所有运行退出 `0` 且 stderr 为空。

工具的通用 case 还分别运行无 target 及带 `/usr/bin/true` target 的
`--showstructs`，用于锁定结构清单和 target 处理。

核心 JSON stdout SHA-256：

| Sample | entropy JSON | info JSON | `Hash#MD5` JSON |
| --- | --- | --- | --- |
| `empty.bin` | `dfffd893cea0ad3d9d925824f634b5ceaae92cb12bbbadad904e2e329cc9dc87` | `3f163216b3f0ffd68806770dd4075103db66004c64cddb698ee7f5b126af87ae` | `31783744d420e017d8c6f18f9d7798d568d3542d9faf09374451ddd47d49906f` |
| `minimal.exe` | `d0300ec928fc92726cb16f8efae90dc1d336090ea34b6ab364f0a41ff32b62f4` | `aefcd5a6176bc5c59a79b56ea84b8d69580b7d5d59e693e73f57a9c567b2871f` | `4bd4993eb4533d9c6577c4bd6f171969f8d86d106bc54082b8280a42c1d85c67` |
| `minimal.pdf` | `33d404e9486ec9aaaf09fdea9a8f215fc5edf5ff7dbd4229561888e3cbdb0237` | `14fa8fe35ae1912a3008fe5d7d065c7a7dc9f63a12b4ab8743a04a572c8be9fd` | `fde42e33926114c517aae3e3dec2d2ad02b427b96e83e75fc9d1dd709fe1b67e` |
| `payload.zip` | `c7e599419251c2db6703e4003831a1bde20ae5ba782854eee545968d21babf9e` | `659457c7b05e7be857d79b15dbf73905f4d480683aa485563f48a8b0ec047e5a` | `46835037308e574b97618dcfe7bfdc6d212b24055000ac23cb056e1fa493f8cc` |
| `plain.txt` | `d5f9e298026a4dcd6a35adf8fa18647f111d3ced531eaf3fb60b104d2728ee74` | `410cec51ae2b2af54ffa117c251375b635c40c45b5f4f28502bd7dede8678d29` | `bd82818acc2f06327beef23109cf47eb758ad27298af9853dd618b7f202f699d` |

未知 struct 的 JSON 对所有 5 个输入完全相同，stdout SHA-256 为
`c0538adbaf9b1b80944941180f00fe139fb0457290e47944ef8e7c0c6cd67168`。
`--showstructs` 的 stdout SHA-256 为
`2ef890e26c826858eb053be3db702a629de717c63f35f86432bc1be6181a0699`。

## Entropy 模型

JSON 顶层字段：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `total` | number | 整个输入的 Shannon entropy |
| `status` | string | 当前为 `packed` 或 `not packed` |
| `records` | array | 非 virtual memory-map 区域 |

每个 record 包含 string `name`、整数 `offset`/`size`、number `entropy` 和
string `status`。区域来自 `XFormats::getMemoryMap()`，不是固定大小分块：
最小 PE32 的唯一记录名为 `Header`，PDF/ZIP/text/empty 的记录名为 `Data`。

格式差异：

- text 首行为 `Total <entropy>: <status>`，随后每区一行
  `index|name|offset|size|entropy: status`。
- XML 顶层为 `fileentropy`，total/status 及 record 字段都写为 attribute。
- CSV 使用分号，TSV 使用 tab，均无 header；每行 6 列。
- JSON/XML 使用约 16 位有效数字，text/CSV/TSV 通过默认
  `QString::number(double)` 输出较短值，因此不同 formatter 的数值字符串精度
  不同。

空文件仍产生一个 `Data` record，size、entropy 和 total 都为 `0`，status 为
`not packed`。5 个样本的 status 均为 `not packed`；这不覆盖 packed 阈值边界。

## Info 模型

JSON 固定使用顶层对象 `data`，其中 `Info` 是字段对象。叶子值全部序列化为
string，包括 `Size`。字段集合依格式变化：

- 所有样本包含 file name、size、file type、显示 string 和 MIME。
- PDF/ZIP 增加 extension/version。
- PE32 增加 architecture、mode、operation system、type 和 endianness。

字段和顺序是 formatter 可观察行为。`minimal.exe` 的 JSON key 观测顺序为
Architecture、Endianness、Extension、File name、File type、MIME、Mode、
Operation system、Size、String、Type；text、XML、CSV 和 TSV 则保留 model
插入顺序。例如 PDF 从 File name、Size、File type、String 开始。

XML 使用递归 `record` 元素，叶子值在 `value` attribute。CSV/TSV 不提供
header 或层级列，父节点输出为只有 name 和空 value 的一行。

## Struct 选择语义

`--showstructs` 当前只输出：

```text
Structures:
    Info
    Hash
    Entropy
    Check format
```

即使同时给出 target，输出也不变且不会扫描 target。原因是 CLI 将
`XFileInfo::getMethodNames()` 的 file type 硬编码为 `FT_UNKNOWN`，根据 target
探测格式的代码被注释；PE/ELF/Mach-O 等格式专用方法因此不会出现在清单中。

`--struct` 使用 `#` 分隔的大小写不敏感层级过滤：

- `Hash` 返回 MD4、MD5、SHA1、SHA224、SHA256、SHA384 和 SHA512。
- `Hash#MD5` 只返回 MD5 子记录。
- 未知方法 `NoSuchMethod` 不报错，JSON 为 `{"data": ""}`，退出 `0`。

空文件的 `Hash#MD5` 值是空字符串，不是标准空输入 MD5
`d41d8cd98f00b204e9800998ecf8427e`。Rust 兼容层若提供同名上游行为，必须保留
这一可观察边界；更符合通用预期的 hash API 应与兼容 API 分开设计。

## 组合优先级实验

在全部 5 个样本上：

- 同时传入 `--xml --json --csv --tsv --plaintext`，entropy/info 输出分别与
  单独 JSON 逐字节相同。
- `--entropy --info --struct Hash --json` 与单独 entropy JSON 逐字节相同。
- `--info --struct Hash --json` 与单独 `--struct Hash --json` 逐字节相同。
- 单独 `--plaintext` 与无 formatter 开关的 entropy/info 输出逐字节相同。

## 尚未覆盖

- packed/not-packed 阈值及临界熵值。
- 多区域 PE/ELF/Mach-O、virtual region 排除和异常 memory map。
- PE/ELF/Mach-O/DEX 的格式专用 struct 方法及畸形结构。
- `Entropy`、`Check format` 和多层 `#` struct 过滤。
- 多目标 filename 前缀对 JSON/XML 有效性的影响。
- 路径编码、不可读文件及 Windows/macOS 输出。
