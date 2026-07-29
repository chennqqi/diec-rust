# CLI 依赖闭包与许可证初审

Status: Draft

Upstream: https://github.com/horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-29

## 目的与范围

本文回答固定版本 `diec` 命令行目标实际包含哪些 horsicq 组件、哪些 native
静态库进入链接闭包，以及仓库根许可证是否足以覆盖随仓库携带的第三方代码。

本轮是静态源码和 CMake 调研，不是成功构建记录。结论固定到
[`upstream/components.lock.toml`](../../upstream/components.lock.toml) 中的 commit。
机器可读的组件边、LICENSE blob 和第三方证据位于
[`data/cli-dependencies.toml`](data/cli-dependencies.toml)。

## 方法

在 Windows、Git 2.x 环境中按 lock 的精确 SHA 获取对象，不读取浮动分支：

```sh
git fetch --no-tags --no-write-fetch-head <repository> <commit>
```

对每个对象执行：

```sh
git show <commit>:<build-file>
git ls-tree -r --name-only <commit>
git rev-parse <commit>:LICENSE
git grep -n -i -E "license|public domain|GNU General Public License" <commit>
```

检查范围包含下列 16 个直接组件：

```text
Detect-It-Easy  die_script       XOptions       XEntropyWidget
XFileInfo       XScanEngine      Formats        XDEX
XPDF            XArchive         XStaticUnpacker XDisasmCore
XCapstone       SpecAbstract     XCppfilt       XYara
```

这 16 个固定 commit 均不存在 `.gitmodules`。因此 CLI 核心范围没有第二层 Git
submodule；它们的外部代码以普通 vendored tree 存在，不能靠 gitlink 清单完成许可证
审计。

## `diec` 源码闭包

主仓库
[`src/console/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/CMakeLists.txt)
直接 include 四组源码：

- `die_script/die_script.cmake`
- `XOptions/xoptions.cmake`
- `XEntropyWidget/entropyprocess.cmake`
- `XFileInfo/xfileinfo.cmake`

这些 CMake include 使用变量守卫避免重复加入源码。合并各固定组件的 include 关系后，
闭包如下：

```text
diec
├─ die_script
│  ├─ XDisasmCore ── Formats/xbinary + XCapstone
│  ├─ XScanEngine
│  │  ├─ Formats
│  │  ├─ XDEX
│  │  ├─ XPDF
│  │  ├─ XArchive
│  │  ├─ XStaticUnpacker
│  │  ├─ XOptions
│  │  └─ XDisasmCore
│  └─ Detect-It-Easy
├─ XOptions
├─ XEntropyWidget/entropyprocess ── Formats
└─ XFileInfo
   ├─ Formats / XDEX / XPDF / XArchive
   ├─ XDisasmCore / XOptions / die_script
   └─ SpecAbstract ── XScanEngine
```

固定源码证据：

- [`die_script.cmake`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cmake)
- [`xscanengine.cmake`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cmake)
- [`xfileinfo.cmake`](https://github.com/horsicq/XFileInfo/blob/88b8e2821f86d309f141b38c4d46fa0b000aa74b/xfileinfo.cmake)
- [`xformats.cmake`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xformats.cmake)
- [`xarchive.cmake`](https://github.com/horsicq/XArchive/blob/0fcd4e8d3e9933baac3b12246d82ac026557ffd0/xarchive.cmake)
- [`xdisasmcore.cmake`](https://github.com/horsicq/XDisasmCore/blob/c5757cc007d3ddd419e4db9bd46be00e244644b6/xdisasmcore.cmake)

`Formats ↔ XDEX/XPDF/XArchive` 等关系形成源码 include 环，但 `*_SOURCES`
变量守卫使其成为一次性聚合，而不是 CMake target 的循环链接。Rust 架构设计不能直接把
这个 include 图等同于 crate 图。

## 静态库和系统库链接边界

固定版本 `diec` 的 `target_link_libraries` 明确包含：

| 类别 | 目标 |
|---|---|
| 上游 vendored static targets | `xsimd`、`bzip2`、`lzma`、`zlib`、`capstone_x86`、`ppmd` |
| Qt | `Core`、`Concurrent`，Qt 5 使用 `Script`，Qt 6 使用 `Qml` |
| Windows only | `Wintrust`、`Crypt32` |

主
[`src/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/CMakeLists.txt)
还默认创建 `cppfilt`、通用 `capstone`、`XArchive`、`yara` 等 target，但
`cppfilt` 和 `yara` 没有出现在 `diec` 的直接或已观察到的传递链接列表中。因此当前证据
只能证明它们属于默认构建图，不能证明其代码进入 `diec` 二进制。

