# Linux Qt6 Archive Family 分派运行证据

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux Qt6 CMake oracle 已闭合 `CAP-DISPATCH-004` 的完整能力行：

- 公共分派：APK、IPA、JAR、ZIP、RAR、ISO9660；
- 仅 forced `filetypes=NPM` 可达的 NPM engine 分支；
- 仅 singleton `filetypes=ARCHIVE` 可达的 generic Archive engine 分支；
- TAR/GZIP 作为 generic Archive 的自然检测与 Binary fallback 控制。

能力行的八个成员为：

```text
APK / IPA / JAR / ZIP / RAR / NPM / ISO9660 / Archive
```

公共 8-case Qt5/Qt6 CLI 报告没有差异。两个 private harness 共执行 7 个 fixture，
并各自复用同一 Qt6 release 两次作为公共入口控制；完整 behavior projection
与对应 Qt5 报告相同，raw artifact digest、exit code、records、诊断和规则路径
均未出现 Qt major 差异。

因此 `CAP-DISPATCH-004` 达到 Linux Qt6 `evidence_complete`。该结论不声称所有
archive method、损坏流或平台都已覆盖；这些是 format/method 和跨平台扩展范围，
不改变固定源码中本能力行的分派成员闭集。

## 公共分派

公共证据复用
[`cli-output-matrix-linux-qt5-qt6.json`](data/cli-output-matrix-linux-qt5-qt6.json)
的固定 corpus 区：

| Fixture | Qt5/Qt6 root filetype | 兼容含义 |
| --- | --- | --- |
| `minimal.apk` | APK | APK 专用分支 |
| `minimal.ipa` | Binary | detector 识别后 scanner 仍回退 Binary 的固定 quirk |
| `minimal.jar` | JAR | JAR 专用分支 |
| `payload.zip` | ZIP | ZIP 专用分支 |
| `minimal.rar` | RAR | RAR 专用分支 |
| `minimal.iso` | ISO 9660 | ISO9660 专用分支 |
| `payload.tar` | Binary | Binary archive rule 产生 `tar` |
| `payload.txt.gz` | Binary | GZIP 自然检测仍为 Binary/Unknown |

八例的 exit code、stdout/stderr hash 和 detection tree 均相同。TAR/GZIP 不作为
额外能力成员；它们证明自然检测不能使 `stFT.size()==1`，从而为 generic
Archive private branch 提供公共负控制。

## NPM property-only branch

Qt6 NPM harness 原样复用 Qt5 的 4-case fixture：

- `npm-valid.tgz` 与无效 JSON 的 `npm-invalid-json.tgz` 都因精确
  `package/package.json` path 使 direct detector 返回 true；
- root-level `package.json` 和大小写错误的 `package/Package.json` 返回 false；
- 四例自动检测都是 `BINARY|ARCHIVE|GZIP`，public scanner 初始化 Binary；
- 强制 `filetypes=NPM` 后初始化 NPM，并到达 JavaScript/TypeScript language
  rules；合法 package metadata 在默认非 verbose options 下仍不输出。

两次 Qt6 release control 逐案相同，harness custom JSON 与 Qt5 完整 behavior
projection 相同。

## Generic Archive property-only branch

Qt6 generic Archive harness 对 ZIP/TAR/GZIP 三例分别执行：

- automatic quiet；
- automatic verbose；
- forced Archive quiet；
- forced Archive verbose；
- 两轮 Qt6 release quiet/verbose control。

结果与 Qt5 相同：

- natural detection 总是把 `ARCHIVE` 与 ZIP/TAR/GZIP 具体 subtype 同时返回，
  因而不满足 scanner 的 singleton Archive gate；
- ZIP public 初始化 ZIP；TAR/GZIP public 初始化 Binary；
- 强制 singleton `ARCHIVE` 后 quiet 产生 Archive/Unknown；
- verbose 时 `_Archive.0.sg` 重新检测具体 adapter，分别产生 zip/tar/gzip
  format record。

这同时固定了 “parser 可以构造” 与 “public scanner 分派可达” 的区别。

## 分派闭集

本报告绑定
[`archive-gap-closure.json`](data/archive-gap-closure.json) 的固定源码审计：
engine 成员解包 family 仍是
`ZIP / 7Z / RAR / CAB / ISO9660` 五类，且该 inventory 是源码闭集。

