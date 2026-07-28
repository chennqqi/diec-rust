# Linux Qt6 完整 Path 边界运行证据

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt6 CMake oracle 已把 Linux Qt5 的完整目录枚举能力边界逐案重放两轮：

- 23 个 Unicode、特殊字符、hidden、option terminator 与非 UTF-8 path case；
- 9 个 symlink、dangling link、权限、64 层目录和 self-cycle case；
- 5 个 empty/single/256/flat 4096/nested 4096 大目录 case；
- 4 个 stable、old → new 与 unlink 的 TOCTOU case；
- 3 种可用 locale × `tmpfs`/Docker `volume` 的 6-case 排序矩阵。

共 47 个 case、94 次受限 Qt6 CLI 执行。每组两轮原始 stdout/stderr 相同，
五组行为投影均与固定 Qt5 报告相同，没有新增 Qt5/Qt6 差异。因此
`CAP-CLI-IN-003` 的 Linux Qt6 行边界达到 `evidence_complete`。

这不把 Linux 结果外推到 Windows 或 macOS，也不把 4096、64 或 Linux
symlink resolution 的 40 层当作产品安全上限。Rust 的安全路径策略仍由
[`ADR 0014`](../design/decisions/0014-bounded-path-expansion.md) 约束。

## 五组接纳边界

| Suite | Qt5 报告 | Case | Qt6 结果 |
| --- | --- | ---: | --- |
| special path | `special-path-engine-qt5.json` | 23 | 原始流与路径顺序相同 |
| filesystem | `path-filesystem-engine-qt5.json` | 9 | follow、重复、权限与 cycle 相同 |
| large directory | `large-path-engine-qt5.json` | 5 | flat/nested 4096 全部输出 |
| TOCTOU | `path-toctou-engine-qt5.json` | 4 | swap 等于 new；unlink 保留空结果形状 |
| locale/filesystem | `path-locale-filesystem-engine-qt5.json` | 6 | locale 不改顺序；tmpfs/volume case tie 仍不同 |

special-path 组继续保留 NFC/NFD、不做 Unicode normalization、hidden 目录过滤、
非法 UTF-8 basename 静默跳过和显式 raw argv 失败。filesystem 组继续保留
symlink path prefix、不按 inode 去重、`nobody` 权限失败静默和 self-cycle
41 个 PDF root。large-directory 组对 4096 个 prefix 做完整顺序比较，不只检查
首尾。

TOCTOU 组在第一项 prefix 后用 `SIGSTOP` 建立同步点。old → new 的第二项结果
逐字节等于 stable new；unlink 后仍输出 logical prefix、exit `0`，并返回空
records。报告保留每次执行的实际 device、inode、mode、size 与 link target。
跨版本等价投影只排除动态分配的 device/inode **数值**，不排除：

- before/after identity 是否存在及是否改变；
- mode、size 和 link target；
- stop signal 与 mutation synchronization；
- 原始 stdout/stderr、exit code 和解析后的 entropy document。

因此该规范化不能把替换、删除或打开目标差异隐藏掉。

locale/filesystem 组继续观察到所有容器可用 locale 使用 UTF-8 charmap，locale
不改变 prefix 顺序；同一 locale 下，`tmpfs` 与匿名 Docker `volume` 对
`a-case.empty`/`A-case.empty` 的相对顺序不同。该差异是 Qt5、Qt6 共有的
文件系统事实，不是新出现的平台差异。

## 固定身份

最终机器报告：
[`data/path-boundaries-linux-qt5-qt6.json`](data/path-boundaries-linux-qt5-qt6.json)

| 项目 | 固定值 |
| --- | --- |
| 报告字节数 | `343521` |
| 报告 SHA-256 | `8dbe49bdd2be73a06950e3a9a36dc07b5c65debfdf62428a50a8425b2c296e76` |
| Qt6 image ID | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` |
| Qt6 `diec` SHA-256 | `e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e` |
| replay driver SHA-256 | `5cadc79946ccbb2ab519ca443e67fea1572df1ba6a849c08af4ae3038f0be2f1` |

报告分别绑定五个 Qt5 报告的完整 SHA-256、五个原探针及 fixture generator、
fixture manifest、固定上游源码和 Qt6 oracle。25 个 suite-local raw artifact
均使用 SHA-256 content address 与 `zlib+base64` 保存；测试会逐项解压并重算
哈希，同时要求每个 artifact 至少有一个 stream reference。

五组 Qt5/Qt6 行为投影 SHA-256 为：

| Suite | Projection SHA-256 |
| --- | --- |
| special path | `3a978769f2667a13532d21b68c9cfaeeb4b353842b630eb8a6da8b9ffbc2a8c0` |
| filesystem | `76d433ad993c7152263ed6f6ab0479f6d210bf9bff94d085b75d6a1258a07f47` |
| large directory | `6ff37d6169753b1b4c6e652f84e4347449a1ca4171af6bce23c9dcdcdccee651` |
| TOCTOU | `3fb66ffd9d25cac0865dfee9a3921a9f8336fe56849568c0b50a415f32f1a174` |
| locale/filesystem | `48bb91f7c0d919cf83e5d7f139ae72ddc21b548bf5d5b9d9c7c860a8b0e287bf` |

## 重现

先在临时目录生成项目自有 fixture：

```powershell
python tools/corpus/generate_baseline_corpus.py `
  I:\tmp\diec-path-qt6-baseline
python tools/corpus/generate_special_path_fixture.py `
  I:\tmp\diec-path-qt6-baseline I:\tmp\diec-special-path-qt6
python tools/corpus/generate_path_filesystem_fixture.py `
  I:\tmp\diec-path-qt6-baseline I:\tmp\diec-filesystem-path-qt6
```

再执行聚合驱动器：

```powershell
python tools/upstream/probe_qt6_path_boundaries.py `
  --special-fixture-dir I:\tmp\diec-special-path-qt6 `
  --filesystem-fixture-dir I:\tmp\diec-filesystem-path-qt6 `
  --output docs/research/data/path-boundaries-linux-qt5-qt6.json
```

聚合驱动器不重新实现 fixture、同步或行为断言。它动态加载五个固定 Qt5 probe，
只把两个 oracle repetition 指向同一固定 Qt6 image/binary，然后调用原
`build_report()`。原探针的 case catalog、expected hashes、源码契约和关系断言
仍作为第一道门禁；聚合层再与版本化 Qt5 报告比较投影。

每次底层执行继续使用各原探针记录的 network、CPU、memory、pids、只读 root、
tmpfs/volume 与 timeout 限制。描述性 wall time、CPU 和 RSS 不进入跨版本等价
投影，也不进入版本化 Qt6 报告。

## 范围与后续

本证据关闭的是固定 Linux Qt5 行边界在固定 Linux Qt6 oracle 上的重放缺口。
它不关闭跨平台路径 gap，也不授权 Rust 正式实现提前越过 Phase 0 设计门禁。

Qt6 能力闭环仍剩：

- `CAP-DISPATCH-004`：完整 archive family dispatch；
- `CAP-NEST-009`：独立 depth/累计展开量边界。