固定 Linux Qt5 CMake 的这一区分现已由
[`product-source-closure.md`](product-source-closure.md) 用 byte-identical
链接重放、GNU ld map 和 237-source 清单复核；其他平台、qmake、GUI 与发布包
仍须分别建立闭包。

## 组件根许可证

16 个组件的根 `LICENSE` 首行均为 `MIT License`。每个固定 LICENSE 的 Git blob SHA
已写入机器可读附件。多个仓库的 blob 不相同，主要原因是版权年份或版权人不同，因此发布
归属文件不能只保留一份通用 MIT 文本。

根 LICENSE 只能说明组件自身的授权声明，不能覆盖其中来源不同、带独立文件头或独立
LICENSE 的 vendored 代码。

## 已观察到的 bundled code 许可证

| 所有者/路径 | 是否进入当前 `diec` 链接闭包 | 固定版本证据 | 初步分类 |
|---|---:|---|---|
| `Formats/xsimd` | 是 | `xsimd/src/xsimd.c` 文件头 | MIT；该目录是 horsicq 自有实现，不是同名外部 C++ xsimd 项目的快照 |
| `XCapstone/3rdparty/Capstone` | 是 | `LICENSE.TXT`、`LICENSE_LLVM.TXT` | BSD-3-Clause；部分来源另有 NCSA/LLVM license |
| `XArchive/3rdparty/bzip2` | archive 在 link line；8/8 member 未抽取 | `src/LICENSE`、GNU ld map | bzip2 许可；仍是构建/archive 内容，不是本配置最终 ELF member |
| `XArchive/3rdparty/lzma` | archive 在 link line；`LzmaDec.c.o` 1/2 被抽取 | `LzmaDec.c`、GNU ld inclusion reason | Igor Pavlov Public Domain；最终五文件依赖闭包已固定 |
| `XArchive/3rdparty/ppmd` | archive 在 link line；4/4 member 未抽取 | `Ppmd7.c`、GNU ld map | Public Domain；仍是构建/archive 内容 |
| `XArchive/3rdparty/zlib` | archive 在 link line；8/8 member 未抽取 | `src/zlib.h`、GNU ld map | zlib License；仍是构建/archive 内容 |
| `XArchive/Algos` | 是，作为聚合源码 | `xarchive.cmake`、RAR 官方归档/token 来源报告 | Brotli/Zstd 已追溯；RAR decoder 与官方自报 UnRAR 7.13 高度重合但 notice/acknowledgments 不一致；其余实现仍待逐文件分类 |
| `XArchive/Algos/xucldecoder.cpp` | 是；84 个 direct object 之一 | product source closure、官方 UCL 1.03 来源映射 | 外层 horsicq MIT；内嵌 UCL 技术分类为 GPL-2.0-or-later，XArchive 缺失 `ACC_LICENSE`；组合与不同书面授权仍须评审 |
| `XCppfilt/3rdparty/cppfilt` | 否；默认构建 target | `cp-demangle.c` 等文件头 | GPL-2.0-or-later，并带文件级不限制链接的额外许可；另有 Public Domain 文件 |
| `XYara/3rdparty/yara` | 否；51-object 默认构建 target | 官方 YARA v4.5.2 内容映射与 109-file `.o.d` closure | 主体为 BSD-3-Clause；vendored tree 未保存官方 `COPYING` |
| YARA 生成 parser 文件 | 否；6 个 `.c/.h` 实际进入 `yara` closure | `grammar.c/.h`、`hex_grammar.c/.h`、`re_grammar.c/.h` | GPL-3.0-or-later + Bison parser-skeleton special exception |
| YARA bundled TLSH | 否；6 个文件实际进入 `yara` closure | YARA PR #1624 → `avast/tlshc@bb91fef...` blob chain | Apache-2.0 OR BSD-3-Clause；缺失原 `LICENSE`/Trend Micro `NOTICE.txt` |
| YARA Authenticode parser | 否；当前无 `HAVE_LIBCRYPTO`，10/10 未进入 closure | 10 个 Avast 文件头与 `.o.d` | MIT；启用 OpenSSL 后必须重审 |
| `XArchive/3rdparty/lzfse` | 当前 CMake target 未包含 | `src/LICENSE` | BSD-3-Clause；存在于源码树不等于进入当前产物 |

