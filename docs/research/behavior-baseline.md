# 上游行为基线

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-27

## 范围

本轮建立首批安全、确定性的多格式语料，并用 Linux Qt5 的 CMake 和 qmake
`diec` 候选 oracle 分别扫描。比较保留原始 stdout、stderr 和退出码，不解析后
再重排 JSON。

26 个样本在两个 oracle 上均返回退出码 `0`、空 stderr，默认 JSON stdout
逐字节相同。扫描开关矩阵仍覆盖首版 15 个样本；输出格式矩阵覆盖
`empty.bin`、`minimal.exe`、`minimal.pdf`、`payload.zip` 和 `plain.txt`。
这些结论不代表其他选项组合、畸形变体或平台已经兼容。

## 语料来源与安全

所有样本由
[`tools/corpus/generate_baseline_corpus.py`](../../tools/corpus/generate_baseline_corpus.py)
从常量和公开格式字段构造：

- 不下载或复制第三方样本；
- 不包含可执行指令或恶意载荷；
- PE32/64、ELF32/64、Mach-O32/64/FAT 只有最小 header/load command；
- APK/JAR/IPA 使用固定 store ZIP 和最小成员，RAR 使用空 main header，
  ISO9660 使用固定 primary volume descriptor；
- PYC 固定为 CPython 3.8 timestamp header，JPEG 为 1×1 JFIF/SOF/SOS；
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

独立 `file(1) 5.45` 验证了 24 种结构均符合生成意图；空文件和纯文本也被
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
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --corpus-dir /tmp/diec-baseline-corpus
```

工具先校验两个 image revision、语料清单、文件大小和哈希，再将同一 host 目录
以只读方式挂载到 `/corpus`。任何输入身份或输出差异都会令命令非零退出。

扫描所有样本的开关矩阵使用：

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --corpus-dir /tmp/diec-baseline-corpus \
  --matrix-all \
  --matrix-kind scan
```

输出格式实验将 `--matrix-kind` 改为 `output`，并用重复的
`--matrix-sample <name>` 选择上述 5 个代表样本。报告为 JSON，保存两侧每次
运行的退出码及原始 stdout/stderr SHA-256；`left_changes` 和
`right_changes` 分别指出相对默认 JSON 的可观察变化。

## 观测结果

“上游类型”是 JSON `detects[].filetype`；“规则结果”保留关键
`detects[].values[].string`。Unknown 是上游实际结果，不表示实验失败。

