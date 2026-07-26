# 固定上游 58 个组件许可证与递归边界清单

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 范围与结论

本轮对主仓库全部 58 个直接 gitlink 做固定源码清单，不再只覆盖 CLI 核心 16 个：

- 58/58 组件目录存在于固定 CMake Qt5 source image；
- 58/58 `git rev-parse HEAD` 与 `upstream/components.lock.toml` 一致；
- 58/58 组件都没有嵌套 `.gitmodules`；
- 58/58 根目录都有且只有一个 license candidate；
- 58/58 根许可证首个非空行都是 `MIT License`；
- 58 个根许可证共有 12 个不同 SHA-256，不能只保留一份通用 MIT 文本；
- 全组件共发现 103 个按文件名识别的 license candidate：58 个根文件和 45 个
  nested 文件。

机器清单为
[`data/component-license-inventory-linux.json`](data/component-license-inventory-linux.json)。
它固定 image ID/revision、component lock hash、每个组件 commit，以及每个候选
文件的相对路径、长度、SHA-256 和首个非空行。

这些事实关闭“其余 42 个组件是否还有递归 git submodule”和“是否缺少根许可证”
两个清单缺口，但不构成发布许可结论或法律意见。

## Nested license candidates

45 个 nested candidate 只出现在三个组件：

| Component | Count | 范围 |
| --- | ---: | --- |
| Detect-It-Easy | 41 | `autotools/dbcompiler/node_licenses/` 中的 Node 构建工具依赖 |
| XArchive | 2 | bundled bzip2 与 lzfse |
| XCapstone | 2 | Capstone 主许可证与 LLVM/NCSA 来源许可证 |

Detect-It-Easy 的 41 个文件包含 MIT、ISC、Apache、Node.js 等不同文本。它们位于
数据库编译工具路径，不等于发布规则数据或 `diec` runtime 链接了这些 Node 包；
最终产物闭包必须把 build tool 与 shipped/runtime content 分开。

XArchive 的 candidate 只有 bzip2 和 lzfse，但已知实际 CLI 闭包还编译
zlib、LZMA、PPMd 和 `Algos`。这些来源主要通过源码文件头声明，并不一定有匹配
`LICENSE*`/`COPYING*`/`NOTICE*` 文件。因此“103 个候选文件”不是完整 third-party
license inventory，不能用其缺失证明某目录没有独立条款。

XCapstone 同时保存 Capstone BSD-3-Clause 和 LLVM/NCSA 来源文本，发布归属必须
保留两者，不能被组件根 MIT 覆盖。

XYara 的根 license candidate 只有组件 MIT，但
[`yara-license-closure.md`](yara-license-closure.md) 已证明其 bundled YARA
目录没有独立 license candidate。实际 YARA build closure 另含 YARA
BSD-3-Clause、Bison GPL-3.0-or-later + special exception，以及无内联声明的
TLSH 双许可证源码；因此根候选清单明确不能代表 XYara 的 source/default-build
发布义务。

## 方法与复现

工具
[`audit_component_licenses.py`](../../tools/upstream/audit_component_licenses.py)
先检查 OCI revision，再把当前仓库只读挂载到固定 CMake Qt5 image，并在
`--network=none` 下读取：

- `/opt/die-source` 的主仓库与 58 个 submodule git metadata；
- `upstream/components.lock.toml`；
- 每个组件递归的 `.gitmodules`；
- 文件名以 `LICENSE`、`COPYING`、`NOTICE` 或 `COPYRIGHT` 开头的 regular file。

```powershell
python tools\upstream\audit_component_licenses.py `
  --output docs\research\data\component-license-inventory-linux.json
```

工具拒绝缺失组件、commit/revision/lock 漂移，并要求所有关系成立后才写报告。
报告不包含扫描时间或本机路径，可逐字节重复生成。

## 对 Rust 项目的约束

- upstream sync 必须重新生成该清单，展示新增/删除组件、license path 和 hash diff；
- 规则 bundle 应保存 Detect-It-Easy 根 LICENSE，但不能无依据附带 build-only
  Node licenses，也不能因未附带而忽略实际使用的工具链义务；
- Rust runtime 不会直接复用大部分 C++ 组件，但所选 Rust crate、QuickJS、
  archive/反汇编 backend 需要独立的 cargo/SBOM license closure；
- 若复制、转换或链接任何上游 bundled 文件，必须按实际文件级 build/link
  inventory 继承相应 LICENSE/NOTICE，而不是只引用组件根 MIT；
- 发布 attribution 必须以 component/path/hash 为单位生成，不能按 SPDX 名称去重
  掉不同版权文本。

## 尚未完成

- [`xarchive-license-closure.md`](xarchive-license-closure.md) 已固定 Linux Qt5
  CMake CLI 的 106 个 XArchive 编译单元和 217 个依赖文件；其中聚合
  Brotli/Zstandard 已完成固定官方版本/许可证追溯，但 XArchive 未保存对应文本，
  且 Brotli 仍有约 1.4% 的 64-token 区域未逐段分类；
- XYara 内 bundled YARA 已完成当前 Linux CMake target 的 51-object/109-file
  审计及 TLSH/Authenticode/Bison 分类；仍缺 Windows/macOS/OpenSSL/qmake
  闭包和书面组合评审；
- qmake/CMake、普通 scan/info/struct 和 GUI 的实际 object/link map 对应关系；
- rules、YARA rules、PEiD rules 和 signatures 数据资产的逐路径许可结论；
- 候选 Rust dependency graph、最终 static library 和发布包的 SBOM/NOTICE；
- 由发布/法律责任人完成书面组合评审。
