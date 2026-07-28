# Linux Qt6 Scan Options 与 Nested Gate 运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-29

## 结论

固定 Qt5/Qt6 CMake oracle 已执行：

- 26 个安全 baseline 样本的普通 JSON 扫描；
- 5 个代表样本 × default/deep/heuristic/aggressive/alltypes/format/
  hideunknown/combined，共 40 个 scan-option vectors；
- 8 个 nested 样本 × default/recursive/aggressive/
  recursive+aggressive，共 32 个 internal-recursion vectors。

除 `minimal.exe` 的 alltypes 和 combined 外，所有退出码、stdout、option
相对变化和 JSON detection tree 在两侧相同。nested 的 32 个 detection tree
全部相同。

原始矩阵共有 32 个差异：

- 30 个仅为 PE 输入上的 Qt6 四行 `Unimplemented code.` stderr；
- 2 个同时有 stdout/stderr 差异，分别是 `minimal.exe` 的 alltypes 和
  combined。

后两者的 stdout 差异不是 detection 变化。Qt6 在完整 JSON document 后追加：

```text
_init: MSDOS/_init: 41: TypeError: Cannot assign to read-only property "getEntryPointOffset"
extender_DOS4G.0a.sg: MSDOS/extender_DOS4G.0a.sg: 10: TypeError: Property 'getNEOffset' of object MSDOS_Script(<address>) is not a function
```

`<address>` 对应原始 `MSDOS_Script(0x...)` 对象地址。聚焦探针对 alltypes 和
combined 各重复 3 次；每次 Qt5/Qt6 JSON 前缀相同，Qt5 无 trailing
diagnostics，Qt6 规范化后的两行 diagnostics 相同，原始地址在本次三次运行中
各不相同。规范化仅在保存 base64 原始 stdout/stderr 后执行。

## 固定证据

- scan/nested matrix：
  [`data/cli-scan-nested-matrix-linux-qt5-qt6.json`](data/cli-scan-nested-matrix-linux-qt5-qt6.json)
- alltypes raw-first probe：
  [`data/qt6-alltypes-diagnostics.json`](data/qt6-alltypes-diagnostics.json)
- 聚焦探针：
  `tools/upstream/probe_qt6_alltypes_diagnostics.py`
- baseline corpus manifest SHA-256：
  `f5adabeedeaf3bb69b8e52f8de20efd0f0b87bd4dcd247610d4e876b9266f329`
- nested fixture manifest SHA-256：
  `b382bd0a903cd4dda5a8128508f7a3f514a67a721baacda4c6722c99aefc4229`

Oracle identity 与
[`qt6-cli-runtime-evidence.md`](qt6-cli-runtime-evidence.md) 相同：
Qt5 image ID
`sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`，
Qt6 image ID
`sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`。

## 能力影响

以下能力具有完整 Linux Qt6 行级证据：

- `CAP-CLI-OPT-001/002/003/005/006/007/010`
- `CAP-NEST-002`
- `CAP-NEST-005`

“完整证据”表示能力边界已执行且差异已精确分类，不表示 Qt5/Qt6 原始流完全
相同。特别是 `CAP-CLI-OPT-006` 必须保留上述 Qt6 diagnostics。

以下能力由 missing 提升为 partial：

- `CAP-NEST-001`：内部 recursive gate 已覆盖，Qt6 目录遍历尚未覆盖；
- `CAP-NEST-003`：CLI 各组合均不解包 archive，但 Qt6 engine-only archive
  option 尚未执行；
- `CAP-RULE-005`：真实规则集的 deep/heuristic 效果已覆盖，独立 rule gate
  正反 fixture 尚未执行。

本切片当时使汇总达到 28 项 complete。后续 special-mode 证据见
[`qt6-special-runtime-evidence.md`](qt6-special-runtime-evidence.md)；
当前计数以
[`qt6-capability-closure-plan.md`](qt6-capability-closure-plan.md)
为准。`CAP-GAP-007` 保持开放。

后续 archive-option paired matrix 已执行 engine-only 边界并将
`CAP-NEST-003` 提升为 complete，见
[`qt6-archive-option-runtime-evidence.md`](qt6-archive-option-runtime-evidence.md)。

## 重现

scan/nested matrix 使用
`tools/upstream/compare_cli_oracles.py`，参数与输出矩阵相同，另传：

```text
--nested-corpus-dir <nested-fixture>
--matrix-kind scan
--matrix-sample empty.bin
--matrix-sample minimal.exe
--matrix-sample minimal.pdf
--matrix-sample payload.zip
--matrix-sample plain.txt
```

聚焦诊断：

```text
python tools/upstream/probe_qt6_alltypes_diagnostics.py \
  --fixture-dir <baseline-corpus> \
  --repetitions 3 \
  --output <alltypes-report.json>
```

通用比较器因原始差异返回非零；聚焦探针在精确 JSON、diagnostics 和 stderr
断言全部成立时返回零。68 行生成器还会独立解码并校验每份 base64 原始流，
拒绝 stdout、detection tree、相对 option effect、差异集合或规范化诊断漂移。