上述分类是源码证据摘要，不构成法律意见。尤其不能把仓库根 MIT 机械地应用于
`libiberty`、Capstone、YARA、bzip2、zlib 或其他第三方文件。

## 对兼容范围的事实约束

- `--entropy` 并非 GUI 依赖：CLI 只编译 `XEntropyWidget` 中的
  `entropyprocess` 非 UI 子集。
- `--info`/`--struct` 把 `XFileInfo`、`SpecAbstract` 和扫描/规则闭包带入 CLI。
- 上游在 CLI 编译时无条件定义 `USE_DEX`、`USE_PDF`、`USE_ARCHIVE`、`USE_XSIMD`；
  这些格式不能在未建立行为证据前从兼容范围删除。
- `yara` target 和 YARA 数据是否属于 `diec` 可观察能力是两个不同问题。
  [`rule-asset-provenance.md`](rule-asset-provenance.md) 已进一步验证固定 CLI
  source list、入口和 link line：YARA、PEiD、signatures 均无运行时数据入口；
  它们只在 GUI/替代引擎和打包路径可达。
- Rust 重写若采用不同的纯 Rust crate，可以改变依赖实现和许可证组合，但仍需差分证明
  解压、反汇编、格式解析等可观察行为一致。

完整 58 个直接组件的根 LICENSE、commit 和嵌套 `.gitmodules` 已由
[`component-license-inventory.md`](component-license-inventory.md) 补齐：全部根
许可证为 MIT、共有 12 个文本 hash，且没有组件含递归 git submodule。该清单同时
发现 45 个 nested license candidates，但不替代文件级 bundled code 审计。

固定 Linux Qt5 CMake `diec` 的全局产品闭包已由
[`product-source-closure.md`](product-source-closure.md) 收口为 223 个直接对象、
8 个 archive 的 36-built/14-included member 和 237 个 compile source；逐组件
计数、237 个源码 hash、14 个根 LICENSE、AUTOMOC 的 13 组件来源均已绑定。
该清单同时发现实际 direct-link 的 `xucldecoder.cpp` 内嵌 GPL 声明并引用缺失的
`ACC_LICENSE`，记录为 `PRODUCT-LICENSE-GAP-001`。
后续 [`xucl-origin.md`](xucl-origin.md) 将两个内嵌文件固定到官方 UCL 1.03：
合并 12/64-token 覆盖为 94.76%/89.08%，官方源码技术分类为
`GPL-2.0-or-later`，`COPYING` 与 `acc/ACC_LICENSE` 均已精确 hash-bind。
XArchive 未保留正文或 ACC 原版权/GPL 头，书面组合评审仍未完成。

