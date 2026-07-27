# DIE 规则兼容性调研

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`  
Runtime: `horsicq/die_script@5d82316c110abf0eb863b50bc679d330e05067b6`  
Host API: `horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`  
Last updated: 2026-07-27

## 结论摘要

“1:1 复用上游规则”要求兼容一个完整的嵌入式 JavaScript 宿主环境，不是实现一种签名字符串语法。

兼容面至少包括：

- JavaScript 解析与执行语义。
- 全局 init、文件类型 init 和 `includeScript()` 的共享作用域。
- 结果写入、去重、删除、停止和错误行为。
- `Binary` 基类及每种文件格式的宿主方法。
- Qt 类型到 JavaScript 值的转换、默认参数及 64 位整数行为。
- 规则文件加载、文件名排序、main/extra/custom 优先级。
- 上游初始化脚本增加的 polyfill 和动态对象扩展。

因此，规则引擎选型必须通过代表性规则和全库加载 spike；不能仅依据 ECMAScript 版本宣称兼容。

## 规则资产基线

| 目录 | 文件数 | 字节数 | `.sg` | 无扩展名 | 其他 |
| --- | ---: | ---: | ---: | ---: | --- |
| `db` | 2124 | 2,832,469 | 2037 | 60 | 22 PNG、3 TXT、1 INI、1 JSON |
| `db_extra` | 142 | 76,651 | 138 | 0 | 2 TXT、1 INI、1 JSON |
| `db_custom` | 2 | 196 | 0 | 0 | 1 TXT、1 JSON |
| `dbs_min` | 2269 | 1,536,757 | 2175 | 60 | 22 PNG、6 TXT、3 JSON、2 INI、1 LOG |
| `dbs_special` | 2 | 7,372 | 0 | 0 | 2 DB |

`dbs_min` 不是简单的 `db` 文件副本：其 `.sg` 数量等于 `db + db_extra` 的 2175 条，但总字节更小。它的生成、压缩/裁剪方式和发布用途尚待分析。

主规则按目录统计：

| Type | Rules | Type | Rules | Type | Rules |
| --- | ---: | --- | ---: | --- | ---: |
| Amiga | 96 | APK | 52 | Archive | 1 |
| AtariST | 1 | Binary | 292 | CFBF | 3 |
| COM | 245 | DEX | 29 | DOS16M | 2 |
| DOS4G | 2 | ELF | 46 | Image | 1 |
| ISO9660 | 23 | JAR | 2 | JavaClass | 1 |
| JPEG | 5 | LE | 3 | LX | 5 |
| MACH | 12 | MACHOFAT | 2 | MSDOS | 349 |
| NE | 13 | NPM | 4 | PDF | 7 |
| PE | 834 | PNG | 1 | PYC | 2 |
| RAR | 1 | ZIP | 3 |  |  |

Extra database 为 Amiga 2、COM 2、ELF 1、MSDOS 2、PE 131。

## 加载协议

### 目录结构

[`XScanEngine::loadDatabase()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L1284) 显式加载根目录和每个已知类型目录。数据库也可以是 ZIP；ZIP 内使用相同的一级目录名称。

当前基类实现中：

- `isSignatureFileValid()` 恒返回 true。
- `getSignaturesFromData()` 将一个文件整体作为一条 `SIGNATURE_RECORD`。
- signature name 是完整文件名。
- 文件内容原样作为待求值程序。

这意味着引擎会尝试加载所枚举目录中的所有直接文件，而不是只认 `.sg` 扩展名。同步工具不能擅自按扩展名过滤。

### Init 与 include

规则环境有两层特殊 init：

1. 数据库根目录 `_init`：定义通用 `meta()` / `result()`，并 include `_debug`、`_runtime_helpers`、`language`。
2. 当前类型目录 `_init`：为 PE、ELF 等宿主对象增加 JavaScript helper、属性和别名。

本轮在 `db` 与 `db_extra` 中静态发现 56 次 `includeScript("...")`，涉及 27 个不同目标。include 是按 signature name 从已加载记录中查找并在当前引擎/全局作用域求值，不是 ECMAScript module。

需要验证：

