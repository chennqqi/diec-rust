# 上游基线

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-29

## 结论摘要

本轮调研将 DIE-engine 基线固定为：

| 项目 | 值 |
| --- | --- |
| Repository | `https://github.com/horsicq/DIE-engine` |
| Branch | `master` |
| Commit | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Commit time | `2026-07-24T18:30:29Z` |
| Commit subject | `Update submodules to latest versions` |
| `release_version.txt` | `4.0.0` |
| Submodule count | 58 |
| Main license | MIT |

固定 SHA 是兼容性实验的唯一身份；文档中的日期或版本号不能替代 SHA。

## 获取方式

```sh
git clone https://github.com/horsicq/DIE-engine.git
git -C DIE-engine checkout 74eaf505c250ab47e709024e9dc41657cd8f2254
git -C DIE-engine submodule update --init --recursive
git -C DIE-engine submodule status --recursive
```

仓库中的 subtree 只物化主仓库和规则数据；Linux qmake/CMake CLI 实验会在隔离
容器中从固定 SHA 初始化全部 58 个直接 submodule。构建、产物和可重复性边界见
[`upstream-build-baseline.md`](upstream-build-baseline.md) 与
[`upstream-cmake-differential.md`](upstream-cmake-differential.md) 与
[`upstream-qt6-differential.md`](upstream-qt6-differential.md)。实验尚未
覆盖完整发布打包及 Windows/macOS，因此本文件仍为 Draft。

本仓库目前还物化了两个可审计快照：

- `upstream/DIE-engine/`：主仓库 squash subtree。
- `upstream/Detect-It-Easy/`：与主仓库 gitlink 一致的规则/发布数据 squash subtree。

其他核心 submodule 目前只在 `upstream/components.lock.toml` 锁定 SHA，源码分析使用外部临时 checkout。该状态不等同于完整 recursive build checkout。

## 完整性记录

| 文件 | SHA-256 |
| --- | --- |
| `LICENSE` | `BE0FE2D727CD0A754FB0B2FDC579EAD8F19EF575840B4DAEF221BE201701EAAD` |
| `.gitmodules` | `7AA824AFAC7F4C74A995519989A9089EF1FA23022E4A9570667A7785B173ACB9` |

主仓库 `LICENSE` 为 MIT License，copyright 为 `2012-2026 hors<horsicq@gmail.com>`。本轮检查的 `Detect-It-Easy`、`Formats`、`StaticScan`、`XScanEngine`、`die_script`、`signatures`、`XOptions`、`XFileInfo` 和 `XEntropyWidget` 均有以 `MIT License` 开头的独立 `LICENSE` 文件。固定 XScanEngine external research checkout 的 LICENSE SHA-256 为 `ac4f868b0034a4047dd1394409e412a25b03013a42f75f20fb0a4f9b4692a827`，其 HostApi 头文件清单见 [`host-api-inventory.md`](host-api-inventory.md)。

完整 58 个直接组件均已固定根 LICENSE path/hash，全部首行为 MIT，且确认没有嵌套
`.gitmodules`；58 份根文本有 12 个不同 hash。机器清单与限制见
[`component-license-inventory.md`](component-license-inventory.md)。这仍不是完整
许可证审计：bundled code 文件头、构建工具及测试样本仍需逐项核对。YARA、
PEiD 与 signatures 数据已完成固定路径/hash/可见标记审计，但多项第三方来源
许可仍未关闭，见
[`rule-asset-provenance.md`](rule-asset-provenance.md)。

## Submodule 基线

主仓库记录 58 个直接 submodule。完整名称如下：

