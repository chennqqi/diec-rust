# Windows Qt5 legacy/archive dispatch 行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-29

## 目的

本文关闭 Windows Qt5 能力审计中的三个 dispatch 缺口：

- `CAP-DISPATCH-002`：DOS/COM 公共分发和 BW DOS16M property-only 分支；
- `CAP-DISPATCH-003`：Amiga Hunk 公共分发和 Atari ST
  detector-only/Binary fallback；
- `CAP-DISPATCH-004`：NPM automatic/forced 和通用 Archive
  property-only 分支。

固定机器报告为
[`dispatch-engine-windows-qt5.json`](data/dispatch-engine-windows-qt5.json)，
SHA-256 为
`398b30af7ab44a9a13591822581a1a5145cb84b2b7b1f233f243a8e39085e617`。

## 构建边界

[`build_windows_dispatch_harnesses.ps1`](../../tools/upstream/build_windows_dispatch_harnesses.ps1)
验证固定 source/rules、58 个递归 submodule、Qt 5.15.2 DLL/qmake、发布 CLI
以及原始 qmake Release Makefile、`main_console.obj`、`die_script.obj` 的
SHA-256。它从同一组 Release engine objects 链接三项研究 harness：

| Harness | 用途 |
| --- | --- |
| `bw_dispatch_harness_main.cpp` | automatic 与强制 `BWDOS16M` |
| `npm_dispatch_harness_main.cpp` | direct detector、automatic 与强制 `NPM` |
| `generic_archive_dispatch_harness_main.cpp` | automatic/forced × quiet/verbose |

构建只替换 console main object，不修改任何 engine object。NPM 与 Archive
harness 原本把 Linux 固定数据库位置写在项目自有研究源码中；构建器只在临时
源码副本内将三个精确字面量替换为位置无关的
`Detect-It-Easy/db`、`db_extra`、`db_custom` 相对路径。清单记录原始/适配后
源码哈希和每个替换；采集器把运行目录固定为已验证的 source root，因此不会
把本机路径编入二进制或正式报告。

## 输入与执行

四套输入均由项目生成器重新产生，并逐字节等于已提交 manifest：

- 19 个 DOS/COM positive、truncated、near-magic、chain、suffix 和 size
  boundary；
- 8 个 Amiga Hunk/Atari ST positive、truncated、endian 和 near-magic；
- 4 个 NPM exact-path/JSON/path/case fixture；
- 3 个 ZIP/TAR/GZIP generic Archive fixture。

[`collect_windows_dispatch.py`](../../tools/upstream/collect_windows_dispatch.py)
复用五个既有 Linux Qt5 probe 的 fixture 和语义校验函数。每项输入连续执行
两轮，原始 stdout/stderr 保存在未跟踪目录：

| Suite | 进程执行 | Case observation |
| --- | ---: | ---: |
| DOS/COM CLI scan | 38 | 38 |
| Amiga/Atari CLI scan + `--info` | 32 | 16 |
| BW harness | 2 | 4 |
| NPM harness | 8 | 8 |
| Generic Archive harness | 6 | 6 |
| **合计** | **86** | **72** |

公开 CLI 与 Linux Qt5 比较既有 `detect_tree` 投影；Amiga/Atari 另比较
`--info` 的 `File type`。这是 Linux 报告已经固定的跨平台语义边界。三个
private harness 不做字段删除或内容改写，完整解析 JSON 文档逐字段比较。

## 结果

所有执行 exit code 为 `0`、stderr 为空，同一 Windows case 两轮语义稳定；
九条派生关系全部成立。

### DOS/COM 与 BW

19 个公共 case 的 filetype、offset、size、value tree 全部等于 Linux Qt5。
七个 public detector 成员仍为 MSDOS、NE、LE、LX、DOS/16M、DOS/4G、COM。
BW 不会被 automatic detector 发出；显式 `filetypes=BWDOS16M` 才进入
`BW DOS16M`，并产生单个 Unknown record。BW 完整 harness 文档与 Linux
Qt5 相同。

### Amiga Hunk 与 Atari ST

8 个 scanner tree 和 detector `File type` 全部等于 Linux Qt5：

- 完整 Amiga Hunk 同时由 detector 与 scanner 识别；
- 完整 Atari ST 由 detector 识别为 `Atari ST`，scanner 顶层仍回退
  `Binary`，由 Binary 规则报告 `Atari ST TOS executable`；
- truncated/endian/magic 控制保留既有 detector/scanner 分歧，未被
  normalization 隐藏。

### NPM 与通用 Archive

四个 NPM 完整 harness 文档与 Linux Qt5 相同：

- direct detector 只接受精确 `package/package.json` 路径，且不要求 JSON
  可解析；
- automatic scan 仍得到 `BINARY|ARCHIVE|GZIP` 并回退 Binary Unknown；
- 强制 `NPM` 进入 NPM 规则，JavaScript/TypeScript record 集合逐例相同。

ZIP/TAR/GZIP 三个 Archive 完整 harness 文档也与 Linux Qt5 相同：

- automatic ZIP 进入 specialized ZIP，TAR/GZIP 保持 Binary public fallback；
- 强制 quiet `ARCHIVE` 产生 Archive Unknown；
- 强制 verbose `ARCHIVE` 分别由 adapter 重识别为 ZIP、tar、GZIP。

## 复现

```powershell
powershell -File tools\upstream\build_windows_dispatch_harnesses.ps1 `
  -SourceDir <fixed-source> `
  -BuildDir <fixed-qmake-build> `
  -QtDir <fixed-qt> `
  -VsDevCmd <vsdevcmd.bat> `
  -OutputDir <harness-output> `
  -OutputJson <harness-output>\build-manifest.json

python tools\upstream\collect_windows_dispatch.py `
  --binary <fixed-source>\build\release\diec.exe `
  --binary-dir <harness-output> `
  --source-dir <fixed-source> `
  --qt-dir <fixed-qt> `
  --dos-fixture <dos-fixture> `
  --legacy-fixture <legacy-fixture> `
  --npm-fixture <npm-fixture> `
  --generic-fixture <generic-fixture> `
  --working-dir <working-directory> `
  --build-manifest <harness-output>\build-manifest.json `
  --raw-dir <untracked-raw-directory> `
  --output docs\research\data\dispatch-engine-windows-qt5.json
```

本报告把三个能力行提升为 Windows `evidence_complete`，不关闭
`CAP-CLI-IN-003` 或其余四项 nested-engine 缺口，也不代表 Windows 68 行基线已经
接纳。
