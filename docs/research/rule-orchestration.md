# 上游规则编排端到端行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Components:
`XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`,
`die_script@5d82316c110abf0eb863b50bc679d330e05067b6`

Last updated: 2026-07-27

## 范围

本文用一个完全项目生成的无害 Binary 数据库，同时验证：

- 单层 signature priority 与文件名字典序的关系；
- type `_init` 参与排序时的非传递比较；
- main、extra、custom 分层 append；
- global init、type init 和同名 include 的层优先级；
- file type 过滤；
- `DS`/`EP` deep 与 `HEUR` heuristic 过滤；
- 空数据库的 Unknown 结果。

fixture 清单为
[`rule-orchestration-fixture.json`](data/rule-orchestration-fixture.json)，
生成器为
[`generate_rule_orchestration_fixture.py`](../../tools/corpus/generate_rule_orchestration_fixture.py)。
输入只是固定 ASCII 文本，规则只调用 `_setResult()`，不包含第三方规则或样本字节。

探针
[`probe_rule_orchestration.py`](../../tools/upstream/probe_rule_orchestration.py)
同时运行固定 Linux Qt5 qmake/CMake oracle。报告
[`rule-orchestration-linux-qt5.json`](data/rule-orchestration-linux-qt5.json)
保留每个 mode/oracle 的原始 stdout/stderr 长度与 SHA-256、规范化执行顺序和完整
detection 字段；原始流保存在 `--raw-dir` 指定的非版本化目录。

固定 Windows Qt5 的相同十个 case 已完成，见
[`windows-rule-orchestration.md`](windows-rule-orchestration.md)。Windows
canonical case、14 条关系及 `_init` 实际顺序均与 Linux Qt5 完全相同。

## 固定身份

| Oracle | Image ID | Binary |
| --- | --- | --- |
| Linux Qt5 qmake | `sha256:cc5561a5d256...bac964ab` | `/opt/die-source/build/release/diec` |
| Linux Qt5 CMake | `sha256:466102628c3a...0255040` | `/opt/die-build/src/console/diec` |

两个镜像的 revision 都是 `74eaf505...`。10 个 case 的规范化执行顺序与 detection
逐字段相同，所有进程 exit 0、stderr 为空。profiling elapsed 毫秒不作为稳定
字段；原始 artifact 仍保留哈希。

## Priority 的正常路径与 `_init` 排序环