```text
Detect-It-Easy Formats SpecAbstract StaticScan XArchive XQwt XOptions
XStyles XTranslation XDEX FormatDialogs FormatWidgets Controls
XMemoryMapWidget XEntropyWidget XCapstone XHashWidget die_script die_widget
nfd_widget archive_widget XMIME XSingleApplication XMIMEWidget XHexView
XDisasmView XGithub XShortcuts XHexEdit signatures XDemangle
XDemangleWidget XCppfilt XDynStructs XDynStructsEngine XDynStructsWidget
XFileInfo XPDF XInfoDB XSymbolsWidget XOnlineTools XAboutWidget
hex_templates XExtractorWidget XExtractor XUpdate XVisualizationWidget
XDecompiler XYara yara_widget XDataConvertorWidget XScanEngine
XDisasmCore XRegionsWidget XStaticUnpacker XPEID build_tools peid_widget
```

首轮核心源码分析使用以下主仓库 gitlink：

| Submodule | Commit | 初步角色 |
| --- | --- | --- |
| `Detect-It-Easy` | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` | 发布数据、`db*` 规则库、YARA/PEiD 规则 |
| `Formats` | `1151e7254fdee3c0294ff7095edbdd7bfccf8201` | 二进制格式探测和解析基础 |
| `StaticScan` | `fcdcb25b16d0e0c6b2f82c2b270b2a3d58c1e11d` | 静态扫描相关 UI/模型；与 CLI 范围关系待确认 |
| `XScanEngine` | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` | 扫描编排、结果模型、递归和数据库加载 |
| `die_script` | `5d82316c110abf0eb863b50bc679d330e05067b6` | DIE 规则脚本运行时 |
| `signatures` | `5d80fb2863d02e9366aee7b3ade6abb7d6598dbb` | crypto/junk 二进制签名，不等同于 `db` 脚本规则 |
| `XOptions` | `810d78d0654f45d39bf07bcda5dc92ce287a4aeb` | CLI 选项定义 |
| `XFileInfo` | `88b8e2821f86d309f141b38c4d46fa0b000aa74b` | `--info` 和 `--struct` 信息输出 |
| `XEntropyWidget` | `d2bf95b1019e21e5a5ae71f55fcd6c12349c3030` | `--entropy` 的非 UI 处理代码 |

全部 58 个直接 gitlink 的 repository URL 和 commit SHA 已记录在
[`../../upstream/components.lock.toml`](../../upstream/components.lock.toml) 的
`[gitlink]` 表中，可通过以下命令与基线重复核对：

```sh
python3 tools/verify_upstream.py
```

该清单覆盖主仓库的直接 submodule。固定 source image 审计确认 58 个组件都没有
嵌套 `.gitmodules`，因此 git submodule closure 在本 commit 到此终止；普通
vendored 目录仍需独立 source/license 审计。

## 构建系统静态分析

主入口 [`CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/CMakeLists.txt) 要求 CMake 3.18，并进入 `src/`。

[`src/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/CMakeLists.txt)：

- 自动选择 Qt 5 或 Qt 6。
- Qt 组件包含 Core、Widgets、Concurrent、Network、PrintSupport、OpenGL、Svg、Sql；Qt 5 额外使用 Script/ScriptTools，Qt 6 使用 Qml。
- 添加 `XCppfilt`、`XCapstone`、`XArchive`、`XYara` 和 `Formats/xsimd`。
- 同时构建 `gui`、`console` 和 `lite`。

