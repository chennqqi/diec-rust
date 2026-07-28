# Linux Qt6 Database 与脚本诊断运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Qt5/Qt6 CMake oracle 已执行 18 个 database CLI 用例，覆盖：

- missing、empty、invalid archive、malformed、throwing、valid main database；
- showdatabase 与 scan；
- `--messages` 对 database load error 的 stdout channel；
- entropy/info 与 messages 的 structured framing；
- valid main 加 missing extra/custom；
- parse error 与 runtime error。

17 个用例的退出码、stdout 和 stderr 逐字节相同。唯一差异是
`scan_malformed_main_json`：两侧 detection JSON 相同、exit 0、stderr 为空，
但 JSON 后的 parse diagnostic 取决于 Qt JavaScript runtime：

```text
Qt5: broken.1.sg: Binary/broken.1.sg: 1: SyntaxError: Parse error
Qt6: broken.1.sg: Binary/broken.1.sg: 2: SyntaxError: Expected token `}'
```

runtime throw 两侧完全相同：

```text
throw.1.sg: Binary/throw.1.sg: 2: Error: database fixture
```

聚焦探针对 malformed/runtime 两类各重复 2 次，先保存完整 base64
stdout/stderr，再分离 JSON document 与 trailing diagnostics。每个 oracle
内部原始输出稳定，两侧 JSON document 相同。

## Messages 与 framing

missing main 的 `--messages` 在两侧都把 `Cannot load database:` 写入 stdout：

- normal scan JSON 不再是单一合法 JSON document；
- entropy/info structured 输出同样被消息污染；
- showdatabase 的退出码与 load-error 标记相同。

invalid database archive 在所测 CLI 路径上没有产生同一 load-error message；
该上游差异也保持一致，不能由 Rust 层按“更合理”行为统一。

空的有效 main/extra/custom database 在两侧产生完全相同的唯一 Unknown
fallback，stdout SHA-256 为
`83cbe006c9b24c93260312b75a213904e76b75b7fcdb17612c6640f37a20c78c`。

## 固定证据

- matrix：
  [`data/cli-database-matrix-linux-qt5-qt6.json`](data/cli-database-matrix-linux-qt5-qt6.json)
- raw-first diagnostics：
  [`data/qt6-database-diagnostics.json`](data/qt6-database-diagnostics.json)
- focused probe：`tools/upstream/probe_qt6_database_diagnostics.py`
- fixture generator：`tools/corpus/generate_database_fixture.py`
- fixture manifest SHA-256：
  `90b6ce18e5656fa30c2dfd55573df4612825a74e77cb9e2f4fc1baa81fd7223c`

Oracle identity：

- Qt5 image ID：
  `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
- Qt6 image ID：
  `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-CLI-OPT-009` messages；
- `CAP-RULE-008` empty-database Unknown fallback；
- `CAP-RULE-010` script error collection。

“完整证据”不表示 Qt5/Qt6 parse diagnostic 文本相同；它表示完整边界已执行，
差异已 raw-first 保存并精确分类。

以下内容仍未由本轮证明：

- main/extra/custom 三层 append 与 priority ordering；
- global/type init masking；
- database archive cache、reload 和 stale state；
- engine-level error/list ownership。

本切片当时使汇总达到 37 项 complete。后续 option/profiling 证据见
[`qt6-option-profiling-runtime-evidence.md`](qt6-option-profiling-runtime-evidence.md)；
当前计数以
[`qt6-capability-closure-plan.md`](qt6-capability-closure-plan.md)
为准。`CAP-GAP-007` 保持开放。

## 重现

先运行：

```text
python tools/corpus/generate_database_fixture.py <database-fixture>
```

通用 matrix 使用 `tools/upstream/compare_cli_oracles.py`，传入固定左右
image/binary/revision 和：

```text
--database-fixture-dir <database-fixture>
--output <database-report.json>
```

聚焦诊断：

```text
python tools/upstream/probe_qt6_database_diagnostics.py \
  --fixture-dir <database-fixture> \
  --repetitions 2 \
  --output <diagnostic-report.json>
```

68 行清单生成器独立要求 18-case catalog、唯一 failure path、load-error 标记、
framing、空数据库 stdout hash 和 fixture layout 精确；同时重新解码聚焦报告
的每份原始流，校验哈希、JSON equality、exit/stderr 和两套固定 diagnostics。
