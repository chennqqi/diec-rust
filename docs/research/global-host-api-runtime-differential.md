# Qt 5/Qt 6 全局 HostApi 运行时差分

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Component: `horsicq/die_script@5d82316c110abf0eb863b50bc679d330e05067b6`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-30

## 结论

固定 Qt 5.15.13 `QScriptEngine` 与 Qt 6.4.2 `QJSEngine` 对未修改
`DiE_ScriptEngine` 的 global HostApi 并不等价。共享 harness 证明：

- Qt 5 注册 15 个 global；Qt 6 另注册 `_getQtVersion`，共 16 个；
- Qt 5 对 `_log()`、`_setResult()`、`_isResultPresent()` 和
  `_getNumberOfResults()` 缺参进行宽松 `"undefined"` 转换，Qt 6 四者均抛出
  `Error: Insufficient arguments`；
- `_log(null)` 在 Qt 5 发出 `"null"`，Qt 6 发出空字符串；
- Qt 5 的显式 `undefined`/`null` query 分别按字符串查询，Qt 6 都转换为空
  QString，并触发“空 type 统计全部结果”的 wildcard；
- Qt 5 query 会执行对象的自定义 `toString` 并传播异常；Qt 6 QObject 参数转换
  不执行该方法；
- Qt 5 不提供 Proxy、BigInt 或 Symbol；Qt 6.4.2 提供 Proxy 和 Symbol、仍不
  提供 BigInt，两个可用类型都能转换并命中预置结果；
- self-referential plain object 两侧都能转换；self-referential array 在 Qt 5
  转为空串并触发 wildcard，在 Qt 6 QString 参数转换中以 signal 11 崩溃；
- Qt 6 对额外 query 实参执行调用但向 stderr 发出精确 warning，Qt 5 静默忽略；
- include 内部 parse/runtime error 两侧都发出 `errorMessage`；Qt 5 还把嵌套
  engine exception 传播为外层 `includeScript(...)` error，Qt 6 外层仍返回
  undefined；
- `_log` 两侧都把转换后的文本直接写入 `PDSTRUCT.sInfoString`，后续
  `_encodingList()` 不会覆盖该字段；
- `_encodingList()` 在 Qt 5 返回 false 并发出 104 条 encoding 消息，Qt 6
  返回 undefined 且不发消息；
- `_isLibraryMode()` 在两侧都只由空 application name 触发；普通
  `setApplicationName("")` 会回退到可执行文件名，但以空 `argv[0]` 构造
  `QCoreApplication` 时两侧都得到 library=true；
- 结果增删/block、数组字符串化、first-wrapper stop、正常/缺失
  `includeScript`、application mode 和 `_getOS` 在当前 fixture 中相同。

因此 Rust runtime 不能只实现一个“合理”的 native function 签名再声称兼容两个
上游 runtime。当前 primary Qt 5 legacy profile 必须保存宽松缺参和字符串转换；
若未来公开 Qt 6 profile，应使用独立 expected namespace。

## 共享 harness 与身份

[`global_host_api_harness_main.cpp`](../../tools/upstream/global_host_api_harness_main.cpp)
是 project-generated harness。两侧使用同一业务 fixture，只在值/异常提取层按
上游 `QT_SCRIPT_LIB` 分支：

- Qt 5 使用 `QScriptValue`、`clearExceptions()` 和
  `uncaughtExceptionBacktrace()`；
- Qt 6 使用 `QJSValue` 的 `lineNumber` 与 `stack`；
- 只有 Qt 6 执行 `_getQtVersion()`，因为固定 Qt 5 构造器没有注册它。

harness 替换固定 CLI 的 `main_console.cpp.o`，其余编译对象和 link command
完全复用对应 oracle build。两个 Dockerfile 分别是：