[`src/console/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/CMakeLists.txt) 为 `diec` 定义：

- C++17。
- 编译开关 `USE_DEX`、`USE_PDF`、`USE_ARCHIVE`、`USE_XSIMD`。
- 链接 `xsimd`、`bzip2`、`lzma`、`zlib`、`capstone_x86`、`ppmd`。
- 链接 Qt Core、Concurrent，以及 Qt 5 Script 或 Qt 6 Qml。
- Windows 额外链接 `Wintrust` 和 `Crypt32`。

仓库也包含 Autoconf 生成物和 qmake `.pro/.pri` 文件。哪个构建入口是各平台发布基线，仍需通过官方 release workflow 和实际构建验证。

## 数据资产

`Detect-It-Easy` 固定版本包含：

- `db/`：Amiga、APK、Archive、AtariST、Binary、CFBF、COM、DEX、DOS16M、DOS4G、ELF、Image、IPA、ISO9660、JAR、JavaClass、JPEG、LE、LX、MACH、MACHOFAT、MSDOS、NE、NPM、PDF、PE、PNG、PYC、RAR、ZIP。
- `db_extra/`：Amiga、COM、ELF、MSDOS、PE。
- `db_custom/`：默认没有规则类别目录。
- `dbs_min/`、`dbs_special/`：用途和发布选择规则待分析。
- `yara_rules/`、`peid_rules/`：固定 `diec` CLI 不加载；Detect release tree
  与 XYara/XPEID component tree 又不是字节镜像。它们属于 GUI/替代引擎及
  发布物审计范围，见
  [`rule-asset-provenance.md`](rule-asset-provenance.md)。

## 尚未完成

- [`component-license-inventory.md`](component-license-inventory.md) 已确认全部
  58 个直接组件 commit/root LICENSE，并证明没有嵌套 `.gitmodules`。
- Linux Qt5 qmake、Qt5 CMake、Qt6 CMake 和 Windows Qt5 qmake CLI 候选
  oracle 已构建。Windows clean build、官方 CMake/xsimd 断点及一个 PE64 smoke
  见 [`windows-qt5-build-baseline.md`](windows-qt5-build-baseline.md)；Windows
  默认 26-sample baseline、首轮 338-case option/output/special 及
  46-case path/nested、18-case database、17-case 特殊路径、8-case
  filesystem、7-case long-path、5-case ADS、剩余 21-sample 普通 output 和
  21-sample special 矩阵已归档；同 special 矩阵的 Linux Qt5/Qt6 raw 与
  Windows structured projection 三方差分，以及同 output 矩阵的 Linux
  Qt5/Qt6/Windows JSON 与有效性差分也已完成。完整能力差分、CMake 发布打包、
  bit-for-bit 验证及 macOS 构建仍待完成。
- release workflow、预编译包与源码构建之间的数据资产差异。
- bundled code、规则原始来源和最终发布组合的许可证审计；YARA/PEiD/signature
  资产路径与可见标记已固定，但 GPL/未知来源仍需书面评审。
- 已采集 Linux Qt5 qmake/CMake 与 Qt6 CMake 产物的链接证据；完整静态依赖与
  发布产物清单仍待采集。
- 已完成自扫描 smoke baseline、26 个项目生成安全样本的默认 JSON/退出码差分
  及 Windows 首轮 option/output/special/path/nested/database 矩阵；特殊路径、
  Unicode/Hidden/前导短横线、Junction/`\\?\`、324/325-code-unit 长路径首轮
  矩阵、显式 ADS/目录不枚举 named stream 及 26-sample 普通 output/special
  以及 17-case ZIP database 也已完成；Linux Qt5/Qt6 的全 26-sample
  output/special 扩展也已完成；Windows 19-case engine cache/DACL harness
  也已完成两轮；新增 37-case engine-contract、CLI option/profiling 和
  10-case rule-orchestration 双轮及 private signature-path engine harness
  双轮、五组 result-model harness 各双轮，再加入 86 次 legacy/archive
  dispatch、debug-data paired harness 双轮、archive-option 128 次及
  count-boundary 22 次执行后，Windows 68 行 closure 已分类为
  66 complete、1 partial、1 missing；
  CLI profiling 保留 `image_ICNS.sg`
  的精确 Windows/Linux 顺序差异，而规则编排 canonical 语义完全相同；
  UNC、精确 namespace
  上限、symbolic link/reparse cycle、domain/group DACL、network
  share/EFS/integrity level、其他 engine-only、畸形矩阵和其余
  跨平台原始输出仍待采集。

## 主要证据

- [主仓库 commit](https://github.com/horsicq/DIE-engine/tree/74eaf505c250ab47e709024e9dc41657cd8f2254)
- [`.gitmodules`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/.gitmodules)
- [`LICENSE`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/LICENSE)
- [`release_version.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/release_version.txt)
