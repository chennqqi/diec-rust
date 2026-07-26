# Qt 5/Qt 6 格式 HostApi 参数与异常差分

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

XScanEngine: `dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-26

## 结论

共享 harness 在固定 Linux Qt 5.15.13 `QScriptEngine` 和 Qt 6.4.2
`QJSEngine` 中直接注册未修改的上游 `Binary_Script`/`PE_Script`。实验关闭了
[`host-api-inventory.md`](host-api-inventory.md) 静态声明无法解释的四个规则
调用形状：

- `X.U8(0, 12)`、`X.SA(0, 1, 99)` 和
  `X.SC(0, 1, "System", 99)` 在两侧都忽略额外实参，语义返回值与精确 arity
  调用相同；
- Qt 5 对三个额外实参调用保持空 stderr，Qt 6 每次发出两行
  `Too many arguments, ignoring 1` 诊断；
- 完整 PE `_init` 在两侧都只定义 `PE.getEntryPointSignature`，不存在
  `PE.getEPSignature`；调用后两侧都抛出 `TypeError`，但消息和 backtrace
  framing 不同。

代表性参数实验还证明格式 QObject 的转换不能从 Qt 5 外推到 Qt 6：

- `X.U8("0")` 和 `X.U8(false)` 在两侧都转换为 offset 0；
- `X.U8(null)` 和 `X.U8(undefined)` 在 Qt 5 也转换为 offset 0，在 Qt 6
  则抛出 incompatible-arguments `TypeError` 并写 stderr；
- `X.SA(0)`、`X.SC(0)` 和 `X.SC(0, 1)` 的 C++ 默认参数在两侧均生效；
- 缺少必需参数时，两侧的异常类型、消息和 backtrace 不同。

这些结论只覆盖 `Binary_Script`/`PE_Script` 的代表性 `qint64`、`QString`、
默认/额外参数和未知方法边界，不证明 30 个格式类、337 个直接 slot 的完整转换、
返回值和副作用兼容。

## 共享 harness 与所有权

[`host_api_arity_harness_main.cpp`](../../tools/upstream/host_api_arity_harness_main.cpp)
按上游 `QT_SCRIPT_LIB` 分支选择 `QScriptEngine`/`QJSEngine`，其余 fixture、
表达式、JSON 字段和上游对象完全共享。两个镜像只替换固定 console build 的入口，
并链接对应 oracle 中未修改的 XScanEngine 对象：

- [`Dockerfile.host-api-arity-harness-qt5`](../../tools/upstream/Dockerfile.host-api-arity-harness-qt5)；
- [`Dockerfile.host-api-arity-harness-qt6`](../../tools/upstream/Dockerfile.host-api-arity-harness-qt6)。

项目生成的 fixture 把 `Binary_Script` 和 `PE_Script` 放在栈上。Qt 6 harness
必须显式设置 `QJSEngine::CppOwnership`，否则引擎会尝试释放栈对象。初版 Qt 6
harness 因缺少该设置在退出时触发 `free(): invalid pointer`；这是 harness
生命周期错误，不能写成上游扫描行为。当前设置只约束项目生成 fixture，不对
上游实际对象所有权作额外推断。

Qt 6 的未知 QObject 方法消息包含进程地址。harness 仅在 JSON error
`string`/`message` 中把匹配
`[A-Za-z_][A-Za-z0-9_:]*\(0x[0-9a-fA-F]+\)` 的地址替换为相同类名加
`(<address>)`。该精确 token 是派生的 semantic observation，不是上游 raw
文本；stderr 保持逐字节原样，不执行宽泛规范化。

## 固定身份

| 项目 | Qt 5 | Qt 6 |
| --- | --- | --- |
| Runtime | Qt Script 5.15.13 | QJSEngine 6.4.2 |
| Base oracle | `upstream-oracle-cmake:74eaf505` | `upstream-oracle-cmake-qt6:74eaf505` |
| Harness image ID | `sha256:0db880fc25300a5eae56650798863e3c8edd85e31d3aeefc85ce18a595267a52` | `sha256:e88739194238e805e769338c5ddbc08bbccc1a7d9b78332e2b746762a6d2593d` |
| Harness binary SHA-256 | `1ebe7d03ccdb05489b033a2d079d603382618d81900c90d0f07088f70d7d89bc` | `6970f3f61a3399f63e44058e08ed6b93ba9cccce03f89222e7a396a94699997b` |
| Report | [`host-api-arity-qt5.json`](data/host-api-arity-qt5.json) | [`host-api-arity-qt6.json`](data/host-api-arity-qt6.json) |
| Report SHA-256 | `e5f7108a55f9af59e6c07c1362cf59297f7c5f0e95d2bfff76ed1a305b7e2a46` | `cd4262afa0acaf96f38d42be0383050e6d5053995f55a48f3f8c427fc5a58994` |

逐字段比较报告
[`host-api-arity-qt5-qt6.json`](data/host-api-arity-qt5-qt6.json)
SHA-256 为
`d82d88a91ffe9fe54c93483c45b4f30b8b5ba213773b860f97eb4899ad7bd459`，
记录 41 个差异路径。比较器同时验证两个输入 report、stderr 和生成器源码哈希；
数值、布尔值、null、缺失字段按类型比较。

## 复现

```sh
docker build \
  --file tools/upstream/Dockerfile.host-api-arity-harness-qt5 \
  --tag diec-rust/upstream-host-api-arity-harness:74eaf505 \
  tools/upstream
