# 上游 CLI 多目标与目录行为

Status: Draft
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 范围

本文记录 Linux `diec` 对多个 positional target、目录、空目录、重复目标、缺失
目标和 `--recursivescan` 的可观察行为。实验使用固定 Qt5 qmake/CMake oracle，
逐字节比较退出码、stdout 和 stderr。

路径语料只重排
[`baseline-corpus.json`](data/baseline-corpus.json)
中的项目生成字节，不引入第三方样本。版本化目录清单为
[`path-corpus.json`](data/path-corpus.json)。

Unicode 与特殊名称现由独立的可移植 USTAR 实验覆盖，见
[`special-path-behavior.md`](special-path-behavior.md)。它固定 Linux Qt5 下的
NFC/NFD、中文、emoji、前导/尾随空格、tab/newline、colon/backslash、hidden、
leading-dash 与目录排序，但不把 Linux 结果外推到其他平台。

## 源码语义

固定上游
[`ScanFiles()`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)
按 positional argument 顺序执行：

1. 不存在的路径立即向 stdout 打印 `Cannot find: <path>`，并把最终结果设为
   `CR_CANNOTFINDFILE`。
2. 存在的每个 target 传给 `XBinary::findFiles()`，结果追加到同一个 list。
3. list 总数大于 1 时，每个结果前打印绝对 filename 和 `:`。
4. 按 list 顺序逐文件调用选中的普通或专用扫描路径。

CLI 调用的是没有 `bSubDirectories` 参数的
[`XBinary::findFiles()`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L2452)。
该 overload 对目录无条件递归，通过 `QDir::entryInfoList()` 取得已排序 entry，
再进行 depth-first 遍历；没有深度参数、visited set 或显式 symlink 排除。

