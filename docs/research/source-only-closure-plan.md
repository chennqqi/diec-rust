# Linux Qt5 source-only 能力关闭计划

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 目的与结论

[`capability-coverage.json`](data/capability-coverage.json) 当前仍有 1 个
Linux Qt5 source-only 能力。本文不把源码证据提升为 runtime compatibility，
而是为每项固定缺失证据、最小 fixture、oracle/harness、强断言和关闭方式。

机器清单为
[`data/source-only-closure.json`](data/source-only-closure.json)，由
[`build_source_only_closure.py`](../../tools/research/build_source_only_closure.py)
生成。生成器要求清单 ID 与 coverage report 的 source-only 闭集完全相等；
新增、提升或删除能力而未同步计划会显式失败。

## 2. 当前一项

| 能力 | 关闭类型 | 关键缺口 |
| --- | --- | --- |
| `CAP-NEST-009` | bounded escalation + ADR | 缺深度/总展开量递增实验和 Rust 有界偏离决策 |

`CAP-RULE-007` 已由
[`signature-path-filter-behavior.md`](signature-path-filter-behavior.md) 关闭：
private harness 链接未修改的固定 engine object，以 main/extra 两层同名规则
证明非空 filter 严格匹配保存的绝对路径，区分大小写、不清理 `..`，也不接受
basename-only 输入；同时源码证据继续固定公共 `_processDetect()` 只能传空路径。

`CAP-NEST-007` 已由
[`debug-data-dispatch-behavior.md`](debug-data-dispatch-behavior.md) 关闭：
同一 PE 的 Formats 枚举同时产生 Manifest resource 与 RSDS debug-data part；
public recursive+aggressive 只为 resource 建 child，direct debug context 则被
原样规则识别为 PDB link，从而形成同输入正负控制。

## 3. 关闭原则

### 负向能力

“公共入口不可达”“scanner 不分派”“没有独立上限”不能仅靠一次未观察到行为来
证明：

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

`CAP-DISPATCH-002` 已由七个公共成员的
[`dos-dispatch-corpus.json`](data/dos-dispatch-corpus.json) 和
[`generate_dos_dispatch_corpus.py`](../../tools/corpus/generate_dos_dispatch_corpus.py)
固定为 19 个正例/控制；
[`probe_dos_dispatch.py`](../../tools/upstream/probe_dos_dispatch.py) 已实现双
Qt5 oracle、manifest 身份、present/absent filetype 和 raw stream 门禁，并
形成通过的
[`dos-dispatch-linux-qt5.json`](data/dos-dispatch-linux-qt5.json)。BW 路径的
[`probe_bw_dispatch_harness.py`](../../tools/upstream/probe_bw_dispatch_harness.py)
形成
[`bw-dispatch-engine-qt5.json`](data/bw-dispatch-engine-qt5.json)：
automatic 不产生 BW，compact `BWDOS16M` property 可强制到达 branch，并产生
唯一 BW Unknown record。两份报告共同关闭 source-only 状态。

`CAP-DISPATCH-003` 已由
[`legacy-dispatch-corpus.json`](data/legacy-dispatch-corpus.json) 对应的 8-case
生成器和
[`legacy-dispatch-linux-qt5.json`](data/legacy-dispatch-linux-qt5.json)
关闭 source-only 状态。首次实验纠正了两个假设：Atari `HEADER` 的字段共
28 bytes，但固定 Linux ABI 的 `sizeof` 为 32；且 detector 虽返回
`Atari ST`，`scanProcess` 没有 `FT_ATARIST` 分支并回退 Binary。最终 probe
对两套 oracle 同时执行 info detector 与 normal scan：Amiga 两侧均命中，
Atari 两侧均形成 `Atari ST → Binary` 成对结果，六个边界控制均保持 Binary。

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

`CAP-RESULT-003` 已由
[`result-flags-engine-qt5.json`](data/result-flags-engine-qt5.json)
关闭 source-only 状态。normal、`~format`、`!format` 和空数据库 fallback
分别形成三 flag 全 false、普通 heuristic、advanced heuristic 和 Unknown
四行真值表；harness 同时导出原始 type 与 bool，但不从显示文本推导 flag。

`CAP-RESULT-004` 已由
[`result-ids-engine-qt5.json`](data/result-ids-engine-qt5.json)
关闭 source-only 状态。PE root 与 resource child 的 id/parentId 均导出八个
字段；child parent 用 root UUID 建边，但 filePart/offset/size 保存 Resource
edge，因此不能用完整结构相等寻找父节点。随机 UUID 只断言非空、不同和引用
关系，不硬编码具体值。

`CAP-RESULT-005` 已由
[`result-enums-engine-qt5.json`](data/result-enums-engine-qt5.json)
关闭 source-only 状态。固定 harness 在同一 record 中同时导出原始 type/name、
数值 enum 和规范字符串，覆盖已知别名、heuristic 前缀、自定义原文与真实
Unknown fallback；另以直接映射固定大小写/空格/连字符行为、十个数值互异但
同名的 `_Unknown` 保留槽位，以及未知输入和越界 enum 的 `Unknown` 投影。

## 4. 可重复生成与验证

```text
python tools/research/build_source_only_closure.py
python tools/tests/test_source_only_closure.py
python tools/corpus/generate_signature_path_fixture.py <fixture-dir>
python tools/upstream/probe_signature_path_harness.py \
  --fixture-dir <fixture-dir> \
  --committed-manifest docs/research/data/signature-path-fixture.json \
  --raw-dir <raw-dir> \
  --output docs/research/data/signature-path-engine-qt5.json
python tools/corpus/generate_debug_dispatch_fixture.py <fixture-dir>
python tools/upstream/probe_debug_dispatch_harness.py \
  --fixture-dir <fixture-dir> \
  --committed-manifest docs/research/data/debug-dispatch-fixture.json \
  --raw-dir <raw-dir> \
  --output docs/research/data/debug-dispatch-engine-qt5.json
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
python tools/corpus/generate_result_flag_fixture.py <fixture-dir>
python tools/upstream/probe_result_flags_harness.py \
  --fixture-dir <fixture-dir> --raw-dir <raw-dir> \
  --output docs/research/data/result-flags-engine-qt5.json
python tools/upstream/probe_result_ids_harness.py \
  --corpus-dir <nested-corpus-dir> --raw-dir <raw-dir> \
  --output docs/research/data/result-ids-engine-qt5.json
python tools/corpus/generate_result_enum_fixture.py <fixture-dir>
python tools/upstream/probe_result_enums_harness.py \
  --fixture-dir <fixture-dir> --raw-dir <raw-dir> \
  --output docs/research/data/result-enums-engine-qt5.json
```

测试要求：

- committed manifest 与生成结果逐字节一致；
- 一个 ID 与当前 source-only 行完全相等；
- 每项都有非空缺失证据、fixture、harness 和至少三个强断言；
- 剩余负向能力保持 ADR 关闭路径；
- catalog 漂移和重复 JSON key 显式失败。

## 5. 对 Phase 0 的影响

该清单使 `P0-BLOCK-005` 的 Linux source-only 部分具备逐项执行入口。
`CAP-RULE-007`、`CAP-NEST-007` 与 `CAP-RESULT-001` 至 `CAP-RESULT-005`
已经完成实验、原始流哈希绑定和 traceability 提升；最后一项只有在对应实验
实际通过、原始证据落盘并更新 traceability 后，才能消除 source-only 计数。
