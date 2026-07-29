# 固定 Linux diec 产品级源码贡献闭包

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux x86_64、Qt 5、CMake Release `diec` 的产品级 compile-source
贡献闭包已形成闭集：

- 223 个直接对象：
  - 13 个 gitlink 组件贡献 220 个；
  - DIE-engine 根 `main_console.cpp` 与 `consoleoutput.cpp` 贡献 2 个；
  - CMake AUTOMOC 生成 `mocs_compilation.cpp` 贡献 1 个；
- link line 中有 8 个项目静态 archive，共构建 36 个 member；
- byte-identical GNU ld map 抽取 14 个 member，排除 22 个；
- 最终合计 223 + 14 = **237 个 compile source**。

机器报告位于
[`data/product-source-closure-linux-qt5.json`](data/product-source-closure-linux-qt5.json)。
它逐一保存 237 个 compile source 的组件、路径、linkage、dependency file、
大小、SHA-256、许可证 marker 和 archive inclusion reason，并绑定此前
XArchive、XCapstone 与 XSIMD 三份 member 级报告。

该清单关闭固定 Linux Qt5 CMake CLI 的“哪些源码实际形成最终产品”技术缺口，
但不关闭跨平台、发布包或法律评审；`P0-BLOCK-004` 继续保持 Open。

## 组件计数

| 归属 | 直接对象 | 抽取 archive member | 最终 compile source |
| --- | ---: | ---: | ---: |
| DIE-engine 根源码 | 2 | 0 | 2 |
| Formats | 37 | 3 XSIMD | 40 |
| SpecAbstract | 30 | 0 | 30 |
| XArchive | 84 | 1 LZMA | 85 |
| XCapstone | 1 | 10 Capstone | 11 |
| XDEX | 2 | 0 | 2 |
| XDisasmCore | 5 | 0 | 5 |
| XEntropyWidget | 1 | 0 | 1 |
| XFileInfo | 4 | 0 | 4 |
| XOptions | 5 | 0 | 5 |
| XPDF | 1 | 0 | 1 |
| XScanEngine | 34 | 0 | 34 |
| XStaticUnpacker | 11 | 0 | 11 |
| die_script | 5 | 0 | 5 |
| CMake AUTOMOC generated | 1 | 0 | 1 |
| **合计** | **223** | **14** | **237** |

AUTOMOC 单元不是可忽略的“构建噪声”。其 `.o.d` 绑定全部 13 个贡献组件的
QObject headers，生成代码由这些输入派生；报告将其单独标记为
`cmake-automoc-generated`，不虚构单一组件归属。

## Archive 闭集

| Archive 组 | Archive 数 | 构建 member | 抽取 | 排除 |
| --- | ---: | ---: | ---: | ---: |
| Formats/XSIMD | 3 | 3 | 3 | 0 |
| XArchive bzip2/LZMA/PPMd/zlib | 4 | 22 | 1 | 21 |
| XCapstone/Capstone x86 | 1 | 11 | 10 | 1 |
| **合计** | **8** | **36** | **14** | **22** |

抽取集合与三份局部报告完全相等：

- [`xarchive-final-link-closure.md`](xarchive-final-link-closure.md)：
  仅 `LzmaDec.c.o`；
- [`xcapstone-license-closure.md`](xcapstone-license-closure.md)：
  10/11，排除 `MCInstrDesc.c.o`；
- [`xsimd-license-closure.md`](xsimd-license-closure.md)：
  三个单 member archive 全部抽取。

全局报告不再使用“link line 出现 archive”或 `nm` 符号名交集代替实际抽取证据。

## 根许可证与文件级 marker

贡献闭包覆盖 DIE-engine 根和 13 个组件。14 个根 `LICENSE` 均存在、hash-bound，
且都含 MIT permission marker；不同文本不能仅保留一份通用 MIT。

237 个 compile source 的保守字符串计数为：

| Marker | 文件数 | 边界 |
| --- | ---: | --- |
| MIT permission | 212 | 不覆盖同文件内的第三方片段 |
| LLVM/NCSA | 4 | Capstone 抽取源码 |
| Public Domain | 3 | LZMA/PPMd wrapper 与 LzmaDec |
| GNU GPL | 1 | XUCL 聚合源码；见下节 |

这些是非互斥字符串标记，不是自动 SPDX 结论。缺少 marker 也不能证明没有许可证
义务；XArchive RAR、Brotli、Zstandard 和 XCapstone 的详细来源结论仍以各自
专项报告为准。

## XUCL 引用缺失的 ACC_LICENSE

`XArchive/Algos/xucldecoder.cpp` 是 84 个 XArchive 直接对象之一，因此确定进入
最终 ELF。固定文件 SHA-256 为：

```text
f2f2fe4e11beaa122c2474a44c7c1c97242e9d211eacc15d0c7f3c646b2a45cf
```

