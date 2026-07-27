# Linux Qt5 source-only 能力关闭计划

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 1. 目的与结论

[`capability-coverage.json`](data/capability-coverage.json) 当前仍有 8 个
Linux Qt5 source-only 能力。本文不把源码证据提升为 runtime compatibility，
而是为每项固定缺失证据、最小 fixture、oracle/harness、强断言和关闭方式。

机器清单为
[`data/source-only-closure.json`](data/source-only-closure.json)，由
[`build_source_only_closure.py`](../../tools/research/build_source_only_closure.py)
生成。生成器要求清单 ID 与 coverage report 的 source-only 闭集完全相等；
新增、提升或删除能力而未同步计划会显式失败。

## 2. 当前八项

| 能力 | 关闭类型 | 关键缺口 |
| --- | --- | --- |
| `CAP-RULE-007` | scope review / private harness | 公共 API 不可传非空 signature path，private comparator 未运行 |
| `CAP-DISPATCH-002` | generated oracle + scope review | 七个公共 detector 成员缺 runtime；BW 只有不可自动到达的分支 |
| `CAP-DISPATCH-003` | generated format oracle | fixture/probe 已就绪；固定 Qt5 oracle 尚未执行 |
| `CAP-NEST-007` | paired negative nested oracle | 缺“直接可检测、递归不分派”的同输入正负控制 |
| `CAP-NEST-009` | bounded escalation + ADR | 缺深度/总展开量递增实验和 Rust 有界偏离决策 |
| `CAP-RESULT-003` | engine harness extension | unknown 有正反例，heuristic/advanced flags 只有 false |
| `CAP-RESULT-004` | nested result harness | record ID、parent ID 未导出 |
| `CAP-RESULT-005` | engine harness extension | 字符串 type/name 已见，数值 enum 未导出 |

## 3. 关闭原则

### 负向能力

“公共入口不可达”“scanner 不分派”“没有独立上限”不能仅靠一次未观察到行为来
证明：

- signature path 必须由 private harness 验证 comparator，或经 ADR 明确排除
  非公共能力；
- debug data 必须使用相同 PE 的直接 debug-context 正例、resource recursive
  正例和 debug recursive 负例；
- 无独立 depth/total limit 必须用单调递增语料记录 timeout、peak memory、
  partial result 和 cancellation，并用 ADR 固定 Rust 的有界策略。

### 组合格式

DOS/COM 和 Amiga/Atari 必须为每个矩阵成员提供项目生成、hash-bound 的正例，
同时提供截断、近似 magic 或错误端序控制。所有 case 在固定 qmake/CMake oracle
上保存原始 stdout/stderr、退出码、大小和 SHA-256。

固定源码审计
[`dos-dispatch-source-audit.json`](data/dos-dispatch-source-audit.json) 纠正了
DOS/COM 的原始关闭假设。`scanProcess()` 的活动 detector 是
`XFormats::getFileTypes`；它能自动产生 MSDOS、NE、LE、LX、DOS16M、DOS4G 和
COM，却没有 `FT_BWDOS16M` token。BW magic 只留在旧
`XBinary::getFileTypes`，而 scanner 仍保留 BW 分支，且 device 的外部
`filetypes` property 可以绕过 detector。因此七个公共成员走 CLI oracle；BW
必须由显式 property harness 验证，或经 scope review 排除，不能伪造为第八个
CLI 正例。

七个公共成员的
[`dos-dispatch-corpus.json`](data/dos-dispatch-corpus.json) 已由
[`generate_dos_dispatch_corpus.py`](../../tools/corpus/generate_dos_dispatch_corpus.py)
固定为 19 个正例/控制；
[`probe_dos_dispatch.py`](../../tools/upstream/probe_dos_dispatch.py) 已实现双
Qt5 oracle、manifest 身份、present/absent filetype 和 raw stream 门禁。Docker
daemon 不可用，因此 runtime report 仍待采集。BW 路径的
[`probe_bw_dispatch_harness.py`](../../tools/upstream/probe_bw_dispatch_harness.py)
也已实现 automatic/forced property 成对对照和 Unknown fallback 断言，但同样
尚未运行；若不保留该 engine-only 入口则仍需 scope review。

