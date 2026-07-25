# Qt Script 跨规则求值作用域语义

Status: Draft

Baseline: DIE-engine `74eaf505c250ab47e709024e9dc41657cd8f2254`

Platform: Linux amd64, Qt 5, qmake/CMake 双 oracle

## 问题

固定 Binary 执行顺序的 QuickJS 实验出现两个跨规则错误：

- `audio.1.sg` 的顶层 `const debug` 阻止后序规则给 `debug` 赋值；
- 前序规则留下的 `function detect` 与
  `__MiniExtensionsHeuristic_By_DosX.7.sg` 的 `const detect = main`
  冲突。

固定 Qt oracle 没有报告这些错误，但 profiling 本身只能证明扫描继续，不能说明
`const`、赋值和 `detect` 的可观察行为。为避免从错误缺失推断运行时模型，本实验
使用项目生成的最小规则数据库直接观察结果。

## Fixture

生成器是
[`generate_script_scope_fixture.py`](../../tools/corpus/generate_script_scope_fixture.py)，
清单是
[`script-scope-fixture.json`](data/script-scope-fixture.json)。fixture 只含 29
字节良性输入和 7 条项目生成规则，不复制上游规则或样本。规则优先级固定为
1–7，依次覆盖：

1. 顶层 `const scopeValue = 1`；
2. 后一 `evaluate()` 执行 `scopeValue = 2`；
3. `function detect`；
4. 后一 `evaluate()` 执行 `const detect = main`；
5. 再次声明 `function detect`；
6. 顶层 `const debug = 1`；
7. 后一 `evaluate()` 执行 `debug = 2`。

每条规则的 `detect` 都写入唯一结果；两个赋值结果还记录读取值。这样可以区分
“规则仅被枚举”“求值成功”和“求值后宿主成功调用本次 detect”。

## Qt 5 观察

探针
[`probe_script_scope.py`](../../tools/upstream/probe_script_scope.py) 对固定 qmake 和
CMake oracle 使用同一只读 fixture。完整机器证据见
[`script-scope-qt5.json`](data/script-scope-qt5.json)。

两个构建的规范化输出完全相同：

| Rule | 观察结果 |
| --- | --- |
| `scope_const_define.1.sg` | detect 成功，读取 `scopeValue == 1` |
| `scope_const_assign.2.sg` | 求值和 detect 成功，读取 `scopeValue == 2` |
| `scope_function_detect.3.sg` | detect 成功 |
| `scope_const_detect.4.sg` | `const detect = main` 成功且宿主调用 `main` |
| `scope_after_const_detect.5.sg` | 后续 `function detect` 成功 |
| `scope_debug_const.6.sg` | detect 成功，读取 `debug == 1` |
| `scope_debug_assign.7.sg` | 求值和 detect 成功，读取 `debug == 2` |

两者均退出 0、stderr 为空，并产生全部 7 个结果。这证明的可观察契约是：

- 一条规则的顶层 lexical `const` 不会在后续规则求值中形成只读冲突；
- `function detect`、后续 `const detect`、再后续 `function detect` 可连续使用；
- 当前规则的 lexical `detect` 在该规则求值后可被上游宿主提取并调用。

实验不声称 Qt 内部一定采用某种 ECMAScript environment 实现；生产兼容层只应
依赖上述可观察行为。

## QuickJS-NG 对照

同一 fixture 在一个 rquickjs/QuickJS-NG context 中按相同顺序执行，并在每次
成功求值后调用 `detect`。结果是 4 个 detection 和 3 个求值错误：

| Rule | QuickJS-NG |
| --- | --- |
| `scope_const_assign.2.sg` | `'scopeValue' is read-only` |
| `scope_const_detect.4.sg` | `redeclaration of 'detect'` |
| `scope_debug_assign.7.sg` | `'debug' is read-only` |

这与完整 Binary 顶层 lifecycle 中的 `const detect`、`const debug` 两类错误直接
对应。因而那两个等长 overlay 只是 feasibility workaround，不是已证明等价的
生产方案。

## Per-rule lexical wrapper 验证

后续 spike 将每条规则包装在非 strict function lexical scope 中，在同一个
QuickJS context 中共享宿主/global 状态，并在 wrapper 返回前解析和调用本次
`detect`。同一 7 规则 fixture 的结果为：

- 0 个 eval error；
- 7/7 detection；
- detection 的 type、name、version、info 和顺序均与 Qt 5 基线相同。

再按固定 Qt 顺序运行全部 292 条 Binary 规则：

- global `_init`、Binary `_init` 和 30 次 include 保持不变；
- 292/292 规则成功求值并解析出 function 类型的 `detect`；
- `audio.1.sg` 和 MiniExtensions 不再需要跨规则 overlay；
- 仅 Nintendo 规则仍需要绑定 path/size/hash 的单脚本语法 overlay。

这证明 per-rule lexical wrapper 是比“单一 global eval + 三个 overlay”更接近
Qt 可观察契约的候选方案，但仍不是 runtime 选型结论：完整规则的 `detect` 尚未
逐条调用，wrapper 对 `this`、direct eval、top-level `var`、异常栈和 helper
可见性的差分也需继续验证。

Nintendo 规则内部同一函数的 `var`/`const` 重定义属于单脚本语法差异，不由本
实验解释，仍需独立 compatibility 决策。

## 复现

```powershell
$fixture = Join-Path $env:TEMP diec-rust-script-scope-fixture
python tools/corpus/generate_script_scope_fixture.py $fixture

python tools/upstream/probe_script_scope.py `
  --fixture-dir $fixture `
  --raw-dir (Join-Path $env:TEMP diec-rust-script-scope-raw) `
  --output docs/research/data/script-scope-qt5.json

cargo +1.88.0 run --release --locked `
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- `
  eval-scope-fixture $fixture `
  docs/research/data/script-scope-fixture.json `
  docs/research/data/script-scope-qt5.json

cargo +1.88.0 run --release --locked `
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- `
  eval-scope-fixture-lexical $fixture `
  docs/research/data/script-scope-fixture.json `
  docs/research/data/script-scope-qt5.json

cargo +1.88.0 run --release --locked `
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- `
  eval-binary-lifecycle-lexical `
  upstream/Detect-It-Easy/db `
  docs/research/data/binary-rule-order-linux-qt5.json
```

profiling 毫秒值不是确定性数据；报告保留每个 oracle 的原始 stdout 哈希，但双
构建一致性判定使用规则顺序和结构化 detection。
