# Windows Qt5 CLI verbose、profiling 与测试入口行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-29

## 1. 目的

本实验在固定原生 Windows Qt5 发布 CLI 上执行 Linux
[`cli-option-behavior.md`](cli-option-behavior.md) 定义的 option/test
边界，并补充完整 Binary profiling announcement order，覆盖：

- verbose 对结构化结果的影响；
- profiling 在无 messages 和有 messages 时的 channel 行为；
- `--test` 对存在/不存在 directory 的 no-op；
- `--createtest` 完整参数和缺少 positional arguments；
- 292 条 Binary 规则的完整 Windows 执行顺序。

机器报告为
[`data/windows-qt5-cli-option-behavior.json`](data/windows-qt5-cli-option-behavior.json)，
SHA-256 为
`538b58ed461eb174dc73d9a621110b23f6b0b6b1e6f2e7d6acf4cf62df7b6f1c`。

## 2. 输入与身份

采集器
[`collect_windows_cli_option_behavior.py`](../../tools/upstream/collect_windows_cli_option_behavior.py)
拒绝非 Windows 主机，并验证：

- DIE-engine、58 个递归 submodule 和规则 commit；
- tracked-clean source 与固定 Windows CLI SHA-256
  `e8579a6e...ac635e`；
- Qt 5.15.2 qmake、Qt5Core 和 Qt5Script 身份；
- 项目生成的 `minimal.elf`（64 bytes，
  `e717b57a...2e704`）；
- 项目生成的 `ps3-type-1-elf.self`（512 bytes，
  `201eaef0...7c4ed`）；
- Linux option、292-rule order 和 Binary lifecycle 报告的完整 SHA-256。

未导入或提交外部样本。九个确定性 option case 和一个 profiling-order case
各运行两轮，共 20 次 Windows 进程执行。另运行三个固定 Linux Qt5 qmake
same-sample controls；它们只用于跨平台关系比较，不计入 Windows execution
总数。

## 3. 确定性 option case

九个 case 的 exit code、raw stdout 和 raw stderr 在两轮间逐字节相同，
stderr 均为空。文本规范化只执行 CRLF→LF，并替换已验证的实际
fixture/database path；不改写诊断、JSON、record 或 exit code。

### 3.1 `--test`

存在的 working directory 和保证不存在的 directory 都：

- 先成功加载固定 database；
- exit `0`；
- stdout/stderr 为空；
- 不读取或验证 directory 内容。

这与 Linux Qt5 的 no-op 关系相同。

### 3.2 `--createtest`

缺少 detect string 和 directory 时：

- exit `4`；
- stdout 仍为旧名称诊断
  `Error: --addtest requires <filename> <detect_string> <directory>`；
- stderr 为空。

完整参数时 exit `0`，只打印 file/detect string/directory announcement，
没有创建或修改文件。路径标记替换后与 Linux 契约相同。

### 3.3 verbose

同一个项目生成 `minimal.elf` 在默认模式只有 fallback `Unknown`。verbose
模式删除该 fallback，并增加唯一 OS record：

```json
{
  "type": "operation system",
  "name": "Unix",
  "version": "",
  "info": "AMD64, 64-bit"
}
```

固定 Linux Qt5 qmake 对同一 64-byte 样本的 default/verbose 完整规范化
stdout 与 Windows 相同。因此“删除 Unknown”不是平台差异，而是 Unknown
只在没有真实 record 时收尾的结果。verbose 仍然证明它改变核心扫描结果，
不是表示层日志开关。

### 3.4 profiling 与 messages

`--profiling --json` 不带 `--messages` 时，Windows raw output 与默认 JSON
逐字节相同；同样本 Linux control 也满足该关系。

missing database 下，`--messages` 继续把
`Cannot load database: <missing-main>` 前置写入 stdout，不改变 exit `3`，
stderr 为空。它不是独立 stderr 日志 channel。

## 4. 292 条 profiling 顺序

`--profiling --messages --json --deepscan --heuristicscan` 使用项目生成
`ps3-type-1-elf.self`。两轮 raw stdout 都是 34,344 bytes，但 elapsed timing
不同，因此 SHA-256 分别为：

- `6c19f675f8db5548f6ab2470f312c8b5e877b66b810d1f70a7ad50c35b43a107`；
- `acdeedca27516bf2cb3eac18013a1938c903979a663e2b321bd933c9fd27c779`。

采集器不改写 elapsed。它只从 raw lines 精确提取 lifecycle manifest 中声明的
292 个唯一规则名。两轮 order SHA-256 都是
`ec4e8c020ec5d9eccec7fca869cab09c172c627f611a8e314fccb0e46b17c898`。

Windows 与 Linux Qt5 的规则集合相同，但顺序不完全相同：

- Linux 的 `image_ICNS.sg` 位于零基 index `248`；
- Windows 将它移到最后一个 index `291`；
- Windows 的其余 291 项恰好等于删除该项后的 Linux 相对顺序；
- 因单项移动，共有 index `248..291` 的 44 个位置不同。

该差异没有被规范化或 allowlist 为“相同”。报告把它分类为
`platform_difference_retained_as_defect`。它与上游 priority/filename
比较的非传递排序及不同平台目录枚举输入顺序一致，但本实验只把可观察的精确
单项移动作为 runtime 事实；Rust 若不复现 Windows 顺序，默认属于兼容缺陷，
除非后续 ADR 明确选择跨平台 canonical order。

## 5. 对 Windows closure 的影响

本报告为 verbose、profiling、test no-op、create-test no-op 和 script
profiling 五行提供直接 Windows runtime 证据。完整行为已执行、raw/结构化
证据已保留、唯一跨平台顺序差异已精确分类，因此五行可从 `missing` 提升为
`evidence_complete`。

这不表示 Windows 平台已经接纳。本实验自身不关闭其他能力；后续证据已关闭
rule orchestration、private filter、result model 和 legacy/archive dispatch，
当前仍开放 nested engine 五行与 path profile 一行。

## 6. 复现

```powershell
python tools\corpus\generate_baseline_corpus.py `
  <external-baseline-corpus>

python tools\corpus\generate_nintendo_certified_corpus.py `
  <external-nintendo-corpus>

python tools\upstream\collect_windows_cli_option_behavior.py `
  --binary <fixed-source>\build\release\diec.exe `
  --source-dir <tracked-clean-fixed-source> `
  --qt-dir <fixed-qt-5.15.2> `
  --baseline-corpus-dir <external-baseline-corpus> `
  --nintendo-corpus-dir <external-nintendo-corpus> `
  --working-dir <external-working-directory> `
  --raw-dir <external-raw-directory> `
  --output docs\research\data\windows-qt5-cli-option-behavior.json
```

raw streams 保存在未跟踪外部目录；提交报告只保存完整 option canonical text、
每轮 raw hash、完整 292-name order、输入/工具身份和关系断言。
