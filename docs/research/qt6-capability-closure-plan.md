# Linux Qt6 能力闭环计划

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-29

## 结论

`CAP-GAP-007` 尚未关闭。现有固定 Qt6 oracle 与多组差分报告已经提供
有价值的运行时证据，但不能从抽样结果推导出 68 项能力全部兼容。机器清单
[`data/qt6-capability-closure-plan.json`](data/qt6-capability-closure-plan.json)
逐项列出当前证据和缺失实验：

- 63 项已有证据完整覆盖能力行；
- 2 项只有部分证据；
- 3 项没有可接纳的逐行 Qt6 运行时证据；
- 因此仍有 5 项需要执行闭环实验。

Linux Qt6 在能力覆盖报告中继续保持 `platform_missing`。本计划只负责把
缺口变成可执行清单，不改变平台门禁状态。

## 已接纳证据的边界

现有 CLI 对比固定了 8 个控制用例、扩展后的 26 个项目生成样本、4 个
不可读输入用例、5 样本 × 7 普通输出组合和 10 个 escaping/nested
formatter 边界。它足以直接证明单文件扫描、help/version/showstructs、
五种普通无颜色 formatter、三个数据库路径与 showdatabase，
PE/ELF/Mach-O、DEX/Class/PYC、PDF/CFBF、JPEG/PNG/generic Image 和
Binary fallback，以及 nested JSON 结果树。新增运行证据详见
[`qt6-cli-runtime-evidence.md`](qt6-cli-runtime-evidence.md)。

第二批 scan/nested 矩阵进一步完整覆盖 recursive、deep、heuristic、
aggressive、alltypes、format、hideunknown，以及 resource/overlay gate；
见
[`qt6-scan-nested-runtime-evidence.md`](qt6-scan-nested-runtime-evidence.md)。
其中 alltypes 的 detection JSON 相同，但 Qt6 在 JSON 后追加地址相关 MSDOS
TypeError。该差异已完整保存和分类，不代表 Qt5/Qt6 原始 stdout 相同。

第三批 special-mode 证据覆盖五样本 formatter/priority 矩阵和完整 28-case
精确边界；entropy、info 和 struct 三行均可提升为完整证据。见
[`qt6-special-runtime-evidence.md`](qt6-special-runtime-evidence.md)。

第四批基础 path matrix 完整覆盖多目标、单文件/空目录和
directory-vs-internal recursion；目录枚举的复杂文件系统边界仍是 partial。
见 [`qt6-path-runtime-evidence.md`](qt6-path-runtime-evidence.md)。

第五批 database matrix 与 raw-first diagnostics 完整覆盖 messages、空数据库
Unknown fallback 和脚本错误收集；database cache 仍需 engine harness。见
[`qt6-database-runtime-evidence.md`](qt6-database-runtime-evidence.md)。

第六批 option/profiling 证据完整覆盖 verbose、profiling、test、createtest
和 292-rule script profiling order。见
[`qt6-option-profiling-runtime-evidence.md`](qt6-option-profiling-runtime-evidence.md)。

第七批 engine-contract harness 在相同 37-case fixture 上完整覆盖四个公共
扫描入口、device/subdevice I/O、signature-name filter、取消与 record 排序，
其 23 条确定性关系与 Qt5 完全一致。见
[`qt6-engine-contract-runtime-evidence.md`](qt6-engine-contract-runtime-evidence.md)。

第八批 rule-orchestration 差分完整覆盖三层数据库、priority、global/type init、
file-type gate 和 deep/heuristic 独立 gate；10 个 canonical case 与 Qt5 完全
一致。见
[`qt6-rule-orchestration-runtime-evidence.md`](qt6-rule-orchestration-runtime-evidence.md)。

第九批五组 result-model harness 完整覆盖 scalar、四类列表、flags、IDs、
enums 和 record metadata；时间、UUID、parse diagnostic 三类差异均逐字段保留
并分类。见
[`qt6-result-model-runtime-evidence.md`](qt6-result-model-runtime-evidence.md)。

第十批 private signature-path harness 覆盖七个 exact/empty/missing/case/`..`/
basename 边界，完整输出与 Qt5 逐字节相同。见
[`qt6-signature-path-runtime-evidence.md`](qt6-signature-path-runtime-evidence.md)。

