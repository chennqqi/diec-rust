# DIE 规则兼容性调研

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`  
Runtime: `horsicq/die_script@5d82316c110abf0eb863b50bc679d330e05067b6`  
Host API: `horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`  
Last updated: 2026-07-26

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

从 `public slots` 静态提取到 30 个 `*_Script` 类、338 个直接声明的方法。继承后每个具体类型还拥有父类方法。

| Class | Parent | Direct methods |
| --- | --- | ---: |
| `Binary_Script` | `QObject` | 155 |
| `MSDOS_Script` | `Binary_Script` | 13 |
| `PE_Script` | `MSDOS_Script` | 88 |
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

结果删除会维护 blacklist，后续相同 type/name 不再加入。比较基本采用 uppercase 后的 case-insensitive 语义。精确去重范围仍需测试：当前代码的 blacklist 与已产生结果列表使用方式并不完全相同。

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

## 候选运行时初筛

本节只记录候选，不作设计决定：

| Candidate | 优点 | 风险/代价 | 当前结论 |
| --- | --- | --- | --- |
| [Boa](https://github.com/boa-dev/boa) | JavaScript engine 以 Rust 实现；可注册 native class/function | 0.21.1 拒绝 1 条 Qt 接受的固定规则；shared lexical semantics 不同；MSRV 1.88、Windows spike 126 个 target packages | 保留为需 patch/上游修复的候选，不能原样采用 |
| [rquickjs](https://github.com/DelSkayn/rquickjs) | 0.12.1 的 interrupt/heap limit 可用；Windows spike 18 个 target packages、约 1.39 MiB | 同样拒绝 1 条 Qt 接受的规则；必须显式 sloppy eval；编译 vendored QuickJS-NG C，MSVC 仍属 engine experimental | 保留为需 legacy compatibility 层的候选，不能原样采用 |
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

rquickjs 0.12.1 的同语料 eval、sloppy-script 要求、interrupt/heap limit 和
native 构建成本见
[`rquickjs-rule-runtime-spike.md`](rquickjs-rule-runtime-spike.md)。它拒绝与
Boa 相同的 Nintendo legacy 规则，因此两个候选都未通过零差异门禁。精确等长
overlay 加 per-rule lexical wrapper 已让固定 292 条 Binary 规则全部加载；在该
环境中选定调用 archive_DEFLATE、EA-XA 和 Nintendo `detect` 后，Qt 5 目标结果
14/14 匹配，并发现由前一 `detect` 动态建立隐式全局 `bad` 的跨规则依赖。其余
`detect` 随后也已由 fallback-tolerant diagnostic 逐条尝试。首轮发现
253 条规则调用 34 类缺失路径；按固定上游契约补入基础读取方法后降为 233 条规则、
19 类路径，但又显式识别出 32 条规则调用 317 种当前简化 `X.c` 不支持的 signature
pattern。代理制造的结果不具兼容意义，完整 signature parser、HostApi 与逐条 Qt
oracle 尚未验证。signature 的固定源码文法、实现怪癖、动态 pattern inventory 和
纯 Rust parser spike 见
[`signature-language.md`](signature-language.md)；兼容模式已解析动态 317/317，
固定 XBinary oracle 已运行 34 个 compare/find/边界向量，Rust context-free
compare 差分 16/16、六类合成 memory-map 差分 7/7；同时确认 compare 与 find
的 byte-class/search 语义不同。真实格式 map 构造、完整 find 与全调用点
inventory 仍未完成。

固定 Binary 生命周期、init/include 首个命中规则、共享 global scope 和上游
排序比较器缺陷见
[`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)。该证据排除了
“每条规则一个 context”作为兼容执行模型。

## 尚未完成

- 对所有规则进行 AST 级语法与 signature 调用点统计。
- 自动生成完整宿主方法签名清单。
- Qt 5 与 Qt 6 的 conformance oracle。
- include 同名、重复、循环和异常实验。
- database cache 与 ZIP database 行为。
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