- [`Dockerfile.global-host-api-harness-qt5`](../../tools/upstream/Dockerfile.global-host-api-harness-qt5)；
- [`Dockerfile.global-host-api-harness-qt6`](../../tools/upstream/Dockerfile.global-host-api-harness-qt6)。

| 项目 | Qt 5 | Qt 6 |
| --- | --- | --- |
| Runtime | Qt Script 5.15.13 | QJSEngine 6.4.2 |
| Base oracle | `upstream-oracle-cmake:74eaf505` | `upstream-oracle-cmake-qt6:74eaf505` |
| Harness image ID | `sha256:bfdf599045d6c32753b7620d2e663e22b2544ccbad485ac6e36a982d4e918b3e` | `sha256:f24edee99353945ed4a83ee8361cdcdf6eae7377b48a6059302fdb84e63611a8` |
| Harness binary SHA-256 | `e6bcc2470dd5b5e1d3abebfe5db680cecfaef338f054eaadfbfebec03af54801` | `ec0bbeb4ae629011f1e53984603a5cdc5437cf99c8d16ac853a5c8f286003e1e` |
| OCI revision | `74eaf505...2254` | `74eaf505...2254` |

本轮共享 harness schema v5 在 v4 的对象图、runtime type、2^53 邻域与
UTF-16 matrix 基础上，新增空 `argv[0]` 的隔离进程模式实验；因此 image、
binary 和 report identity 都相对 schema v4 改变。它是 project-generated
研究入口的变化，不是上游对象变化。

## 复现与机器报告

```sh
docker build \
  --file tools/upstream/Dockerfile.global-host-api-harness-qt5 \
  --tag diec-rust/upstream-global-host-api-harness:74eaf505 \
  tools/upstream

docker build \
  --file tools/upstream/Dockerfile.global-host-api-harness-qt6 \
  --tag diec-rust/upstream-global-host-api-harness-qt6:74eaf505 \
  tools/upstream

python tools/upstream/probe_global_host_api.py --runtime qt5
python tools/upstream/probe_global_host_api.py --runtime qt6
python tools/upstream/compare_global_host_api_reports.py
```

固定输出：

| Report | SHA-256 |
| --- | --- |
| [`global-host-api-qt5.json`](data/global-host-api-qt5.json) | `087e4181562af80b3ff07d1cc501dc1b64db3c34d12bee236bf6b04a4accd96e` |
| [`global-host-api-qt6.json`](data/global-host-api-qt6.json) | `983f1d717b4b459c98daafd70f45cdefb72a9644b5e0ae7c15a8dd32665cb197` |
| [`global-host-api-qt5-qt6.json`](data/global-host-api-qt5-qt6.json) | `467e6f3bb5dc66ed19d59144d5a9a707c52dfd0f134bb985d5002de667227a62` |

probe 在写报告前严格验证全部预期行为、非零退出、额外 stdout、身份漂移和
非预期 JavaScript error。schema v5 把父进程及六个隔离子进程的 stdout/stderr
原始字节以 Base64、长度和
SHA-256 保存并从中重放 observation；Qt 5 stderr 必须为空，Qt 6 stderr 必须
逐字节等于两个 extra-argument warning。比较器再次重放两份输入，随后递归比较
原始 observation，保留 missing key、类型和值的差异。

两次完整重采集得到逐文件相同 SHA-256。报告有 94 个原始字段差异。这个数字
不是 94 项独立语义：一个 error object 或 raw child stream 会
引入 name/message/line/stack/type 等多个字段，必须按下列行为组解释。

## Global surface

两侧被检查的所有已注册 function 都有 JavaScript `typeof == "function"` 且
`function.length == 0`。差异只有 `_getQtVersion`：

| 调用 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `typeof _getQtVersion` | `"undefined"` | `"function"` |
| `_getQtVersion()` | 不调用 | `"6.4.2"` |

固定源码中 Qt 5 分支以 `_addFunction` 注册 15 个 static wrapper；Qt 6 分支将
`die_global_script` 暴露为 QObject，并复制 16 个 slot property 到 global
object。Qt 6 的 `_getQtVersionSlot` 返回 `QT_VERSION_STR`。

