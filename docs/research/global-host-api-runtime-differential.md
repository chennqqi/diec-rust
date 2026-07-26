# Qt 5/Qt 6 全局 HostApi 运行时差分

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Component: `horsicq/die_script@5d82316c110abf0eb863b50bc679d330e05067b6`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-26

## 结论

固定 Qt 5.15.13 `QScriptEngine` 与 Qt 6.4.2 `QJSEngine` 对未修改
`DiE_ScriptEngine` 的 global HostApi 并不等价。共享 harness 证明：

- Qt 5 注册 15 个 global；Qt 6 另注册 `_getQtVersion`，共 16 个；
- Qt 5 对 `_log()`、`_setResult()`、`_isResultPresent()` 和
  `_getNumberOfResults()` 缺参进行宽松 `"undefined"` 转换，Qt 6 四者均抛出
  `Error: Insufficient arguments`；
- `_log(null)` 在 Qt 5 发出 `"null"`，Qt 6 发出空字符串；
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
| Harness image ID | `sha256:c9f9360714fbb4fc50bcb9a28d4e97253002ebf2e96fc94c479c1784c5032a11` | `sha256:96954960b811a109967862640201fdde268a026d332b3e3034c99facf1eca0b3` |
| Harness binary SHA-256 | `b7ca1e67ba929670e7c288c5e4ed2ebd7f43d99dbcb5fbbce828501eaa40a432` | `036799bef3dd38cb222f0f09e5e3b123fa5442da03262782f42a307a3a84bde0` |
| OCI revision | `74eaf505...2254` | `74eaf505...2254` |

共享 harness 适配后重新构建 Qt 5 镜像，Qt 5 `observation` 与先前版本逐字段
相同；版本化报告只改变 image/source identity 并增加 `runtime_profile`。Qt 5
binary SHA-256 也未改变。

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
| [`global-host-api-qt5.json`](data/global-host-api-qt5.json) | `99c4085d6f267ff95e3743c0b0be91a577e4bab4e5ebfdd4ee29910f9b43f81b` |
| [`global-host-api-qt6.json`](data/global-host-api-qt6.json) | `572b3a19d5260673c612accbf8cfe2bdd3bee76c55e3a1846a3ceac22e823a17` |
| [`global-host-api-qt5-qt6.json`](data/global-host-api-qt5-qt6.json) | `3895fde7bb3885e6197afe7216daf8540b7808562ff5287984615d5b022634eb` |

probe 在写报告前严格验证全部预期行为，拒绝 stderr、非零退出、额外 stdout、
身份漂移以及非预期 JavaScript error。比较器再次验证两份输入，随后递归比较
原始 observation，保留 missing key、类型和值的差异。

报告有 49 个原始字段差异。这个数字不是 49 项独立语义：一个 error object 会
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
进程仍 exit 0，stdout 是单个 JSON document，stderr 为空。Qt 5 static wrapper
直接读取不存在的 `QScriptContext::argument(i)` 并调用 `toString()`，所以得到
`"undefined"`；Qt 6 QObject wrapper 在进入 slot 前执行 arity 检查。

这项差异具有规则兼容意义：Rust HostApi 若用普通 Rust 函数签名拒绝缺参，会匹配
Qt 6 而不是当前 primary Qt 5 profile。

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
- Qt 6 profile 必须精确测试四个 missing-argument error、原子无副作用和空 stderr。
- raw differential 保留 build-date 字段；semantic projection 可以把它标为
  build identity，但需要显式规则，不能全局删除版本字符串。
- format QObject 的 arity/转换仍由独立 HostApi matrix 覆盖，本实验不能外推
  337 个格式 slot。

## 尚未覆盖

- arrays、objects、NaN、Infinity、整数边界、invalid UTF-16 和 extra arguments；
- `includeScript` 中 parse/runtime error 的两侧传播；
- `_log` 对 PDSTRUCT info 的后续扫描可见性；
- library=true 的可达宿主条件；
- Qt 6 其他 minor、Windows 和 macOS；
- 全部 format QObject 与逐规则 execution conformance。
