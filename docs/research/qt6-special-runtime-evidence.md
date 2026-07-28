# Linux Qt6 Special Modes 运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Qt5/Qt6 CMake oracle 在全部已定义 CLI special-mode 边界上相同：

- 5 个代表样本 × 19 个 entropy/info/struct formatter 与 priority vectors，
  共 95 个成对用例；
- 28 个精确边界用例，包括 6.5 entropy 浮点临界值、multi-target framing、
  struct filter、空/未知/超深路径和 11 个 PE/ELF/Mach-O/DEX 专用方法。

95 个 special vectors 的退出码、stdout 和 stderr 均逐字节相同。通用报告
仍包含 26 个普通 corpus 扫描，其中只有 PE32/PE64 的两次已知 Qt6 stderr
warning；它们不来自 special-mode 路径。

28-case 探针在发现任何原始差异时会直接失败。本次两侧全部相同，并在未跟踪
外部目录先保存 112 个 stdout/stderr 文件，即
`2 oracles × 28 cases × 2 streams`。

## 覆盖边界

Entropy：

- below/exact/above 理论值分别为 6.484375、6.5、6.515625；
- runtime total 在 exact 样本上略小于 6.5，因此状态仍为 `not packed`；
- JSON/XML/CSV/TSV/formatted text、全部 formatter 开关和 multi-target JSON
  framing 均成对执行。

Info：

- 五样本全部 formatter；
- multi-target JSON framing；
- 与 struct 同时出现时 struct 优先。

Struct：

- `Hash`、`Hash#MD5`、未知方法、空值、大小写和 trailing segments；
- PE 的 Entry point、DOS/NT/section/resource/export；
- ELF 的 Entry point、`Elf_Ehdr`；
- Mach-O 的 Entry point、Header；
- DEX 的 Header；
- entropy 与 struct 同时出现时 entropy 优先。

## 固定身份与机器证据

- 上游：
  `74eaf505c250ab47e709024e9dc41657cd8f2254`
- Qt5 image ID：
  `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
- Qt6 image ID：
  `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`
- special fixture manifest SHA-256：
  `7238e38a4c06bde6e2af8ff38016a4f2207aad1fd51fb268ee68368840d99874`
- baseline manifest SHA-256：
  `f5adabeedeaf3bb69b8e52f8de20efd0f0b87bd4dcd247610d4e876b9266f329`

报告：

- [`data/cli-special-matrix-linux-qt5-qt6.json`](data/cli-special-matrix-linux-qt5-qt6.json)
- [`data/cli-special-boundaries-linux-qt5-qt6.json`](data/cli-special-boundaries-linux-qt5-qt6.json)

薄编排器
`tools/upstream/probe_qt6_cli_special_boundaries.py` 不复制 case 或关系逻辑；
它加载并固定
`tools/upstream/probe_cli_special_boundaries.py` 的哈希，只替换为 Qt5 CMake
与 Qt6 CMake oracle，然后调用原探针。原 Qt5 报告和原生成器哈希不变。

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-CLI-MODE-001` entropy
- `CAP-CLI-MODE-002` info
- `CAP-CLI-MODE-003` struct

本切片当时使汇总达到 31 项 complete。后续基础 path 证据见
[`qt6-path-runtime-evidence.md`](qt6-path-runtime-evidence.md)；
当前计数以
[`qt6-capability-closure-plan.md`](qt6-capability-closure-plan.md)
为准。`CAP-GAP-007` 保持开放。

## 重现

五样本矩阵使用 `tools/upstream/compare_cli_oracles.py`，传入固定左右
image/binary、baseline corpus、五个 `--matrix-sample`，并设置：

```text
--matrix-kind special
```

精确边界先运行 fixture generator，再运行：

```text
python tools/upstream/probe_qt6_cli_special_boundaries.py \
  --fixture-dir <special-fixture> \
  --raw-dir <untracked-raw-directory> \
  --output <special-boundary-report.json>
```

后续
[`cross-platform-special-matrix-extension.md`](cross-platform-special-matrix-extension.md)
把首轮未包含的 21 个 baseline 样本接入相同 19-case 矩阵。新增 399 对
Qt5/Qt6 raw observations 全部逐字节相同，且 231 个 JSON/XML projection 在
Qt5/Qt6 之间相同；因此 Linux Qt5/Qt6 special baseline 现覆盖全部 26 个样本。

机器清单生成器独立要求：五样本 × 19 case catalog 完整且无 special
differences；28-case catalog 完整、两侧全相同、关系断言和固定源码审计全部
通过。任一 case、oracle、source hash 或关系漂移都会拒绝能力晋级。
