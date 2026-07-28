# Linux Qt6 能力闭环计划

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

`CAP-GAP-007` 尚未关闭。现有固定 Qt6 oracle 与四组差分报告已经提供
有价值的运行时证据，但不能从抽样结果推导出 68 项能力全部兼容。机器清单
[`data/qt6-capability-closure-plan.json`](data/qt6-capability-closure-plan.json)
逐项列出当前证据和缺失实验：

- 28 项已有证据完整覆盖能力行；
- 13 项只有部分证据；
- 27 项没有可接纳的逐行 Qt6 运行时证据；
- 因此仍有 40 项需要执行闭环实验。

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

下列结果只能算部分证据：

- archive 只覆盖 TAR、gzip 和 ZIP，未覆盖完整 archive family；
- entropy/info 只覆盖不可读输入；
- CLI JSON 和脚本探针只暴露结果模型的一部分；
- typo、HostApi 与 arity 报告证明 Qt5/Qt6 诊断确有差异，但没有覆盖完整的
  `listErrors` 契约。

这些边界由生成器中的显式 allow catalog 约束；未列入的能力默认是
`missing`，不会因共享 evidence set 而自动晋级。

## 已知差异

现有证据不得在规范化时隐藏以下差异：

- `minimal.exe` 的检测树和退出码相同，但 Qt6 stderr 多出四条
  `Unimplemented code.`；
- global HostApi 报告有 49 处差异；
- HostApi arity 报告有 45 处差异；
- global typo 的规范化检测相同，但诊断文本不同。

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

清单对 traceability 和四份现有差分报告做 SHA-256 绑定，并拒绝重复 JSON
键、commit 漂移、能力数量变化和 evidence-set catalog 漂移。

## 限制与下一步

本切片没有重新执行 Qt6 容器，也没有补建 14 组 Qt6 harness。后续应按
机器清单优先复用 CLI 探针，随后批量建立 engine harness 的 Qt6 构建变体。
只有 68 行全部达到 `evidence_complete`，且差异完成评审，
`CAP-GAP-007` 才能关闭。
