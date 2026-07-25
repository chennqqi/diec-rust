# Binary 规则加载与执行生命周期

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-26

## 结论

固定上游的 Binary 规则不是相互隔离的程序。一次 `processDetect()` 创建一个
`DiE_ScriptEngine`，global init、Binary init、helper 和所有被选中的签名都在该
引擎的同一 global scope 中顺序求值。每条签名求值后，引擎从 global object
重新取得 `detect` 并调用；下一条签名通常用新的函数声明覆盖它。

因此，按文件建立独立 JavaScript context 会改变上游语义。候选 Rust runtime
至少必须复现：

1. 每次 scan 创建隔离引擎；
2. global `_init` 求值一次；
3. Binary `_init` 求值一次；
4. `includeScript()` 在当前引擎中立即求值目标；
5. 规则按数据库层和上游顺序逐条求值、调用；
6. parse/runtime error 不自动销毁引擎，后续规则仍可继续；
7. stop/cancel 才中断遍历。

机器清单由
[`analyze_binary_lifecycle.py`](../../tools/rules/analyze_binary_lifecycle.py)
从未修改的规则 subtree 生成，见
[`binary-rule-lifecycle.json`](data/binary-rule-lifecycle.json)。

## 数据库装载

`XScanEngine::loadDatabase(SCAN_OPTIONS*)` 依次装载 main、extra、custom；extra
和 custom 受选项控制。目录数据库对每一层分别收集记录、调用
`sort_signature_prio()`，再 append 到总列表，并不会把三层重新做一次全局排序。

`DiE_Script::isSignatureFileValid()` 只接受 regular file，且后缀必须是 `.sg`
或为空。一个文件整体生成一条 record，name 为 basename。Binary 固定规则实际为：

| Database | Binary records | Executable signatures | `_init` |
| --- | ---: | ---: | ---: |
| `db` | 293 | 292 | 1 |
| `db_extra` | 0 | 0 | 0 |
| `db_custom` | 0 | 0 | 0 |

当前版本的 Binary 执行签名全部来自 main；这只是固定数据事实，不能把 runtime
写死为“Binary 永远没有 extra/custom”。

## Init 选择

`findInitSignatures()` 从已经 append 的总列表头部向后扫描：

- 首个 `fileType == FT_UNKNOWN && name == "_init"` 成为 global init；
- 首个与当前 file type 匹配且 name 为 `_init` 的记录成为 type init；
- 两者找到后立即停止。

在正常 main → extra → custom 装载下，同名 init 由前层遮蔽。固定 Binary 基线选择：

```text
db/_init
db/Binary/_init
```

global init 依次 include `_debug`、`_runtime_helpers`、`language`；Binary init 设置
`File = Binary`、`X = Binary`，然后 include `read`。这四个 helper 都解析到 main
根目录中的无扩展名文件。

## Include 选择和作用域

`DiE_ScriptEngine::includeScriptSlot()` 有几个容易遗漏的约束：

- 只搜索 `fileType == FT_UNKNOWN` 的 root records，不搜索当前类型目录；
- name 使用 `toUpper()` 后比较，即大小写不敏感；
- 总列表中首个命中者胜出，因此正常情况下 main 遮蔽 extra/custom；
- 每次调用都会再次 `evaluate()`，没有 include cache、once guard 或 cycle guard；
- helper 在当前 engine/global scope 中执行，不是 module；
- helper 求值错误会发出 error message，但 include slot 本身不把异常重新抛给调用规则。

对 global init、Binary init 和 292 条 Binary 规则静态提取到 23 个 literal
`includeScript()` 调用，固定根记录中全部能解析；文本 site 数与 literal 数相等，
当前没有动态参数。生成器会把未来出现的非 literal site 单独列为诊断，不能把它
当成“无 include”。

重复 include 具有语义意义。例如不同签名可以重复求值同一 helper；实现不能仅凭
文件 hash 自动去重。循环 include 没有上游保护，仍需用受控 fixture 测出 Qt 5/6
的实际失败和资源行为。

## 每条规则的执行

`_executeSignature()` 先用 `evaluateEx()` 更新当前 parent/result/signature/path
metadata，再在共享引擎中求值规则文本。只有该次求值通过 error handling 后才会：

1. 从 global object 按 `SCAN_OPTIONS.sDetectFunction` 取函数；
2. 默认函数名为空时使用 `detect`；
3. 默认 `detect` 接收 show-type、show-version、show-info 三个布尔参数；
4. 调用函数并再次记录 runtime error。

外层循环随后继续处理下一条 record，只有 engine stopped 或 scan canceled 才停止。
这意味着 global variable、prototype 修改、include side effect 和前序规则留下的
函数/对象都可能被后序规则观察到。QuickJS spike 的“每文件 isolated eval”只能
证明 parser 覆盖，不能证明生命周期兼容。

## 排序比较器缺陷

`sort_signature_prio()` 的优先级提取有一个成对条件：只有左右两个 name 都包含
至少两个点时，才比较倒数第二段；否则该 pair 直接按完整 name 比较。优先级和
name 都按字符串比较。

该比较器不满足 `std::sort` 要求的 strict weak ordering。固定 Binary 文件名已经
形成环，例如：

```text
archive_DotBundle.sg
  < archive_archives.1.sg       (name)
  < __MiniBatchHeuristic_By_DosX.7.sg  (priority "1" < "7")
  < archive_DotBundle.sg        (name)
```

机器清单保存 10 个可复验环。调用 `std::sort` 时违反比较器前置条件，因此不能仅凭
源码推导一个跨 STL、编译器和平台稳定的“正确顺序”。这也解释了为什么 Rust 端
不能简单按 `(priority, name)` 排序后宣称兼容。

