# Linux Qt6 Engine-only Archive Option 运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-29

## 结论

固定 Linux amd64 Qt5/Qt6 paired matrix 执行：

- 8 个项目生成 nested fixture × 8 种 archive/recursive/aggressive engine
  组合 × 2 个 harness oracle，共 128 次；
- 不含 archive 的 8 × 4 种模式 × 2 个 release CLI oracle，共 64 次；
- 合计 192 次受限容器调用。

64 个 Qt6 harness case 的 exit code、完整 stdout 和 detection tree 均与 Qt5
相同；32 个无 archive harness case 在各自 Qt 版本内又与发布 CLI 完全相同。
三个顶层 archive fixture 在所有无 archive 组合下均为 0 Stream；显式
`bIsArchivesScan` 后均产生 Stream，ZIP→ZIP 的 archive flag 跨层传播并产生
2 个 Stream。因此固定版本中 archive 解包仍是 engine-only 独立选项，发布
CLI 的 recursive/aggressive 组合不能替代它。

唯一差异是五个 PE fixture 的每次 Qt6 调用都输出精确四行
`Unimplemented code.`。40 次 harness 与 20 次 release 调用各保留 80-byte
stderr，SHA-256
`b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`；
其他 132 次 stderr 为空。没有 stdout 或 detection 差异。

## 固定证据

机器报告：
[`data/archive-option-engine-qt5-qt6.json`](data/archive-option-engine-qt5-qt6.json)，
324149 bytes，SHA-256
`5cdadeb09d97a0afd03b2f73ebbb5eb4ffd227b9a21973d34d5a3db739bb8d65`。
fixture manifest SHA-256：
`b382bd0a903cd4dda5a8128508f7a3f514a67a721baacda4c6722c99aefc4229`。

| Oracle | Harness image ID | Harness binary SHA-256 |
| --- | --- | --- |
| Qt5 | `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc` | `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e` |
| Qt6 | `sha256:2e46aa3e3d2fa731e92bd57c11f905bc3ff4a4064106d020314ad05a422c4488` | `6fed831d6c11b67e0a9e0ea0aa57b2a9e380a5a6f53dd46f426122aec3839d76` |

Qt5/Qt6 release image ID 分别为
`sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
和
`sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`。
四个 image revision label 都等于固定上游 commit。

为避免把重复 raw 输出膨胀为大型文档 artifact，报告使用内容寻址：

- 20 个唯一 raw stdout/stderr stream 各保存一次完整 base64；
- 18 个唯一规范化 detection tree 各保存一次；
- 192 个 observation 通过 SHA-256 引用 catalog，共 576 个闭合引用；
- 生成器和测试逐个解码并重算 bytes/hash，case 仍保留各自 count 与 identity。

## 能力影响

`CAP-NEST-003` 从 partial 提升为 Linux Qt6 `evidence_complete`。机器清单现在为
63 项 complete、2 项 partial、3 项 missing；5 项仍需闭环，
`CAP-GAP-007` 保持开放。这里的当前统计包含随后完成的 count-boundary
批次；本 archive-option 批次完成当时为 62/2/4。

本矩阵也再次观察默认 archive/resource count 为 21、aggressive 控制到达 22，
但单独看仍不足以关闭 count/depth 能力。随后：

- `CAP-NEST-004` 已由
  [`qt6-count-boundary-runtime-evidence.md`](qt6-count-boundary-runtime-evidence.md)
  的 99999/100000/100001 archive 三点和 21/2001 resource 计数闭合；
- `CAP-NEST-009`：尚未在 Qt6 执行 64 层、累计展开量与 cancellation 边界。

## 重现

```text
python tools/corpus/generate_nested_corpus.py <nested-fixture>

docker build --network=none --provenance=false \
  --file tools/upstream/Dockerfile.archive-harness-qt6 \
  --tag diec-rust/upstream-archive-harness-qt6:74eaf505 \
  tools/upstream

python tools/upstream/probe_qt6_archive_option_harness.py \
  --nested-corpus-dir <nested-fixture> \
  --output docs/research/data/archive-option-engine-qt5-qt6.json

python tools/research/build_qt6_closure_plan.py
```

所有容器调用使用 network none、1 CPU、512 MiB memory、128 PIDs 和只读
fixture mount。Qt6 Dockerfile 只替换 CLI `main` object，不修改上游扫描、
archive adapter、规则或 formatter 实现。

## 限制

- 仅覆盖 Linux amd64、Qt 5.15.8/Qt 6.4.2 和八个安全 fixture；
- 本实验固定 option reachability，不代表完整 archive family 已在 Qt6 闭环；
- Qt6 PE warning 仍需兼容评审，不得在 Rust 差分层静默删除。
