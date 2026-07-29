# Windows Qt5 engine 入口、过滤、排序与取消行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Components:
`XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`,
`die_script@5d82316c110abf0eb863b50bc679d330e05067b6`

Last updated: 2026-07-29

## 1. 目的

本实验把 Linux Qt5
[`engine-contract-behavior.md`](engine-contract-behavior.md) 的同一个
37-case research harness 移植到固定 Windows Qt5 qmake Release object set，
验证 CLI 无法直接覆盖的五行能力：

- `CAP-ENG-IN-001`：file/memory/device/subdevice 入口；
- `CAP-ENG-IN-002`：device/subdevice I/O 与范围边界；
- `CAP-RULE-006`：`sSignatureName` 精确过滤；
- `CAP-RULE-009`：最终 record 排序；
- `CAP-RULE-012`：callback、规则 break、预停止和同步取消。

机器报告为
[`data/engine-contract-windows-qt5.json`](data/engine-contract-windows-qt5.json)，
SHA-256 为
`4f7d1629d4c0cf627fd8f5fa1ff6adaf838f8c9fc910e95fac0c50bfd105233e`。

## 2. 固定构建

[`build_windows_engine_contract_harness.ps1`](../../tools/upstream/build_windows_engine_contract_harness.ps1)
验证以下身份后才构建：

- DIE-engine、58 个递归 submodule 和规则 commit；
- 固定 CLI SHA-256；
- Qt 5.15.2 qmake、Qt5Core 和 Qt5Script SHA-256；
- tracked-clean 上游 source；
- 原始 `Makefile.Release` 和 `main_console.obj` 身份。

构建器显式进入 MSVC 2019 amd64 host/target 环境，只把
`release/main_console.obj` 替换为同一共享
[`engine_contract_harness_main.cpp`](../../tools/upstream/engine_contract_harness_main.cpp)
编译出的 object，其余 engine object 和链接输入不变。生成的 PE32+ harness：

| 项目 | 值 |
| --- | --- |
| 大小 | 3,110,400 bytes |
| SHA-256 | `7ec7af525c3eb9fec28600b6792d895d6bcd6414658f79ba0fa5b5a203245e83` |
| Build manifest SHA-256 | `907dbd1f6c01761d5765557328376e833940007b6c23718d6e9a92f3fcbe5953` |

构建清单保存在机器报告内部，外部二进制和临时 build manifest 不提交。

## 3. 采集与比较

[`collect_windows_engine_contract_harness.py`](../../tools/upstream/collect_windows_engine_contract_harness.py)
重新验证 source、Qt、binary、build manifest、项目生成 fixture 和固定 Linux
Qt5 报告。七个参与结构审计的上游源码文件必须与 Linux 报告中的字节数和
SHA-256 完全相同，才复用已固定的源码可达性结论。

同一 harness 连续运行两轮：

| 指标 | 结果 |
| --- | ---: |
| Process executions | 2 |
| Case observations | 74 |
| 每轮 stdout | 63,145 bytes |
| 每轮 stdout SHA-256 | `d36162bc39669445be5c45c0ce3d3d7bc89afe76290915d691cce9b75f05feb0` |
| 每轮 stderr | 0 bytes |
| Raw determinism failures | 0 |
| Named relationship failures | 0 / 23 |
| Linux case differences | 0 / 37 |

规范化只在解析后的路径字符串中，把已经验证的实际 fixture root 前缀替换为
`<fixture>`，并在该前缀内部把反斜杠改为斜杠。不删除或重排 case/record，
不改写结果、错误、callback、I/O、取消字段、Qt 版本或 raw hash。

Windows 使用 Qt 5.15.2，固定 Linux oracle 使用 Qt 5.15.13。比较明确排除唯一
身份字段 `qt_version` 后，完整结构化文档相同；37 个 case 逐项也全部相同。

## 4. 观察结果

Windows 复现了 Linux Qt5 的全部固定关系：

- file、memory、`QBuffer` device 和精确 subdevice 的 record 数组相同；
- direct device 的 3-byte chunk 被循环补齐；subdevice 的 Qt buffering
  同样触碰 slice 末端后一字节；
- early EOF、read error、seek error 和 sequential device 仍静默得到成功
  Binary 结果，不向 result/PDSTRUCT 传播 I/O 错误；
- 初始 cursor 被重置，非法 subdevice 范围不执行 I/O，精确末字节有效；
- `sSignatureName` 是区分大小写的完整文件名匹配，且不绕过 deep gate；
- `bIsSort=false` 保留插入顺序，`true` 按 type priority 排序；
- callback false、同步外部 stop 和规则 `_breakScan()` 都保留当前 record 后停止；
- 预停止仍进入 Unknown 收尾，新 `PDSTRUCT` 可恢复同一 engine 实例。

这些结果把 Windows closure 中上述五行从 `missing` 提升为
`evidence_complete`。它们也确认 ADR 0013 记录的 silent short-read、范围和
未初始化尾部安全偏离不是 Linux 特有现象。

## 5. 复现

```powershell
python tools\corpus\generate_rule_orchestration_fixture.py `
  I:\tmp\diec-windows-engine-contract-fixture

tools\upstream\build_windows_engine_contract_harness.ps1 `
  -SourceDir <tracked-clean-fixed-source> `
  -BuildDir <fixed-qmake-build> `
  -QtDir <fixed-qt-5.15.2> `
  -VsDevCmd <vs2019-vsdevcmd.bat> `
  -OutputBinary <external-output>\diec-engine-contract-harness.exe `
  -OutputJson <external-output>\build.json

python tools\upstream\collect_windows_engine_contract_harness.py `
  --binary <external-output>\diec-engine-contract-harness.exe `
  --source-dir <tracked-clean-fixed-source> `
  --qt-dir <fixed-qt-5.15.2> `
  --fixture-dir I:\tmp\diec-windows-engine-contract-fixture `
  --build-manifest <external-output>\build.json `
  --working-dir <external-output> `
  --raw-dir <external-raw-dir> `
  --output docs\research\data\engine-contract-windows-qt5.json
```

raw stdout/stderr、harness binary、临时 Makefile/object 和 build manifest 留在
未跟踪外部目录；提交报告保存它们的身份和摘要。

## 6. 限制

- 同步跨线程 stop 使用 `join` 建立 happens-before，不执行上游普通 `bool`
  stop flag 的未同步数据竞争；
- callback exception、unknown-size/null device、并发修改和 signed overflow
  路径仍不在固定 37-case 契约；
- 强制 Binary 规则隔离入口/I/O 语义，不把 short-read 未初始化尾部字节作为
  compatibility golden；
- 本实验自身不关闭其他能力；后续证据已关闭 CLI option/test、完整 rule
  orchestration、result model 和 legacy/archive dispatch，当前仍开放
  nested engine 与 path profile 缺口。