该文件外层有 horsicq MIT header，但内嵌 UCL 1.03 源码在第 842 行声明其工作按
GNU General Public License 授权，并要求查阅 `ACC_LICENSE`。固定 XArchive tree
中不存在任何名为 `ACC_LICENSE` 的文件，也没有其他文件重复该声明。

机器报告将其固定为 `PRODUCT-LICENSE-GAP-001`：

- `linkage=direct-object`；
- `gpl_marker_lines=[842]`；
- `referenced_license_file=ACC_LICENSE`；
- `matching_license_paths_in_component=[]`；
- `classification=release-legal-review-required`。

后续 [`xucl-origin.md`](xucl-origin.md) 已把两个内嵌文件追溯到固定官方
UCL 1.03 归档：合并 12/64-token shingle 覆盖为 94.76%/89.08%，官方源码头为
GPL-2.0-or-later，且官方 `COPYING` 与 `acc/ACC_LICENSE` 都是 GPL v2 正文。
XArchive 仍没有保存该正文，`xucldecoder_acc.h` 还省略官方 ACC 版权/GPL 头。
这证明根 MIT 不能代表聚合文件的完整条款；在 MIT/GPL 组合与可能存在的不同书面
授权完成评审前，仍不得直接复制或翻译该 decoder 到 Rust。

## 产品范围分层

本报告只回答编译后的 `diec` ELF 源码贡献，不把不同发布输入混为一类：

| 层 | 本报告状态 |
| --- | --- |
| compile sources | 237 个闭集 |
| runtime `db*` rules/assets | 独立 2,268-file 闭包，不是 compile source |
| XYara/YARA、XCppfilt | 默认 build-only target，不在 `diec` link |
| Qt/系统动态依赖 | 由 deployment-size/runtime dependency 报告管理 |
| GUI/YARA/PEiD/signature 打包资产 | 由 release artifact/provenance 报告管理 |

这一区分防止两类错误：把 build-only 代码误写成 CLI 最终贡献，或因“不在 ELF”
而忽略实际随发布包分发的数据/静态库。

## 固定身份与复现

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| source image | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| component lock SHA-256 | `9fabcaf6a0062fcae7007ea5af13a98876e8a6e08b3e2e4727fdff06d974c63c` |
| link line SHA-256 | `b2a4c7953997137d45f06eb3541d5da2efe127e85905c62311f5e03e5a500afb` |
| original/replayed ELF SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| GNU ld map SHA-256 | `9cdf167d355b6d0aad4d04c100a3602f9aa90139f78ac47be517b2518bf8f566` |

[`audit_product_source_closure.py`](../../tools/upstream/audit_product_source_closure.py)
在固定、禁网、只读挂载的 image 中：

1. 校验主仓库、13 个组件 commit、component lock 和三份前置报告；
2. 解析 223 个 direct object 及其 `.o.d`；
3. 重放原 link tokens 并生成 GNU ld map，要求 ELF 逐字节相同；
4. 枚举八个 archive、36 个 member 与 14 个 inclusion reason；
5. 将所有直接/抽取 compile source 规范化为 237 个唯一身份并逐文件 hash；
6. 绑定 14 个根 LICENSE、AUTOMOC 的 13 组件来源及 XUCL 缺口。

```powershell
python tools\upstream\audit_product_source_closure.py `
  --output docs\research\data\product-source-closure-linux-qt5.json

python -m unittest discover -s tools\tests `
  -p test_product_source_closure.py
```

审计器对 223/220/2/1、8/36/14/22、237、逐组件计数、AUTOMOC 来源、marker
计数、XUCL 第 842 行和缺失 `ACC_LICENSE` 全部 fail closed。报告不保存本机或
`/opt` 路径。

## 对 Rust 实现的约束

- crate/backend 划分应由能力和单向依赖决定，不应照抄 13 组件或 237 源文件图。
- Rust 可以替换 native backend，但每项删除或替换都要由能力矩阵和差分结果证明，
  不能仅以 archive 未抽取为由缩小功能。
- 禁止直接翻译组合授权未评审的 XUCL 与条款未闭合的 RAR decoder；优先选择
  来源、许可证和资源边界明确的纯 Rust 实现。
- Phase 1 建立 workspace 后，最终 Rust staticlib 和 CLI 必须按 target/feature
  自动生成 compile/native/SBOM/NOTICE 闭包，并与本报告的能力范围而非代码行
  做比较。

## 尚未完成

- XUCL 的官方来源、精确 `ACC_LICENSE` 和内容映射已完成；仍缺 MIT/GPL 组合、
  可能存在的不同书面授权及发布责任人的书面评审；
- qmake、Qt6、Windows、macOS 及发布包的同类 product-level closure；
- GUI 与 build-only target 的发布物边界；
- Rust dependency graph、staticlib/CLI archive extraction、SBOM 和 NOTICE；
- 发布/法律责任人的书面结论。
