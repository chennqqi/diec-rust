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
- Qt 6 对额外 query 实参执行调用但向 stderr 发出精确 warning，Qt 5 静默忽略；
- `_encodingList()` 在 Qt 5 返回 false 并发出 104 条 encoding 消息，Qt 6
  返回 undefined 且不发消息；
- 结果增删/block、数组字符串化、first-wrapper stop、`includeScript`、
  application mode 和 `_getOS` 在当前 fixture 中相同。

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
| Harness image ID | `sha256:0511795cffb9bde645e4c904c074697aba0e6f28b338f266f5e06ef67cefb88b` | `sha256:1d4b39017c54ea2a51c495d4e05f06b77f821573c1763ebf0e8a838fc783419f` |
| Harness binary SHA-256 | `2889fc8268db0379594098d9866245b082e070909ea5f470c89d6f71153980c9` | `a8c67f717a90ee9514add6920e4d6aace087367df894d1c82cf93dd300c8eb45` |
| OCI revision | `74eaf505...2254` | `74eaf505...2254` |

本轮共享 harness schema v2 新增 query conversion matrix，并重建两侧镜像；
因此 image、binary 和 report identity 都相对 schema v1 改变。它是
project-generated 研究入口的变化，不是上游对象变化。

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
| [`global-host-api-qt5.json`](data/global-host-api-qt5.json) | `034e9cb78391d78c5607411b11ebdfefd46afe6e204e076b9f9279b9512a719e` |
| [`global-host-api-qt6.json`](data/global-host-api-qt6.json) | `711c2615c5e5c45b32a4656239f69b5384d2c96decc669e932595aa0ca1810ed` |
| [`global-host-api-qt5-qt6.json`](data/global-host-api-qt5-qt6.json) | `e63e0f8ab41b4eebd08082ec95676ff47cad49e5ebbb1ec560cda71b4e9f8328` |

probe 在写报告前严格验证全部预期行为、非零退出、额外 stdout、身份漂移和
非预期 JavaScript error。schema v2 把 stdout/stderr 原始字节以 Base64、长度和
SHA-256 保存并从中重放 observation；Qt 5 stderr 必须为空，Qt 6 stderr 必须
逐字节等于两个 extra-argument warning。比较器再次重放两份输入，随后递归比较
原始 observation，保留 missing key、类型和值的差异。

报告有 59 个原始字段差异。这个数字不是 59 项独立语义：一个 error object 会
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
但同一 schema v2 进程的 extra-argument cases 会产生后述 stderr。Qt 5 static wrapper
直接读取不存在的 `QScriptContext::argument(i)` 并调用 `toString()`，所以得到
`"undefined"`；Qt 6 QObject wrapper 在进入 slot 前执行 arity 检查。

这项差异具有规则兼容意义：Rust HostApi 若用普通 Rust 函数签名拒绝缺参，会匹配
Qt 6 而不是当前 primary Qt 5 profile。

## Query 参数转换边界

共享 fixture 预置 9 条结果，再运行 16 个 query case。两侧共同观察到：

- `["compiler"]`、`["Rust"]` 和 `["compiler","linker"]` 分别字符串化为
  `"compiler"`、`"Rust"` 和 `"compiler,linker"`；
- 普通对象转换为 `"[object Object]"`，自定义 `toString` 返回
  `"custom-type"`；
- `NaN`、`Infinity`、`-Infinity`、`-0` 和 `2^53` 分别匹配
  `"NaN"`、`"Infinity"`、`"-Infinity"`、`"0"` 和
  `"9007199254740992"`；
- 孤立 high surrogate `U+D800` 能在 `_setResult` 后被同值 query 命中；
  QJsonDocument 原样输出 `\ud800`，报告因此使用 ASCII JSON escape；
- 额外实参不改变返回值。

三项 runtime 差异不能被统一 normalizer 隐藏：

| Case | Qt 5 | Qt 6 |
| --- | --- | --- |
| `_getNumberOfResults(undefined)` | 以 `"undefined"` 查询，返回 0 | 转为空 QString，wildcard 返回 9 |
| `_getNumberOfResults(null)` | 以 `"null"` 查询，返回 0 | 转为空 QString，wildcard 返回 9 |
| throwing `toString` object | 执行方法并传播 `Error: conversion-boom` | 不执行方法，空查询结果返回 0 |
| 两个 extra-argument query | 静默忽略 | 返回值不变，stderr 各发一条 warning |

Qt 6 的 stderr 共 176 bytes，精确包含 fixture URL、行号和
`Too many arguments, ignoring 1`。Rust primary Qt 5 profile 不得产生这些
warning；未来 Qt 6 profile 若保留兼容模式，需要把诊断也纳入可观察契约。

## 字符串转换与 encoding

`_log(42)` 两侧都发出 `"42"`。其余行为：

| 调用/观察 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `_log(null)` | `"null"` | `""` |
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
- `die`/`diel`/空 application name 的 mode 结果；
- `_getOS() == "Linux Ubuntu x64"`。

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
- raw differential 保留 build-date 字段；semantic projection 可以把它标为
  build identity，但需要显式规则，不能全局删除版本字符串。
- format QObject 的首轮 arity/转换差分见
  [`format-host-api-runtime-differential.md`](format-host-api-runtime-differential.md)；
  两项实验都不能外推 337 个格式 slot 的完整矩阵。

## 尚未覆盖

- 更复杂的 cyclic/proxy 对象、BigInt/Symbol、多个 invalid UTF-16 code unit、
  2^53 邻域和 qint32/qint64 typed return 边界；
- `includeScript` 中 parse/runtime error 的两侧传播；
- `_log` 对 PDSTRUCT info 的后续扫描可见性；
- library=true 的可达宿主条件；
- Qt 6 其他 minor、Windows 和 macOS；
- 其余 format QObject 完整矩阵与逐规则 execution conformance。