源码证据：

- [`die_scriptengine.cpp`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp)：
  `DiE_ScriptEngine` constructor、`_getQtVersionSlot`；
- [`die_global_script.h`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_global_script.h)：
  Qt 6 QObject public slots。

## 缺失实参

| 调用 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `_log()` | 发出 `"undefined"` | error，无消息 |
| `_setResult()` | 加入四字段均为 `"undefined"` 的结果 | error，无结果 |
| `_isResultPresent()` | true，命中上述结果 | error |
| `_getNumberOfResults()` | 1 | error |

四个 Qt 6 error 都精确为：

```text
name: Error
message: Insufficient arguments
line: 1
string: Error: Insufficient arguments
```

stack 分别指向对应 fixture 文件的第一行。error 作为 `QJSValue` 返回给 harness；
进程仍 exit 0，stdout 是单个 JSON document；这四个调用本身不产生 warning，
但同一 schema v5 进程的 extra-argument cases 会产生后述 stderr。Qt 5 static wrapper
直接读取不存在的 `QScriptContext::argument(i)` 并调用 `toString()`，所以得到
`"undefined"`；Qt 6 QObject wrapper 在进入 slot 前执行 arity 检查。

这项差异具有规则兼容意义：Rust HostApi 若用普通 Rust 函数签名拒绝缺参，会匹配
Qt 6 而不是当前 primary Qt 5 profile。

## Query 参数转换边界

共享 fixture 预置 17 条结果，再运行 30 个进程内 query case，并另以五个子进程
隔离复杂对象/类型 case。两侧共同观察到：

- `["compiler"]`、`["Rust"]` 和 `["compiler","linker"]` 分别字符串化为
  `"compiler"`、`"Rust"` 和 `"compiler,linker"`；
- 普通对象转换为 `"[object Object]"`，自定义 `toString` 返回
  `"custom-type"`；
- `NaN`、`Infinity`、`-Infinity`、`-0` 和 `2^53` 分别匹配
  `"NaN"`、`"Infinity"`、`"-Infinity"`、`"0"` 和
  `"9007199254740992"`；
- 孤立 high surrogate `U+D800` 能在 `_setResult` 后被同值 query 命中；
  QJsonDocument 原样输出 `\ud800`，报告因此使用 ASCII JSON escape；
- `2^53-1`、`2^53`、源码字面量 `2^53+1`、`2^53+2` 及三个对应负值都按
  ECMAScript Number 字符串化命中；`2^53+1` 因 binary64 舍入命中
  `"9007199254740992"`；
- lone low、double high、double low、low-high 逆序和合法 high-low pair 都能
  原样加入并由同一 JavaScript 字符串命中；合法 pair 在 JSON 解码后为 U+10000；
- 额外实参不改变返回值。

三项 runtime 差异不能被统一 normalizer 隐藏：

| Case | Qt 5 | Qt 6 |
| --- | --- | --- |
| `_getNumberOfResults(undefined)` | 以 `"undefined"` 查询，返回 0 | 转为空 QString，wildcard 返回 9 |
| `_getNumberOfResults(null)` | 以 `"null"` 查询，返回 0 | 转为空 QString，wildcard 返回 9 |
| throwing `toString` object | 执行方法并传播 `Error: conversion-boom` | 不执行方法，空查询结果返回 0 |
| 两个 extra-argument query | 静默忽略 | 返回值不变，stderr 各发一条 warning |

对象图与 runtime type 的隔离结果：

