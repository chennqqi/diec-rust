# 上游源码分析

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-28

## 范围

本轮只分析无 GUI 命令行扫描的主路径。GUI、反汇编视图、编辑器、在线工具、更新器和其他辅助 widget 暂未纳入调用链。

## 顶层关系

```text
src/console/main_console.cpp
    ├── XOptions                 CLI option definitions
    ├── XFileInfo               --info / --struct
    ├── EntropyProcess          --entropy
    ├── DiE_Script              rule engine facade
    │     └── XScanEngine       scan orchestration and result model
    │           ├── Formats     format probing/parsers
    │           ├── XArchive    archive unpacking
    │           └── modules/*   per-format script host objects
    └── ScanItemModel           text/JSON/XML/CSV/TSV rendering

Detect-It-Easy/db*               JavaScript-like DIE rules
signatures/*                     binary crypto/junk signatures
```

`StaticScan` 在顶层作为 submodule 存在，但当前 `src/console/CMakeLists.txt` 没有直接包含它。它是否属于目标“能力相同”的 engine 范围，需要从产品行为而非仓库名称决定。

## CLI 主流程

[`main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp) 的流程：

1. 注册 Qt application identity、编码和 CLI options。
2. 把选项转换为 `XScanEngine::SCAN_OPTIONS`。
3. 默认启用 main、extra 和 custom database 路径。
4. 根据模式进入 database listing、struct listing、未完成的 test/create-test，或目标扫描。
5. 对目标调用 `XBinary::findFiles()`；目录在 CLI 中无条件递归展开。
6. entropy 和 file-info 走独立处理器；普通扫描调用 `DiE_Script::scanFile()`。
7. 使用 `ScanItemModel` 输出 text/JSON/XML/CSV/TSV。
8. 追加打印脚本错误，返回 `XOptions::CR`。

重要观察：CLI 不是单纯的扫描引擎包装。entropy、file info 和普通规则扫描有
三条不同路径，且 formatter 优先级不同。专用路径的固定 oracle 实验见
[`cli-special-modes.md`](cli-special-modes.md)。

`--recursivescan` 不控制第 5 步的目录枚举，而是控制单个文件内部的
resource/overlay 递归。多目标顺序、filename prefix 和结构化输出有效性见
[`cli-path-behavior.md`](cli-path-behavior.md)；无参数 `QDir::entryInfoList()`
在 Linux Qt5 的 Unicode、非 UTF-8、控制字符、hidden 与大小写排序结果见
[`special-path-behavior.md`](special-path-behavior.md)。固定镜像全部 locale
在同一 filesystem 上输出一致，但 tmpfs 与 `ext2/ext3` volume 会交换
`A-case`/`a-case` 顺序，见
[`path-locale-filesystem-behavior.md`](path-locale-filesystem-behavior.md)。
同一 overload 的
file/directory symlink follow、alias 重复、权限静默、depth-64 与 self-cycle
运行边界见 [`path-filesystem-behavior.md`](path-filesystem-behavior.md)；
循环终止来自 Linux 路径解析上限，不是 engine visited set 或预算。
flat/nested 4096 项均完整枚举；Formats overload 虽按可选 `PDSTRUCT` 检查取消，
发布 CLI 的两参数调用使用默认 `nullptr`，所以 target expansion 没有可达的
cooperative cancellation。固定 source/runtime 证据见
[`large-directory-behavior.md`](large-directory-behavior.md)。
完整 list 中只保存 absolute path string；后续 entropy 才按该 path 打开。
SIGSTOP 同步实验确认枚举后原子替换 symlink 会扫描新 target，unlink 则保留
prefix 但返回空成功文档，见
[`path-toctou-behavior.md`](path-toctou-behavior.md)。

## 扫描主流程

`DiE_Script` 继承 `XScanEngine`，只重写 `_processDetect()`，因此格式分派、嵌套扫描和结果聚合在 `XScanEngine`，DIE JavaScript 规则执行在 `die_script`。

普通文件扫描调用链：

```text
DiE_Script::scanFile()
  -> XScanEngine::scanFile()
  -> XScanEngine::scanDevice()
  -> XScanEngine::scanProcess()
       -> XFormats::getFileTypes()
       -> choose preferred file type
       -> DiE_Script::_processDetect()
            -> DiE_Script::processDetect()
                 -> init signatures
                 -> filter signatures
                 -> DiE_ScriptEngine::evaluateEx()
                 -> Detect/DetectHeuristic/... function
                 -> collect/sort SCANSTRUCT
       -> optional archive/resource/overlay recursion
       -> aggregate SCAN_RESULT
```

源码证据：

- [`XScanEngine::scanFile/scanProcess`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2555)
- [`DiE_Script::processDetect`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp#L109)

## 格式探测与分派

`scanProcess()` 先调用 `XFormats::getFileTypes(device, true, pdStruct)` 获得集合，之后使用有序的 `if/else if` 选择主类型。这意味着：

- 类型集合可能包含多个候选。
- 首选顺序是可观察语义，不能仅用独立 parser 成功与否替代。
- `--alltypes` 会为部分兼容/容器类型额外执行父类型规则，例如 PE 同时执行 MS-DOS，APK/IPA 同时执行 JAR/ZIP。
- 未命中特定主类型时会尝试 COM 与 Binary fallback。

Rust 设计前必须把完整分派顺序提取为测试表，并用多义样本验证。

## 规则数据库加载

`XScanEngine::loadDatabase(SCAN_OPTIONS*)` 按顺序加载：

1. main database。
2. 如果启用，extra database。
3. 如果启用，custom database。

数据库规则被解析为 `SIGNATURE_RECORD`，汇总后按优先级排序。加载支持目录和
ZIP；发布 CLI 零初始化 `bUseCache=false`，不会 cache hit，并会删除同路径旧
cache。engine cache 是 Qt `QDataStream` version 5，只用 file count、total
size、newest mtime 判定 freshness，没有内容 hash 或读取/record 上限。ZIP
截断、重复名称和路径选择，以及 engine cache stale/corrupt/cancel 实验证据见
[`database-archive-cache.md`](database-archive-cache.md)。

固定 Qt5 harness 进一步确认：保持三项统计不变的内容替换命中旧规则；截断
record 在 fallback 前已向结果追加部分记录；预取消 miss 仍返回成功并写出空
cache，下一次未取消加载会复用该 cache 并静默得到 `Unknown`。因此 Rust database
build/cache decode 必须事务化，取消或失败不得发布 records 或提交 cache。

运行实验还确认：函数返回值只反映 main；extra/custom 失败被忽略；空目录被视为
成功；CLI positional target 分支漏设 `bIsDbUsed`，使 main 加载失败不改变
普通扫描退出码。完整错误矩阵见
[`database-error-behavior.md`](database-error-behavior.md)。

三层成功加载时，每层内部按 signature priority/name 排序后，以
`main → extra → custom` 连续块 append；同名 record 不覆盖也不去重。扫描时
`_shouldExecuteSignature()` 仍可按 extra/custom flag 过滤已经加载的 records。
固定同名 fixture 与 Qt5 engine 证据见
[`database-layer-behavior.md`](database-layer-behavior.md)。

`DiE_Script::_shouldExecuteSignature()` 过滤条件包括：

- signature file type 与当前 file type 匹配。
- 可选 signature name/path 精确过滤。
- deep 和 heuristic 开关。
- 跳过普通循环中的 `Init`。
- database type 是否启用。

## 脚本运行时

`DiE_ScriptEngine` 在 Qt 5 构建使用 `QScriptEngine`，在 Qt 6 构建使用 `QJSEngine`。每个扫描对象创建脚本引擎，依次：

1. 查找并执行 global init。
2. 查找并执行当前 file type init。
3. 遍历已排序 signature。
4. `evaluateEx()` 加载 signature 文本。
5. 从 global object 获取选择的 detect function。
6. 默认 detect function 接收 show-type/show-version/show-info 三个布尔参数。
7. 脚本通过宿主 API 添加/删除结果、检查停止状态、include 其他脚本等。

各格式宿主对象位于 `XScanEngine/modules/*_script.{h,cpp}`，继承关系复用了 Binary、
MSDOS、Archive、ZIP、JAR 和 Image 等公共能力。固定声明、默认参数、继承和规则
调用覆盖见 [`host-api-inventory.md`](host-api-inventory.md)；类型转换和行为
fixture 仍是规则 1:1 复用的核心风险。

NPM 是“类、宿主和规则存在，但公共自动分派不可达”的具体反例。固定源码中
`getFileTypesTGZ()` 能加入 `FT_NPM`，但活动的 `getFileTypesGZIP()` 细分逻辑
被整体注释，外层只加入 `FT_ARCHIVE|FT_GZIP`；`scanProcess()` 只有显式
`FT_NPM` 分支。直接检测、自动扫描和强制属性三层的固定源码/运行证据见
[`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)。后续 Rust
调用链模型必须分别表达 detector 命中与 public dispatch 结果，不能从类型实现
存在性推断公共可达性。

generic Archive 又揭示了三阶段分派：Formats 自然检测同时加入
`FT_ARCHIVE + concrete subtype`；scanner 仅在单一 `FT_ARCHIVE` 时进入通用
分支；脚本宿主随后重新检测 concrete subtype，经 `createClass()` 创建具体
XArchive adapter。ZIP/TAR/GZIP 的双 release 与 forced-property 控制见
[`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)。
Rust 结果与调试模型必须能区分这三阶段，避免用任一中间集合覆盖顶层初始类型。

## 结果与层级

`SCAN_RESULT` 不只是字符串：

- 文件级元数据：filename、size、initial file type、scan time。
- detection records。
- script errors 和 profiling/debug records。
- handlers。

`SCANSTRUCT` 用 `id` 与 `parentId` 表达树。`SCANID` 包含 UUID、file type、file part、version/info、size/offset 和 original name。嵌套 archive entry、resource、overlay 或其他 subdevice 可以形成子结果。

本项目应先保留完整内部结构，再决定哪些字段进入稳定 C ABI；不能直接把上游格式化字符串作为核心模型。

## 内存与资源行为观察

`scanProcess()` 对不超过 `XBinary::getFileBufferSize()` 的非内存 device 分配与文件大小相等的 buffer，并完整读取后继续扫描。大文件继续使用原 device。

archive 扫描源码包含：

- 只由 `bIsArchivesScan` 启用；发布 `diec` CLI 不设置该选项。
- 默认 `nLimit` 为 20，但扫描后的 `>` 判断允许第 21 个符合条件的成员；
  22 个 PDF 成员实验已确认。
- aggressive 模式限制 100000。
- 循环硬上限 100000。
- 为每个 entry 创建按 uncompressed size 定义的 file buffer，再决定是否递归扫描。

resource/overlay 由 `bIsRecursiveScan` 或各自独立选项启用。resource 枚举上限
10000、扫描 `nLimit` 为 20/2000，22 个 PDF resource 实验确认默认扫描 21
个、aggressive 扫描 22 个；overlay
每层最多取 1 个且无条件扫描。递归复制完整 options，源码路径未见独立深度或
总解压字节限制。固定 PE resource/overlay 和 archive 不可达实验见
[`nested-scan-behavior.md`](nested-scan-behavior.md)。

固定 source audit 还确认 XPE 格式层支持 `FILEPART_DEBUGDATA` 枚举，但普通
`XScanEngine::scanProcess()` 的完整源码中没有该 token，只请求 resource 与
overlay。resource 的父类型 ID 会写入 child `sScanID`；项目生成的
RT_MANIFEST 样本已在固定 CMake Qt 5 CLI 中端到端触发原样 Binary 规则。机器
证据见
[`subdevice-source-audit.json`](data/subdevice-source-audit.json) 和
[`resource-context-chain-qt5.json`](data/resource-context-chain-qt5.json)。
同一 PE 的 paired runtime oracle 又证明 Formats 确实枚举出 RSDS debug part，
原样 debug rule 在 direct context 命中，而 public recursive+aggressive 只调度
同文件的 Manifest resource；见
[`debug-data-dispatch-behavior.md`](debug-data-dispatch-behavior.md)。
Rust 兼容模式必须同时复现 resource context 传播和 debug-data 默认不可达性，
不能因 parser 能枚举某类 file part 就自动把它加入 work queue。

这些是 Rust 实现需要重新审视的安全边界。兼容检测结果不代表必须复制潜在的无界内存风险；若设置更严格限制导致可观察差异，应通过 API/配置和 ADR 明确处理。

## Qt 耦合点

无 GUI CLI 仍直接依赖 Qt：

- `QCoreApplication`、`QCommandLineParser`、QString/containers、QIODevice。
- Qt signals/slots 和 QObject。
- Qt Concurrent。
- Qt 5 Script/ScriptTools 或 Qt 6 Qml JavaScript engine。
- 格式、archive、结果模型也广泛使用 Qt 类型。

因此去 Qt 不是替换 CLI parser 就能完成，而是需要同时替换：

- 字节设备抽象。
- 字符串/集合/variant/data model。
- signal/cancellation/progress。
- JavaScript runtime 与宿主绑定。
- formatter 和部分并发代码。

## 初步风险

| 风险 | 影响 | 下一项验证 |
| --- | --- | --- |
| Qt Script 与 QJSEngine 方言/行为差异 | 规则无法 1:1 复用 | 统计语法并选复杂规则做双引擎实验 |
| 格式宿主 API 面积未知 | 工作量和漏报风险 | 自动提取所有 exposed method/property |
| 多候选格式的优先顺序 | 分类结果偏差 | 建立分派顺序表和多义样本 |
| archive/resource/overlay 递归 | 无深度/总解压限制；runtime 到达 ZIP 64 层/33,554,546 累计展开 bytes；resource 为 21/2001，PE parser 每目录限 1000；archive 第 100000 条可达、第 100001 条不可达；7Z Copy/LZMA/LZMA2/BZip2/Deflate、RAR4 store、CAB Store/MSZIP、ISO9660 正例及 ZIP deflate/ZipCrypto/首轮畸形已固定 | 继续验证 PPMd7/Deflate64/filter/AES、RAR 压缩、CAB LZX/Quantum、系统化畸形和资源耗尽 |
| 目录枚举无深度/循环保护 | symlink loop、栈/时间耗尽 | 隔离测试并为 Rust 设计资源限制 |
| formatter 分散 | nested XML 非良构；CSV/TSV 无引用且丢失父节点 | 已保存逐格式 schema/escaping golden；Rust legacy 层不得“修复”后冒充兼容 |
| engine database cache | `readAll`/无界 record count、弱 freshness；截断会泄漏部分 record，取消可持久化空 cache；CLI 不启用 | 验证 header/长度上限、写失败和并发 writer |
| 数据库/输入错误语义随入口变化 | 静默漏报、无效 JSON、调用方误判 | 核心 typed error + CLI compatibility ADR |
| CLI 部分选项有 `TODO` | “能力相同”范围争议 | 构建并运行确认真实行为 |

## 后续调研

1. 建立完整规则目录和语法统计。
2. 提取 `Binary_Script` 及每个派生宿主类的公开 API。
3. 扩展 engine archive harness，验证其他格式、高上限和资源限制。
4. 将已闭合的 `ScanItemModel` 转义与嵌套 schema 纳入未来 legacy serializer golden。
5. 建立 Windows/macOS oracle 并与当前 Linux 行为基线差分。