`CAP-DISPATCH-003` 已具备
[`legacy-dispatch-corpus.json`](data/legacy-dispatch-corpus.json) 对应的 8-case
生成器和 [`probe_legacy_dispatch.py`](../../tools/upstream/probe_legacy_dispatch.py)。
probe 要求临时生成的 manifest 与提交版本逐字节相同，并对两套 oracle 分别断言
正例命中精确 filetype、三类控制不命中 Amiga/Atari，同时把每次 stdout/stderr
写入外部 raw 目录。Docker daemon 当前不可用，因此尚无可提交的 runtime report，
能力仍保持 source-only。

### 结果模型

不能从 CLI JSON 反推 engine 内部字段。harness 必须在同一 record 中同时导出
原始 enum/flag/ID 与字符串投影，并分别覆盖空/非空、true/false、root/child、
success/error/debug/handler 状态。随机 ID 可断言关系和唯一性，不硬编码具体值。

`CAP-RESULT-001` 已由
[`result-metadata-engine-qt5.json`](data/result-metadata-engine-qt5.json)
关闭 source-only 状态。固定 harness 对同一 128-byte MSDOS 输入调用 file、
memory、device、subdevice 四个入口，同时导出 `nScanTime`、`sFileName`、
`nSize` 和数值/字符串 `ftInit`。四次扫描均成功且无错误；size 均为 128，
filetype 均为数值 9 / `MSDOS`；filename 分别为固定文件路径、空、显式设备名、
空。scan time 保留原始整数值（本次为 9/0/0/0 ms），只断言非负，不抹平其
非确定性。

`CAP-RESULT-002` 已由
[`result-lists-engine-qt5.json`](data/result-lists-engine-qt5.json)
关闭 source-only 状态。固定 harness 分别观察默认成功扫描与开启 profiling /
collection 的综合扫描；四个列表独立导出，并保留 2 个重复 detection、
runtime/parse 两条错误、四条规则的 debug 顺序，以及 2 个完全相同的 copy
handler。harness 不调用 `processRecords`，因此不会执行文件副作用。

## 4. 可重复生成与验证

```text
python tools/research/build_source_only_closure.py
python tools/tests/test_source_only_closure.py
python tools/corpus/generate_legacy_dispatch_corpus.py <corpus-dir>
python tools/upstream/probe_legacy_dispatch.py \
  --corpus-dir <corpus-dir> --raw-dir <raw-dir> --output <report.json>
python tools/corpus/generate_dos_dispatch_corpus.py <dos-corpus-dir>
python tools/upstream/probe_dos_dispatch.py \
  --corpus-dir <dos-corpus-dir> --raw-dir <raw-dir> --output <report.json>
python tools/upstream/probe_bw_dispatch_harness.py \
  --raw-dir <raw-dir> --output <bw-report.json>
python tools/upstream/probe_result_metadata_harness.py \
  --raw-dir <raw-dir> \
  --output docs/research/data/result-metadata-engine-qt5.json
python tools/corpus/generate_result_list_fixture.py <fixture-dir>
python tools/upstream/probe_result_lists_harness.py \
  --fixture-dir <fixture-dir> --raw-dir <raw-dir> \
  --output docs/research/data/result-lists-engine-qt5.json
```

测试要求：

- committed manifest 与生成结果逐字节一致；
- 八个 ID 与当前 source-only 行完全相等；
- 每项都有非空缺失证据、fixture、harness 和至少三个强断言；
- 三类负向能力保持 paired control、scope review 或 ADR 关闭路径；
- catalog 漂移和重复 JSON key 显式失败。

## 5. 对 Phase 0 的影响

该清单使 `P0-BLOCK-005` 的 Linux source-only 部分具备逐项执行入口。
`CAP-RESULT-001` 和 `CAP-RESULT-002` 已经完成实验、原始流哈希绑定和
traceability 提升；其余能力只有在对应实验实际通过、原始证据落盘并更新
traceability 后，才能继续减少 source-only 计数。