- 重复 include 是否重复求值。
- 循环 include 行为。
- main/extra/custom 存在同名 helper 时的选择顺序。
- include 异常对当前 signature 和后续 signature 的影响。

### 排序

[`sort_signature_prio()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L35) 先按 file type，再从文件名倒数第二个点分段提取优先级字符串，最后按完整文件名排序。

例如 `compiler_Foo.4.sg` 的优先级来自 `"4"`。比较是字符串比较，不应未经实验改成数值比较。文件重命名可能改变执行顺序和最终结果，因此文件名也是规则协议的一部分。

后续固定源码复核发现，优先级仅在比较双方都至少包含两个点时启用。Binary
现有文件名可构造非传递比较环，违反 `std::sort` 的 strict weak ordering
前置条件；各数据库又是分别排序后 append，而非 main/extra/custom 全局排序。
完整证据和 Rust 端门禁见
[`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)。

项目生成的端到端 fixture 进一步证明，type `_init` 本身就可与普通 priority
文件构成比较环；不含 `_init` 的 priority-only 列表按字符串 priority
`1 → 2 → 4`，真实 init 布局的固定 Linux 执行序列则偏离纯 priority。main、
extra、custom 的 `.0`/`.4` 反例同时确认三层分别排序后 append。见
[`rule-orchestration.md`](rule-orchestration.md)。

补充的同名 fixture 确认三个 `shared.5.sg` records 全部保留并按层执行，而非
extra/custom 覆盖 main；层已全部加载后，scan options 仍能过滤 extra/custom。
见 [`database-layer-behavior.md`](database-layer-behavior.md)。

## 执行生命周期

每个扫描对象创建一个 `DiE_ScriptEngine`：

1. 注入全局函数。
2. 注入 `Util`。
3. 注入 `Binary` 和当前格式对象；两者通常指向同一个 C++ script wrapper。
4. 执行 global `_init`。
5. 执行当前 file type `_init`。
6. 按排序后的 signature 顺序遍历。
7. 按 file type、signature name/path、deep/heuristic 和 database type 过滤。
8. 在同一引擎中求值 signature 文本。
9. 默认查找并调用全局 `detect` 函数。
10. 收集错误、结果和 profiling 信息。
11. 最终按配置排序检测记录；无结果时可增加 `Unknown`。

默认 `detect(showType, showVersion, showInfo)` 接收三个布尔参数。`SCAN_OPTIONS.sDetectFunction` 可以改用其他函数名，因此实现不应把 `detect` 写死在 parser 中。

## 全局宿主函数

Qt 5 `QScriptEngine` 路径注册：

```text
includeScript
_log
_setResult
_isResultPresent
_getNumberOfResults
_removeResult
_isStop
_encodingList
_isConsoleMode
_isLiteMode
_isGuiMode
_isLibraryMode
_breakScan
_getEngineVersion
_getOS
```

Qt 6 `QJSEngine` 路径还暴露 `_getQtVersion`。该差异需要在上游双版本实验中确认，Rust 兼容目标不能默认选择其中一边。

`Util` 暴露 7 个函数：有符号/无符号 64 位 shift、division，以及 seconds-to-time string。

## 格式宿主对象

`DiE_ScriptEngine` 总是注册 `Binary`，并在非 Binary 类型下额外以格式名注册同一 wrapper。规则中的 `File` 和 `X` 通常由类型 `_init` 指向该格式对象。

从 `public slots` 静态提取到 30 个 `*_Script` 类、337 个直接声明的方法。此前
人工计数 338 误包含 `pe_script.h` 中一条已注释声明；继承后每个具体类型还拥有
父类方法。完整机器清单和规则调用覆盖见
[`host-api-inventory.md`](host-api-inventory.md)。