固定
[`sort_signature_prio()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L35-L67)
只有在比较双方的文件名都包含至少两个点时，才取倒数第二段作为字符串 priority；
否则直接比较完整文件名。

### 没有 type init

priority-only 数据库不含 Binary `_init`，并故意让字典序与 priority 冲突：

| 文件 | Priority | 字典序位置 | 实际执行 |
| --- | --- | ---: | ---: |
| `z_priority.1.sg` | `"1"` | 3 | 1 |
| `a_priority.2.sg` | `"2"` | 1 | 2 |
| `m_priority.4.sg` | `"4"` | 2 | 3 |

两个 oracle 都按 `1 → 2 → 4` 执行，证明有效比较路径使用字符串 priority，而不是
完整文件名字典序。

### 比较器边界闭合

四个隔离数据库进一步固定 `sort_signature_prio()` 的 pairwise 行为：

| Case | 输入文件名 | 实际执行顺序 | 结论 |
| --- | --- | --- | --- |
| equal priority | `z_equal.2.sg`, `a_equal.2.sg`, `m_equal.2.sg` | `a → m → z` | priority 相等时回退完整文件名 |
| lexical priority | `z_ten.10.sg`, `a_two.2.sg` | `10 → 2` | priority 是 `QString` 字典序，不是整数 |
| missing priority | `a_plain.sg`, `z_ranked.1.sg` | `a_plain → z_ranked` | 任一名称不足两个点时，双方都使用默认 `"9"` 并回退文件名 |
| empty priority | `a_empty..sg`, `z_empty_ranked.1.sg` | `a_empty → z_empty_ranked` | 任一提取段为空时跳过 priority 比较并回退文件名 |

profiling 行固定的是规则执行顺序；CLI 的 `bIsSort=true` 还会独立排序 detection，
因此探针分别校验执行顺序和 detection 集合，不能用后者倒推出规则顺序。

### 加入真实 type init

正常 main/Binary 层包含 `_init`。它的点数不足，导致以下比较环：

```text
DS.deep.2.sg < _init          # lexical
_init < z_normal.1.sg         # lexical
z_normal.1.sg < DS.deep.2.sg  # priority "1" < "2"
```

这不满足 `std::sort` 的 strict weak ordering 前置条件。combined 模式在两个固定
Linux 构建中实际得到：

```text
DS.deep.2.sg
HEUR.heuristic.3.sg
EP.entrypoint.4.sg
z_normal.1.sg
a_extra.0.sg
a_custom.0.sg
```

因此不能把规则排序实现为无条件 `(priority, name)` 并称为 1:1。这里固定的是
Linux Qt5 的观察值；Windows MSVC 和 macOS libc++ 仍需各自 oracle。

## 数据库分层不是全局 priority

main、extra、custom 分别收集并排序，然后按层 append。fixture 中 extra/custom
普通规则 priority 都是 `"0"`，main 最后一条是 `"4"`，实际仍为：

```text
... main priority "4"
extra priority "0"
custom priority "0"
```

这证明层优先级高于跨层 priority；不能把三层合并后全局排序。

同优先级、字符串 priority、缺失/空段、跨层 append 和 `_init` 非传递环已共同
闭合 Linux Qt5 的 `CAP-GAP-010`。该闭合不外推到 MSVC/libc++；其余平台仍由
`CAP-GAP-007` 覆盖。

## Init 与 include 首层胜出

三个数据库层都提供 root `_init`、Binary `_init` 和同名 `shared_helper`。main
global init 设置 `main-global` 并 include helper，main helper 设置
`main-helper`，main Binary init 再追加 `main-type`。

所有 default/deep/heuristic/combined detection 的 version 都精确为：

```text
main-global:main-helper:main-type
```

extra/custom 的替代值从未出现。这同时证明：

- main global init 遮蔽后层 global init；
- main type init 遮蔽后层 type init；
- root 同名 include 选择已装载列表中的首个 main record；
- main/extra/custom 普通规则共享这次 init 后的同一脚本状态。

## Mode 与 file type 过滤

profiling 中只接受 fixture manifest 声明的完整 rule basename。四种模式为：

| Mode | Main rules executed before extra/custom |
| --- | --- |
| default | `z_normal.1.sg` |
| deep | `DS.deep.2.sg`, `EP.entrypoint.4.sg`, `z_normal.1.sg` |
| heuristic | `HEUR.heuristic.3.sg`, `z_normal.1.sg` |
| combined | `DS.deep.2.sg`, `HEUR.heuristic.3.sg`, `EP.entrypoint.4.sg`, `z_normal.1.sg` |

这验证 `DS` 和 `EP` 只由 deep 开关放行，`HEUR` 只由 heuristic 放行，两个开关
彼此独立。

main/PE 中另放置 `decoy.0.sg`。同一 Binary 输入的四种模式都没有执行该规则，也
没有产生 `PE decoy` detection，验证 file type filter 在 mode filter 之前排除
错误类型记录。

## Unknown

同一 Binary 输入使用存在但完全为空的 main/extra/custom 目录时：

- exit 0；
- profiling execution order 为空；
- stderr 为空；
- 唯一 normalized value 为
  `type=Unknown, name=Unknown, version="", info=""`。

这证明 `bAddUnknown` 在没有规则结果时生成 Unknown，而不是要求至少装载一条规则。

## 复现

```powershell
python tools\corpus\generate_rule_orchestration_fixture.py `
  I:\tmp\diec-rule-orchestration-fixture

python tools\upstream\probe_rule_orchestration.py `
  --fixture-dir I:\tmp\diec-rule-orchestration-fixture `
  --raw-dir I:\tmp\diec-rule-orchestration-raw `
  --output docs\research\data\rule-orchestration-linux-qt5.json
```

Docker 执行使用 `--network=none`。探针校验 fixture 文件/目录全集、每个字节 hash、
image revision、执行顺序、detection 集合、init 值、Unknown 以及双 oracle
规范化相等；失败不会静默生成新基线。

## 尚未覆盖

- `sSignatureName`、`bIsSort`、callback stop、`_breakScan()` 和预停止
  `PDSTRUCT` 已由 [`engine-contract-behavior.md`](engine-contract-behavior.md)
  覆盖；`sSignatureFilePath` 经源码审计确认公共扫描 API 不可达；
- scan 运行期间由其他线程设置 `PDSTRUCT` 的精确时序仍未覆盖；
- 非 Binary file type 和 macOS 的排序/层行为；固定 Windows Qt5 与 Linux Qt6
  对照已完成，见
  [`windows-rule-orchestration.md`](windows-rule-orchestration.md) 和
  [`qt6-rule-orchestration-runtime-evidence.md`](qt6-rule-orchestration-runtime-evidence.md)；
- include 重复、循环及异常传播。

这些缺口不能从本轮成功外推。
