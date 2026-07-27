# 上游源码分析

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-27

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
[`cli-path-behavior.md`](cli-path-behavior.md)。

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
截断、重复名称和路径选择实验证据见
[`database-archive-cache.md`](database-archive-cache.md)。

运行实验还确认：函数返回值只反映 main；extra/custom 失败被忽略；空目录被视为
成功；CLI positional target 分支漏设 `bIsDbUsed`，使 main 加载失败不改变
普通扫描退出码。完整错误矩阵见
[`database-error-behavior.md`](database-error-behavior.md)。

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
| archive/resource/overlay 递归 | 无深度/总解压限制；CLI 与 engine 可达性不同 | 其他格式、高上限和资源耗尽实验 |
| 目录枚举无深度/循环保护 | symlink loop、栈/时间耗尽 | 隔离测试并为 Rust 设计资源限制 |
| formatter 分散 | JSON/XML 契约不明确 | 逐格式保存 schema 和 escaping 样本 |
| engine database cache | `readAll`/无界 record count、弱 freshness；CLI 不启用 | 专用 harness 验证 stale/corrupt/cancel |
| 数据库/输入错误语义随入口变化 | 静默漏报、无效 JSON、调用方误判 | 核心 typed error + CLI compatibility ADR |
| CLI 部分选项有 `TODO` | “能力相同”范围争议 | 构建并运行确认真实行为 |

## 后续调研

1. 建立完整规则目录和语法统计。
2. 提取 `Binary_Script` 及每个派生宿主类的公开 API。
3. 扩展 engine archive harness，验证其他格式、高上限和资源限制。
4. 补齐 `ScanItemModel` 的转义、多目标和嵌套输出 schema。
5. 建立 Windows/macOS oracle 并与当前 Linux 行为基线差分。