| Class | Parent | Direct methods |
| --- | --- | ---: |
| `Binary_Script` | `QObject` | 155 |
| `MSDOS_Script` | `Binary_Script` | 13 |
| `PE_Script` | `MSDOS_Script` | 87 |
| `ELF_Script` | `Binary_Script` | 26 |
| `MACH_Script` | `Binary_Script` | 12 |
| `DEX_Script` | `Binary_Script` | 4 |
| `Archive_Script` | `Binary_Script` | 2 |
| `ISO9660_Script` | `Archive_Script` | 9 |
| `JAR_Script` | `ZIP_Script` | 2 |
| `APK_Script` | `JAR_Script` | 2 |
| `NPM_Script` | `Archive_Script` | 2 |
| `Jpeg_Script` | `Image_Script` | 5 |
| `PNG_Script` | `Image_Script` | 11 |
| `PDF_Script` | `Binary_Script` | 4 |
| `PYC_Script` | `Binary_Script` | 1 |
| other 15 classes | various | 0–2 each |

`Binary_Script` 的能力包括：

- 定长整数、24-bit、float、BCD、字符串和 UUID 读取。
- signature/string/number 查找与比较。
- offset/RVA/VA 转换。
- entry point、overlay、file part 和格式状态。
- entropy、MD5、CRC16/32、Adler32。
- 反汇编。
- compression 探测与解压。
- encoding、文件名及格式诊断。
- deep/heuristic/aggressive/recursive 等扫描状态。
- 短别名 `U8/U16/U24/U32/U64`、`I*`、`F*`、`SA`、`Sz`、`fSig`、`c` 等。

PE 的新增 API 覆盖 section、resource、imports/exports、.NET metadata、Rich header、manifest、TLS、debug data、版本信息和表完整性。

静态规则调用统计显示，仅 PE 对象就出现约 4,331 次方法调用、134 个不同方法名。这里包含类型 `_init` 动态添加的 JavaScript helper，不全是 C++ slot。`X` 短别名出现约 8,351 次调用、31 个不同方法名。该统计证明高频使用面很大，但不能替代 AST 级调用分析。

## JavaScript 语言与动态扩展

规则主要使用传统 function/var 风格，但真实代码也使用 `const`。在 41 个文件中词法命中 `let` 或 `const`，抽查确认多个 `const` 是实际代码。

本轮对 arrow function 的两次命中都位于注释，并明确写有 Qt 5 compatibility；`class` 命中也是注释/JSDoc。`?` 同时是 binary signature wildcard，因此 optional chaining/nullish 等特征不能用简单正则可靠统计。下一步需要用选定 JavaScript parser 生成 AST 统计。

根 `_runtime_helpers` 会修改内建 prototype：

- `String.append`, `appendS`, `addIfNone`。
- `String.startsWith/endsWith` 及 case-insensitive 变体。
- `String.repeat`, `replaceAll`, `includes`。
- `String.padStart` 和 `Number.padStart/clamp`。
- `Array.includes`。

规则还广泛使用 RegExp、`String.match()`、动态 property、prototype method、嵌套 function、Error/stack 和数组。规则执行必须允许 init 脚本对宿主对象继续添加 JavaScript 方法。

## 结果语义

根 `_init` 的 `meta()` 设置 type/name/version/options/language，`result()` 最终调用 `_setResult()`。

