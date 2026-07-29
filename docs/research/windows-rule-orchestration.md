# Windows Qt5 规则编排行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Components:
`XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`,
`die_script@5d82316c110abf0eb863b50bc679d330e05067b6`

Last updated: 2026-07-29

## 范围

本实验把 Linux Qt5
[`rule-orchestration.md`](rule-orchestration.md) 的完整十个 case 移植到固定
Windows x86_64 Qt5 qmake oracle，验证：

- main、extra、custom 三层 append 以及同名 init/include 的首层胜出；
- priority-only、相同 priority、字符串 priority、缺失/空 priority 段；
- 含 `_init` 时非传递比较器的实际 MSVC 顺序；
- default/deep/heuristic/combined 四模式的 `DS`、`EP`、`HEUR` gate；
- Binary 输入排除 PE decoy；
- 空数据库生成 Unknown。

fixture 完全由项目生成，输入为 35-byte ASCII 文本，规则仅调用
`_setResult()`；不包含上游规则字节或第三方样本。manifest SHA-256 为
`535d96510e1a807a07af752ed60b0239bdbb91331ce51b1f89d2be043d07f23e`。

## 固定身份

| 项目 | 身份 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Detect-It-Easy rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| Windows CLI | `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e` |
| Qt | 5.15.2, `win32-msvc` |
| Linux Qt5 reference | `6787b8a67ee9ee3692d38c668f392a85861d2f517b6827117b478d63df678a5e` |
| Windows report | `e6c7d47b35f89abdb10719e8578a550dcf5c9caf882a5d7825d3e0dbde3cf9da` |

采集器在执行前拒绝非固定 commit、非 58 个 clean recursive submodule、规则
commit 漂移、Qt DLL/qmake 哈希漂移、CLI 哈希漂移、fixture inventory/hash
漂移以及 Linux reference generator/hash/关系漂移。

## 方法

[`collect_windows_rule_orchestration.py`](../../tools/upstream/collect_windows_rule_orchestration.py)
复用 Linux 探针的参数生成、stdout parser 和逐 case validator。十个 case
各运行两次，共 20 次原生 Windows 进程执行：

| 组 | Case |
| --- | --- |
| Scan mode | `default`, `deep`, `heuristic`, `combined` |
| Priority | `priority_only`, `equal_priority`, `lexical_priority`, `missing_priority`, `empty_priority` |
| Fallback | `unknown` |

每次未改写的 stdout/stderr 保存在外部 `--raw-dir`，版本化报告只保存长度和
SHA-256。跨平台比较只提取：

- profiling 行中的完整规则 basename 和原始顺序；
- JSON 中每个 detection value 的 `type/name/version/info`。

没有删除或重排 rule/detection，没有改写 elapsed time、路径、大小写、版本或
字段值，也没有重写 raw hash。

## 结果

20/20 执行 exit `0`、stderr 为空；十个 case 的两轮 raw stdout 和结构化语义
都稳定。14/14 命名关系为 true，Windows 的十个 canonical case 与固定 Linux
Qt5 qmake/CMake reference 逐字段相同。

### 数据库层与 init/include

四个 scan mode 中 main 普通规则始终先于 extra，extra 先于 custom；后两层
priority `"0"` 不会越过 main 的 priority `"4"`。所有结果 version 都是：

```text
main-global:main-helper:main-type
```

因此 Windows 上同样由 main global init、main 同名 helper 和 main Binary
type init 胜出，extra/custom 的同名记录不覆盖它们。

### 排序

Windows 与 Linux Qt5 的五个排序 case 完全相同：

| Case | 顺序 |
| --- | --- |
| priority only | `z_priority.1.sg`, `a_priority.2.sg`, `m_priority.4.sg` |
| equal priority | `a_equal.2.sg`, `m_equal.2.sg`, `z_equal.2.sg` |
| lexical priority | `z_ten.10.sg`, `a_two.2.sg` |
| missing priority | `a_plain.sg`, `z_ranked.1.sg` |
| empty priority | `a_empty..sg`, `z_empty_ranked.1.sg` |

含真实 type `_init` 的 combined 顺序也是：

```text
DS.deep.2.sg
HEUR.heuristic.3.sg
EP.entrypoint.4.sg
z_normal.1.sg
a_extra.0.sg
a_custom.0.sg
```

这只是固定 MSVC/Qt5 oracle 的观察值。上游比较器不满足 strict weak ordering，
Rust 兼容层不能把它未经 ADR 和差分证明地简化为稳定 `(priority, name)` 排序。

### Mode 与 file type gate

- `DS.deep.2.sg`、`EP.entrypoint.4.sg` 只在 deep/combined 出现；
- `HEUR.heuristic.3.sg` 只在 heuristic/combined 出现；
- 四个 mode 均不执行 `main/PE/decoy.0.sg`，也不产生 `PE decoy`；
- empty main/extra/custom 不执行规则，只生成一个完整 Unknown value。

## 能力闭环含义

该报告为 Windows 直接执行证据，关闭规则库分层、priority 排序、global/type
init、file-type filter 和 deep/heuristic filter 五行。它不证明：

- 所有真实数据库类型都具有相同排序；
- 其他 MSVC、Qt、Windows 或 STL 版本会选择相同的非传递排序结果；
- include cycle、重复 include 或脚本异常行为；
- private signature-path filter。

最后一项不能从本公共 CLI 报告外推，现已由独立的原生 Windows engine
harness 直接闭合，见
[`signature-path-filter-behavior.md`](signature-path-filter-behavior.md)。

## 复现

```powershell
python tools\corpus\generate_rule_orchestration_fixture.py `
  I:\tmp\diec-windows-rule-orchestration-fixture

python tools\upstream\collect_windows_rule_orchestration.py `
  --binary <clean-source>\build\release\diec.exe `
  --source-dir <clean-source> `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --fixture-dir I:\tmp\diec-windows-rule-orchestration-fixture `
  --working-dir I:\tmp\diec-windows-rule-orchestration-work `
  --raw-dir I:\tmp\diec-windows-rule-orchestration-raw `
  --output docs\research\data\rule-orchestration-windows-qt5.json
```

正式报告为
[`rule-orchestration-windows-qt5.json`](data/rule-orchestration-windows-qt5.json)。
