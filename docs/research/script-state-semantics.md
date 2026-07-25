# Qt Script 跨规则持久状态语义

Status: Draft

Upstream: DIE-engine@`74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-26

## 问题

[`script-scope-semantics.md`](script-scope-semantics.md) 已证明 Qt 5 不会让一条
规则的顶层 lexical `const` 阻止后续规则使用同名绑定。per-rule function wrapper
能够复现该行为，但它也隔离顶层 `var` 和普通函数。若 Qt 会持久化这些声明，
wrapper 就不是通用等价模型。

本实验分别观察：

- 顶层 `var` 能否被后一规则读取和更新；
- 顶层普通函数能否被后一规则调用；
- sloppy implicit global 是否持久化；
- top-level `this` 是否指向共享全局对象。

## Fixture 与 oracle

项目生成器
[`generate_script_state_fixture.py`](../../tools/corpus/generate_script_state_fixture.py)
生成 29 字节良性输入和 7 条规则；逐文件身份见
[`script-state-fixture.json`](data/script-state-fixture.json)。探针
[`probe_script_state.py`](../../tools/upstream/probe_script_state.py) 复用相同的
只读挂载、原始输出保存和结构化解析逻辑。

固定 Linux Qt5 qmake/CMake oracle 的规范化结果完全一致，完整机器证据见
[`script-state-qt5.json`](data/script-state-qt5.json)：

| 行为 | 后序观察 |
| --- | --- |
| `var sharedVar = 40`，后一规则 `+= 2` | `42` |
| 前一规则定义 `sharedFunction()` | 后一规则调用得到 `42` |
| 前一规则写 `sharedImplicit = 7` | 后一规则读取 `7` |
| 顶层 `this` 写共享属性 | detect 中读取成功，identity 为 `true` |

两个 oracle 均产生 7/7 detection、退出 0、stderr 为空。首轮 fixture 还观察到
Qt5 不提供现代 `globalThis`，因此最终 `this` case 使用共享属性和传统 `this`
identity，不依赖该内建。

可观察契约因此是混合模型：

- lexical `const`/`let` 不在后续规则中形成绑定冲突；
- 顶层 `var`、普通函数和 implicit global 会留在共享状态中；
- 当前规则的 lexical `detect` 仍可在该次求值后由宿主调用。

## QuickJS 对照

同一 fixture 在 raw shared-context QuickJS 中得到 0 error、7/7 detection，
与 Qt5 基线完全一致。per-rule function wrapper 得到 2 error、5/7 detection：

- `state_var_update.2.sg` 看不到前一规则的 `sharedVar`；
- `state_function_read.4.sg` 看不到前一规则的 `sharedFunction`。

wrapper 仍正确保留 implicit global，因为 sloppy assignment 写入共享 global；通过
`.call(globalThis)` 也复现了 top-level `this`。因此 wrapper 解决 lexical
binding 冲突的同时，会丢失显式 `var`/function 的跨规则状态，不能被描述为通用
Qt Script 替代。

## 固定 Binary 规则静态审计

工具
[`audit_binary_cross_rule_state.js`](../../tools/upstream/audit_binary_cross_rule_state.js)
使用固定上游 bundled UglifyJS 3.19.3（BSD-2-Clause）解析按 Qt5 顺序排列的 292
条 Binary 规则。摘要见
[`binary-cross-rule-state.json`](data/binary-cross-rule-state.json)：

- 1,122,477 bytes、292/292 文件成功解析；
- 302 个顶层 persistent `var`/function 声明；
- 2 个 lexical 声明；
- 3,347 个逐文件 distinct unresolved global access；
- 1,085 个访问先前 shared state 的静态候选；
- 其中 provider 为前序显式 `var`/function、会被 wrapper 丢失的候选为 0。

最后一项说明固定 Binary 集合中没有发现“后一规则依赖前一规则显式 var/function”
的静态候选，所以 wrapper 的 292/292 顶层结果没有被当前审计直接否定。但这不是
动态等价证明：computed property、`eval` 生成绑定和执行可达性不由该分析解决，
init/include 状态也不属于跨规则 provider 集。

## 设计影响

runtime 门禁必须同时包含 lexical 隔离和 persistent state 两组 fixture。可行方向
至少包括：

- 对固定规则做受审计的 wrapper，并持续要求 wrapper-loss candidate 为 0；
- 在 QuickJS 中实现更精确的 per-evaluate lexical environment，同时保留 global
  var/function property；
- 使用更接近 Qt evaluate 语义的其他 runtime。

在完整 detect/HostApi differential 和动态状态 trace 通过前，不能接受 QuickJS
runtime ADR，也不能把当前静态零候选泛化到其他 file type 或未来规则版本。

## 复现

```powershell
$fixture = Join-Path $env:TEMP diec-rust-script-state-fixture
python tools/corpus/generate_script_state_fixture.py $fixture

python tools/upstream/probe_script_state.py `
  --fixture-dir $fixture `
  --raw-dir (Join-Path $env:TEMP diec-rust-script-state-raw) `
  --output docs/research/data/script-state-qt5.json

cargo +1.88.0 run --release --locked `
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- `
  eval-scope-fixture $fixture `
  docs/research/data/script-state-fixture.json `
  docs/research/data/script-state-qt5.json

cargo +1.88.0 run --release --locked `
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- `
  eval-scope-fixture-lexical $fixture `
  docs/research/data/script-state-fixture.json `
  docs/research/data/script-state-qt5.json

node tools/upstream/audit_binary_cross_rule_state.js `
  upstream/Detect-It-Easy/db `
  docs/research/data/binary-rule-order-linux-qt5.json `
  upstream/Detect-It-Easy/autotools/dbcompiler/node_modules/uglify-js `
  docs/research/data/binary-cross-rule-state.json
```