后续差分必须分别采集固定 Linux/Windows/macOS oracle 的真实执行序列。若上游平台
间不同，本项目需要 ADR 明确选择逐平台复刻、固定一种顺序，或把该差异作为有界
compatibility waiver；在此之前顺序策略不能冻结。

### Linux Qt5 实测顺序

[`probe_binary_rule_order.py`](../../tools/upstream/probe_binary_rule_order.py)
使用项目生成的 `ps3-type-1-elf.self`，对固定 qmake/CMake Docker oracle 运行：

```sh
python3 tools/upstream/probe_binary_rule_order.py \
  --corpus-dir /tmp/diec-nintendo-certified-corpus \
  --raw-dir /tmp/diec-binary-order-raw \
  --output docs/research/data/binary-rule-order-linux-qt5.json
```

实际传给两个 `diec` 的扫描参数为：

```text
--profiling --messages --json --deepscan --heuristicscan
--database /opt/die-source/Detect-It-Easy/db
--extradatabase /opt/die-source/Detect-It-Easy/db_extra
--customdatabase /opt/die-source/Detect-It-Easy/db_custom
```

采集器只接受 stdout 中与固定 Binary inventory 完全相等的独立行，拒绝缺失、
重复或意外名称。结果见
[`binary-rule-order-linux-qt5.json`](data/binary-rule-order-linux-qt5.json)：

- qmake、CMake 均 exit 0、stderr 为空；
- 两侧都恰好提取 292 条且逐项相等；
- canonical UTF-8/LF 顺序 SHA-256 为
  `27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc26b1a9ff0e1ff3`；
- 连续重复两次实验，四次序列 hash 相同；
- profiling 毫秒数会改变原始 stdout hash，因此原始 hash 只标识当次 artifact，
  不作为重跑时必须逐字节相等的断言。

没有标准优先级段的六条可执行规则实际位置为：

| Index（0-based） | Signature |
| ---: | --- |
| 1 | `ROM_1.sg` |
| 20 | `archive_DotBundle.sg` |
| 41 | `archive_PC_Secure.sg` |
| 148 | `format_MS-PST.sg` |
| 150 | `format_MS-VHDX.sg` |
| 248 | `image_ICNS.sg` |

该清单可以驱动 Linux QuickJS lifecycle probe，但只能证明这两个 GCC/libstdc++
构建在固定输入上的顺序。Windows MSVC、macOS libc++ 仍必须分别采集，不能从
Linux 一致性推断。

## 对 runtime spike 的门禁

QuickJS Nintendo probe 已经在每个共享 context 中执行真实 global/Binary init，
include trace 固定为 `_debug`、`_runtime_helpers`、`language`、`read`，且
manifest-pinned overlay 后 14/14 target detection 匹配。

固定 Linux 顺序的完整顶层 eval 进一步发现 3 个 modern-JavaScript 差异：
Nintendo function 内重定义，以及跨 rule eval 的 `const detect`、`const debug`
绑定冲突。三个 path/size/declaration/hash-pinned 等长 overlay 后，292/292 顶层
程序在同一 QuickJS context 中通过，共执行 30 次 include。详细错误、overlay
和源 hash 见
[`rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json)。

专用跨规则 fixture 已进一步证明，Qt 5 的可观察契约不会把前一规则的 lexical
`const` 作为后一规则的只读或重声明冲突，同时仍能在每次求值后调用本次 lexical
`detect`。QuickJS 单一 global context 与此不等价；详见
[`script-scope-semantics.md`](script-scope-semantics.md)。

同一 spike 的 per-rule non-strict function lexical wrapper 已在共享
host/global context 中按本清单重跑：292/292 规则均成功求值并解析出 function
类型的 `detect`，30 次 include trace 不变，只保留 Nintendo 单脚本语法 overlay。
这消除了 `audio const debug` 和 MiniExtensions `const detect` 的跨规则改写需求，
但尚未调用完整规则库的 detect，不能据此接受 runtime ADR。

下一轮完整 signature lifecycle probe 仍至少要满足：

- 逐条调用已固定 Linux 顺序中的 `detect`，再补齐 Windows/macOS 顺序；
- Nintendo overlay 只在 manifest-pinned 目标规则求值前应用；
- 同一 context 中运行 `audio.1.sg`、Nintendo 规则和 `audio_EXA.1.sg` 所需依赖；
- 对 14 个 Nintendo 样本比较完整有序结果，包括 Vita 的 EA-XA 邻接结果；
- 保存每条 rule eval、include、host call、result/error 的 trace；
- 单条失败后验证后续规则是否继续且 metadata 已切换；
- 不把静态分析器的任意排序结果当作上游 oracle。

在该门禁通过前，R-001 仍为 Open，也不能据 Nintendo 单规则 14/14 结果接受
QuickJS ADR。

## 固定源码证据

- [`DiE_Script::processDetect()`、`findInitSignatures()` 与 `_executeSignature()`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp)
- [`DiE_ScriptEngine::includeScriptSlot()` 与 `evaluateEx()`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp)
- [`sort_signature_prio()` 与数据库装载](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp)
- [`db/_init`](https://github.com/horsicq/Detect-It-Easy/blob/c2c17dfa5ea4e078ba31eab55d87430c96622fb6/db/_init)
- [`db/Binary/_init`](https://github.com/horsicq/Detect-It-Easy/blob/c2c17dfa5ea4e078ba31eab55d87430c96622fb6/db/Binary/_init)

三个 C++ 源文件的下载内容 SHA-256 已固定在机器清单中；规则文件的 path、size 和
SHA-256 直接从 subtree 重算。
