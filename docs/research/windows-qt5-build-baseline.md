# 上游 Windows Qt5 CLI 构建基线

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-29

## 结论

固定上游及其 58 个递归 submodule 可以在 Windows x64、MSVC 2019、Qt
5.15.2 环境中，从 tracked-clean 检出通过 qmake/jom 构建 `diec 4.0.0`。
构建产物成功加载固定
`Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6` 规则，并对项目
生成的 26 个 baseline 样本各执行两次默认 JSON 扫描：64 次总执行全部原始输出
稳定，26/26 detection projection 和退出码与 Linux Qt5 基线一致。
同一产物随后完成 338-case option/output/special 矩阵，每项两轮共 676 次；
0 个确定性或默认基线 continuity failure，与 Linux 报告重叠的 170 个 case
退出码全部相同。
首轮 14-case path 和 32-case nested 矩阵又完成 92 次执行；退出码、相对
filename-prefix 顺序和 nested detection tree 均与 Linux Qt5 相同。
随后 18-case database success/error 矩阵完成 36 次执行；退出码、load-error
可见性、JSON validity 和受限 path/CRLF normalization 后的 stdout 均与
Linux Qt5 相同。
17-case ZIP database 矩阵再完成 34 次执行；完整/空/截断、重复/`..` entry
和额外根前缀的退出码、stderr、JSON validity 及受限规范化 stdout 均与
Linux Qt5 相同。
19-case engine `bUseCache=true` harness 连续运行两轮；raw stream 稳定，
19/19 语义投影和 18/18 非身份关系与 Linux Qt5 相同，并固定 Windows DACL
write/read denial 与 403-byte populated cache。
Windows 专用 17-case Unicode/特殊路径矩阵再完成 34 次执行；固定可表示名称、
默认大小写别名、点号/Hidden attribute 过滤和目录/显式 target 顺序。
Windows 专用 8-case filesystem 矩阵再完成 16 次执行；固定 Junction 目录、
两跳 Junction 链、alias 重复扫描和普通长度 `\\?\` 命名空间。
Windows 专用 7-case long-path 矩阵再完成 14 次执行；固定 324/325-code-unit
显式文件、深目录和从短根目录递归发现长叶子。
Windows 专用 5-case ADS 矩阵再完成 10 次执行；固定显式普通/`\\?\` named
stream 按内容扫描，以及目录只枚举 carrier 默认 stream。
剩余 21 个 baseline 样本的 7-case 普通 output 矩阵再完成 294 次执行；固定
JSON continuity、CSV 优先级及四个带空格 filetype 的 invalid XML。
同 21 个样本的 19-case entropy/info/struct 矩阵再完成 798 次执行；固定全部
输出有效性、JSON-first formatter 和 entropy/struct 模式优先级。

本仓库用
[`build_windows_qt5_oracle.ps1`](../../tools/upstream/build_windows_qt5_oracle.ps1)
固定源码、规则、Qt 二进制身份和构建目标。它产生的是 **Windows Qt5 qmake CLI
候选 oracle**，不是固定上游官方 workflow 的发布包。Windows 的 68 项能力仍
保持 `platform_missing`，直到完整差分语料在该平台执行并归档。

机器证据见
[`data/windows-qt5-build-baseline.json`](data/windows-qt5-build-baseline.json)
和
[`data/baseline-corpus-windows-qt5.json`](data/baseline-corpus-windows-qt5.json)、
[`data/windows-qt5-cli-matrix.json`](data/windows-qt5-cli-matrix.json) 和
[`data/windows-qt5-cli-path-nested.json`](data/windows-qt5-cli-path-nested.json)、
[`data/windows-qt5-cli-database.json`](data/windows-qt5-cli-database.json)、
[`data/windows-qt5-cli-database-archive.json`](data/windows-qt5-cli-database-archive.json)、
[`data/database-cache-engine-windows-qt5.json`](data/database-cache-engine-windows-qt5.json)、
[`data/windows-qt5-cli-special-paths.json`](data/windows-qt5-cli-special-paths.json)
和
[`data/windows-qt5-cli-filesystem.json`](data/windows-qt5-cli-filesystem.json)。
另见
[`data/windows-qt5-cli-long-paths.json`](data/windows-qt5-cli-long-paths.json)
和
[`data/windows-qt5-cli-ads.json`](data/windows-qt5-cli-ads.json)。
普通 output 扩展见
[`data/windows-qt5-cli-output-remaining.json`](data/windows-qt5-cli-output-remaining.json)。
special 扩展见
[`data/windows-qt5-cli-special-remaining.json`](data/windows-qt5-cli-special-remaining.json)。

## 固定环境

| 输入 | 观测值 |
| --- | --- |
| Host | Windows build `26100`, x86_64 |
| Visual Studio | 2019 Build Tools `16.11.47` |
| MSVC compiler | `19.29.30159.0` |
| MSVC tools | `14.29.30133` |
| Qt | `5.15.2`, `win64_msvc2019_64`, module `qtscript` |
| qmake | spec `win32-msvc` |
| jom | `1.1.4`, SHA-256 `93eb6b9d…365cc2e8` |

Qt 使用 `aqtinstall 3.3.0` 安装，且没有关闭 aqt 的 archive hash 校验：

```powershell
python -m aqt install-qt windows desktop 5.15.2 win64_msvc2019_64 `
  -O <qt-root> --modules qtscript --timeout 30
```