固定 Linux Qt5 CMake CLI 的 XArchive 实际闭包已由
[`xarchive-license-closure.md`](xarchive-license-closure.md) 展开为 84 个直接对象、
22 个 archive 构建对象和 217 个源码/头文件依赖。后续
[`xarchive-final-link-closure.md`](xarchive-final-link-closure.md) 通过
byte-identical 链接重放和 GNU ld map 证明 22 个 member 中仅
`LzmaDec.c.o` 被抽取，最终贡献为 84+1=85 个编译源；另有八个未抽取 member
具有非空最终符号名交集，不能用 `nm` 交集代替 linker map。该证据确认 XYara 未链接进 `diec`，
同时发现实际编译的 Brotli/Zstandard 聚合源没有保留许可证声明。后续
[`embedded-compression-origins.md`](embedded-compression-origins.md) 已把它们
分别固定到 Brotli 1.2.0 MIT 和 Zstandard 1.6.0-dev BSD/GPLv2 官方来源。
[`rar-decoder-provenance.md`](rar-decoder-provenance.md) 又把实际编译的
RAR decoder 固定到自报 UnRAR 7.13 的 RARLAB 官方归档与镜像：官方 150 个
`.cpp/.hpp` 与镜像逐字节相同，decoder 的 12/64-token 覆盖为
94.21%/74.21%。XArchive 文件没有 UnRAR 修改分发 notice 或官方
acknowledgments；书面评审前不得直接复制或翻译进 Rust。

XCapstone/Capstone 的最终 ELF 贡献现已由
[`xcapstone-license-closure.md`](xcapstone-license-closure.md) 固定：
`xcapstone.cpp.o` 直接链接，`libcapstone_x86.a` 构建 11 个 member，但只有
10 个具有最终 ELF 全局符号见证；`MCInstrDesc.c.o` 未被抽取。实际闭包为
11 个 compile source/71 个依赖文件，必须分别保留 XCapstone MIT、Capstone
BSD-3-Clause 和 LLVM University of Illinois/NCSA 文本。

Formats/xsimd 的最终 ELF 贡献也已由
[`xsimd-license-closure.md`](xsimd-license-closure.md) 固定：三个链接 archive
各只有一个 member，三个 member 均有最终 ELF 全局符号见证；实际闭包为三个
compile source/六个依赖文件，全部含 horsicq copyright 与完整 MIT marker。
根 `Formats/LICENSE` 已单独 hash-bind，CUDA 两文件不在该 Linux Qt5 闭包。

XYara/YARA 当前 Linux target 也已由
[`yara-license-closure.md`](yara-license-closure.md) 固定：51 个编译单元、
109 个依赖文件，132 个 vendored YARA 文件全部映射官方 v4.5.2（129 个内容
精确相同、3 个 MSVC compatibility patch）。TLSH 6 文件已追溯到
`avast/tlshc` 的双许可证和 Trend Micro NOTICE；bundled tree 未携带这些文本。
构建同时保留 12 条 `atoms.c -Wstringop-overflow=` warning，尚不能据此判定为
可达越界或 false positive。

## 尚未完成

- 固定 Linux Qt5 CMake CLI 的全局 237-source/link-map 闭包已完成；仍需
  qmake、Qt6、Windows、macOS、GUI 和发布包的对应 object/link/dependency 闭包。
- XUCL 1.03 官方来源和精确 `ACC_LICENSE` 已完成；仍须取得 MIT/GPL 组合、
  不同书面授权和发布责任人的书面结论。
- 为 XArchive 聚合 Brotli/Zstandard 恢复独立 LICENSE/NOTICE/attribution，
  完成 Brotli 剩余约 1.4% token 分类；RAR decoder 的官方源码/条款技术闭包
  已完成，仍须对 UnRAR notice、第三方归属和复用边界取得书面结论；为
  YARA/TLSH 恢复独立
  COPYING/LICENSE/NOTICE，并补 Windows/macOS/OpenSSL/qmake 闭包。
- 区分正常扫描、`--info`、`--struct`、YARA/PEiD 数据和 GUI-only 路径的最小产物闭包。
- YARA/PEiD/signatures 的 CLI 可达性已关闭；其 GUI/辅助 engine 运行闭包、
  第三方数据来源许可和 release artifact 内容仍待关闭。
- 对 Qt 5 与 Qt 6 构建分别记录链接依赖和规则运行时行为。
- 形成发布时必须携带的 LICENSE/NOTICE 清单；在审计完成前不得把当前表当作发布许可结论。
