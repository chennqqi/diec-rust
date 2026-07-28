# Linux Qt6 基础 Path 运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Qt5/Qt6 CMake oracle 已执行 14 个基础 path 用例：

- 单文件；
- 两个文件与参数顺序；
- 重复文件；
- depth-first 目录树；
- 目录树加 `--recursivescan`；
- 目录的 JSON/XML/CSV/plain text；
- 目录 entropy/info；
- 只含一个文件的目录；
- 空目录；
- 缺失 target 后跟有效 target；
- 目录后再显式传入目录中的重复文件。

两侧的退出码、stdout、filename prefixes、JSON/XML framing 有效性和
`--recursivescan` 相对效果均相同。6 个原始差异均仅为目录包含 PE32 时的
Qt6 四行 `Unimplemented code.` stderr：

- tree JSON、recursive JSON、XML、CSV、plain text；
- directory + duplicate JSON。

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-CLI-IN-002` 多目标扫描；
- `CAP-CLI-IN-004` 单文件目录与空目录；
- `CAP-NEST-001` 目录遍历与文件内部 recursive 的区别。

`CAP-CLI-IN-003` 由 missing 提升为 partial。基础 depth-first 树已执行，但
该能力在 Linux Qt5 上还固定了 symlink/alias、权限、4096 项目录、TOCTOU、
locale、非 UTF-8 与不同 volume 的大小写 tie；这些 Qt6 边界尚未执行，不能
由本轮小型目录树外推。

本切片当时使汇总达到 34 项 complete。后续 database 证据见
[`qt6-database-runtime-evidence.md`](qt6-database-runtime-evidence.md)；
当前计数以
[`qt6-capability-closure-plan.md`](qt6-capability-closure-plan.md)
为准。`CAP-GAP-007` 保持开放。

## 固定证据

- report：
  [`data/cli-path-matrix-linux-qt5-qt6.json`](data/cli-path-matrix-linux-qt5-qt6.json)
- fixture generator：`tools/corpus/generate_path_corpus.py`
- baseline generator：`tools/corpus/generate_baseline_corpus.py`
- path fixture manifest SHA-256：
  `edfd3cc6fb07a7e45e9541413f0f4a769f0db57ef34e608cabe94c4845c86609`
- baseline manifest SHA-256：
  `f5adabeedeaf3bb69b8e52f8de20efd0f0b87bd4dcd247610d4e876b9266f329`

Oracle identity 与前三批相同：

- Qt5 image ID：
  `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
- Qt6 image ID：
  `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`

## 重现

先生成 baseline corpus，再以其作为输入生成 path fixture：

```text
python tools/corpus/generate_path_corpus.py \
  <baseline-corpus> <path-fixture>
```

随后执行 `tools/upstream/compare_cli_oracles.py`，传入固定左右
image/binary/revision 和：

```text
--path-corpus-dir <path-fixture>
--output <path-report.json>
```

通用比较器会因保留的 PE stderr 返回非零。68 行清单生成器独立要求：
14-case catalog 精确、stdout/exit 相同、仅允许精确 warning 哈希、filename
prefixes 相同、structured framing 有效性相同、recursive 相对变化相同，并
拒绝 fixture layout 或 failure catalog 漂移。
