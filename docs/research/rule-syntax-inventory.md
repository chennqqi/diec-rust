# 固定规则语法与宿主调用清单

Status: Draft

Upstream: Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6

Last updated: 2026-07-26

## 1. 目的与边界

本文固定上游规则实际使用的 JavaScript 语法、未声明全局和格式宿主调用形状，为
规则 runtime 与 HostApi 设计提供完整的“规则侧用法”清单。它不等同于：

- Qt 5/Qt 6 JavaScript 运行语义兼容证明；
- C++ 宿主类声明的完整 API 清单；
- 调用成功、返回值或异常行为证明；
- 规则 detection 结果差分。

这些边界很重要：一个 parser 接受源码，只证明能够建立 AST；例如固定 Nintendo
规则仍会在 Boa/QuickJS 原始 eval 中触发已记录的 lexical early error。

## 2. 输入与复现

输入严格选择固定 sibling subtree 的：

- `db/` 与 `db_extra/` 下全部 `.sg` 文件；
- 同两目录下全部无扩展名公共脚本；
- 不包括 `.ini`、`.json`、`.txt`、图标和其他发布附件。

因此口径为 2175 个 `.sg` 加 60 个无扩展名脚本，共 2235 个文件、2,902,881
bytes，与 Boa/rquickjs runtime spike 的输入数量和字节数一致。每个文件的相对路径、
字节数和 SHA-256 保存在
[`rule-syntax-inventory.json`](data/rule-syntax-inventory.json)；按序 manifest
SHA-256 为
`e370cb2f9e7ba8e384bfe25abad1e4af7a1d38bafb99d1cdce1ec03e374c944c`。

生成器
[`extract_rule_syntax_inventory.js`](../../tools/rules/extract_rule_syntax_inventory.js)
复用固定规则 subtree 内 dbcompiler 自带的 UglifyJS parser，不下载 npm 依赖。
其 18-file parser manifest SHA-256 与 signature 静态清单相同，为
`08dce1589c2782677f197d6289ebce3edc968aa0a35c982c0e6b66788e9e70a6`。
任一文件 parse 失败会让生成整体失败，不生成部分成功清单；机器清单同时记录
生成器自身 SHA-256。

```sh
node tools/rules/extract_rule_syntax_inventory.js \
  --rules-root upstream/Detect-It-Easy \
  --parser-module upstream/Detect-It-Easy/autotools/dbcompiler/node_modules/uglify-js/tools/node.js \
  --output docs/research/data/rule-syntax-inventory.json
```

## 3. 语法结果

固定输入 2235/2235 建立 AST，0 parse failure，共 349,446 个 AST 节点、55 种
实际节点类型。机器清单保存每种节点和所有 binary、unary、assignment operator
的精确计数。

对 runtime 选型影响较大的非平凡构造包括：

| 构造 | AST 数量 |
| --- | ---: |
| `RegExp` literal | 551 |
| `switch` | 348 |
| `while` / `do` / `for` | 284 / 67 / 1032 |
| `for…in` | 5 |
| `try` / `catch` / `throw` | 2 / 2 / 4 |
| labeled statement | 10 |
| `new` | 38 |
| `this` | 345 |
| `delete` | 14 |
| `typeof` | 91 |
| `instanceof` | 4 |
| `debugger` | 4 |

固定语料没有出现 `with`、class、arrow function、`for…of`、generator/yield 或
async/await。这个“零使用”只约束当前固定规则 commit；同步新规则时必须重生成，
不能据此从 parser 中永久删除这些语法而不产生明确诊断。

运算符面包含宽松和严格相等、逻辑短路、位运算、signed/unsigned shift、复合赋值、
prefix/postfix 增减及 `delete`。其中 `>>>` 实际出现 8 次，说明 JS 32-bit
unsigned coercion 不是可选语义；`==`/`!=` 共 2179 次，也不能统一改写为严格比较。

## 4. 调用形状

普通 `Call` AST 共 28,372 个；38 个 `new` 单独计数，不混入调用：

| 分类 | 调用次数 | receiver/name 记录 | arity 形状 |
| --- | ---: | ---: | ---: |
| 规则内具名函数 | 1,053 | 363 | 372 |
| 未声明 global 直接调用 | 7,834 | 71 | 101 |
| member 调用 | 19,485 | 1,016 | 1,082 |
| 其中第一层已知格式宿主 receiver | 16,499 | 429 | 464 |