该五类集合服务 nested extraction；本页八成员集合服务顶层 scanner dispatch。
二者不能混淆。7Z/CAB 不在 `CAP-DISPATCH-004` 的命名行中，但其 archive-option
行为已有独立 Qt6 证据；TAR/GZIP 是 generic Archive 可达性控制，却不是新的
engine extraction family。

## 固定身份

最终报告：
[`data/archive-dispatch-linux-qt5-qt6.json`](data/archive-dispatch-linux-qt5-qt6.json)

| 项目 | 固定值 |
| --- | --- |
| 报告字节数 | `86650` |
| 报告 SHA-256 | `7f4492a0ab48714d5654f5d244266de822c2268c766a2eb75a9de066cc1cb52b` |
| replay driver SHA-256 | `c307439025c40b26d769fb848fd30904e05011976edb91d110ea6d12f309f31d` |
| Qt6 release `diec` SHA-256 | `e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e` |
| NPM Qt6 image ID | `sha256:8c6311d4740eb15055cb8bf474b1c3c36ede78fe9f2293ce5673b86c12957f64` |
| NPM harness SHA-256 | `b623930bca7301706edad4ab66ebef4718012d112015da7a1b2dae76ea70416f` |
| generic Archive Qt6 image ID | `sha256:384844c09790b019a388381ed8beee2f160e6d3bd405f19b88cea9b87662095f` |
| generic Archive harness SHA-256 | `0969dd12914d20964b2d60d660e904f7706c1b4857f66314589386cddf615be7` |

NPM 与 generic Archive 的 Qt5/Qt6 behavior projection SHA-256 分别为：

- `ca5a01ab0178e877089e0a584f8f3649da48dd4ae49dfb49c0bf314592073911`；
- `ff2d7f5810f766e629486eeb35f91ca8c2c9b8699bb97524b417e4343b672da6`。

两个 suite 分别保存 6 和 8 个 content-addressed raw artifact。测试逐项解压、
重算 SHA-256，并要求所有 artifact 都被至少一个 harness/release stream 引用。

## 重现

生成项目自有 fixture：

```powershell
python tools/corpus/generate_npm_dispatch_fixture.py `
  I:\tmp\diec-npm-dispatch-qt6
python tools/corpus/generate_generic_archive_dispatch_fixture.py `
  I:\tmp\diec-generic-archive-dispatch-qt6
```

构建两个 Qt6 harness：

```powershell
docker build --provenance=false `
  --file tools/upstream/Dockerfile.npm-dispatch-harness-qt6 `
  --tag diec-rust/npm-dispatch-harness-qt6:74eaf505 `
  tools/upstream

docker build --provenance=false `
  --file tools/upstream/Dockerfile.generic-archive-dispatch-harness-qt6 `
  --tag diec-rust/generic-archive-dispatch-harness-qt6:74eaf505 `
  tools/upstream
```

生成聚合报告：

```powershell
python tools/upstream/probe_qt6_archive_dispatch.py `
  --npm-fixture-dir I:\tmp\diec-npm-dispatch-qt6 `
  --generic-fixture-dir I:\tmp\diec-generic-archive-dispatch-qt6 `
  --output docs/research/data/archive-dispatch-linux-qt5-qt6.json
```

两个 Dockerfile 只在固定 Qt6 CMake oracle 中替换 console main object 并复用
原 link command，不下载依赖、不修改上游 subtree。聚合驱动器动态加载两个
固定 Qt5 probe，只替换 image、Dockerfile 和第二个 release repetition 身份；
fixture loader、源码契约、expected records 和所有关系断言继续由原 probe
执行。

每次 container 继续使用原 probe 固定的 `network=none`、只读 root、只读
fixture mount、1 CPU、512 MiB memory、128 pids 和 60 秒 timeout。

## 范围与后续

本页闭合固定 Linux Qt6 的 archive top-level dispatch 行，不关闭 Windows/
macOS，也不把安全边界外推到未测压缩算法或损坏流。

Qt6 68 行能力闭环只剩 `CAP-NEST-009`：独立 depth/累计展开量的完整 Qt6
运行时证据。
