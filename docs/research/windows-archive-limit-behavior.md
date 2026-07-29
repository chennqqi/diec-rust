# Windows Qt5 archive 深度、累计展开量与取消边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

`CAP-NEST-009` 已在固定 Windows x86_64 Qt5 oracle 上闭合：

- 与 Linux Qt5 相同的 8 个单成员 ZIP 深度样本均到达最深 PDF；最大样本为
  64 层、64 个 `Stream` node、最深 PDF depth 64。
- depth 固定为 2 的 6 个展开量样本均到达第二层 PDF；最大累计成员展开量为
  33,554,546 bytes。
- depth-64 在第一次 progress callback 内停止后，稳定保留 1 条 root record，
  没有 `Stream` 或 PDF child；该部分前缀与 Linux Qt5 完全相同。
- 14 个正常 case 和 1 个取消 control 各运行两次，共 30 次原生 Windows
  进程执行。所有执行 exit 0、stderr 为空，确定性语义投影与固定 Linux Qt5
  逐项相等。
- 固定 `xscanengine.cpp` archive block 的正向递归、声明大小分配与每层数量
  限制 token 均存在；该 block 仍没有独立 depth、cumulative、
  total-extracted 或 total-decompressed token。

这证明固定上游在本实验上界内没有额外的深度或累计展开量 cutoff，不证明任意
深度或大小都可成功。Rust 侧的有界偏离继续由
[`ADR 0012`](../design/decisions/0012-bounded-nested-scan-budget.md) 管理。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Detect-It-Easy rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| XScanEngine | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| `xscanengine.cpp` SHA-256 | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| Qt | 5.15.2，`win32-msvc` |
| harness source SHA-256 | `9bba1c21cf01b93a1ac80ab5cea4145330e1b2621d9f2b6e4275ab04723a68a4` |
| Windows-adapted source SHA-256 | `b33630b803679d3fe29244e85d996d120ce4b95e894b5e9110a8ac34bd10d24c` |
| harness binary SHA-256 | `7ff116ba367b2c40218c463f658f38b3212d3507837cbed07b8f7f4b98d25392` |

机器报告为
[`archive-limit-engine-windows-qt5.json`](data/archive-limit-engine-windows-qt5.json)，
SHA-256 为
`8487a1376b0f41ca938b8c1fdc1efdcc22f80f049cb64fcfb916f39e88b62dd0`。
报告绑定构建 manifest、语料、Linux Qt5 参考报告、源码契约、每次 stdout/stderr
哈希、语义投影和资源描述值。

## Harness 与平台适配

[`build_windows_archive_limits_harness.ps1`](../../tools/upstream/build_windows_archive_limits_harness.ps1)
验证固定 commit、58 个递归 submodule、规则 commit、Qt DLL/qmake、Release
Makefile、原始 `main_console.obj` 和 CLI artifact。它只在固定 qmake Release
链接中用
[`archive_limits_harness_main.cpp`](../../tools/upstream/archive_limits_harness_main.cpp)
替换 console main object；其余 engine、format、archive 与 rule runtime object
不变。

原 harness 的唯一平台适配是把 Linux `getrusage(RUSAGE_SELF)` 换成 Windows
`GetProcessMemoryInfo` 的 `PeakWorkingSetSize`。三个数据库绝对路径替换为以已验证
source root 为工作目录的相对路径。这两项都只影响 harness 的测量和数据库定位，
不改变扫描 options、callback 或 engine 语义。

## 语料与判据

语料由
[`generate_archive_limit_fixture.py`](../../tools/corpus/generate_archive_limit_fixture.py)
确定性生成，清单为
[`archive-limit-corpus.json`](data/archive-limit-corpus.json)。14 个 ZIP 均为
store-only、单成员、项目自有字节：

| 序列 | case 数 | 固定项 | 范围 |
| --- | ---: | --- | --- |
| depth | 8 | leaf 331 bytes，每层 1 member | 1、2、4、8、12、16、32、64 |
| expanded bytes | 6 | depth 2，每层 1 member | leaf 1 KiB—16 MiB，累计 2,162—33,554,546 bytes |

采集器
[`collect_windows_archive_limits.py`](../../tools/upstream/collect_windows_archive_limits.py)
对每个 case 执行两次，并把确定性字段与
[`archive-limit-engine-qt5.json`](data/archive-limit-engine-qt5.json) 比较。
`elapsed_ms`、`scan_result_time_ms`、callback 次数和 peak RSS 只验证类型、非负值及
high-watermark 不倒退，不要求跨平台数值相等。callback 次数受扫描耗时影响，
因此不属于正常 case 的稳定语义投影。

取消 control 在扫描线程的第一次 callback 内设置 `PDSTRUCT::bIsStop`，避免异步
写 stop flag 的数据竞争。其稳定结果为：

| 字段 | 完整 depth-64 | 第一次 callback 取消 |
| --- | ---: | ---: |
| `record_count` | 66 | 1 |
| `stream_node_count` | 64 | 0 |
| `pdf_node_count` | 1 | 0 |
| `max_stream_depth` | 64 | 0 |
| `pd_stopped` | false | true |

## 复现

```powershell
$work = Join-Path $env:TEMP diec-windows-archive-limits
python tools\corpus\generate_archive_limit_fixture.py `
  (Join-Path $work corpus)

tools\upstream\build_windows_archive_limits_harness.ps1 `
  -SourceDir <fixed-clean-source> `
  -BuildDir <fixed-qmake-build> `
  -QtDir <qt-5.15.2-msvc2019_64> `
  -VsDevCmd <VS2019-VsDevCmd.bat> `
  -OutputBinary (Join-Path $work diec-archive-limits-harness.exe) `
  -OutputJson (Join-Path $work build-manifest.json)

python tools\upstream\collect_windows_archive_limits.py `
  --harness (Join-Path $work diec-archive-limits-harness.exe) `
  --source-dir <fixed-clean-source> `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --fixture-dir (Join-Path $work corpus) `
  --build-manifest (Join-Path $work build-manifest.json) `
  --raw-dir (Join-Path $work raw) `
  --repetitions 2 `
  --output docs\research\data\archive-limit-engine-windows-qt5.json
```

原始 stdout/stderr 保存在外部工作目录，不提交仓库；机器报告保留每个流的长度、
SHA-256 和对应语义投影。

## 限制

- 只验证 Windows x86_64、Qt 5.15.2、MSVC 2019、ZIP store method、depth 64
  和约 32 MiB 累计展开量。
- 没有施加独立进程内存上限；本实验不覆盖真正 OOM、欺骗声明长度、循环
  container 或超时后的清理。
- `PeakWorkingSetSize` 包含数据库加载形成的历史高水位，不能解释为单个 archive
  allocation。
- macOS 仍需独立固定 oracle；后续 Windows path closure 已关闭
  `CAP-CLI-IN-003`，Windows 平台现已接纳为完整 baseline。
