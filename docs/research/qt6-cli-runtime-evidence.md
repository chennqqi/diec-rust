# Linux Qt6 CLI 输出与分派运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Qt5 CMake 与 Qt6 CMake oracle 在以下可观察语义上相同：

- 26 个安全、项目生成格式样本的退出码、stdout 和 JSON detection tree；
- 5 个代表样本 × 默认文本、plain、JSON、XML、CSV、TSV、全部格式开关，
  共 35 组普通 formatter 的退出码和 stdout；
- escaping 与 nested 各 5 种无颜色 formatter 的退出码和 stdout；
- 普通 formatter 的全部派生 escaping、排序、层级和格式优先级事实。

唯一差异是 PE 输入触发 Qt6 stderr：

```text
Unimplemented code.
Unimplemented code.
Unimplemented code.
Unimplemented code.
```

这 80 bytes 的 SHA-256 为
`b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`；
Qt5 stderr 为空。差异不影响退出码、stdout 或 detection tree，但它仍是
可观察平台差异，不能被规范化静默删除。

## 固定身份

- 上游 commit：
  `74eaf505c250ab47e709024e9dc41657cd8f2254`
- Qt5 image：
  `diec-rust/upstream-oracle-cmake:74eaf505`
- Qt5 image ID：
  `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
- Qt6 image：
  `diec-rust/upstream-oracle-cmake-qt6:74eaf505`
- Qt6 image ID：
  `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`
- 两侧 binary：
  `/opt/die-build/src/console/diec`

机器证据：

- [`data/cli-output-matrix-linux-qt5-qt6.json`](data/cli-output-matrix-linux-qt5-qt6.json)
  保存 26 样本及五样本输出矩阵的身份、参数、退出码和流哈希；
- [`data/cli-output-boundaries-linux-qt5-qt6.json`](data/cli-output-boundaries-linux-qt5-qt6.json)
  额外保存 escaping/nested 十个用例的完整 base64 原始流和派生事实；
- [`data/qt6-capability-closure-plan.json`](data/qt6-capability-closure-plan.json)
  对上述报告做 SHA-256 绑定并执行逐能力晋级断言。

## Fixture

所有输入均由项目生成器重新产生，不包含第三方或恶意样本：

- baseline corpus：26 个样本，manifest SHA-256
  `f5adabeedeaf3bb69b8e52f8de20efd0f0b87bd4dcd247610d4e876b9266f329`
- output-boundary fixture manifest SHA-256
  `eae1cedd3ed4bd2ec6ac0b376851d990e2aee71e9c0f22612ef08fbc336c71d8`
- nested fixture manifest SHA-256
  `b382bd0a903cd4dda5a8128508f7a3f514a67a721baacda4c6722c99aefc4229`

对应生成器分别为：

- `tools/corpus/generate_baseline_corpus.py`
- `tools/corpus/generate_output_boundary_fixture.py`
- `tools/corpus/generate_nested_corpus.py`

fixture 目录和大型原始运行输出位于未跟踪的外部临时目录，不提交仓库。

## 能力影响

本次证据将以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-CLI-OUT-001/003/004/005`
- `CAP-DISPATCH-001`
- `CAP-DISPATCH-005`
- `CAP-DISPATCH-007`
- `CAP-NEST-008`

`CAP-DISPATCH-004` 仍是 partial：baseline 虽覆盖 APK、IPA、JAR、ZIP、RAR、
ISO9660、TAR 和 gzip，但尚不能替代 NPM、generic Archive 以及各 archive
adapter 的完整正反边界 harness。

本切片使完整 Qt6 能力从 11 增至 19，仍有 10 项 partial、39 项 missing；
`CAP-GAP-007` 保持开放。

## 重现

先分别运行三个 fixture generator，再执行：

```text
python tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --left-binary /opt/die-build/src/console/diec \
  --right-image diec-rust/upstream-oracle-cmake-qt6:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --corpus-dir <baseline-corpus> \
  --matrix-kind output \
  --matrix-sample empty.bin \
  --matrix-sample minimal.exe \
  --matrix-sample minimal.pdf \
  --matrix-sample payload.zip \
  --matrix-sample plain.txt \
  --output <matrix-report.json>
```

输出边界报告使用
`tools/upstream/probe_cli_output_boundaries.py`，左右 image/binary/revision
参数相同，并额外传入 output-boundary 与 nested fixture 目录。

两个原始比较器都会因保留的 Qt6 stderr 差异返回非零；这不是运行失败。
`tools/research/build_qt6_closure_plan.py` 只接受上述精确差异集合和精确 warning
哈希，任何 stdout、退出码、detection tree、样本集合或 formatter 集合变化都会
拒绝生成。
