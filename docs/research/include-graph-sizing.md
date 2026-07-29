# 固定规则 include 图与预算 sizing

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 结论

固定 `Detect-It-Easy@c2c17dfa...` 的 2,235 个程序文件中共有 56 个
`includeScript()` 调用，分布在 48 个 caller，解析到 27 个不同的 root helper：

- 56/56 都是静态 literal；
- 56/56 都能按固定 database layer 与 case-insensitive first-match 规则解析；
- helper 子图没有静态 cycle；
- 30 个规则 scope 中，单次完整 lifecycle 的最大传递 include evaluation 数为
  30，由 Binary 和 PE 同时达到；
- 最大 active include depth 为 2，由 Binary、MSDOS 和 PE 达到；
- Binary 的静态 23 个直接调用展开为 30 次 evaluation，与既有 rquickjs 动态
  lifecycle trace 的 30 次完全一致。

机器报告为
[`data/include-graph-sizing.json`](data/include-graph-sizing.json)，生成器为
[`analyze_include_graph.py`](../../tools/rules/analyze_include_graph.py)。

## 输入身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Detect-It-Easy rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| program files | 2,235 |
| program bytes | 2,902,881 |
| combined rule tree SHA-256 | `20f2b74e…348bfda` |
| asset identity report | [`runtime-rule-assets-license.json`](data/runtime-rule-assets-license.json) |

分析器重新枚举 `db`、`db_extra`、`db_custom`，只将 `.sg` 或无扩展名 regular
file 视为程序，并复核总文件数与总字节数。PNG、INI、JSON、TXT 等非程序资产不会
进入 include 图。

## 解析模型

固定上游的 include lookup 在 root/unknown records 中按不区分大小写的名称查找。
本报告使用：

1. database layer 顺序 `db → db_extra → db_custom`；
2. 只在每层 root program records 中匹配 target；
3. 名称 case-insensitive；
4. 同名时采用第一个 layer record；
5. 每个调用都重新 evaluate，不使用 include-once cache。

分析器同时使用宽松 site regex 与 literal regex。二者计数不同即视为动态或无法
闭合的调用并失败；target 缺失、helper cycle、program inventory 漂移也都失败。

## 全库结果

| Metric | 结果 |
| --- | ---: |
| rule scopes | 30 |
| literal call sites | 56 |
| calling files | 48 |
| resolved helpers | 27 |
| non-literal sites | 0 |
| missing targets | 0 |
| helper cycles | 0 |
| maximum transitive evaluations | 30 |
| maximum active depth | 2 |

三个非平凡最大 scope：

| Scope | Program files | Direct calls | Transitive evaluations | Max depth |
| --- | ---: | ---: | ---: | ---: |
| Binary | 293 | 23 | 30 | 2 |
| MSDOS | 352 | 7 | 10 | 2 |
| PE | 966 | 25 | 30 | 2 |

其余 27 个 scope 都只有 global `_init` 的 `_debug`、`_runtime_helpers`、
`language` 三次 evaluation，最大 depth 为 1。

## 候选预算推导

本报告提供 fixed-rule sizing envelope，不把观察最大值直接当 hard ceiling。
ADR 0010 的候选采用明确的 8× headroom：

- modern default include depth：`2 × 8 = 16`；
- modern default total evaluations：`30 × 8 = 240`，向上取 2 次幂为 `256`；
- 显式 legacy-high：depth `64`、evaluations `4096`。

该倍数为设计候选，不是上游事实。它容纳固定规则与适度 custom database 扩展，
同时保持有限；超出 modern 候选的受控差分可显式选择 legacy-high。ADR 未评审、
production active-stack/budget 未实现、dynamic/user database 边界未测试前，
这些数值保持 `review_candidate_not_admitted`。

## 不能推出的结论

- static literal closure 不证明未来或用户规则不会使用动态 include name；
- 最大 depth/evaluation 不证明 QuickJS heap、stack、fuel 或 deadline 值；
- 30 次静态 evaluation 与 Binary 动态 trace 一致，不等于 PE/MSDOS 已完成新的
  runtime trace；
- helper graph 无 cycle 不替代恶意 self/two-node/dynamic cycle 的
  `limit-1/exact/+1` 与 SafetyDeviation 测试；
- program bytes 不是 runtime heap usage，不能用于选择 script heap limit。

## 复现

```powershell
python tools\rules\analyze_include_graph.py --check
python -m unittest discover -s tools\tests -p "test_include_graph_sizing.py"
```

分析只读取版本化规则与资产报告，不执行规则，不修改上游文件，也不生成 materialized
语料。
