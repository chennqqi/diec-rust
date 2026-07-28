# Linux Qt6 规则编排运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Linux amd64 Qt5/Qt6 CMake oracle 在同一个项目生成规则数据库上各执行
10 个 case。两侧 canonical execution order、完整 detection 投影及 14 条关系
全部相同；20 次进程均 exit 0、stderr 为空。

本轮完整覆盖：

- main、extra、custom 三层数据库分别排序后按层 append；
- 正常 priority、相同 priority、字符串 priority、缺失/空 priority 和带
  type `_init` 的非传递比较器边界；
- global init、type init 和同名 include 的首层优先级；
- Binary 输入排除 PE 规则；
- `DS`/`EP` deep gate 与 `HEUR` heuristic gate 的四种独立组合；
- 空数据库的唯一 Unknown fallback。

这证明 Qt6 在该固定边界上保持 Qt5 的规则编排行为，包括上游 priority
比较器的非直觉边界；不能据此把 Rust 实现简化为全局数值 priority 排序。

## 固定身份

机器报告：
[`data/rule-orchestration-linux-qt5-qt6.json`](data/rule-orchestration-linux-qt5-qt6.json)。
Qt5 对照报告：
[`data/rule-orchestration-linux-qt5.json`](data/rule-orchestration-linux-qt5.json)。

| 项目 | Qt5 CMake | Qt6 CMake |
| --- | --- | --- |
| Image | `diec-rust/upstream-oracle-cmake:74eaf505` | `diec-rust/upstream-oracle-cmake-qt6:74eaf505` |
| Image ID | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` |
| Revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` | 同左 |
| Binary | `/opt/die-build/src/console/diec` | 同左 |
| Cases | 10 | 10 |
| Exit / stderr | 全部 0 / empty | 全部 0 / empty |

固定 fixture manifest SHA-256 为
`535d96510e1a807a07af752ed60b0239bdbb91331ce51b1f89d2be043d07f23e`。
报告 SHA-256 为
`a3a3fb8409cd0006729d0eac625586ad30a432580e7ca5a37c4ed491a4c15b0a`。

薄 wrapper `tools/upstream/probe_qt6_rule_orchestration.py` hash-bound 原
`probe_rule_orchestration.py`，只替换两个 oracle 身份和报告 metadata。
fixture 校验、进程执行、输出解析、case 断言和 normalized equality 仍由原探针
唯一实现。

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-RULE-001` three database layers；
- `CAP-RULE-002` rule priority ordering；
- `CAP-RULE-003` global and type init；
- `CAP-RULE-004` file-type rule filtering；
- `CAP-RULE-005` deep and heuristic filtering。

完成本批时汇总为 52 项 complete、9 项 partial、7 项 missing。后续
result-model 批次已将当前汇总推进到 58/3/7，见
[`qt6-result-model-runtime-evidence.md`](qt6-result-model-runtime-evidence.md)；
`CAP-GAP-007` 仍保持开放。

## 重现

```text
python tools/corpus/generate_rule_orchestration_fixture.py <fixture>

python tools/upstream/probe_qt6_rule_orchestration.py \
  --fixture-dir <fixture> \
  --raw-dir <untracked-raw> \
  --output docs/research/data/rule-orchestration-linux-qt5-qt6.json
```

两个容器均以 `--network=none` 运行，fixture 只读挂载。profiling elapsed time
不是稳定字段；原始 stdout/stderr 的长度和 SHA-256 仍保存在报告中，原始流放在
未跟踪目录。

能力清单生成器要求固定 image ID/revision、精确 2 × 10 case catalog、空 stderr、
14 条关系全 true，并要求 paired report 与原 Qt5 报告的 canonical cases、
relationships 和 fixture manifest 完全相等。

## 限制

- 仅覆盖 Linux amd64、Qt 5.15.13/Qt 6.4.2 和固定上游 commit；
- 不覆盖 Windows/macOS 的 `std::sort` 实现差异；
- include 重复/循环、异常传播和非 Binary file type 仍未覆盖；
- signature path 是独立 engine-only 能力，仍由 `CAP-RULE-007` 跟踪。