| Case | Qt 5 | Qt 6 |
| --- | --- | --- |
| `typeof Proxy / BigInt / Symbol` | 全部 `undefined` | `function / undefined / function` |
| cyclic plain object | `"[object Object]"`，命中 1 | 相同 |
| cyclic array | 转为空串，wildcard 命中 1 | signal 11；exit status crash；stdout/stderr 均空 |
| custom Proxy `toString` | runtime 不支持，sentinel -1 | 转为 `"proxy-type"`，命中 1 |
| `BigInt(1)` | runtime 不支持，sentinel -1 | runtime 不支持，sentinel -1 |
| `Symbol("probe")` | runtime 不支持，sentinel -1 | 转为 `"Symbol(probe)"`，命中 1 |

cyclic array 不是 harness 自身整体崩溃：父进程通过 `QProcess` 每案启动同一固定
binary，保存 child exit code/status、process error enum 和 raw streams；Qt 5
五案及 Qt 6 其余四案均 exit 0，只有 Qt 6 cyclic array 为 crash/11。两次完整
报告哈希相同，排除了偶然采集差异。

Qt 6 的 stderr 共 176 bytes，精确包含 fixture URL、行号和
`Too many arguments, ignoring 1`。Rust primary Qt 5 profile 不得产生这些
warning；未来 Qt 6 profile 若保留兼容模式，需要把诊断也纳入可观察契约。

## Include error 传播

fixture 新增一个单行 parse error include 和一个在赋值前后抛错的 runtime
include。两侧都由 `includeScriptSlot()` 捕获内部 `evaluate()` 的 error value，
并发出带 include 名、行号和 error string 的 `errorMessage`：

| 观察 | Qt 5 | Qt 6 |
| --- | --- | --- |
| parse signal | `SyntaxError: Parse error` | `SyntaxError: Expected token \`}'` |
| parse 外层调用 | `SyntaxError: Parse error` | undefined |
| runtime signal | `Error: include-runtime-boom` | 相同 |
| runtime 外层调用 | `Error: include-runtime-boom` | undefined |

parse error 前的变量没有生效；runtime error 前的变量类型为 `number`，抛错后的
变量保持 `undefined`。这证明两侧内部执行边界相同，但 Qt Script 的嵌套 engine
exception 会决定外层返回值，而 QJSEngine QObject slot 只把错误留在 signal
通道。Rust primary Qt 5 profile 必须同时复现 signal 与外层异常，不能把 include
失败简化成单一返回码。

## 字符串转换、PDSTRUCT 与 encoding

`_log(42)` 两侧都发出 `"42"`。其余行为：

| 调用/观察 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `_log()` 后 `sInfoString` | `"undefined"` | `""`（缺参未进入 slot） |
| `_log(null)` signal / `sInfoString` | `"null"` / `"null"` | `""` / `""` |
| `_log(42)` signal / `sInfoString` | `"42"` / `"42"` | `"42"` / `"42"` |
| encoding 后 `sInfoString` | `"42"` | `"42"` |
| `_encodingList()` return | boolean false | undefined |
| Encoding message count | 104 | 0 |
| Qt 5 first/last | `""` / `TIS-620` | 不适用 |

`_encodingListSlot()` 的固定源码只在 Qt major < 6 或定义
`QT_CORE5COMPAT_LIB` 时枚举 code pages。本轮 Qt 6 build 没有
`QT_CORE5COMPAT_LIB`，所以 slot 是明确的 no-op；这不是 harness 丢失 signal。

## 相同的行为

递归 raw comparison 除前述字段和 `_getEngineVersion()` 的 build date 外，没有
其他差异。当前 fixture 证明两侧共同保持：

- ordinary result 可保留大小写不同的重复项；
- lookup/delete 大小写不敏感，delete 只删首项并加入 block list；
- array 参数转换成单个 `"Enigma,Denuvo"` 字符串；
- first-wrapper compiler 丢弃、protection 保留及 internal/PDSTRUCT 双 stop；
- include 名称大小写不敏感、重复 include 重新求值、缺失 include 只发 signal；
- `die`/`diel`/空 application name 与空 `argv[0]` 的 mode 结果；
- `_getOS() == "Linux Ubuntu x64"`。

