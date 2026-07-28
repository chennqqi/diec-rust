# Linux Qt6 Resource Context 传播运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-29

## 结论

固定 Linux amd64 Qt6 CLI 在项目生成的 RT_MANIFEST PE 上保持 Qt5 的四模式
行为：

- default、仅 recursive、仅 aggressive 都只产生 PE32 root Unknown；
- 只有 recursive+aggressive 建立 `Binary / Resource` child；
- child 保留 offset `608`、size `20` 和 `parentfilepart=Resource`；
- 原样 `win_resources.1.sg` 仍根据传播的 resource type `24` 报告
  `Format: Manifest[Resources]`。

四案的 exit code、完整 stdout 和规范化 detection tree 均与 Qt5 相同。每次
Qt6 CLI 调用额外产生精确四行 `Unimplemented code.`：80 bytes，SHA-256
`b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`。
报告在分类前保存了完整 stdout 与 stderr hex，没有通过规范化删除差异。

## 固定身份

Qt6 报告：
[`data/resource-context-chain-qt6.json`](data/resource-context-chain-qt6.json)，
SHA-256
`0619aa5e1768ef4044d9cd60378dd991057bb97960b70887b0de84552978aabc`。
Qt5 对照：
[`data/resource-context-chain-qt5.json`](data/resource-context-chain-qt5.json)，
SHA-256
`56090cee25f736eeb1c1fbb90a1619199f0fc2a93c7c318c0731ddffb585de64`。

| 项目 | Qt6 值 |
| --- | --- |
| Image | `diec-rust/upstream-oracle-cmake-qt6:74eaf505` |
| Image ID | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` |
| Revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Binary SHA-256 | `e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e` |
| Fixture | 1024 bytes / `0a973cbde2f520bdbd6e1b75304e4a412462113d4de9a8139cdf997af16641ee` |

default、recursive 和 aggressive 的 stdout 均为 468 bytes，SHA-256
`94941d54fe62e2c43a0709062c7628eb2fa26d7fda825dc366547a4dc85a8f8b`；
recursive+aggressive 为 1060 bytes，SHA-256
`c9e8a5c7f3eab49f1f8b533917aba24abebc9f1f05128bf4a359bedbeffab7fa`。
四案 stderr 都保留上述 80-byte warning。

## 能力影响

`CAP-NEST-006` 提升为 Linux Qt6 `evidence_complete`。机器清单现在为
62 项 complete、2 项 partial、4 项 missing；6 项仍需闭环，
`CAP-GAP-007` 保持开放。

该计数包含后续
[`qt6-archive-option-runtime-evidence.md`](qt6-archive-option-runtime-evidence.md)
对 `CAP-NEST-003` 的闭环。

这项结论只证明固定 public CLI work queue 中 resource context 的传播行为。
它不扩大 public scanner 的 file-part 范围；debug-data 默认不可达性仍由
[`qt6-debug-dispatch-runtime-evidence.md`](qt6-debug-dispatch-runtime-evidence.md)
单独固定。

## 重现

```text
python tools/corpus/generate_nested_corpus.py <nested-fixture>

python tools/upstream/probe_qt6_resource_context_chain.py \
  --nested-corpus-dir <nested-fixture> \
  --output docs/research/data/resource-context-chain-qt6.json

python tools/research/build_qt6_closure_plan.py
```

探针验证固定 image ID/revision、CLI binary hash、fixture size/hash、Qt5 baseline
raw identity和四案预期树。任一 stdout、exit code、context 字段或 warning
字节变化都会失败。闭环生成器再次逐案重算 raw hash，并要求 Qt5/Qt6 完整
stdout 相同、Qt5 stderr 为空、Qt6 stderr 恰为固定 warning。

## 限制

- 仅覆盖 Linux amd64、Qt 6.4.2 和一个项目生成 RT_MANIFEST PE；
- 本实验隔离 recursive/aggressive gate，不覆盖 resource count 上限；
- Qt6 warning 属于待兼容评审的平台差异，不等于 Rust 实现可静默忽略。
