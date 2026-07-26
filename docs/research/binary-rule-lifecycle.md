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
但 persistent-state fixture 证明 wrapper 会隔离 Qt 本应保留的顶层 var/function。
固定 Binary 静态审计虽未发现后一规则依赖前一规则显式声明的候选，仍尚未调用
完整规则库的 detect，不能据此接受 runtime ADR。详见
[`script-state-semantics.md`](script-state-semantics.md)。

后续 selected lifecycle probe 已在同一固定 292 条加载环境中完成：

- Nintendo overlay 每个样本只在 manifest-pinned 目标规则求值前应用一次；
- 按固定顺序调用 `archive_DEFLATE.1.sg`、`audio_EXA.1.sg` 和 Nintendo 规则；
- 对 14 个 Nintendo 样本比较目标完整有序结果，Qt 5 baseline 14/14 匹配；
- Vita 的 EA-XA 邻接结果已复现，选定 `detect` 的 fallback HostApi 增量为零；
- 发现 `archive_DEFLATE.detect()` 动态创建隐式全局 `bad`，是
  `audio_EXA.detect()` 的前置状态。

这项动态依赖不在此前顶层 AST 审计范围内，证明完整生命周期不能只依赖静态
wrapper-loss 零候选。在该 selected probe 中，非目标规则只执行了顶层代码，未
调用 `detect`。

全 Binary diagnostic probe 又按该顺序逐条尝试了 292 个 `detect`，并在单条异常
后继续执行。首轮得到 281 条无异常、11 条异常，253 条规则调用 34 类缺失
HostApi。按固定上游契约补入基础整数、字符串、字节数组、size 和 `Util.div64`
后，结果改善为 285 条无异常、7 条异常，但仍有 233 条规则调用 19 类 fallback；
代理制造的 153 条 detection 仍然无效。此外 32 条规则调用了 317 种简化 `X.c`
未支持的签名 pattern。因此该实验完成的是动态缺口 inventory，不是完整
signature compatibility。

后续固定 Qt 5/Qt 6 numeric oracle 又闭合 `U24`/`read_uint24` 的端序、别名及
`Util.shru64` 的 0/4/32 位移。Rust fixture 精确匹配后，全库 fallback 调用由
387 降到 365、唯一路径由 19 降到 17；触发规则仍为 233，不能据此声称新增规则
兼容。

随后以固定 Qt 5 oracle 验证的 pure-Rust adapter 替换五-pattern
`X.c` 特判，并同时注册 `Binary.c`/`compare` 与 `X.c`/`compare`。固定样本上
共执行 799 次 compare（776 fast、23 generic、5 个显式 quirk、0 error），
292/292 个 `detect` 无异常完成；fallback 降为 16 条规则、58 次、18 条路径，
未记录 fallback 的规则增至 276。代理仍会影响控制流，当前 10 条 detection
不是兼容证据。

同一 adapter 随后接入 `fSig`、`findSignature` 和 `isSignaturePresent`。固定
输入实际执行 11 次搜索、1 个兼容 quirk、0 adapter error。真实 `false/-1`
替换 truthy fallback proxy 后改变控制流，compare 增至 1179 次；291/292 个
`detect` 无异常，fallback 为 14 条规则、39 次、15 条路径，未记录 fallback
的规则为 278。`data_overlays.6.sg` 的唯一异常来自随后抵达的
`isOverlay/getOverlayOffset/getOverlaySize` 缺口，不是签名搜索错误。

固定 oracle 的 3/3 个 overlay HostApi 向量随后确认“当前 file-part 是 overlay”
与“当前对象含 nested overlay”相互独立。显式 `BinaryHostContext` 接入后，两条
规则各调用一次 `isOverlay` 并得到 false，offset/size/presence 因短路未调用；
compare 变为 1109 次，292/292 个 `detect` 无异常，fallback 降为 12 条规则、
34 次、11 条路径，未记录 fallback 的规则为 280。该单一 header 输入仍不能证明
格式 parser 或实际 overlay subdevice 的 context 构造。

oracle 扩展到 82-case 后，其中 15 个向量固定 Qt 文件后缀、plain/UTF-8/
UTF-16 分类和 header 解码。`BinaryStringContext` 15/15 一致并接入
`getFileSuffix`、`getHeaderString`、`isPlainText`、`isUTF8Text`；固定输入
实际调用 9/5/2/0 次。292/292 条规则无异常，fallback 降为 3 条规则、4 次、
4 条路径，未记录 fallback 的规则为 289，真实返回值下只产生 1 条 Nintendo
detection。上游 `m_bIsUnicodeText` 在非 Unicode 路径未初始化，因此
`isUnicodeText`/`isText` 不能直接冻结为确定性 Rust 行为。

下一轮完整 signature lifecycle probe 仍至少要满足：

- 以真实 HostApi 逐项替换剩余 4 条动态 fallback 路径，并补齐
  Windows/macOS 顺序；
- 为格式专用 signature receiver 和 memory map 建立端到端差分；
- 给 289 条未记录 fallback 的规则建立对应 Qt oracle，而不是按“无异常”计 pass；
- 保存每条 rule eval、include、host call、result/error 的 trace；
- 单条失败后验证后续规则是否继续且 metadata 已切换；
- 以完整上游结果排序逻辑代替当前仅用于 Nintendo/EA-XA 的目标类型投影；
- 不把静态分析器的任意排序结果当作上游 oracle。

在该门禁通过前，R-001 仍为 Open，也不能据 selected lifecycle 14/14 结果接受
QuickJS ADR。

## 固定源码证据

- [`DiE_Script::processDetect()`、`findInitSignatures()` 与 `_executeSignature()`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp)
- [`DiE_ScriptEngine::includeScriptSlot()` 与 `evaluateEx()`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp)
- [`sort_signature_prio()` 与数据库装载](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp)
- [`db/_init`](https://github.com/horsicq/Detect-It-Easy/blob/c2c17dfa5ea4e078ba31eab55d87430c96622fb6/db/_init)
- [`db/Binary/_init`](https://github.com/horsicq/Detect-It-Easy/blob/c2c17dfa5ea4e078ba31eab55d87430c96622fb6/db/Binary/_init)

三个 C++ 源文件的下载内容 SHA-256 已固定在机器清单中；规则文件的 path、size 和
SHA-256 直接从 subtree 重算。