| Sample | 上游类型 | 规则结果摘要 | stdout SHA-256 |
| --- | --- | --- | --- |
| `empty.bin` | Binary | `Format: Empty file` | `85d959957f5cdfc3b3e5d45d83f1d73e5cfe74d5d7906dc13cf3f0c1b351fe5a` |
| `plain.txt` | Binary | `Format: Plain text[LF]` | `f354d8df85d30a257d89ed74805c60964bc7f65260fc9ba4e01040f845f7cdf7` |
| `minimal.elf` | ELF64 | `Unknown: Unknown` | `8130d1163c063377eda3143c12a590c73e4ba5621a902b63c4afc455b4249515` |
| `minimal-elf32.elf` | ELF32 | `Unknown: Unknown` | `f3b54d11d3fc57706c7add5bc72b0e385a65a5b9a3e924c4fd432b43dd0b8383` |
| `minimal.exe` | PE32 | `Unknown: Unknown` | `c94fa4d2fa5742c41a67681779d3fc179aaf0f6558d74d385c648c2dae9dddde` |
| `minimal-pe64.exe` | PE64 | `Unknown: Unknown` | `1b115a1554c59f2afc298ba759378ced161e940072cbc2f8acd7edb763ba690c` |
| `minimal.macho` | Mach-O64 | `Unknown: Unknown` | `533ad66822e6737bb512b6963cecec6671c949333ec804db9f682f446cad995d` |
| `minimal-macho32.macho` | Mach-O32 | `Unknown: Unknown` | `64ae03252f407bdd0888f668591205b44a87a57ef2d80391cdc78bd0eb2321fa` |
| `minimal-fat.macho` | Mach-O FAT | `Converter: lipo` | `978379072d1f74b81f78d2caac4e2f47e0788e1bca1b4a3ec196a4e7c7a39fe8` |
| `minimal.dex` | DEX | `Format: DEX(035)` | `5b42ce5c748c9e66174989be4c56b14dfd03eccc9635fcd5b20fa3f60e2e5c98` |
| `Minimal.class` | Java Class | `Format: Java Class(Java SE 8)` | `e430a0c3b596a3990d5fba87948d94256912ed6f1fb1eee245c0ddb8b33b18e8` |
| `minimal.pyc` | Python Bytecode | `Format: Python Bytecode(3.8b4)` | `99ab55c1bc9708149ca7bd5a896abf7e4860760c8ea855a641cc11ff1de17a4c` |
| `pixel.png` | PNG | `Format: PNG[1x1, 8 bits, RGB]` | `2bbe198a5ab3a9dde62e778e62ad73bc836bb6241a61774cb1591b164fc73802` |
| `pixel.jpg` | JPEG | `Format: JPEG(1.1)`; `Image: DQT` | `49910f50eee0b247031b60131b035229f31410d113253d665e714ac0074842a6` |
| `pixel.bmp` | Binary | `Image: Windows Bitmap(3)[1x1, 24bpp]` | `35b3366ffdb2bc58375af7ac00183338547e42c799a3023ebecb4868bc922f92` |
| `minimal.pdf` | PDF | `Format: PDF(1.4)`; `Complier: HeaderComment(e2e3cfd3)` | `5a475aa450326d3096db01352fe524bbda579173a645f0f502a74bba27a32e35` |
| `payload.zip` | ZIP | `Unknown: Unknown` | `82fb2c4717f3b8063febe1e6f299a10da117f6c4909b63d31aeadc13d247ad31` |
| `minimal.apk` | APK | `Unknown: Unknown` | `60f6f34d539fb6f3f954d3e023fc45f9e0719da92174e4b9bdde88a12afca04e` |
| `minimal.jar` | JAR | `Unknown: Unknown` | `0fd4e7f109e634608e898ee774d934189dd8648c81198f6441ccade6fed6e571` |
| `minimal.ipa` | Binary | `Archive: Zip(2.0)` | `f4e74ed3b429d0a46f53a4e16c306f6bbce6e2c3f2becba0fe00873e1a9caad5` |
| `minimal.rar` | RAR | `Unknown: Unknown` | `5a19df75955d336f0f4573400e86909cf57f14655dc860d58d79dbb150d18574` |
| `minimal.iso` | ISO 9660 | `Unknown: Unknown` | `5a9ccc1bed88d5c23d54b47f99b910e37b635c759002096b944678aa5dc2f3b6` |
| `payload.tar` | Binary | `Archive: tar` | `e7348f825810f6ec94cdcd262c830e2c04532882683827f9351bd7158c692515` |
| `payload.txt.gz` | Binary | `Unknown: Unknown` | `9e1bf608c90e2ff6c0b07259ec8dc25aa8f705a38b66e2be7ca431ea76be2cde` |
| `minimal.cfbf` | CFBF | `Format: CFBF(3.62)`; `Format: Microsoft Office(1997-2003)` | `ccf571f677a541c8f26ec0ce4fe8139880a9ef64b6ec1e1c1de81e444a0ec78f` |
| `tone.wav` | Binary | `Audio: RIFF container/WAVE file (.WAV)(Microsoft PCM8U (uncompressed)/le)` | `9464be930526a60dc86587c08089e3e42f5901f4fe51ffbce4b4ea3d1d89316e` |

## 行为结论

- 格式识别和规则命中是两个不同层次。最小 PE32、ELF64、Mach-O64 已进入正确
  filetype 分派，但在没有编译器/壳等特征时产生 Unknown record。
- Java Class、DEX、PNG、PDF、CFBF 的最小结构足以触发专用 filetype 和格式规则。
- ELF32、PE64、Mach-O32/FAT、PYC、JPEG、APK、JAR、RAR 和 ISO9660 也进入
  对应专用分派；其中 FAT、PYC 和 JPEG 产生非 Unknown 规则结果。
