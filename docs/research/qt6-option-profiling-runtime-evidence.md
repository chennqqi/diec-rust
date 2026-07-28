# Linux Qt6 CLI Options 与 Profiling 运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Qt5/Qt6 CMake oracle 在以下九个 CLI option 用例上原始输出完全相同：

- `--test` 现有/缺失目录；
- `--createtest` 缺失 positionals/完整参数；
- 默认 JSON、verbose JSON、profiling without messages JSON；
- missing database 的 showdatabase，分别不带/带 messages。

精确关系保持一致：

- `--test` 不校验 directory 且无输出、exit 0；
- 完整 `--createtest` 只打印 announcement；
- 缺参 exit 4，错误文本仍误称 `--addtest`；
- verbose 只增加固定 Linux OS record；
- profiling 不带 messages 时与 default 原始输出完全相同；
- messages 在 stdout 前置 database load error，不改变 exit code；
- 九个用例 stderr 全为空。

两侧还在相同 hash-bound Nintendo/Binary 输入上运行
`--profiling --messages --json --deepscan --heuristicscan`。每侧均精确执行
292 条 Binary signature：

- 无缺失、重复或额外规则；
- execution order 完全相同；
- order SHA-256：
  `27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc26b1a9ff0e1ff3`；
- exit 0、stderr 为空。

Profiling elapsed times 留在未跟踪原始 stdout 中，不用于顺序 equality。

## 固定证据

- option report：
  [`data/cli-option-behavior-linux-qt5-qt6.json`](data/cli-option-behavior-linux-qt5-qt6.json)
- profiling order：
  [`data/binary-rule-order-linux-qt5-qt6.json`](data/binary-rule-order-linux-qt5-qt6.json)
- option wrapper：`tools/upstream/probe_qt6_cli_option_behavior.py`
- order wrapper：`tools/upstream/probe_qt6_binary_rule_order.py`
- lifecycle manifest SHA-256：
  `6cf78bbe8c95886978dfba825e2f4d4b130cd92491ecb7f19049cfbd6374e092`
- Nintendo corpus manifest SHA-256：
  `eac3ad62c7f21d5112ee1ca73fbb6cc4e5306b6004357aeaf86144fa3ef51a03`
- selected sample：
  `ps3-type-1-elf.self`
- sample SHA-256：
  `201eaef05a793f1877a7b4a00bf5662cc817a750186783d282db49d442e7c4ed`

两份 wrapper 均不修改或复制原探针逻辑。它们 hash-bound 原
`probe_cli_option_behavior.py` / `probe_binary_rule_order.py`，替换为固定 Qt5
CMake 与 Qt6 CMake oracle，再调用原始 equality、关系、inventory 和 order
验证。原 Qt5 报告不变。

本次外部 raw artifact 数量：

- option：`2 × 9 × 2 = 36` 个 stdout/stderr 文件；
- profiling：两侧各一份 stdout/stderr，共 4 个文件。

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-CLI-OPT-004` verbose；
- `CAP-CLI-OPT-008` profiling；
- `CAP-CLI-TEST-001` test；
- `CAP-CLI-TEST-002` createtest；
- `CAP-RULE-011` script profiling。

`CAP-CLI-OPT-009` messages 已由前一批 database matrix 完整覆盖，本轮提供
额外交叉验证。

完成本批时汇总为 42 项 complete、10 项 partial、16 项 missing。后续
engine-contract 批次已将当前汇总推进到 47/10/11，见
[`qt6-engine-contract-runtime-evidence.md`](qt6-engine-contract-runtime-evidence.md)；
`CAP-GAP-007` 仍保持开放。

## 重现

Option：

```text
python tools/upstream/probe_qt6_cli_option_behavior.py \
  --raw-dir <untracked-option-raw> \
  --output <option-report.json>
```

Profiling order：

```text
python tools/corpus/generate_nintendo_certified_corpus.py <corpus>
python tools/upstream/probe_qt6_binary_rule_order.py \
  --corpus-dir <corpus> \
  --raw-dir <untracked-profiling-raw> \
  --output <order-report.json>
```

68 行清单生成器独立要求九用例 catalog、两侧 identity、all-oracle equality
和全部 option relationship；profiling 部分要求 292 个唯一名称、固定 lifecycle
hash、固定 order hash、两侧 exit/stderr/order metadata 完全满足。