第十一批 paired debug-dispatch harness 证明 public scanner 继续忽略
debug-data child，而 direct debug 正控制仍可检测；JSON 与 Qt5 相同，Qt6
精确四行 PE warning 被保留。见
[`qt6-debug-dispatch-runtime-evidence.md`](qt6-debug-dispatch-runtime-evidence.md)。

第十二批 resource-context raw-first probe 完整保存四种 recursive/aggressive
组合；Qt6 的完整 stdout、exit code 和 detection tree 均与 Qt5 相同，
并保留每次调用的精确四行 PE warning。见
[`qt6-resource-context-runtime-evidence.md`](qt6-resource-context-runtime-evidence.md)。

第十三批 archive-option paired matrix 完整执行 64 个 engine case 和 32 个
release control；显式 archive option 的可达性、跨层传播及无 archive
CLI 等价关系均与 Qt5 相同。见
[`qt6-archive-option-runtime-evidence.md`](qt6-archive-option-runtime-evidence.md)。

第十四批 count-boundary 证据执行 archive 99999/100000/100001 三点和
resource 21/2001 精确计数。resource 结果与 Qt5 相同；archive 因 Qt5/Qt6
对单 NUL `QByteArray` 的 `QString::fromLatin1` 语义不同，Qt6 多保留一个
ISO dot-entry Stream，使最后可达 PDF ordinal 从 100000 变为 99999。源码
revision 相同，direct Qt probe 已固定根因。见
[`qt6-count-boundary-runtime-evidence.md`](qt6-count-boundary-runtime-evidence.md)。

下列结果只能算部分证据：

- archive 只覆盖 TAR、gzip 和 ZIP，未覆盖完整 archive family；
- 目录枚举只覆盖基础目录，未覆盖复杂 filesystem/locale/TOCTOU/large
  directory 边界。

此外，DOS/COM/BW dispatch、Amiga/Atari dispatch 和独立 depth/total
extraction limit 仍没有可接纳的逐行 Qt6 运行时证据。

这些边界由生成器中的显式 allow catalog 约束；未列入的能力默认是
`missing`，不会因共享 evidence set 而自动晋级。

## 已知差异

现有证据不得在规范化时隐藏以下差异：

- `minimal.exe` 的检测树和退出码相同，但 Qt6 stderr 多出四条
  `Unimplemented code.`；
- global HostApi 报告有 49 处差异；
- HostApi arity 报告有 45 处差异；
- global typo 的规范化检测相同，但诊断文本不同。
- ISO9660 三点边界的源码 revision 相同，但 Qt6 保留单 NUL dot entry，
  因而多一个 Stream 并把最后可达 PDF ordinal 从 100000 改为 99999。

规则运行时差异需要单独判断哪些属于 Qt5/Qt6 上游平台事实，哪些会成为
Rust 兼容目标；在评审完成前不能简单忽略。

## 闭环方法

机器清单按现有 14 个 evidence set 复用 Qt5 的受控 fixture，并为 Qt6
指定对应 CLI 或 engine harness。每个未完成能力都必须：

1. 在完全相同的固定上游 commit、规则 commit 和输入哈希上运行 Qt5/Qt6；
2. 同时保留原始 stdout/stderr/engine records 与规范化语义结果；
3. 执行能力矩阵中已固定的全部边界及正反对照；
4. 对每个差异给出明确分类，不允许通过规范化静默消除；
5. 更新逐行清单后，才允许修改 Linux Qt6 的平台覆盖状态。

生成命令：

```text
python tools/research/build_qt6_closure_plan.py
```

清单对 traceability 和全部接纳报告做 SHA-256 绑定，并拒绝重复 JSON
键、commit 漂移、能力数量变化和 evidence-set catalog 漂移。

## 限制与下一步

首组 Qt6 engine harness、规则编排、result-model、signature-path、
debug-dispatch、resource-context、archive-option 和 count-boundary probe
已完成。后续应按机器清单继续复用既有 Qt5 fixture，集中关闭 DOS/COM/BW、
Amiga/Atari、完整 archive family dispatch、独立 depth/total extraction
limit 和复杂目录边界。
只有 68 行全部达到 `evidence_complete`，且差异完成评审，
`CAP-GAP-007` 才能关闭。
