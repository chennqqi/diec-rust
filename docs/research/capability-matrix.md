# 上游能力矩阵

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-25

本矩阵当前只记录静态源码能够证明的入口。`Observed` 表示已用固定二进制和样本验证；本轮尚未完成上游构建，因此所有项目均为 `Source only` 或 `Pending`。

## CLI 输入

| 能力 | 上游入口 | 状态 | 备注 |
| --- | --- | --- | --- |
| 单文件扫描 | positional `target` | Source only | `scanFile()` |
| 多目标扫描 | 多个 positional `target` | Source only | 汇总后逐文件扫描 |
| 目录枚举 | positional directory | Source only | `XBinary::findFiles()` |
| 递归目录 | `-r`, `--recursivescan` | Source only | 实际目录深度行为待实验 |
| 内存扫描 | engine `scanMemory()` | Source only | CLI 不直接暴露 |
| device/subdevice 扫描 | engine API | Source only | 是嵌套扫描基础 |

CLI 主入口为 [`src/console/main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)，选项名称与描述来自 `XOptions@810d78d.../xoptions.cpp`。

## CLI 扫描控制

| Short | Long | 上游描述 | 代码映射 | 状态 |
| --- | --- | --- | --- | --- |
| `-r` | `--recursivescan` | Scan directories recursively | `bIsRecursiveScan` | Source only |
| `-d` | `--deepscan` | Enable deep scanning for thorough analysis | `bIsDeepScan` | Source only |
| `-u` | `--heuristicscan` | Enable heuristic scanning methods | `bIsHeuristicScan` | Source only |
| `-b` | `--verbose` | Show verbose output with detailed information | `bIsVerbose` | Source only |
| `-g` | `--aggressivecscan` | Enable aggressive scanning mode | `bIsAggressiveScan` | Source only; long name含额外 `c` |
| `-a` | `--alltypes` | Scan all file types | `bIsAllTypesScan` | Source only |
| `-f` | `--format` | Format the output result | `bFormatResult` | Source only |
| `-l` | `--profiling` | Profile signatures during scan | `bLogProfiling` | Source only |
| `-M` | `--messages` | Display scan messages and warnings | Qt signal output | Source only |
| `-U` | `--hideunknown` | Hide unknown file types from results | `bHideUnknown` | Source only |

注意：`XScanEngine::SCAN_OPTIONS` 还定义 resource、archive 和 overlay scan，但当前顶层 `src/console/main_console.cpp` 没有注册相应 CLI 选项。这是“引擎能力”和“当前 CLI 能力”必须分开比较的实例。

## CLI 专用模式与输出

| Short | Long | 能力 | 状态 |
| --- | --- | --- | --- |
| `-e` | `--entropy` | 输出分区/区域熵信息 | Source only |
| `-i` | `--info` | 输出文件信息模型 | Source only |
| `-S` | `--struct <value>` | 特定结构信息，如 `Hash` / `Hash#MD5` | Source only |
| `-w` | `--showstructs` | 列出可用结构方法 | Source only |
| `-x` | `--xml` | XML | Source only |
| `-j` | `--json` | JSON | Source only |
| `-c` | `--csv` | CSV | Source only |
| `-t` | `--tsv` | TSV | Source only |
| `-p` | `--plaintext` | plain text | Source only |
| `-D` | `--database <path>` | 主数据库路径 | Source only |
| `-E` | `--extradatabase <path>` | extra 数据库路径 | Source only |
| `-C` | `--customdatabase <path>` | custom 数据库路径 | Source only |
| `-s` | `--showdatabase` | 显示路径及各文件类型规则数量 | Source only |
| — | `--test <directory>` | 规则测试入口 | Source only; 实现含 `TODO` |
| — | `--createtest <filename>` | 创建测试入口 | Source only; 实现含 `TODO` |

同时注册 Qt 自带 `--help` 和 `--version`。无 target 且没有 `--showdatabase` 时调用 `showHelp()`。

默认规则路径为 `$data/db`、`$data/db_extra`、`$data/db_custom`；extra 和 custom 在 CLI 中默认启用。数据库加载失败的最终返回码行为需要实际运行确认。

## 规则与扫描能力

| 能力 | 源码证据 | 状态 |
| --- | --- | --- |
| main/extra/custom 三层规则库 | `XScanEngine::loadDatabase()` | Source only |
| 规则优先级排序 | `sort_signature_prio` | Source only |
| global/type Init 规则 | `findInitSignatures()` + `_executeInitSignature()` | Source only |
| 按文件类型过滤规则 | `_shouldExecuteSignature()` | Source only |
| deep/heuristic 规则过滤 | `_shouldExecuteSignature()` | Source only |
| 自定义单条 signature/file 过滤 | `sSignatureName`, `sSignatureFilePath` | Source only |
| 未命中时产生 Unknown | `DiE_Script::processDetect()` | Source only |
| 检测结果稳定排序选项 | `bIsSort` + `sortRecords()` | Source only |
| 脚本错误收集 | `SCAN_RESULT.listErrors` | Source only |
| 脚本 profiling | `listDebugRecords` / messages | Source only |
| 取消/停止 | `PDSTRUCT`, callback, `breakScan()` | Source only |

规则脚本由 Qt 5 `QScriptEngine` 或 Qt 6 `QJSEngine` 执行。规则兼容性不是简单的模式匹配移植，必须覆盖 JavaScript 方言、全局函数和每种格式宿主对象；详见待建的 `rule-compatibility.md`。

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

## 嵌套与递归

静态源码显示：

- `scanProcess()` 对可扫描 archive 解包记录后递归调用自身。
- archive 默认处理限制为 20，aggressive 模式将限制提高到 100000。
- overlay、resources 和其他 file parts 也可形成 subdevice 并递归扫描。
- 结果通过 `SCANID` / `parentId` 表达父子关系，包含文件类型、file part、大小、偏移和原始名称。

这些路径的默认启用状态、最大深度、防压缩炸弹策略和跨平台差异尚未完成运行验证。

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

- 每个 CLI 选项的 stdout、stderr、退出码和组合优先级。
- 无效路径、空文件、不可读文件、缺失/损坏数据库。
- 多文件与目录输出中的 filename 包装格式。
- JSON/XML/CSV/TSV 的 schema、转义、排序和多目标有效性。
- deep、heuristic、aggressive、alltypes 的实际增量结果。
- archive/resource/overlay 的默认状态、递归深度和限制。
- Qt 5 与 Qt 6 输出差异。
- Linux、Windows、macOS 路径与编码差异。

## 证据

- [CLI main](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp)
- [XOptions option table](https://github.com/horsicq/XOptions/blob/810d78d0654f45d39bf07bcda5dc92ce287a4aeb/xoptions.cpp)
- [XScanEngine result/options model](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.h#L996)
- [XScanEngine scan process](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2606)
- [DiE script filtering/execution](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp#L109)