构建脚本进一步校验安装后的关键文件：

| 文件 | SHA-256 |
| --- | --- |
| `bin/qmake.exe` | `e873ad3a689a0628c3037a6440221dcd2e426395edf14ffa6379612dede26d36` |
| `bin/Qt5Core.dll` | `8d2ff4ce9096ddccc4f4cd62c2e41fc854cfd1b0d6e8d296645a7f5fd4ae565a` |
| `bin/Qt5Script.dll` | `0b58e5e79df13110a8258f14d7b3658d1dd0c8dddc337a164b89d4ac12a0638f` |

## 官方 Windows workflow 的两个断点

固定 commit 的 x64 workflow 在
`.github/workflows/builder.yml:219-249` 安装 MSVC x64、Qt 5.15.2
`win64_msvc2019_64` 和 `qtscript`，然后设置 `QMAKE_PATH` 并调用
`build_win_generic_check.cmd`。

### 环境变量契约漂移

workflow 在第 239 行设置 `QMAKE_PATH`，但被调用脚本没有使用 qmake：
`build_win_generic_check.cmd:7-16` 使用 CMake/NMake，并只读取
`QT_PREFIX_PATH`。workflow 没有设置后者。因此不能只凭 workflow 文件宣称固定
commit 的 Windows job 可重放。

### CMake xsimd 架构探测

即使手工传入正确的 Qt prefix，CMake `4.0.1` + NMake 的实际配置仍显示：

```text
CMAKE_SYSTEM_PROCESSOR=
CMAKE_C_COMPILER_ARCHITECTURE_ID=x64
```

`Formats/xsimd/CMakeLists.txt:15-18` 只用空的
`CMAKE_SYSTEM_PROCESSOR` 判断 x86，因而没有生成
`xsimd_sse2` 和 `xsimd_avx2`。主 `xsimd` 仍编译并引用 SIMD 函数，最终
`diec` 链接产生 46 个 `LNK2019` 和一个 `LNK1120`。增量重现返回退出码 `2`；
外部原始日志 SHA-256 为
`c7757f813abdfe57b7727f8e8003735024748ab4334458589c0a0fcff683e9e5`。

命令行传入 `-DCMAKE_SYSTEM_PROCESSOR=AMD64` 后，平台初始化仍将变量恢复为空，
所以它不是可靠 workaround。修复官方 CMake 路径需要单独验证 toolchain/platform
设置或上游源码修复；本基线没有修改上游源码来掩盖该缺陷。

## qmake 构建路径

上游 qmake 工程对 SIMD 有显式顺序：

- `Formats/xsimd/xsimd.pro` 先列出 `xsimd_sse2`、`xsimd_avx2`，再列出
  `xsimd`；
- `xsimd.depends = xsimd_sse2 xsimd_avx2`；
- 主 xsimd 工程显式链接两个 MSVC `.lib`。

从完整、tracked-clean 的递归检出运行：