docker build \
  --file tools/upstream/Dockerfile.host-api-arity-harness-qt6 \
  --tag diec-rust/upstream-host-api-arity-harness-qt6:74eaf505 \
  tools/upstream

python tools/upstream/probe_host_api_arity.py --runtime qt5
python tools/upstream/probe_host_api_arity.py --runtime qt6
python tools/upstream/compare_host_api_arity_reports.py
```

探针拒绝错误的 commit、image revision、binary、PE `_init` 哈希、stdout framing、
exit code 或 runtime-specific stderr；不把意外诊断当成成功。

## 参数数量与默认参数

三个 wrapper 的 JavaScript `function.length` 在两侧均为 0，不能用它推断 C++
必需参数数量。

| 调用 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `X.U8(0)` | 65 | 65 |
| `X.U8(0, 12)` | 65，空 stderr | 65，两行 extra-argument stderr |
| `X.SA(0, 1)` | `"A"` | `"A"` |
| `X.SA(0, 1, 99)` | `"A"`，空 stderr | `"A"`，两行 extra-argument stderr |
| `X.SA(0)` | `"ABC"` | `"ABC"` |
| `X.SC(0, 1, "System")` | `""` | `""` |
| `X.SC(0)` / `X.SC(0, 1)` | `""` / `""` | `""` / `""` |
| `X.SC(0, 1, "System", 99)` | `""`，空 stderr | `""`，两行 extra-argument stderr |

因此额外实参的语义返回在本 fixture 中相同，但 raw 可观察行为不同；Rust 的 Qt 5
legacy profile 不应输出 Qt 6 warning，Qt 6 profile 也不能丢弃这些 warning。

## 参数转换

fixture 的第一个字节为 ASCII `A`（65），因此 `U8` 返回 65 表示参数成功转换为
offset 0。

| 调用 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `X.U8("0")` | 65 | 65 |
| `X.U8(false)` | 65 | 65 |
| `X.U8(null)` | 65 | `TypeError` + 两行 stderr |
| `X.U8(undefined)` | 65 | `TypeError` + 两行 stderr |
| `X.SC(0, 1, null)` | `""` | `""` |
| `X.SC(0, 1, 42)` | `""` | `""` |

这证明 `qint64` 的 null/undefined 转换存在 runtime 分叉，而当前 `QString`
代表值没有触发错误。空字符串结果不能证明转换后的精确字符串内容；需要带有可区分
编码结果的后续 fixture 才能关闭该项。

## 缺参和未知方法异常

| 表达式 | Qt 5 | Qt 6 |
| --- | --- | --- |
| `X.U8()` | `SyntaxError: too few arguments...` | `Error: Insufficient arguments` |
| `X.SC()` | 单组 overload candidates 的 `SyntaxError` | 三次候选块的 overload `Error` |
| `PE.getEPSignature(19, 14)` | undefined expression 不是 function 的 `TypeError` | `PE_Script(<address>)` property 不是 function 的 `TypeError` |

PE `_init` 在两侧均成功求值并具有相同源码 SHA-256。求值结果在 Qt 5
`is_undefined == false`，Qt 6 为 true；两侧都不是 bool、number、string、null
或 error。这是保留在 raw observation 中的 runtime 返回类型差异，不影响
`getEntryPointSignature` 的安装结果。

Qt 5 backtrace 使用 `<global>() at ...`，Qt 6 使用 `%entry@file:...`。异常的
名称、message、line 和 backtrace 都属于 profile-specific contract，不能只比较
“调用失败”。

## stderr

Qt 5 stderr 为 0 字节。Qt 6 stderr 为 302 字节、10 行，SHA-256：

```text
e0310923c499e07d496a16fa9e9050185d71144cf113642560e08697a9e67bac
```

其中三个 extra-argument 调用各产生两行，两个 `qint64` 转换失败各产生两行。
顺序与表达式执行顺序一致。探针逐字节验证该记录，比较报告仍把 10 行分别列为
差异，不通过语义结果相同隐藏 diagnostics。

## 对 Rust 实现与测试的约束

- primary Qt 5 legacy profile 必须保留 QObject extra-argument 静默忽略、
  `qint64` null/undefined 到 0 的转换和 Qt 5 异常 framing；
- Qt 6 profile 必须保留 extra-argument stderr、null/undefined
  incompatible-arguments 错误及 Qt 6 overload/unknown-property framing；
- 默认参数必须由 HostApi 边界显式建模，不能依赖 Rust 函数默认参数；
- unknown method、conversion error、stdout/stderr 和 backtrace 必须进入可审计
  observation；不得只保留成功返回值；
- 地址 token 只能应用于已批准的 QObject 地址字段，并同时保存未修改 raw
  execution artifact；不能推广为删除所有十六进制值；
- 上游规则同步后必须重新生成静态 arity inventory 和两个 runtime report。

## 尚未覆盖

- 337 个直接 C++ slot 的完整参数/返回类型、overload、继承 override 和副作用；
- `QString` 转换后的精确内容，以及 arrays、objects、NaN、Infinity、整数边界、
  invalid UTF-16、QVariant/QByteArray 等 Qt 类型；
- 13 个公共脚本扩展的 shadowing、默认/额外参数和异常；
- `File`/`X` 对各 file type 的真实绑定和 init/include 生命周期；
- `PE.getEPSignature` 分支的可达输入及上层扫描器对异常的传播/报告；
- Qt 6 其他 minor、Windows、macOS 和完整逐规则 execution conformance。
