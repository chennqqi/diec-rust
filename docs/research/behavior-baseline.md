# 上游行为基线

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-25

## 范围

本轮建立首批安全、确定性的多格式语料，并用 Linux Qt5 的 CMake 和 qmake
`diec` 候选 oracle 分别扫描。比较保留原始 stdout、stderr 和退出码，不解析后
再重排 JSON。

15 个样本在两个 oracle 上均返回退出码 `0`、空 stderr，JSON stdout
逐字节相同。该结论只覆盖默认扫描加 JSON 输出，不代表其他开关、输出格式、
畸形变体或平台已经兼容。

## 语料来源与安全

所有样本由
[`tools/corpus/generate_baseline_corpus.py`](../../tools/corpus/generate_baseline_corpus.py)
从常量和公开格式字段构造：

- 不下载或复制第三方样本；
- 不包含可执行指令或恶意载荷；
- PE、ELF 和 Mach-O 只有最小 header；
- archive 只包含固定文本 `diec-rust deterministic corpus\n`；
- 时间戳、UID、GID、文件名、校验和与未使用字段全部固定；
- PNG/GZIP 使用脚本生成的单个 DEFLATE stored block，不依赖 zlib 压缩器版本；
- ZIP 使用 store 方法，TAR 使用固定 USTAR header。

版本化清单
[`data/baseline-corpus.json`](data/baseline-corpus.json)
记录每个文件的意图、长度和 SHA-256。仓库不提交生成的二进制；单元测试会生成
两份语料逐字节比较，并要求生成结果与该清单完全一致。

生成命令：

```sh
python3 tools/corpus/generate_baseline_corpus.py /tmp/diec-baseline-corpus
```

独立 `file(1) 5.45` 验证了 13 种非空结构均符合生成意图；空文件和纯文本也被
正确分类。`minimal.cfbf` 只有合法 header，`file(1)` 明确报告无法读取 section
信息，因此它同时属于受控截断输入。

## Oracle 与规则

两个候选 oracle 和构建差异见
[`upstream-cmake-differential.md`](upstream-cmake-differential.md)。
扫描固定使用：

```text
--json
--database /opt/die-source/Detect-It-Easy/db
--extradatabase /opt/die-source/Detect-It-Easy/db_extra
--customdatabase /opt/die-source/Detect-It-Easy/db_custom
```