- IPA 的 central directory 命中 `XZip::isIPA()`，但固定
  `XScanEngine::scanProcess()` 的 IPA 分支把 `_processDetect()` file type
  明确设为 `FT_BINARY`（IPA 调用被注释），仅把 `ftInit` 设为 IPA。因此当前
  JSON 是 `Binary / Archive: Zip(2.0)`；Rust legacy 路径不能擅自输出 IPA
  detection。
- BMP、WAV 和 TAR 由 Binary 顶层类型报告更具体的 value；不能把
  `detects[].filetype` 直接等同于所有受支持格式。
- `payload.zip` 默认扫描只返回顶层 ZIP Unknown，没有报告内部 `payload.txt`。
  后续组合实验确认 deep/aggressive/recursive 均不会使发布 CLI 解包 archive；
  archive 需要发布入口未暴露的独立 engine 选项。详见
  [`nested-scan-behavior.md`](nested-scan-behavior.md)。
- GZIP 被独立工具识别为有效 archive，但默认 DIE JSON 是 Binary/Unknown。
  这一区别必须保留为兼容基线，不能按扩展名“修正”。
- PDF 规则原样输出拼写 `Complier`；Rust 兼容实现默认也必须保留该可观察字符串。
- CFBF 截断到 header 仍正常退出且产生版本/Office 规则结果，没有 stderr 或 panic。

## 输出格式矩阵

5 个代表样本分别运行默认彩色文本、plain text、JSON、XML、CSV、TSV，以及
同时传入全部 5 个格式开关。共 35 种输入/模式组合、70 次 oracle 执行；
两侧退出码、stdout 和 stderr 全部逐字节相同，均退出 `0` 且 stderr 为空。