已知宿主调用分布在 29 个 receiver：`APK`、`Amiga`、`Archive`、`AtariST`、
`Binary`、`CFBF`、`COM`、`DEX`、`DOS16M`、`DOS4G`、`ELF`、`File`、
`ISO9660`、`JAR`、`JavaClass`、`LE`、`LX`、`MACH`、`MACHOFAT`、`MSDOS`、
`NE`、`NPM`、`PDF`、`PE`、`PNG`、`PYC`、`RAR`、`X` 和 `ZIP`。

规则侧未出现动态 computed 第一层宿主方法调用；429 个 receiver/method 均可静态命名。
更深成员链单独保留，不把 `MSDOS.addressToOffset.apply(...)` 的 `apply` 误记为
MSDOS HostApi。
但同名方法可能有多个实参个数。例如 `X.c` 有 494 次一参数和 699 次二参数调用，
`PE.compareEP` 有 1434 次一参数和 85 次二参数调用。HostApi 设计不能只保存
“方法名存在”，必须为每个方法核对全部观察到的 arity、默认参数和 Qt 转换行为。

`known_host_first_level_members` 还保存宿主第一层字段/方法读取及直接写入计数，
用于覆盖 `PE.section` 一类非调用访问。嵌套属性的最终键可能由普通 JS 下标决定；
本清单只把静态第一层宿主成员作为 HostApi 边界。

`known_receiver_script_extensions` 另保存 13 个公共脚本函数扩展，包括
`Archive.add/contents`、MSDOS `_init` 的 5 个方法和 PE `_init` 的 6 个方法。
这些是 JavaScript 层，不应误写成 C++ slot；与固定声明的联合差分见
[`host-api-inventory.md`](host-api-inventory.md)。

## 5. 未声明 global 的解释限制

清单保存 1408 个未声明 global symbol 名及 read/call/write 摘要，并新增 183 个
顶层函数名、2371 次定义的清单，但不提前把所有 undeclared symbol 都标成 HostApi。
该集合混合了：

- Qt/ECMAScript 内建，如 `String`、`Number`、`parseInt`；
- 引擎注入函数，如 `includeScript`、`_setResult`；
- 根规则框架定义的 `meta`、`result` 等普通 JavaScript 函数；
- 公共脚本稍后定义的 helper；
- 规则有意创建并跨脚本共享的隐式 global；
- 加载顺序错误时才会表现为未声明的符号。

71 个 undeclared direct-call 名已与固定 `die_script` 声明、规则顶层定义和
ECMAScript global 做完第一轮集合差分：55 个规则函数候选、7 个 native engine
global、7 个 ECMAScript global 和 2 个固定规则拼写错误。详见
[`global-host-api-inventory.md`](global-host-api-inventory.md)。scope analysis
中的 `undeclared` 仍不能直接等价为“缺失宿主方法”；跨规则 global 还必须遵守
[`binary-rule-lifecycle.md`](binary-rule-lifecycle.md) 已确认的共享 context。

## 6. 对设计和测试的约束

- runtime conformance corpus 至少覆盖机器清单中的全部 55 种 AST 类型和运算符；
- 未支持语法必须在规则加载阶段产生路径、行列和构造类型诊断；
- HostApi codegen/trait 设计必须以源码声明为主，并证明覆盖 429 个观察到的方法组合、
  464 个 arity 形状、16 个非格式 native global、13 个脚本扩展和第一层字段访问；
- 规则同步校验必须重生成清单；文件 manifest、AST 类型、宿主方法或 arity 变化均
  进入人工评审；
- 该清单不能作为 runtime 兼容率或 detection 正确率使用，后者仍依赖 Qt oracle
  和真实 HostApi 差分。

## 7. 尚未完成

- 为固定 C++ 声明和脚本 shadowing 补齐 Qt 类型转换、默认/额外参数及异常行为；
- 为 1408 个未声明 global 中非直接调用的读取、写入和动态访问完成分类，并验证
  55 个跨文件函数候选的 include 可达性；
- 为 55 种 AST 类型、全部运算符及 464 个宿主 arity 形状生成最小 Qt 5/Qt 6
  conformance fixture；
- 用完整 HostApi 逐条执行规则并与固定 Qt oracle 比较结果和异常。