因此 `-r` / `--recursivescan` 不控制顶层目录枚举。它设置
`SCAN_OPTIONS.bIsRecursiveScan`，在扫描单个文件时启用 resource 和 overlay
file-part 扫描，并传入规则宿主选项。源码证据为固定
[`XScanEngine::scanProcess()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2934)。

## 确定性路径语料

生成命令：

```sh
python3 tools/corpus/generate_baseline_corpus.py /tmp/diec-baseline-corpus
python3 tools/corpus/generate_path_corpus.py \
  /tmp/diec-baseline-corpus \
  /tmp/diec-path-corpus
```

目录树：

```text
empty-dir/
single/
└── only.elf
tree/
├── a-first.pdf
├── b-dir/
│   ├── a-child.exe
│   └── c-deep/
│       └── z-child.zip
└── z-last.txt
```

生成器校验来源 manifest 的 size/SHA-256，复制后重新计算每个 destination 的
size/SHA-256。测试要求两次生成的 manifest 和全部文件逐字节相同，并与版本化
清单一致。oracle 工具拒绝路径逃逸、反斜杠、symlink、未声明文件、重复路径及
任何 size/hash 不匹配。

## 可重复实验

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --path-corpus-dir /tmp/diec-path-corpus
```

路径矩阵包含 14 个 case、28 次 oracle 执行：

- single file、两个显式文件、重复显式文件；
- tree、tree + `--recursivescan`、single directory、empty directory；
- tree 的 JSON/XML/CSV/plaintext；
- tree 的 entropy JSON 和 info JSON；
- missing + existing；
- tree + tree 中已包含的显式文件。

两个 oracle 的所有退出码、原始 stdout 和原始 stderr 均逐字节相同。全部
stderr 为空；只有 missing + existing 退出 `1`，其余 case 退出 `0`。

## 枚举顺序与重复

Linux 固定 oracle 的 tree 顺序为：

```text
/paths/tree/a-first.pdf
/paths/tree/b-dir/a-child.exe
/paths/tree/b-dir/c-deep/z-child.zip
/paths/tree/z-last.txt
```

这验证了当前语料上的 name ordering 和 depth-first recursion。两个显式文件按
命令行顺序 `z-last.txt -> a-first.pdf`，不会重新全局排序。

上游不去重：

- 同一文件显式传入两次，会扫描并输出两次。
- 先传 tree、再显式传入 tree 中的 `a-first.pdf`，会按上述 4 个文件后再扫描
  PDF，共输出 5 个 filename prefix。

`tree_json` stdout SHA-256 为
`05d3853c9b1087107efa01e4324b752b4bd27a055dd852a2f4f0e414c80a4d4f`。
同一 tree 加 `--recursivescan` 后哈希完全相同；当前最小文件没有可触发的
resource/overlay，不能据此推断内部递归开关无效。

## Filename prefix 与结构化输出

filename prefix 的条件是“最终展开后的文件总数大于 1”，不是“参数个数大于
1”或“target 是目录”：

- single file 的 JSON 有效，且与原基线 PDF JSON 哈希相同。
- 只含一个 ELF 的 single directory 不打印 prefix，输出是有效 JSON，且与
  单文件 ELF 基线哈希相同。
- empty directory 退出 `0`、stdout/stderr 都为空；若调用方期待 JSON，该空
  stdout 不是有效 JSON。
- tree 展开为 4 个文件，每个独立结果前都打印
  `/paths/...:`。程序不会构造 JSON array 或 XML root。

因此 tree 的普通 JSON、entropy JSON、info JSON 和 XML 都不是单个有效文档。
CSV 同样在记录之间插入不符合 CSV schema 的 filename/colon 行。plaintext
适合人读，但 prefix 仍是输出契约的一部分。

代表性原始 stdout 哈希：

| Case | Exit | stdout SHA-256 | 有效单文档 |
| --- | ---: | --- | --- |
| single file JSON | 0 | `5a475aa450326d3096db01352fe524bbda579173a645f0f502a74bba27a32e35` | JSON: yes |
| single directory JSON | 0 | `8130d1163c063377eda3143c12a590c73e4ba5621a902b63c4afc455b4249515` | JSON: yes |
| empty directory JSON | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | JSON: no |
| tree JSON | 0 | `05d3853c9b1087107efa01e4324b752b4bd27a055dd852a2f4f0e414c80a4d4f` | JSON: no |
| tree XML | 0 | `715d2f73f70d892cdc73f7203771c668dd8948a47b2bcc82dfda8c3ee445b05c` | XML: no |
| tree CSV | 0 | `90b9b486cdb7a059e83a1a4910edc8c2a7c2f3493c1d8f564cc709405a19d3d2` | n/a |

## 缺失目标与部分成功

`/paths/does-not-exist /paths/tree/a-first.pdf` 的行为是：

1. 先向 stdout 打印 `Cannot find: /paths/does-not-exist`。
2. 继续扫描存在的 PDF。
3. 因最终只有一个存在文件，不打印 filename prefix。
4. 返回退出码 `1`，stderr 为空。

错误文本和 JSON 对象拼接在同一 stdout，因此不是有效 JSON。stdout SHA-256
为 `b2f77a9902274e7af30e8bfe110e9df4d6bd3b62dc3326a1fbc394cdfe5c942f`。
这说明上游同时具有 partial result 和 nonzero exit；差分测试不能看到非零退出
就丢弃 stdout。

## 兼容与安全含义

- 上游结构化多目标输出在语法上无效，但仍是固定基线的可观察行为。Rust CLI
  是否默认复制、提供显式 compatibility 模式，或默认输出有效聚合文档，必须
  在 CLI 设计中用 ADR 明确；不能静默“修好”后仍声称逐字节兼容。
- “目录递归”和“文件内部递归”必须是两个独立概念。沿用上游 `-r` 名称时，
  help/API 文档应避免暗示它决定目录深度。
- `findFiles()` 源码没有目录深度和循环检测。确定性语料刻意不含 symlink；
  symlink-to-directory、循环链接、权限错误和超深目录需要受控隔离实验。Rust
  实现不能继承无限递归风险；若安全限制产生差异，需要配置、诊断和 ADR。

## 尚未覆盖

- symlink、junction、循环目录、超深目录和权限错误。
- 非 UTF-8 filename bytes；UTF-8 Unicode、空格、colon、backslash、tab/newline
  与 hidden/leading-dash 已由特殊路径实验覆盖。
- QDir ordering 已固定一个大小写/NFC/NFD/控制字符矩阵；locale 与 filesystem
  边界仍缺。
- Windows/macOS path separator、绝对路径和枚举顺序。
- 能实际触发 resource/overlay 的 `--recursivescan` 样本。
- 大目录的取消、时间、内存和最大文件数。