固定上游
[`main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)
对普通扫描使用固定优先级
`CSV > JSON > TSV > XML > plain text > colored text`，与命令行参数顺序无关。
实验中依次传入 `--xml --json --csv --tsv --plaintext`，5 个样本的输出都与
单独 `--csv` 逐字节相同。

以 `minimal.pdf` 为例：

- 默认文本在 stdout 被重定向时仍包含 ANSI SGR 转义；`--plaintext` 保留相同
  层级文本但不含颜色控制序列。
- JSON 是带缩进的对象，顶层为 `detects`；详细默认结果哈希见上表。
- XML 顶层为 `Result`，每个 filetype 是子元素，规则命中为 `detect` 子元素。
- CSV 使用分号分隔且没有 header；TSV 使用 tab 分隔且没有 header。
- CSV 和 TSV 均逐条输出规则记录；字段为 type、name、version、info 和
  完整显示字符串。

该优先级只适用于普通扫描。entropy/info 专用分支已验证按
`JSON > XML > CSV > TSV > formatted text` 选择 formatter；详见
[`cli-special-modes.md`](cli-special-modes.md)。Rust CLI 不能把两条路径误
合并为一个全局优先级。

## 扫描开关矩阵

每个样本分别运行默认 JSON、deep、heuristic、aggressive、alltypes、format、
hideunknown，以及 deep/heuristic/aggressive/alltypes 组合模式。完整矩阵包含
120 种输入/模式组合、240 次 oracle 执行；两套上游构建的退出码、stdout 和
stderr 逐字节相同，均退出 `0` 且 stderr 为空。

相对默认 JSON，发生 stdout 变化的样本如下；未列出的模式/样本逐字节不变：

| 模式 | stdout 变化的样本 |
| --- | --- |
| deep | 无 |
| heuristic | `minimal.exe`、`pixel.bmp`、`tone.wav` |
| aggressive | 无 |
| alltypes | `minimal.exe` |
| format | `Minimal.class`、`minimal.cfbf`、`minimal.dex`、`minimal.pdf`、`pixel.bmp`、`pixel.png`、`plain.txt`、`tone.wav` |
| hideunknown | `minimal.elf`、`minimal.exe`、`minimal.macho`、`payload.txt.gz`、`payload.zip` |
| combined | `minimal.exe`、`pixel.bmp`、`tone.wav` |

代表性的可观察增量为：

- `minimal.exe` 的 heuristic 把 `Unknown: Unknown` 变为
  `(Heur)Protection: Generic`，记录 type 为 `~protection`。
- `pixel.bmp` 和 `tone.wav` 的 heuristic 分别增加根据扩展名产生的
  `(Heur)Format: Bitmap Image[by extension]` 和
  `(Heur)Format: Waveform Audio[by extension]`；组合模式的输出与各自
  heuristic 输出逐字节相同。
- `minimal.exe` 的 alltypes 在 PE32 之前额外报告 MSDOS Unknown；组合模式同时
  保留 MSDOS 结果和 PE32 heuristic protection。
- hideunknown 不会产生空 `detects`，而是把 Unknown filetype 折叠为一个
  `name`、`type`、`version`、`info` 为空的顶层 value；`string` 保留
  `ELF64`、`PE32`、`Mach-O64`、`Binary` 或 `ZIP`。这是需要原样兼容的
  schema 变化。
- format 不改变结构化字段，只重排完整显示字符串中的空格。例如
  `PDF(1.4)` 变为 `PDF (1.4)`，`Plain text[LF]` 变为
  `Plain text [LF]`，PNG 的名称与方括号信息之间也增加空格。
- deep 和 aggressive 在全部 15 个输入上都没有改变输出；这只能证明它们在
  当前语料上无增量，不能推断开关未生效。

多目标、目录、重复 target、缺失+存在 partial result，以及结构化输出的
filename prefix 行为单独记录在
[`cli-path-behavior.md`](cli-path-behavior.md)。

数据库缺失/空/无效 ZIP、规则 parse/runtime error 和不可读输入行为见
[`database-error-behavior.md`](database-error-behavior.md)。

resource、overlay 和 archive 嵌套行为已用 7 个独立样本验证，见
[`nested-scan-behavior.md`](nested-scan-behavior.md)。

26 个默认扫描的机器报告为
[`data/baseline-corpus-linux-qt5.json`](data/baseline-corpus-linux-qt5.json)。
它绑定 compare tool、corpus manifest、两个 image revision，保存每次 raw stream
长度/SHA-256 和未重排 detection tree；测试要求双 oracle 无差异。

verbose、messages、profiling 以及 test/create test 两个遗留入口的确定性行为见
[`cli-option-behavior.md`](cli-option-behavior.md)。其中 profiling 的非确定
elapsed 值与固定规则执行序列另见
[`binary-rule-lifecycle.md`](binary-rule-lifecycle.md#linux-qt5-实测顺序)。

## 尚未覆盖

- 26-sample 通用基线本身不含 7Z、CAB、NPM、Amiga Hunk、Atari ST 及
  DOS/COM/NE/LE/LX 等格式；其中 CAB store 正例现由
  [`archive-format-behavior.md`](archive-format-behavior.md) 固定，legacy 与
  DOS/COM 由各自专用 oracle 固定，7Z/NPM 仍缺。
- 新增 11 个格式的 scan/output/special 选项矩阵（当前仅固定 default JSON）。
- 输出格式的转义和嵌套排序已由
  [`cli-output-boundaries.md`](cli-output-boundaries.md) 的 10-case 双 oracle
  固定；特殊 filename 与跨平台路径编码仍待覆盖。专用 struct/entropy 阈值
  边界已由 [`cli-special-modes.md`](cli-special-modes.md) 的 28-case 双 oracle
  固定。
- deep 增量、aggressive resource filter 和默认 21/aggressive 2001 精确上限已由
  [`scan-option-boundaries.md`](scan-option-boundaries.md) 固定。
- 7Z、archive aggressive 100000 上限和高压缩比/畸形边界；RAR4/CAB/ISO9660
  store 正例及 ZIP depth 16/约 2 MiB 累计展开量已有专用报告。
- 发布 CLI 的 ZIP database 截断/重复/`..`/根前缀边界及 cache-disabled
  副作用已由 [`database-archive-cache.md`](database-archive-cache.md) 覆盖；
  Qt5 engine cache 的 miss/hit/stale/bad-magic/truncated/cancel 已固定，其他
  cache 边界和权限仍待实验；main/extra/custom 同名规则保留、顺序和 gate 已由
  [`database-layer-behavior.md`](database-layer-behavior.md) 固定。
- 系统化畸形/截断矩阵、资源限制、超时、内存峰值和 fuzz seeds。
- Windows/macOS oracle 以及路径编码差异。

后续扩展不得改变现有样本字节；需要修正时新增带版本的样本名和清单记录。
