# Linux Qt6 Debug-data 分派运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-29

## 结论

固定 Linux amd64 Qt6 paired harness 保持 Qt5 的完整九项语义关系：

- Formats 同时枚举 PE resource 与 debug-data part；
- public recursive+aggressive scanner 正常分派 resource child；
- public scanner 不建立 debug-data child；
- 同一枚举 debug part 经 direct private entry 可由原样规则识别为
  `PDB file link / 7.0`。

Qt5/Qt6 的完整 harness JSON 和 stdout SHA-256 相同。唯一原始差异是 Qt6
在 stderr 输出四行 `Unimplemented code.`，80 bytes，SHA-256
`b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`。
这是此前已固定的 PE 规则 runtime warning；报告原样保留，没有从 raw
comparison 中删除。

## 固定身份

机器报告：
[`data/debug-dispatch-engine-qt6.json`](data/debug-dispatch-engine-qt6.json)，
SHA-256
`4aa91c7ecc275c2d92549f66ee2b421ada6ab3f2c51fc7c0b1934f6cbf94b78f`。
Qt5 对照：
[`data/debug-dispatch-engine-qt5.json`](data/debug-dispatch-engine-qt5.json)。

| 项目 | Qt6 值 |
| --- | --- |
| Image | `diec-rust/debug-dispatch-harness-qt6:74eaf505` |
| Image ID | `sha256:10a4ab04d46419ae7e3ea7285588d2c8cd9dc7fd75b82e00d6aa9e8f7156f3c3` |
| Revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Binary SHA-256 | `e19582c9401a493016f8933df642ebc89460f4769d580a6e1aced1fca89d6855` |
| Raw stdout | 5010 bytes / `6068b2b4d1a322b2ba398546e865ba0dbdfd269da99d935fdaa2f8538c22f0cd` |
| Raw stderr | 80 bytes / `b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b` |

运行限制与 Qt5 相同：network none、1 CPU、512 MiB memory、128 PIDs，
fixture 只读挂载。Qt6 Dockerfile 从固定 CMake Qt6 oracle 派生，不下载依赖。

薄 wrapper `tools/upstream/probe_qt6_debug_dispatch_harness.py` 只在真实 harness
进程处捕获精确已知 stderr，使原验证器继续校验 JSON；随后把真实 80-byte
stderr 写回 raw artifact 和报告。任何其他 stderr、行数或 SHA 都会失败。

## 能力影响

`CAP-NEST-007` 提升为 Linux Qt6 `evidence_complete`。当前汇总为
62 项 complete、2 项 partial、4 项 missing；6 项仍需闭环，
`CAP-GAP-007` 保持开放。

该计数包含后续
[`qt6-resource-context-runtime-evidence.md`](qt6-resource-context-runtime-evidence.md)
对 `CAP-NEST-006` 的闭环。
后续 archive-option 证据又关闭 `CAP-NEST-003`，见
[`qt6-archive-option-runtime-evidence.md`](qt6-archive-option-runtime-evidence.md)。

## 重现

```text
python tools/corpus/generate_debug_dispatch_fixture.py <fixture>

docker build --network=none \
  -f tools/upstream/Dockerfile.debug-dispatch-harness-qt6 \
  -t diec-rust/debug-dispatch-harness-qt6:74eaf505 \
  tools/upstream

python tools/upstream/probe_qt6_debug_dispatch_harness.py \
  --fixture-dir <fixture> \
  --raw-dir <untracked-raw> \
  --output docs/research/data/debug-dispatch-engine-qt6.json
```

能力清单生成器要求固定 image/revision/资源限制、九项关系全部通过、Qt5/Qt6
完整 JSON 与 stdout hash 相同，并只接纳上述精确 Qt6 warning。

## 限制

- 仅覆盖 Linux amd64、Qt 6.4.2 和一个项目生成 PE；
- direct debug 正控制使用 private engine entry，不表示 public API 暴露该路径；
- 其他未被 public scanner 调度的 file-part 类型仍需各自证据。