### Library mode 的可达条件

固定上游
[`die_scriptengine.cpp`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp#L773-L799)
表明四个 mode slot 都在每次调用时读取 `qApp->applicationName()`：
console/gui 还受 build 是否含 GUI 约束并要求名称为 `die`，lite 要求 `diel`，
library 则精确要求空字符串。

同一正常进程中的 `setApplicationName("")` 不能触发 library：Qt5/Qt6 都把读取值
恢复为 `diec-global-host-api-harness`。schema v5 另以同一 binary 启动隔离子进程，
在构造 `QCoreApplication` 前把唯一的 `argv[0]` 设为空。两侧子进程均 exit 0、
stderr 为空、effective application name 为空，且
`console/gui/lite/library == false/false/false/true`；710-byte stdout 逐字节相同，
SHA-256 为
`297e0f5dba1d2d3da7458a7087079f0103035d9407dbfd745316eafca6aa91dd`。

因此上游 library mode 可达，但它把嵌入语义偶然绑定到 Qt 进程初始化。Rust
静态库不能从宿主可执行文件名推断该事实；正式 HostApi/options 设计需要显式表达
运行模式，并用 legacy adapter 复现上述 mode 函数的可观察值。

`_getEngineVersion()` 的末尾日期来自上游对象编译时的 `__DATE__`，本轮 Qt 5 与
Qt 6 image 构建日期不同。该 raw 差异由 binary/image identity 保存，但不能用来
推断 script runtime 语义差异。

## 对 Rust 实现与测试的约束

- global HostApi contract 必须按 runtime profile 描述 arity、转换、返回值、signal
  和副作用，不能仅列函数名。
- primary Qt 5 legacy profile 必须测试缺参 `"undefined"`、null 字符串化和 104
  条 encoding 顺序；不得因 Rust typed API 更严格而静默改变规则边界。
- Qt 6 profile 必须精确测试四个 missing-argument error、原子无副作用，以及
  extra-argument cases 的非空 stderr；不能把整个进程概括为“空 stderr”。
- query conversion 必须保留数组/对象的 runtime-specific coercion、throwing
  `toString`、空 type wildcard、孤立 surrogate 和 extra-argument diagnostics。
- 不可信规则值必须在 Rust 边界防止 cyclic graph 导致 native stack overflow；
  兼容 oracle 会保留 Qt 6 crash 事实，但安全实现不得照搬崩溃。
- Proxy/Symbol/BigInt availability 与转换必须按 runtime profile 显式声明；
  “引擎支持该语法”不等于 QObject/HostApi 转换语义一致。
- include parse/runtime error 必须分别比较 signal、外层 evaluation、已执行
  side effect 和未执行 tail；Qt 5 与 Qt 6 不可共用同一个错误传播约定。
- `_log` 必须同时测试 signal 和 `PDSTRUCT.sInfoString`，不能把它实现为纯日志；
  encoding signal 又不能误写该字段。
- library mode 必须由显式宿主配置进入核心层；C/Go/Python 静态库调用不能依赖
  `argv[0]` 或调用方进程名。legacy Qt oracle 仍保留空 application name 的判定。
- raw differential 保留 build-date 字段；semantic projection 可以把它标为
  build identity，但需要显式规则，不能全局删除版本字符串。
- format QObject 的首轮 arity/转换差分见
  [`format-host-api-runtime-differential.md`](format-host-api-runtime-differential.md)；
  两项实验都不能外推 337 个格式 slot 的完整矩阵。

## 尚未覆盖

- 更复杂的 proxy trap/error/revocation、嵌套 cyclic graph，以及 qint32/qint64
  typed return 边界；
- `PDSTRUCT.sInfoString` 在真实后续 scan consumer/callback 中的读取时机；
- Qt 6 其他 minor、Windows 和 macOS；
- 其余 format QObject 完整矩阵与逐规则 execution conformance。