差分命令：

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505 \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --corpus-dir /tmp/diec-baseline-corpus
```

工具先校验两个 image revision、语料清单、文件大小和哈希，再将同一 host 目录
以只读方式挂载到 `/corpus`。任何输入身份或输出差异都会令命令非零退出。

## 观测结果

“上游类型”是 JSON `detects[].filetype`；“规则结果”保留关键
`detects[].values[].string`。Unknown 是上游实际结果，不表示实验失败。

| Sample | 上游类型 | 规则结果摘要 | stdout SHA-256 |
| --- | --- | --- | --- |
| `empty.bin` | Binary | `Format: Empty file` | `85d959957f5cdfc3b3e5d45d83f1d73e5cfe74d5d7906dc13cf3f0c1b351fe5a` |
| `plain.txt` | Binary | `Format: Plain text[LF]` | `f354d8df85d30a257d89ed74805c60964bc7f65260fc9ba4e01040f845f7cdf7` |
| `minimal.elf` | ELF64 | `Unknown: Unknown` | `8130d1163c063377eda3143c12a590c73e4ba5621a902b63c4afc455b4249515` |
| `minimal.exe` | PE32 | `Unknown: Unknown` | `c94fa4d2fa5742c41a67681779d3fc179aaf0f6558d74d385c648c2dae9dddde` |
| `minimal.macho` | Mach-O64 | `Unknown: Unknown` | `533ad66822e6737bb512b6963cecec6671c949333ec804db9f682f446cad995d` |
| `minimal.dex` | DEX | `Format: DEX(035)` | `5b42ce5c748c9e66174989be4c56b14dfd03eccc9635fcd5b20fa3f60e2e5c98` |
| `Minimal.class` | Java Class | `Format: Java Class(Java SE 8)` | `e430a0c3b596a3990d5fba87948d94256912ed6f1fb1eee245c0ddb8b33b18e8` |
| `pixel.png` | PNG | `Format: PNG[1x1, 8 bits, RGB]` | `2bbe198a5ab3a9dde62e778e62ad73bc836bb6241a61774cb1591b164fc73802` |
| `pixel.bmp` | Binary | `Image: Windows Bitmap(3)[1x1, 24bpp]` | `35b3366ffdb2bc58375af7ac00183338547e42c799a3023ebecb4868bc922f92` |
| `minimal.pdf` | PDF | `Format: PDF(1.4)`; `Complier: HeaderComment(e2e3cfd3)` | `5a475aa450326d3096db01352fe524bbda579173a645f0f502a74bba27a32e35` |
| `payload.zip` | ZIP | `Unknown: Unknown` | `82fb2c4717f3b8063febe1e6f299a10da117f6c4909b63d31aeadc13d247ad31` |
| `payload.tar` | Binary | `Archive: tar` | `e7348f825810f6ec94cdcd262c830e2c04532882683827f9351bd7158c692515` |
| `payload.txt.gz` | Binary | `Unknown: Unknown` | `9e1bf608c90e2ff6c0b07259ec8dc25aa8f705a38b66e2be7ca431ea76be2cde` |
| `minimal.cfbf` | CFBF | `Format: CFBF(3.62)`; `Format: Microsoft Office(1997-2003)` | `ccf571f677a541c8f26ec0ce4fe8139880a9ef64b6ec1e1c1de81e444a0ec78f` |
| `tone.wav` | Binary | `Audio: RIFF container/WAVE file (.WAV)(Microsoft PCM8U (uncompressed)/le)` | `9464be930526a60dc86587c08089e3e42f5901f4fe51ffbce4b4ea3d1d89316e` |

## 行为结论

- 格式识别和规则命中是两个不同层次。最小 PE32、ELF64、Mach-O64 已进入正确
  filetype 分派，但在没有编译器/壳等特征时产生 Unknown record。
- Java Class、DEX、PNG、PDF、CFBF 的最小结构足以触发专用 filetype 和格式规则。
- BMP、WAV 和 TAR 由 Binary 顶层类型报告更具体的 value；不能把
  `detects[].filetype` 直接等同于所有受支持格式。
- `payload.zip` 默认扫描只返回顶层 ZIP Unknown，没有报告内部 `payload.txt`。
  是否需要 deep/aggressive 或引擎内部 archive 选项才能递归，仍待组合实验。
- GZIP 被独立工具识别为有效 archive，但默认 DIE JSON 是 Binary/Unknown。
  这一区别必须保留为兼容基线，不能按扩展名“修正”。
- PDF 规则原样输出拼写 `Complier`；Rust 兼容实现默认也必须保留该可观察字符串。
- CFBF 截断到 header 仍正常退出且产生版本/Office 规则结果，没有 stderr 或 panic。

## 尚未覆盖

- PE64、ELF32、Mach-O32/FAT、APK/JAR/IPA、RAR、ISO9660、PYC、JPEG 等格式。
- deep、heuristic、aggressive、alltypes、entropy、info、struct 和 profiling。
- XML、CSV、TSV、plain text 以及多目标输出 schema。
- 目录、递归、archive 内部成员、overlay/resource 和最大深度。
- 缺失、空、损坏和含未知语法的规则数据库。
- 系统化畸形/截断矩阵、资源限制、超时、内存峰值和 fuzz seeds。
- Windows/macOS oracle 以及路径编码差异。

后续扩展不得改变现有样本字节；需要修正时新增带版本的样本名和清单记录。
