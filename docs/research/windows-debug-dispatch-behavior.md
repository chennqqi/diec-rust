# Windows Qt5 PE debug-data 分派基线

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-29

## 1. 结论

原生 Windows x86_64 Qt5 重复了 Linux Qt5 的同输入 paired harness，关闭
`CAP-NEST-007` 的 Windows runtime 缺口：

- Formats 枚举 offset 608 的 Manifest resource 和 offset 1088 的
  CodeView/RSDS debug-data part；
- public recursive+aggressive scan 调度 Manifest resource child，但不调度
  debug-data child；
- direct `FILEPART_DEBUGDATA` context 使用枚举出的同一组 RSDS bytes，并由
  原样 `debug_data_debugData.1.sg` 识别为 `PDB file link / 7.0`；
- 枚举、公共扫描和 direct scan 都未取消且没有错误。

两轮进程执行产生 6 次语义 case observation，raw stdout/stderr 完全相同，
九项关系断言全部成立。机器报告为
[`debug-dispatch-engine-windows-qt5.json`](data/debug-dispatch-engine-windows-qt5.json)，
SHA-256：
`14c9901d40a0689e1dee91d8f40d7a35bf17e74604525a71e0ada9fc67006b9a`。

## 2. 固定构建

[`build_windows_debug_dispatch_harness.ps1`](../../tools/upstream/build_windows_debug_dispatch_harness.ps1)
校验固定源码、规则、58 个递归 submodule、Qt 5.15.2、release CLI、
Makefile、`main_console.obj` 和 `die_script.obj` 身份。构建复用固定 qmake
Release engine objects，只替换 console main object；engine objects 未修改。

harness 原源码仅把 Linux 固定数据库路径改写为相对于已验证源码根的
`Detect-It-Easy/db`、`db_extra` 和 `db_custom`。manifest 同时记录原始与
适配后 harness SHA-256 及每项精确替换次数。

private `DiE_Script::processDetect()` 入口使用 MSVC `/alternatename` access
bridge：harness translation unit 声明 public decorated symbol，链接到固定
`die_script.obj` 中的 private definition。该桥只绕过测试入口的 C++ access
check，不修改 engine object 或规则字节。

构建产物：

- `diec-debug-dispatch-harness.exe`：3,097,600 bytes；
- SHA-256：
  `a35c8600dcd857de3dea23c337fedf4f64d6cf55e9e736e6362451c782aaff85`。

## 3. 输入与运行

项目生成 fixture 与 Linux 基线完全相同：

- 文件：`pe-resource-debug.exe`；
- 大小：1536 bytes；
- SHA-256：
  `58e2b8e73ba187977564e719d39022079b8fb9172c5bcdf40c495ed825b38ea1`；
- Manifest resource：offset 608，size 20；
- CodeView/RSDS debug data：offset 1088，size 38。

[`collect_windows_debug_dispatch.py`](../../tools/upstream/collect_windows_debug_dispatch.py)
从已验证源码根运行 harness 两次，原始 stdout/stderr 写入外部 raw 目录。
collector 复用原 Linux probe 的关系校验，并验证 fixture manifest、Linux Qt5
报告、Windows build manifest 以及所有固定身份。

九项关系为：

1. Formats 枚举 resource；
2. Formats 枚举 debug data；
3. public scan 调度 resource；
4. public scan 不调度 debug data；
5. public scan 不产生 PDB link；
6. direct scan 使用枚举出的同一 debug part；
7. direct debug 规则识别 RSDS；
8. resource/debug 两个 part 的范围不同；
9. 全部操作无取消且无错误。

## 4. Linux Qt5 差分

Windows 两轮 raw 输出相同。跨平台比较保留完整结构、记录顺序、filetype、
规则、结果文本、错误文本和 raw stream hash；唯一归一化是三个已验证
`signature_path` 的固定源码根前缀：

- direct debug rule；
- public `_debug_data.5.sg`；
- public `win_resources.1.sg`。

归一化没有删除、重排或改写任何记录字段。归一化后完整 harness 文档与
[`debug-dispatch-engine-qt5.json`](data/debug-dispatch-engine-qt5.json)
相同，九项关系投影也相同。

## 5. 兼容性影响

Windows 证据确认该边界不是 Linux 构建或容器特例。Rust 兼容实现必须区分：

- 格式层能够枚举 debug-data file part；
- 原样规则能够在 direct debug context 检测 RSDS；
- legacy public recursive scanner 不建立 debug-data child。

默认增加 debug child 或 PDB link 会形成上游没有的可观察输出，应按兼容缺陷
处理。显式扩展模式可以另行设计，但不得静默改变默认行为。

## 6. 复现

```powershell
python tools\corpus\generate_debug_dispatch_fixture.py <fixture-dir>

powershell -ExecutionPolicy Bypass `
  -File tools\upstream\build_windows_debug_dispatch_harness.ps1 `
  -SourceDir <verified-source-root> `
  -BuildDir <fixed-qmake-build-root> `
  -QtDir <qt-5.15.2-msvc2019_64> `
  -VsDevCmd <Visual-Studio-VsDevCmd.bat> `
  -OutputBinary <harness-output-root>\diec-debug-dispatch-harness.exe `
  -OutputJson <harness-output-root>\build-manifest.json

python tools\upstream\collect_windows_debug_dispatch.py `
  --source-dir <verified-source-root> `
  --binary <harness-output-root>\diec-debug-dispatch-harness.exe `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --build-manifest <harness-output-root>\build-manifest.json `
  --fixture-dir <fixture-dir> `
  --raw-dir <raw-dir> `
  --output docs\research\data\debug-dispatch-engine-windows-qt5.json

python -m unittest discover -s tools\tests -p "test_*debug_dispatch*.py"
```