```powershell
tools\upstream\build_windows_qt5_oracle.ps1 `
  -SourceDir <recursive-die-source> `
  -QtDir <qt-root>\5.15.2\msvc2019_64 `
  -VsDevCmd "<vs2019>\VC\Auxiliary\Build\vcvars64.bat" `
  -BuildDir <external-build-dir> `
  -JomPath <qt-tools>\jom.exe `
  -Jobs 4 `
  -OutputJson <external-build-dir>\identity.json
```

脚本在构建前拒绝：

- 非固定 DIE-engine/rules commit；
- 不是恰好 58 个 clean recursive submodule；
- 主仓库或任一 submodule 的 tracked 修改；
- Qt 版本、qmake spec 或三个关键 Qt 文件 hash 不匹配。

随后依次构建 `sub-build_libs-release` 和
`sub-console_source-release`。qmake 会在 submodule 中生成未跟踪 `libs/`，
并在主源码树生成未跟踪 `build/`；这些是构建产物，不应提交。一次完整 clean
build 使用 jom 4 workers 耗时 `287,880 ms`。

## 产物与运行检查

clean build 产物：

| 属性 | 观测值 |
| --- | --- |
| Path | `<source>/build/release/diec.exe` |
| Version | `die 4.0.0` |
| Size | `3,236,352` bytes |
| SHA-256 | `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e` |

`dumpbin /dependents` 显示直接依赖为 Qt5Script、Qt5Core、MSVC/Universal CRT 和
Kernel32。archive、Capstone 和 xsimd 等上游依赖以静态 `.lib` 进入 CLI；Qt 与
MSVC runtime 仍是动态依赖。

项目生成语料 `minimal-pe64.exe` 的 SHA-256 为
`63c706607b3d34624313df7356702ff99ce4080f09e6b07ec4b01dfe4dd5e1c3`。
使用固定主规则目录执行 `-j -D <db> <sample>` 得到：

```text
exit code:    0
stdout bytes: 489
stdout SHA:   12362e46500734dd6400230460718e7e100fddb39d069b9249d4d765034455c0
stderr bytes: 0
```

结构化投影为 `PE64`、offset `0`、size `512`、parent part `Header`，唯一值为
`Unknown: Unknown`。初步构建和后续 clean-script 构建的原始 stdout/stderr
hash 相同。

## 26 样本 Windows 基线

[`collect_windows_cli_baseline.py`](../../tools/upstream/collect_windows_cli_baseline.py)
在运行前验证固定 source/rules commit、58 个递归 submodule、tracked-clean
状态、Qt 文件哈希、CLI 哈希，以及生成语料清单与版本化
[`baseline-corpus.json`](data/baseline-corpus.json) 逐字节一致。

采集范围是：

- version、help、no-args、show-structs、show-database 和 missing path 六个 case；
- 26 个安全生成样本各一次默认 JSON scan；
- 每项连续执行两次，共 64 次，分别保存原始 stdout/stderr 长度和 SHA-256；
- 每个 JSON detection tree 与固定 Linux Qt5 qmake/CMake 相同投影比较。

两次完整采集生成的报告 SHA-256 均为
`6beba732e88d90ed1414dd2584a4a783eac24dec70103fc54e6214eb12cca998`。
结果为 0 个 determinism failure、0 个 Linux projection failure。Windows 的
version stdout 是 11 bytes，而 Linux 为 10 bytes；报告保留 CRLF 导致的原始
hash 差异，只在跨平台比较时使用明确的 detection projection 和退出码，不让
normalizer 隐藏平台原始字节。

这批证据直接覆盖单文件默认扫描、基本 CLI 控制以及 PE/ELF/Mach-O、DEX/
Java/PYC、PDF/CFBF 和 Binary fallback 的 baseline dispatch。单独看该报告
不覆盖后续章节的 option/output/special/path/nested/database，也不覆盖
engine-only harness，因此不足以把 Windows 的 68 行整体接纳为 runtime
baseline。

## Windows CLI option/output/special 矩阵

[`collect_windows_cli_matrix.py`](../../tools/upstream/collect_windows_cli_matrix.py)
复用 `compare_cli_oracles.py` 中已经固定 Linux 报告的 case 定义，不复制选项
表。采集器同时校验 source/rules、58 个 submodule、Qt、二进制、语料和默认
Windows 报告身份，并将两个 helper 的 SHA-256 写入结果。

固定范围为：

- 26 个样本 × 8 个 scan case × 两轮：416 次；
- 与 Linux 矩阵相同的 5 个样本 × 7 个 output case × 两轮：70 次；
- 同 5 个样本 × 19 个 entropy/info/struct case × 两轮：190 次；
- 总计 338 个 case、676 次原生进程执行。

报告 SHA-256 为
`0ab0b636361da958ad6ac32272f9ce261c830e2f3654bc42d99a2dfd474be959`，
结果为 0 个 determinism failure、0 个默认基线 continuity failure 和
0 个 Linux Qt5 exit-code failure。26 个 scan `default` 均与前一份 Windows
报告的两轮 raw summary 和 detection tree 相同。与 Linux 报告重叠的 35 个
output、40 个 scan 和 95 个 special case 均保持退出码及空 stderr；170 个
stdout 原始哈希和长度全部不同，主要可观察来源是 CRLF 与平台路径表示，因此
没有把 raw stream 误报为跨平台逐字节相同。

26-sample scan 还扩大了固定增量集合：deep/aggressive 仍无增量；heuristic、
alltypes、format、hideunknown 和 combined 的逐样本变化保存在机器报告中。
该报告本身没有覆盖后续独立报告中的 nested/path/database，也没有覆盖
engine-only；其余 21 个样本的 special 扩展由下一节的独立报告补齐，但这些
engine-only 和跨平台缺口仍使完整 Windows capability baseline 未被接纳。

## Windows CLI 剩余 21 样本普通 output 矩阵

独立调研
[`windows-output-matrix-extension.md`](windows-output-matrix-extension.md)
将 7 个普通 output case 扩展到首轮未覆盖的 21 个 baseline 样本。147 case
各运行两次；机器报告 SHA-256 为
`672370ebb6f689366098af2e2262be60569a37f7f80c781a1b49b044c4887376`。

294 次执行全部稳定、退出 `0` 且 stderr 为空；21/21 JSON 等于 Windows 默认
reference，21/21 all-flags 等于 CSV。`Mach-O FAT`、`Java Class`、
`Python Bytecode` 和 `ISO 9660` 被直接用作动态 XML element name，因空格使
4 个 XML 文档稳定无效；其余 17 个可解析。普通 output 现覆盖全部 26 个
baseline 样本。

## Windows CLI 剩余 21 样本 entropy/info/struct 矩阵

独立调研
[`windows-special-matrix-extension.md`](windows-special-matrix-extension.md)
将首轮 19 个 special case 扩展到剩余 21 个 baseline 样本。399 case 各运行
两次；机器报告 SHA-256 为
`194f1a1610a18f8fe22814315e67e345ed967c3f61df2604ac3089abbc538cc2`。

798 次执行全部稳定、退出 `0` 且 stderr 为空；9 类 JSON、2 类 XML 及 8 类
非空 UTF-8 输出全部有效。entropy/info 的 all-output-flags 分别等于自身 JSON；
entropy/info/struct 组合等于 entropy JSON，info/struct 组合等于 struct Hash
JSON。Windows 的 19-case special matrix 现覆盖全部 26 个 baseline 样本。

## Windows CLI path/nested 矩阵

[`collect_windows_cli_path_nested.py`](../../tools/upstream/collect_windows_cli_path_nested.py)
继续复用 `compare_cli_oracles.py` 的 14 个 path case 和 4 个 nested case。
它要求生成目录中的 manifest 与版本化 `path-corpus.json`、`nested-corpus.json`
逐字节一致，并重新验证 source/rules/submodule、Qt 和二进制身份。

固定范围为：

- 14 个目录、空目录、多目标、重复、缺失+存在及 formatter path case，各两轮；
- 8 个 archive/resource/overlay 样本 × default/recursive/aggressive/
  recursive+aggressive，各两轮；
- 共 46 个 case、92 次原生 Windows 进程执行。

机器报告 SHA-256 为
`e877e112deb244ab1cbf9edf221e94e155cda711a182f216478eeaf9da40e21b`。
结果为 0 个 determinism failure，46/46 退出码、14/14 去除平台根目录后的
filename-prefix 顺序、32/32 nested detection tree 与 Linux Qt5 一致。
Windows path 的 13/14 个 raw stdout 与 Linux 不同，空目录的空 stdout 相同；
32 个 nested raw stdout 全部不同。stderr 均为空，JSON/XML formatter validity
逐项一致。报告保留这些 raw hash 差异，没有让相对路径或 detection projection
比较掩盖平台字节。

该 path 树只覆盖 5 个普通文件，不能替代 Unicode/非 UTF-8、reparse point、
权限、深目录、4096 项和 filesystem ordering 的 Windows 实验。nested 矩阵
只覆盖发布 CLI 暴露的 recursive/aggressive 组合；archive/resource 的
engine-only 控制仍需原生 harness。

## Windows CLI database success/error 矩阵

[`collect_windows_cli_database.py`](../../tools/upstream/collect_windows_cli_database.py)
复用 `compare_cli_oracles.py` 的 18 个 release CLI database case，要求生成
fixture manifest 与版本化 `database-fixture.json` 逐字节一致，并重新验证
source/rules/submodule、Qt 和二进制身份。每个 case 连续运行两次，共 36 次。

机器报告 SHA-256 为
`13e58a8d1b0cc4feb3998c06140e0afe7adb754cb59e5198b0e5b3079a3d5f8c`。
结果为 0 个 determinism failure；18/18 退出码、`Cannot load database:`
可见性和 JSON validity 与 Linux Qt5 相同。18 个 Windows raw stdout 均因
路径或换行不同；报告另执行受限 normalization：

1. 将每个实际 Windows path argument 替换成同 case 的原始 Linux argument；
2. 将 CRLF 替换为 LF；
3. 不解析/重排 JSON，不删除或改写诊断，不进行其他空白变换。

处理后的 18/18 stdout SHA-256 与 Linux Qt5 原始 stdout 相同。malformed rule
仍保留 `SyntaxError: Parse error`，throwing rule 仍保留
`Error: database fixture`，两者继续破坏 JSON framing；所有 stderr 为空。

该矩阵覆盖 missing/empty/invalid/malformed/throwing/valid main、missing
extra/custom 和 entropy/info load-error framing。ZIP archive 由下一节的
独立矩阵覆盖；ACL/permission-denied database、不可读 input 和 engine-only
cache harness 仍不在本矩阵范围内。

## Windows CLI ZIP database 矩阵

[`collect_windows_cli_database_archives.py`](../../tools/upstream/collect_windows_cli_database_archives.py)
复用 Linux `probe_database_archives.py` 的 17 个 case，并验证相同 fixture、
source/rules/submodule、Qt、二进制和固定 Linux 报告身份。每个 case 连续运行
两次，共 34 次。

机器报告 SHA-256 为
`53c673620cc4388f0da7ffe36af7a325a099bceb0e29912c1f733119f942d748`。
结果为 0 个 determinism failure；17/17 exit code 和 stderr、10/10 JSON
validity、17/17 受限 path/CRLF normalization 后 stdout 与 Linux Qt5 相同。
完整、空、无 EOCD、只含 local record、两种 payload 截断、local-header
截断、重复 entry、`..` entry 和额外根前缀的行为均被固定。详见
[`windows-database-archive-behavior.md`](windows-database-archive-behavior.md)。

该矩阵本身不覆盖 Windows 原生 `bUseCache=true`、cache/app-data ACL、
不可读 database 或 cache write denial；这些由下一节的独立 engine harness
覆盖，不改变发布 CLI 的 `bUseCache=false` 可达性。

## Windows engine database cache/DACL 矩阵

[`build_windows_database_cache_harness.ps1`](../../tools/upstream/build_windows_database_cache_harness.ps1)
只替换固定 qmake Release 构建的 `main_console.obj`，继续链接同一批未修改
engine objects。Windows adapter 把 POSIX file time/mode cases 映射为 Qt file
time 和当前用户 SID 的真实 DACL deny/restore，并启用 Qt test mode 隔离
app-data cache。

[`collect_windows_database_cache_harness.py`](../../tools/upstream/collect_windows_database_cache_harness.py)
在非提升 token 下连续运行两轮 19-case harness。机器报告 SHA-256 为
`d1cbcbe741e4cf3999f54f4696f6eee59472b59bd3aaf9d98f94bb337b1e16da`；
两轮 raw stdout/stderr 逐字节相同。19/19 load/cancel/count/scan/
cache-existence 投影与 Linux Qt5 相同，18/18 非身份关系成立。

Windows populated cache 为 403 bytes，比 Linux Qt5 多 4 bytes；三类
empty cache 两侧均为 42 bytes。cache write deny 静默且非致命，DACL 恢复后
重建；继承 DACL 拒绝整棵 database tree 时成功加载 0 records 并写空 cache；
拒绝 ZIP file read 时 load 返回 false；canceled miss 同样产生可被后续命中的
poisoned empty cache。详见
[`windows-database-cache-behavior.md`](windows-database-cache-behavior.md)。

## Windows CLI Unicode/特殊路径矩阵

[`generate_windows_special_path_fixture.py`](../../tools/corpus/generate_windows_special_path_fixture.py)
从固定 `minimal.pdf` 构造原生 Windows 目录，并生成版本化
[`windows-special-path-fixture.json`](data/windows-special-path-fixture.json)。
fixture 包含 12 个可表示目标，并明确列出默认 Win32/NTFS 模型无法与 Linux
一比一表达的 6 类控制：

- 尾随空格被默认 Win32 path parsing 裁剪；
- colon 选择 NTFS alternate data stream，backslash 是目录分隔符；
- TAB/LF 属于 Win32 禁止的 U+0001..U+001F；
- Windows path identity 是 UTF-16，不能表达三个任意 raw-byte basename；
- 默认大小写不敏感目录中 `A-case.pdf`/`a-case.pdf` 互为别名。

[`collect_windows_cli_special_paths.py`](../../tools/upstream/collect_windows_cli_special_paths.py)
对 12 个单目标以及目录、Unicode 目录、显式三目标顺序、前导短横线有/无
terminator 共 17 个 case 各运行两次。机器报告 SHA-256 为
`f4e2f4ced3190a51df3bfa34cbdf8ad949130aadab324c7e725365a2c7fa8e68`；
结果为 0 个 determinism、expected-exit 或 minimal-PDF projection failure。

特殊目录的稳定顺序为：

```text
leading_space, leading_dash, dot_hidden, ascii, upper_case,
emoji, nfd, space, nfc, cjk
```

去除 Windows 特有的 `dot_hidden` 后，与 Linux 共同可表示的 9 项相对顺序完全
相同。NFC/NFD 是两个独立文件；显式 `emoji -> NFC -> ASCII` 保持 argv 顺序；
相对 `--leading-dash.pdf` 仍需 `--` terminator。Windows 上 `.dot-hidden.pdf`
本身没有 Hidden attribute，因此被 `QDir` 枚举；设置
`FILE_ATTRIBUTE_HIDDEN` 的 `attribute-hidden.pdf` 被排除。这与 Linux 上点号
文件由名称过滤的机制不同，但可观察目录结果都不包含真正的 hidden control。

该矩阵本身不覆盖 UNC/extended-length path、junction/reparse/cycle、ACL
denial、alternate data stream 或大小写敏感目录；其中普通长度 `\\?\` 与
Junction 的独立证据见下一节。

## Windows CLI Junction/扩展命名空间矩阵

独立调研
[`windows-filesystem-behavior.md`](windows-filesystem-behavior.md) 使用 4 个固定
PDF 和 4 个有限 Junction 构造 8 个 case，每项运行两次。机器报告 SHA-256 为
`bab9ce41f5bc82e56cba42a2d577669e8d8a6a372da030b0957fcb8b888fa02f`。
16 次执行全部稳定、退出 `0` 且 stderr 为空；显式 Junction 文件、Junction
目录和两跳 Junction 链均得到固定 `minimal.pdf` detection tree。

父目录同时包含 `alias -> real` 和 `real` 时，上游按 alias→real 扫描同一底层
文件两次，不做目标身份去重。普通长度的 `\\?\` 文件和 Junction 目录输出与普通
Win32 path 逐字节相同。普通用户无法创建 symbolic link，因此本轮不把 Junction
行为泛化为其他 reparse tag；UNC、dangling/cycle 和 ACL denial 仍是显式
缺口。alternate data stream 的独立证据见后文。

## Windows CLI 超过 MAX_PATH 的路径矩阵

独立调研
[`windows-long-path-behavior.md`](windows-long-path-behavior.md) 构造相对路径
本身达到 324/325 code units 的两个 PDF 和一个短 control。7 个 case 各运行
两次；机器报告 SHA-256 为
`54084feff726a1da17e8b4b7ff40eed46733bd6eb2f5f900e4f02ec43bfb6cf5`。

普通和 `\\?\` 显式文件、普通和 `\\?\` 深目录、普通和 `\\?\` 短 discovery
root 全部成功扫描。14 次执行均退出 `0`、stderr 为空、JSON 有效；detection
tree 与固定 `minimal.pdf` reference 相同，且 stdout 与短 control 逐字节相同。
这关闭真实超过传统 260-character boundary 的首轮缺口，但不覆盖精确
32,767 namespace 上限、UTF-16 supplementary character 计数或 UNC 长路径。

## Windows CLI NTFS Alternate Data Stream 矩阵

独立调研
[`windows-ads-behavior.md`](windows-ads-behavior.md) 在
`carrier.bin` 默认 stream 保存 `plain.txt`，在 `:payload.pdf` named stream
保存 `minimal.pdf`。5 个 case 各运行两次；机器报告 SHA-256 为
`bfdec0a8a516dd5d86721a9331d1d914c7e66f29df0fe0d6115c6dcca079224e`。

显式普通和 `\\?\` named stream 均按 PDF 内容检测，stdout 与独立 PDF control
逐字节相同；扫描父目录只得到 carrier 默认 stream 的 Plain text detection，
不会把 named stream 当作独立目标。10 次执行全部稳定、退出 `0`、stderr 为空
且 JSON 有效。目录 stream、其他 NTFS stream type、Unicode/大小写/长度组合
仍未覆盖。

## 可重复性边界

当前证据证明“从一次独立 clean recursive checkout 可重复构建并运行”，不证明
bit-for-bit reproducible：

- 位于不同绝对路径的初步产物大小相同、行为输出相同，但可执行文件及静态库
  SHA-256 不同；
- 初步源树此前经过一次 CMake configure，因此两次产物不是严格同输入实验；
- MSVC archive/PE 时间戳、绝对路径和其他非确定输入尚未逐项隔离；
- 已完成 6 个控制 case、26 样本默认 JSON baseline、全 26 样本 scan、
  全 26 样本普通 output 和全 26 样本 19-case special，并完成首轮
  path/nested/database；尚未运行
  UNC、精确 namespace 上限、symbolic link/reparse cycle、domain/group
  DACL、network share/EFS/integrity level 和其他 engine-only 矩阵；
- 尚未验证 x86、ARM64、完整 GUI/lite、install/package 和官方 release zip；
- `cl` 对 x64 的 `/arch:SSE2` 给出 D9002 ignored warning；x64 ABI 本身要求
  SSE2，但该 warning 仍应保留在构建日志中。

下一步扩展原生采集器的 UNC、精确 namespace 上限、symbolic link/reparse
cycle、domain/group DACL、network share/EFS/integrity level 和其他
engine-only 行；然后
独立处理官方 CMake 路径和二进制
确定性。macOS 固定构建仍是三平台基线的剩余大项。

## 上游证据

- [Windows x64 workflow](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/.github/workflows/builder.yml#L219-L249)
- [`build_win_generic_check.cmd`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_win_generic_check.cmd)
- [`die_source.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/die_source.pro)
- [`build_libs.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_libs/build_libs.pro)
- [`Formats/xsimd/CMakeLists.txt`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/CMakeLists.txt)
- [`Formats/xsimd/xsimd.pro`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xsimd.pro)
