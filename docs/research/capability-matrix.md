# 上游能力矩阵

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-27

本矩阵同时记录源码证据和固定 Linux oracle 实验。`Observed` 表示已用固定
二进制、规则和输入验证；未标记为 Observed 的能力仍不能从相邻实验外推。

## CLI 输入

| 能力 | 上游入口 | 状态 | 备注 |
| --- | --- | --- | --- |
| 单文件扫描 | positional `target` | Observed | 15 个确定性样本；见 `behavior-baseline.md` |
| 多目标扫描 | 多个 positional `target` | Observed | 保持参数顺序、不去重；结构化输出不是有效聚合文档 |
| 目录枚举 | positional directory | Observed | 无条件 depth-first 递归；Linux 当前语料按 name 排序 |
| 单文件目录/空目录 | positional directory | Observed | 单文件不加 prefix；空目录退出 0 且无输出 |
| 内存扫描 | engine `scanMemory()` | Observed | Binary fixture 与 file/device/subdevice record 一致；CLI 不暴露 |
| device/subdevice 扫描 | engine API | Observed | Binary fixture record 一致；边界/error 尚未覆盖 |

CLI 主入口为 [`src/console/main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)，选项名称与描述来自 `XOptions@810d78d.../xoptions.cpp`。

## CLI 扫描控制

| Short | Long | 上游描述 | 代码映射 | 状态 |
| --- | --- | --- | --- | --- |
| `-r` | `--recursivescan` | Scan directories recursively | `bIsRecursiveScan` | Observed + source；不控制目录枚举，启用 resource/overlay 内部递归 |
| `-d` | `--deepscan` | Enable deep scanning for thorough analysis | `bIsDeepScan` | Observed；15 个基线样本 |
| `-u` | `--heuristicscan` | Enable heuristic scanning methods | `bIsHeuristicScan` | Observed；PE32 protection 及 BMP/WAV 扩展名 heuristic |
| `-b` | `--verbose` | Show verbose output with detailed information | `bIsVerbose` | Observed；ELF64 新增 OS record，不是纯日志 |
| `-g` | `--aggressivecscan` | Enable aggressive scanning mode | `bIsAggressiveScan` | Observed；15 个基线样本；long name含额外 `c` |
| `-a` | `--alltypes` | Scan all file types | `bIsAllTypesScan` | Observed；最小 PE32 额外报告 MSDOS |
| `-f` | `--format` | Format the output result | `bFormatResult` | Observed；8 个样本的显示字符串空格发生变化 |
| `-l` | `--profiling` | Profile signatures during scan | `bLogProfiling` | Observed；不带 messages 时输出不变；带 messages 时输出规则名及非确定 timing |
| `-M` | `--messages` | Display scan messages and warnings | Qt signal output | Observed；signals 写 stdout，可破坏 JSON framing |
| `-U` | `--hideunknown` | Hide unknown file types from results | `bHideUnknown` | Observed；5 个 Unknown filetype 被折叠为顶层字符串 |

注意：`XScanEngine::SCAN_OPTIONS` 还定义 resource、archive 和 overlay scan，但当前顶层 `src/console/main_console.cpp` 没有注册相应 CLI 选项。这是“引擎能力”和“当前 CLI 能力”必须分开比较的实例。

## CLI 专用模式与输出

| Short | Long | 能力 | 状态 |
| --- | --- | --- | --- |
| `-e` | `--entropy` | 输出分区/区域熵信息 | Observed；5 个代表样本、6 种 formatter |
| `-i` | `--info` | 输出文件信息模型 | Observed；5 个代表样本、6 种 formatter |
| `-S` | `--struct <value>` | 特定结构信息，如 `Hash` / `Hash#MD5` | Observed；Hash、子字段和未知方法 |
| `-w` | `--showstructs` | 列出可用结构方法 | Observed；仅列 4 个通用方法，target 被忽略 |
| `-x` | `--xml` | XML | Observed；5 个代表样本 |
| `-j` | `--json` | JSON | Observed；15 个样本原始输出已固定哈希 |
| `-c` | `--csv` | CSV | Observed；5 个代表样本；normal scan 多格式开关中优先级最高 |
| `-t` | `--tsv` | TSV | Observed；5 个代表样本 |
| `-p` | `--plaintext` | plain text | Observed；5 个代表样本 |
| `-D` | `--database <path>` | 主数据库路径 | Observed |
| `-E` | `--extradatabase <path>` | extra 数据库路径 | Observed |
| `-C` | `--customdatabase <path>` | custom 数据库路径 | Observed |
| `-s` | `--showdatabase` | 显示路径及各文件类型规则数量 | Observed；27 类型、2172 条 |
| — | `--test <directory>` | 规则测试入口 | Observed；加载数据库后 no-op，不校验 directory |
| — | `--createtest <filename>` | 创建测试入口 | Observed；完整参数只打印文案；缺参 exit 4 且误称 `--addtest` |

同时注册 Qt 自带 `--help` 和 `--version`。无 target 且没有 `--showdatabase` 时调用 `showHelp()`。

默认规则路径为 `$data/db`、`$data/db_extra`、`$data/db_custom`；extra 和
custom 在 CLI 中默认启用。main/extra/custom 返回值不对称、入口相关退出码及
错误输出见
[`database-error-behavior.md`](database-error-behavior.md)。

固定源码、CMake source list 和最终 link line 共同证明当前 `diec` CLI 没有
YARA、PEiD 或 SearchSignatures 数据入口。上游安装包仍可能携带这些 GUI/辅助
engine 资产；运行时范围、两套数据树差异及逐文件哈希见
[`rule-asset-provenance.md`](rule-asset-provenance.md)。

entropy/info/struct 不使用普通扫描 formatter，组合优先级、schema、空文件 hash
边界和复现命令见
[`cli-special-modes.md`](cli-special-modes.md)。

多目标 filename prefix、目录顺序、重复 target、部分失败和无效 JSON/XML 聚合
行为见
[`cli-path-behavior.md`](cli-path-behavior.md)。

verbose/messages/profiling 的 channel 与结构化结果关系，以及两个未完成测试入口的
精确 no-op、stdout 和退出码见
[`cli-option-behavior.md`](cli-option-behavior.md)。

## 规则与扫描能力

| 能力 | 源码证据 | 状态 |
| --- | --- | --- |
| main/extra/custom 三层规则库 | `XScanEngine::loadDatabase()` + `_shouldExecuteSignature()` | Observed；各层分别排序并按 main→extra→custom append；同名不覆盖/不去重；load 与 runtime gate 已固定 |
| 规则优先级排序 | `sort_signature_prio` | Observed + source；priority-only 按字符串 priority；含 `_init` 时比较非传递 |
| global/type Init 规则 | `findInitSignatures()` + `_executeInitSignature()` | Observed；Binary main init 遮蔽 extra/custom |
| 按文件类型过滤规则 | `_shouldExecuteSignature()` | Observed；Binary 输入不执行 PE decoy |
| deep/heuristic 规则过滤 | `_shouldExecuteSignature()` | Observed；DS/EP 与 HEUR 独立四模式 |
| 自定义单条 signature 过滤 | `sSignatureName` | Observed；区分大小写，仍受 deep gate，未命中产生 Unknown |
| signature file path 过滤 | 私有 `processDetect(..., sSignatureFilePath, ...)` | Source audit；公共 options 无该字段，当前不可达 |
| 未命中时产生 Unknown | `DiE_Script::processDetect()` | Observed；空的有效三层数据库产生唯一 Unknown |
| 检测结果稳定排序选项 | `bIsSort` + `sortRecords()` | Observed；关闭保持插入顺序，开启按 type priority 升序 |
| 脚本错误收集 | `SCAN_RESULT.listErrors` | Observed；parse/runtime error 追加到 stdout，退出 0 |
| 脚本 profiling | `listDebugRecords` / messages | Observed；292 条 Binary 规则顺序及 CLI channel 已固定 |
| 取消/停止 | `PDSTRUCT`, callback, `breakScan()` | Observed；运行中停止保留当前 record，预停止产生 Unknown |

规则脚本由 Qt 5 `QScriptEngine` 或 Qt 6 `QJSEngine` 执行。规则兼容性不是简单的模式匹配移植，必须覆盖 JavaScript 方言、全局函数和每种格式宿主对象；详见待建的 `rule-compatibility.md`。

priority、数据库分层、init/include、file type、deep/heuristic 和 Unknown 的隔离
端到端证据见
[`rule-orchestration.md`](rule-orchestration.md)。
引擎过滤、record 排序、停止和扫描入口的固定 harness 证据见
[`engine-contract-behavior.md`](engine-contract-behavior.md)。

## 文件类型分派

`XScanEngine::scanProcess()` 当前显式分派：

- PE32/PE64、ELF32/ELF64、Mach-O 32/64、Mach-O FAT。
- DOS/COM 家族：MS-DOS、NE、LE、LX、DOS16M、DOS4G、BW DOS16M、COM。
- Amiga Hunk、Atari ST。
- APK、IPA、JAR、ZIP、RAR、NPM、ISO9660、通用 Archive。
- DEX、Java Class、PYC。
- PDF、CFBF。
- JPEG、PNG、通用 Image。
- Binary fallback。

`Formats` 子模块还包含更多探测/信息解析类，不等于它们都有 DIE 规则目录或完整扫描结果。最终“支持格式”必须以格式探测、规则数据库、扫描分派和样本输出四者交叉验证。

运行实验已观察到专用顶层类型 PE32/64、ELF32/64、Mach-O32/64/FAT、DEX、
Java Class、Python Bytecode、PNG、JPEG、PDF、CFBF、ZIP、APK、JAR、RAR 和
ISO9660。IPA 被格式层识别，但 engine 有意通过 Binary 规则分派。BMP、WAV、
TAR、GZIP 由外部 `file(1)` 验证结构，
但 DIE 顶层类型为 Binary；其中 BMP、WAV、TAR 仍通过 value 报告具体格式，
GZIP 返回 Unknown。扫描开关矩阵还验证了 heuristic、alltypes、format 和
hideunknown 的可观察增量。完整输入哈希和输出见
[`behavior-baseline.md`](behavior-baseline.md)。

## 嵌套与递归

源码与固定 oracle 共同确认：

- CLI 顶层目录枚举始终递归；`--recursivescan` 的“递归”指文件内部
  resource/overlay，不是目录深度。
- 发布 CLI 的 recursive 会启用 resource 和 overlay；默认及单独 aggressive
  不启用。PE PDF resource/overlay 已 Observed。
- archive 解包由独立 `bIsArchivesScan` 控制，发布 CLI 不设置它；ZIP 和
  ZIP→ZIP 样本在 recursive/aggressive 组合下均不解包。
- archive 源码 `nLimit` 为 20/100000，但默认 `>` 判断实际允许第 21 个
  scanable member；resource 的 `<=` 判断也允许第 21 个，aggressive limit
  为 2000。两条默认 21、aggressive 至少 22 的边界均已 Observed。
- overlay 始终作为 subdevice 扫描；非 aggressive resource 仅在探测为
  scanable 类型时扫描。
- 项目生成的 RT_MANIFEST 未分类 payload 证明完整链：recursive 单独跳过，
  recursive+aggressive 产生 `Binary / Resource` child，并将 resource ID `24`
  传入原样 `win_resources.1.sg` 得到 `Manifest[Resources]`。raw 与规范化基线见
  [`resource-context-chain-qt5.json`](data/resource-context-chain-qt5.json)。
- `XPE::getFileParts()` 能生成 debug-data file part，但固定
  `XScanEngine::scanProcess()` 只请求 resource/overlay，完整 engine 源文件中
  `FILEPART_DEBUGDATA` 为 0 次。因此发布 scanner 的普通 recursive 不调度
  debug-data；直接 context-rule 正例只证明规则在显式上下文中的语义。
- JSON 结果通过父 detection 的 `values` 表达树，并保留 file part、size 和
  offset。详见 [`nested-scan-behavior.md`](nested-scan-behavior.md)。
- 源码未见独立嵌套深度和 archive 总解压字节限制；跨平台和资源耗尽行为待验证。

## 结果模型

`SCAN_RESULT` 源码字段：

- `nScanTime`, `sFileName`, `nSize`, `ftInit`。
- `listRecords`, `listErrors`, `listDebugRecords`, `listHandlers`。

每个 `SCANSTRUCT` 包含：

- heuristic/unknown 标记。
- 自身与父级 ID。
- record type/name 枚举及字符串 type/name。
- version、info、规则信息与优先级。

Rust 内部结果模型和差分规范化不能在检查各输出 formatter 前冻结。

## 待实验矩阵

- 尚未实验的 CLI 选项及专用模式剩余 struct/阈值边界。
- 发布 CLI 的合法/空/多级截断/重复/`..`/根前缀 ZIP database 已 Observed；
  engine-only cache miss/hit、同统计 stale、bad magic、截断和预取消已 Observed；
  其他 header/截断边界、写失败、并发和权限失败仍待 harness。
- Unicode/特殊 filename 及 Windows/macOS 的路径和枚举差异。
- JSON/XML/CSV/TSV 的转义和嵌套排序。
- deep 以及 aggressive resource 过滤/计数上限的增量样本。
- 其他 archive 格式、aggressive 高上限、最大深度和总解压资源限制。
- Qt 5 与 Qt 6 的首轮基础/安全语料/不可读输入差分已完成；仍需扩展到完整
  output/scan/special/path/database/nested 矩阵及其他 Qt 6 minor。
- Linux、Windows、macOS 路径与编码差异。

## 证据

- [CLI main](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)
- [XOptions option table](https://github.com/horsicq/XOptions/blob/810d78d0654f45d39bf07bcda5dc92ce287a4aeb/xoptions.cpp)
- [XScanEngine result/options model](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.h#L996)
- [XScanEngine scan process](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2606)
- [DiE script filtering/execution](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp#L109)
