# CLI 依赖闭包与许可证初审

Status: Draft

Upstream: https://github.com/horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

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

这一区分仍需用实际构建后的 link map 和二进制符号表复核。

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
| `XArchive/3rdparty/bzip2` | 是 | `src/LICENSE` | bzip2 许可 |
| `XArchive/3rdparty/lzma` | 是 | `LzmaDec.c` 等文件头 | Public Domain 声明；需要逐个实际编译文件复核 |
| `XArchive/3rdparty/ppmd` | 是 | `Ppmd7.c` 等文件头 | Public Domain 声明；需要逐个实际编译文件复核 |
| `XArchive/3rdparty/zlib` | 是 | `src/zlib.h` | zlib License |
| `XArchive/Algos` | 是，作为聚合源码 | `xarchive.cmake`、RAR token 来源报告 | Brotli/Zstd 已追溯；RAR decoder 与 UnRAR 7.1.10 高度重合但 notice 不一致；其余实现仍待逐文件分类 |
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

固定 Linux Qt5 CMake CLI 的 XArchive 实际闭包已由
[`xarchive-license-closure.md`](xarchive-license-closure.md) 展开为 84 个直接对象、
22 个 archive 对象和 217 个源码/头文件依赖。该证据确认 XYara 未链接进 `diec`，
同时发现实际编译的 Brotli/Zstandard 聚合源没有保留许可证声明。后续
[`embedded-compression-origins.md`](embedded-compression-origins.md) 已把它们
分别固定到 Brotli 1.2.0 MIT 和 Zstandard 1.6.0-dev BSD/GPLv2 官方来源。
[`rar-decoder-provenance.md`](rar-decoder-provenance.md) 又把实际编译的
RAR decoder 固定到 UnRAR 7.1.10 镜像：12-token 覆盖 94.21%、64-token
覆盖 74.21%，但 XArchive 文件没有 UnRAR 修改分发 notice。书面评审前不得把
该 decoder 直接复制或翻译进 Rust。

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

- 已为 XCapstone 与 Formats/xsimd 保存最终 ELF member 符号见证；其余组件仍需补全 CMake
  target graph、link map、动态依赖和符号表。
- 为 XArchive 聚合 Brotli/Zstandard 恢复独立 LICENSE/NOTICE/attribution，
  完成 Brotli 剩余约 1.4% token 分类，并对 RAR decoder 的 UnRAR notice/
  复用边界取得书面结论；为 YARA/TLSH 恢复独立
  COPYING/LICENSE/NOTICE，并补 Windows/macOS/OpenSSL/qmake 闭包。
- 区分正常扫描、`--info`、`--struct`、YARA/PEiD 数据和 GUI-only 路径的最小产物闭包。
- YARA/PEiD/signatures 的 CLI 可达性已关闭；其 GUI/辅助 engine 运行闭包、
  第三方数据来源许可和 release artifact 内容仍待关闭。
- 对 Qt 5 与 Qt 6 构建分别记录链接依赖和规则运行时行为。
- 形成发布时必须携带的 LICENSE/NOTICE 清单；在审计完成前不得把当前表当作发布许可结论。