[`_setResultSlot()`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp#L648)：

- 记录自身与父级 scan ID。
- 保存执行 signature name 和 file path。
- 从 type 计算 heuristic 标记、枚举和优先级。
- type/name 转枚举时会 uppercase 并移除空格、连字符。
- first-wrapper 模式只接受 protection/bundle，并在首次结果后停止。

结果删除会维护 blacklist，后续相同 type/name 不再加入。固定 Qt5/Qt6 global
HostApi harness 已确认：大小写不同的普通结果可同时保留；lookup/delete
大小写不敏感；delete 只删除首个命中并把该 type/name 加入 block list；再次加入
被阻止；空 name 不是删除 wildcard；数组参数先字符串化为
`"Enigma,Denuvo"`。详见
[`global-host-api-runtime-differential.md`](global-host-api-runtime-differential.md)。

## 类型转换兼容风险

Qt 通过 `newQObject()` 暴露 slots。替换运行时必须逐项定义：

- `quint64/qint64` 到 JavaScript Number 的精度、符号和溢出。
- `quint8/qint8` 的表现；源码专门用 `qint16` 避免 JS 把 `qint8` 显示为 char。
- `QString`、无效 UTF-8、NUL 和大小写转换。
- `QList<QVariant>` / `QStringList` 到数组的转换。
- C++ 默认参数在脚本少传参数时的行为。
- overload/virtual method 和继承方法的可见性。
- C++ 返回错误、越界读取和 Qt warning 如何映射到 JavaScript。
- RegExp、Error.stack、NaN、Infinity、位运算和负移位语义。

这些细节必须转为 conformance fixtures，而不能只靠 API 名称匹配。

## 已观测错误传播

project-generated 最小规则实验已经分别触发 Qt Script parse error 和
`detect()` runtime error。两者都：

- 在 database load 阶段被当作一个有效 signature 计数；
- 到实际扫描该 filetype 时才执行并失败；
- 仍产生 Unknown detection；
- 把错误文本追加到结构化 stdout；
- 返回 CLI exit code 0。

该行为及缺失/空/无效 database、不读 input 的对照见
[`database-error-behavior.md`](database-error-behavior.md)。这是上游 CLI
兼容证据，不改变本项目“未知或不支持语法必须明确诊断并计入兼容失败”的门禁。
未来 runtime conformance 需要同时比较错误阶段、文件/行号、后续 signature 是否
继续执行、结果保留和结构化诊断；不能只比较异常类型。

固定规则中的两个未定义 global 也已由 32/40 字节安全输入证明确实可达。固定
Qt 5 qmake/CMake 对二者逐字节一致：`Binary/Unknown` detection 后在 stdout 追加
精确 `ReferenceError`，stderr 为空且 exit 0。由于完整 stdout 是“JSON document +
trailing diagnostic”而不是单个合法 JSON value，oracle reader 必须同时保存原始
字节并解析尾随记录。详见
[`global-typo-error-behavior.md`](global-typo-error-behavior.md)。

固定 Qt 6.4.2 CMake oracle 保持相同 detection、exit、空 stderr 和 framing，但
`ReferenceError` 文本改为 `NAME is not defined`。同一 Qt 5/Qt 6 CLI 初始矩阵还在
最小 PE 上发现 Qt 6 独有的四行 `Unimplemented code.` stderr，并将来源二分到
`PE/__GenericHeuristicAnalysis_By_DosX.7.sg`；四类整数返回桥接和 PE init-only
实验均未复现该 warning。见
[`upstream-qt6-differential.md`](upstream-qt6-differential.md)。同一真实 global
HostApi harness 又证明 Qt 5 宽松接受四个缺参调用，而 Qt 6 抛出
`Insufficient arguments`；null 字符串化和 `_encodingList` 也不同。见
[`global-host-api-runtime-differential.md`](global-host-api-runtime-differential.md)。
这证明 runtime profile、arity、转换、副作用和 stderr 都属于兼容面；尚未覆盖的
format HostApi 行为仍不能外推。

## 候选运行时初筛

本节只记录候选，不作设计决定：

| Candidate | 优点 | 风险/代价 | 当前结论 |
| --- | --- | --- | --- |
| [Boa](https://github.com/boa-dev/boa) | JavaScript engine 以 Rust 实现；可注册 native class/function | 0.21.1 拒绝 1 条 Qt 接受的固定规则；shared lexical semantics 不同；MSRV 1.88、Windows spike 126 个 target packages | 保留为需 patch/上游修复的候选，不能原样采用 |
| [rquickjs](https://github.com/DelSkayn/rquickjs) | 0.12.1 的 interrupt/heap limit 可用，跨线程 token 可中断并同 context 恢复，synthetic native HostApi 已合作取消，VM/native monotonic deadline 已到期；Windows spike 18 个 target packages、约 1.77 MiB；Windows `/MD`/`/MT` 与 Linux GNU staticlib C smoke 已通过 | 同样拒绝 1 条 Qt 接受的规则；必须显式 sloppy eval；编译 vendored QuickJS-NG C；完整 HostApi、macOS 和 sanitizer 仍须验证 | ADR 0006 Proposed 为首个私有 backend；不能未经 compatibility layer 原样采用，也未达到 Accepted |
| [rusty_v8](https://github.com/denoland/rusty_v8) | ECMAScript 兼容性高、成熟宿主 API | V8 很大；默认下载预编译静态库或源码构建成本高，不符合轻依赖目标 | 仅作兼容性上界/备选 |
| 自研 interpreter/transpiler | 可精确控制行为和资源限制 | 语法、RegExp、prototype、异常和动态特性成本极高 | 不作为首选 |

运行时选择必须记录为 ADR，并以 spike 数据而非偏好决定。

## 必做 spike

### 1. 全库 parse/eval

- 加载 main + extra 的所有 2175 个 `.sg` 及 60 个无扩展名 helper。
- 按上游目录、init、include 和排序语义执行。
- 记录 parse error、runtime error、缺失 global/property 和执行耗时。
- 对每个错误保存最小复现规则。

### 2. 宿主 ABI fixture

为每种参数/返回类型建立小脚本：

- signed/unsigned 8/16/24/32/64。
- float/NaN/Infinity。
- string/array/variant。
- omitted/default args 和 extra args。
- exception、stop 和 execution budget。

先在 Qt 5、Qt 6 上采集 oracle，再对候选 Rust runtime 比较。

### 3. 代表性复杂规则

至少选择：

- PE generic heuristic。
- PE/.NET detection。
- ELF compiler。
- Binary `audio.1.sg`。
- Archive 及 include chain。
- APK/DEX。
- PDF。

每条规则使用真实阳性、相似阴性、截断和随机输入。

### 4. 资源约束

验证候选运行时是否支持：

- 指令/时间 budget。
- 外部取消。
- heap limit。
- 禁止文件、网络、进程和动态 native access。
- panic/abort 隔离。
- context 重用与并发策略。

## 当前兼容策略假设

以下只是待验证方向：

- 原始规则文件作为唯一事实来源，运行时不修改规则文本。
- 同步时生成 manifest 和哈希，允许生成 AST/cache，但生成物可重建。
- 为宿主 API 建立显式 Rust trait，而不是把 JavaScript engine 类型渗入格式解析层。
- 每个 scan context 使用隔离的 JavaScript realm/context。
- Rust 内部使用检查过的整数和 byte reader；在 JS 边界模拟已确认的 Qt 行为。

在 spike 完成前，不冻结 JavaScript engine、宿主 trait 或 cache 格式。

Boa 0.21.1 的首轮实际构建、2235 文件 parse 和 runtime fixture 见
[`rule-runtime-spike.md`](rule-runtime-spike.md)。它证明 native binding、
prototype helper、复杂规则和 loop budget 可用，也确认了必须解决的语法/realm
差异。

rquickjs 0.12.1 的同语料 eval、sloppy-script 要求、interrupt/heap limit、
跨线程取消、同 context 恢复、native HostApi 合作取消、VM/native monotonic
deadline 和 native 构建成本见
[`rquickjs-rule-runtime-spike.md`](rquickjs-rule-runtime-spike.md)。它拒绝与
Boa 相同的 Nintendo legacy 规则，因此两个候选都未通过零差异门禁。精确等长
overlay 加 per-rule lexical wrapper 已让固定 292 条 Binary 规则全部加载；在该
环境中选定调用 archive_DEFLATE、EA-XA 和 Nintendo `detect` 后，Qt 5 目标结果
14/14 匹配，并发现由前一 `detect` 动态建立隐式全局 `bad` 的跨规则依赖。其余
`detect` 随后也已由 fallback-tolerant diagnostic 逐条尝试。首轮发现
253 条规则调用 34 类缺失路径；按固定上游契约补入基础读取方法后降为 233 条规则、
19 类路径；固定 Qt 5/Qt 6 numeric oracle 闭合 `U24`/`read_uint24` 和
`shru64` 后仍为 233 条规则，但调用由 387 降为 365、路径降为 17。另有 32 条
规则调用 317 种当前简化 `X.c` 不支持的 signature pattern。代理制造的结果不具
兼容意义，完整 signature parser、HostApi 与逐条 Qt oracle 尚未验证。signature
的固定源码文法、实现怪癖、动态及静态 pattern
inventory 和纯 Rust parser spike 见
[`signature-language.md`](signature-language.md)；兼容模式已解析动态 317/317，
固定 AST inventory 已解析 `db`/`db_extra` 2175/2175 文件并保存 5968 个具名
signature API 调用点：5855 个 literal、109 个可枚举静态表达式、4 个动态表达式，
得到 5628 个静态 pattern，包含动态样本的 317/317。固定 oracle 已运行 89 个
compare/find/边界向量，Rust context-free
compare 差分 16/16、六类合成 memory-map 差分 7/7、PE32/ELF64/Mach-O64/
COM/MS-DOS/AmigaHunk 加上 PE64/ELF32/Mach-O32 parser-derived map 差分
9/9，独立 find 三分支聚焦差分 19/19；同时确认 compare 与 find 的
byte-class/search 语义不同。另有 7/7 `Binary_Script::compare` 向量端到端确认
header fast path 的字符/字节混合计算和严格 `<` 分界会改变 invalid signature
结果，并固定 Qt 5 对负 offset 的 `QString::mid` 起点 clamp；`compareEP` 与
`compareOverlay` 又各有 5/5 向量确认 256-byte cache 被按
512 个 hex 字符计数、原始 pattern 长度参与分支，能让 cache 外合法 literal
误报 false；另有 4/4 搜索 wrapper 向量固定 `findSignature`/`fSig`/
`isSignaturePresent` 的范围裁剪、`size == -1`、别名和布尔投影。畸形 map、
find 的畸形/穷举边界和无效/短小 wrapper 上下文仍未完成。
四个保守动态参数中的 `byteCode` 已通过固定整文件哈希的受限 AST 求值闭合：
33 个真实调用点有限展开为 97 个唯一 pattern；其余 3 个是上游参数次序导致的
输入相关 Number→QString 调用，跨所有输入的运行时值域仍未完成。

rquickjs diagnostic 随后复用该 pure-Rust spike 替换五-pattern `X.c` 特判。
固定 128-byte 样本和 292-rule 顺序下，`Binary.c`/`compare` 共执行 799 次：
776 次 header fast path、23 次 generic、5 次显式兼容 quirk、0 adapter error。
292/292 个 `detect` 无异常完成，fallback 降为 16 条规则、58 次、18 条路径。
继续接入三个 search/presence API 后实际执行 11 次搜索、1 quirk、0 error；
真实 `false/-1` 改变后续分支，compare 增至 1179 次，291/292 个 `detect`
无异常，fallback 为 14 条规则、39 次、15 条路径。唯一异常是随后暴露的 overlay
API 缺口。再用 3/3 个 wrapper 向量区分 file-part 与 nested overlay，并接入
四个 overlay context API 后，2 次 `isOverlay=false` 短路相应规则，得到
1109 次 compare、292/292 无异常、12 条规则 34 次 fallback 和 11 条路径。
这些结果都只是缺口 inventory：剩余 proxy 会改变控制流，当前 4 条 detection
不具兼容意义；格式专用 context/memory map 尚未接入。

固定 oracle 扩展的 15/15 个字符串 context 向量随后固定 Qt 后缀、plain/UTF-8/
UTF-16 分类及 header 解码。接入 4 个确定性 HostApi 后，固定输入调用
`getFileSuffix/getHeaderString/isPlainText/isUTF8Text` 分别为 9/5/2/0 次；
292/292 无异常，fallback 降为 3 条规则、4 次、4 条路径，未记录 fallback
规则为 289。真实字符串分支下只产生 1 条 detection，仍不是兼容证据。
新增 3/3 个 scan/file-part context 与 4/4 个 storage-prefill 用例确认剩余
HostApi 和上游非 Unicode 未初始化状态；Rust 按 ADR 0005 使用确定性文本 facts。
接入后固定 trace 为 292/292、0 异常、0 fallback、1105 次 compare 和同一条
Nintendo detection。“零 fallback”只覆盖该输入实际抵达的分支，仍不是兼容率。
随后固定 Qt5 `Binary_Script` 与 Rust 对
`win_resources.1.sg`、`debug_data_debugData.1.sg`、
`format_DESKTOP.1.sg` 三条原样规则执行 8 个 resource/debugdata/text context：
3 条正例的完整 detection 四元组和 5 条 file-part/ID/content gate 反例 8/8
一致。该结果验证的是已给定 context 后的规则语义，不包含父扫描器枚举 subdevice、
生成 scan ID 和调度/排序子扫描。

固定 Binary 生命周期、init/include 首个命中规则、共享 global scope 和上游
排序比较器缺陷见
[`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)。该证据排除了
“每条规则一个 context”作为兼容执行模型。

全规则语法和调用形状机器清单见
[`rule-syntax-inventory.md`](rule-syntax-inventory.md)：固定 `db`/`db_extra`
的 2175 个 `.sg` 与 60 个无扩展名公共脚本共 2235/2235 建立 AST，得到 55 种
节点类型、28,372 个普通调用；29 个已知宿主 receiver 上共有 16,499 次第一层
调用、429 个 receiver/method 组合和 464 个 arity 形状，动态 computed 第一层
宿主方法名为 0。C++ 337 个 slot 加 13 个公共脚本扩展静态覆盖其中 460/464；
共享 Qt 5.15.13/Qt 6.4.2 QObject 探针进一步证明三个额外实参形状在两侧都会
忽略额外参数并保留相同语义返回，但 Qt 6 额外写 stderr warning；
`PE.getEPSignature` 在完整 PE `_init` 后仍不存在、两侧调用均抛出
runtime-specific `TypeError`。代表性 `qint64` fixture 还确认 Qt 5 会把
`null`/`undefined` 转成 0，Qt 6 则拒绝。详见
[`format-host-api-runtime-differential.md`](format-host-api-runtime-differential.md)。
该清单闭合规则侧语法和静态调用用法面，但不替代其余类型转换和运行行为核对。

非格式 global 另由固定 `die_script` 源码清单闭合：声明 16 个 native slot，
Qt 5 注册 15 个（遗漏规则未调用的 `_getQtVersion`），Qt 6 注册全部 16 个。
固定规则只直接调用其中 7 个，共 253 次且 arity 全部匹配。`meta`、`result` 等
8 个根框架函数来自规则脚本，不是 native HostApi。71 个 undeclared direct-call
名已分成 55 个规则函数候选、7 个 native global、7 个 ECMAScript global 和
2 个固定拼写错误。详见
[`global-host-api-inventory.md`](global-host-api-inventory.md)。

固定 Qt 5 `DiE_ScriptEngine` 行为基线进一步确认：15 个 wrapper 的
`function.length` 全为 0；缺参转成 `"undefined"`；普通结果允许重复；
`_removeResult` 只删第一项并建立后续 block，数组参数不会批量删除；first-wrapper
内部 stop 与 `_isStop()` 的 PDSTRUCT stop 是两个状态；include 可重复求值共享
global。`_getEngineVersion` 还把编译日期写入可观察结果。

## 尚未完成

- 为固定 C++ 声明、默认参数、继承和规则脚本扩展补齐其余 Qt 5/Qt 6 行为
  fixture；四个静态未解释形状及代表性 Binary/PE 边界已完成两侧对照。
- Qt 5 与 Qt 6 的 conformance oracle。
- include 同名、重复、循环和异常实验。
- native global 主行为已完成 Qt 5/Qt 6 对照，仍缺两侧数组、对象、数值等边界；
  两个拼写错误分支仍缺
  Qt 6/Windows/macOS、不带 `--messages` 和多错误/后续规则传播。
- ZIP database 的合法/截断/重复/`..`/根前缀行为与发布 CLI cache-disabled
  副作用已固定；engine `bUseCache=true` 的同统计 stale、bad magic、截断、
  预取消和空 cache 污染也已由 Qt5 harness 固定，剩余 header/长度/并发边界见
  [`database-archive-cache.md`](database-archive-cache.md)。
- `dbs_min` 生成逻辑。
- 用真实 HostApi 和 Qt oracle 逐条验证全库 `detect`、冻结 legacy compatibility
  方案和跨 runtime 性能比较。

## 主要证据

- [DIE rules tree](https://github.com/horsicq/Detect-It-Easy/tree/c2c17dfa5ea4e078ba31eab55d87430c96622fb6/db)
- [DiE Script lifecycle](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp#L109)
- [DiE Script engine globals/classes](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp#L24)
- [Binary host API](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.h)
- [PE host API](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/pe_script.h)
- [Database loading and ordering](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L1284)
