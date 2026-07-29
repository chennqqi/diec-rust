# Windows Qt5 Archive/Resource 精确计数边界

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-29

## 1. 结论

原生 Windows x86_64 Qt5 已执行 `CAP-NEST-004` 的完整 archive/resource
计数边界：

- aggressive archive 第 99999 条 PDF 哨兵可达；
- 第 100000 条 PDF 哨兵仍可达；
- 第 100001 条 PDF 哨兵不可达；
- resource 默认模式对 22 个 PDF resource 产生 21 个 child；
- aggressive 模式对同一输入产生 22 个 child 正控制；
- aggressive 模式对 2002 个不可分类 resource 产生精确 2001 个 child；
- resource child offset 严格递增，证明是 engine limit 而非 parser 少枚举。

三个 archive case 和八个 resource case 均连续运行两轮，共 22 次进程执行。
archive 六次语义投影全部稳定并与 Linux Qt5 相同；resource 十六份完整 JSON
文档全部与 Linux Qt5 相同且 raw stream 各自稳定。十四项关系全部成立。

机器报告：
[`count-boundaries-windows-qt5.json`](data/count-boundaries-windows-qt5.json)，
159310 bytes，SHA-256
`87e901f31408c7187033266318fb2d12fe0838a9b007a8bf93e8e6b332bd97a5`。

## 2. 固定构建与源码契约

[`build_windows_archive_iteration_harness.ps1`](../../tools/upstream/build_windows_archive_iteration_harness.ps1)
校验固定源码、规则、58 个递归 submodule、Qt 5.15.2、release CLI、
Makefile 和 `main_console.obj`，只替换 console main object。engine objects
未修改。

原始
[`archive_iteration_boundary_harness_main.cpp`](../../tools/upstream/archive_iteration_boundary_harness_main.cpp)
使用 Unix `getrusage(RUSAGE_SELF)` 采集描述性 peak RSS。Windows builder
只在 harness translation unit 中把该测量函数改为
`GetProcessMemoryInfo`，并保留以下明确边界：

- 原始 harness SHA-256：
  `b8f35799ddda9e61fcff70081e7cdb6550ca2b9e9442a340a8b4ff31d2170e41`；
- 适配后 harness SHA-256：
  `7f6beffdd46844ee039812c16cd3a4dc7e304e01e9c0040fa25cdba5d2205743`；
- `engine_semantics_changed=false`；
- 三个数据库路径只改为相对已验证源码根。

固定 Windows harness：

- 大小：3,085,824 bytes；
- SHA-256：
  `2b09a0be8932cac8496aa862fffc77f3f8d3b0944325e45d4e9c1557a3212cca`。

collector 同时校验固定源码：

| 源码 | SHA-256 |
| --- | --- |
| `XScanEngine/xscanengine.cpp` | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| `XArchive/xiso9660.cpp` | `d6e97c4ff2395b812b65da5ab480e937c6b365e6e6e8b0288ddf48b8fd398fb1` |

并验证 archive 100000 hard guard、post-increment `>` 检查、resource
20/2000 limit 和 inclusive `<=` 检查仍存在。

## 3. Archive 99999/100000/100001

三个项目生成 ISO9660 各包含 100001 条 archive record，PDF 哨兵分别位于
99999、100000、100001。manifest SHA-256：
`e7f5e3c7aaa04add2b987bbfbc12df5683a3418b227b64fe501b1c8038c08e10`。

占位 record 声明 16 MiB 且指向镜像外。Linux 基线把 `TMPDIR` 指向只读
`/proc`，使其 `QTemporaryFile` 创建失败。Windows collector 将 `TEMP` 和
`TMP` 指向一个已验证为“普通文件而非目录”的外部路径，得到等价的确定性失败：
占位内容不被解包，合法的小 PDF 哨兵仍使用内存 buffer。

| 哨兵 ordinal | 两轮 PDF nodes | 两轮 Stream nodes | Linux Qt5 |
| ---: | --- | --- | --- |
| 99999 | 1 / 1 | 1 / 1 | 相同 |
| 100000 | 1 / 1 | 1 / 1 | 相同 |
| 100001 | 0 / 0 | 0 / 0 | 相同 |

六次均 exit 0、stderr 为空、error/debug/handler count 为 0，且未停止。
Windows 本机 elapsed 和 peak RSS 仅作为有效性描述，不与 Linux 数值比较。

## 4. Resource 21/2001

resource fixture manifest SHA-256：
`e444b6aa0bacaa29077eae1e9710546d8fc5a38f50059c486ce8a1807afd71b2`。
固定 release CLI 对八个 deep/aggressive/resource case 各运行两轮，直接使用
项目生成 database/extra/custom 规则目录。

关键结果：

| Case | Resource child |
| --- | ---: |
| 22 PDF / recursive | 21 |
| 22 PDF / recursive+aggressive | 22 |
| 2002 unclassified / recursive+aggressive | 2001 |

2002-resource fixture 分成 668/667/667 三个合法 type directory，避免触发
PE parser 每目录 1000 项的前置限制。2001-child case 的首尾 offset 为
96704/98704，size 均为 1，offset 严格递增。

collector 解码并重算 Linux Qt5 报告中的 zlib+base64 raw artifact；Windows
每份完整 JSON document 与对应 Linux document 相等，不只比较计数摘要。

## 5. 兼容性影响

Rust legacy-compatible engine 必须保留：

- archive aggressive 第 100000 条可达、第 100001 条不可达；
- resource limit 判断的 inclusive off-by-one：默认 21、aggressive 2001；
- resource parser 前置限制与 engine child limit 的区分；
- child 枚举顺序。

这些数值是固定上游的可观察契约，不应按注释中的 20/2000 或直觉中的
99999 静默“修正”。后续
[`windows-archive-limit-behavior.md`](windows-archive-limit-behavior.md)
已用独立 Windows 证据关闭 `CAP-NEST-009` 的 depth/cumulative expansion
与 cancellation 边界。

## 6. 复现

```powershell
python tools\corpus\generate_archive_iteration_boundary_fixture.py `
  <archive-fixture-dir>
python tools\corpus\generate_scan_option_boundary_fixture.py `
  <resource-fixture-dir>

powershell -ExecutionPolicy Bypass `
  -File tools\upstream\build_windows_archive_iteration_harness.ps1 `
  -SourceDir <verified-source-root> `
  -BuildDir <fixed-qmake-build-root> `
  -QtDir <qt-5.15.2-msvc2019_64> `
  -VsDevCmd <Visual-Studio-VsDevCmd.bat> `
  -OutputBinary <harness-root>\diec-archive-iteration-harness.exe `
  -OutputJson <harness-root>\build-manifest.json

python tools\upstream\collect_windows_count_boundaries.py `
  --harness <harness-root>\diec-archive-iteration-harness.exe `
  --source-dir <verified-source-root> `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --archive-fixture-dir <archive-fixture-dir> `
  --resource-fixture-dir <resource-fixture-dir> `
  --build-manifest <harness-root>\build-manifest.json `
  --raw-dir <raw-dir> `
  --output docs\research\data\count-boundaries-windows-qt5.json
```
