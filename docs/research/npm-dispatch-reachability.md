# NPM 分派可达性

Status: Draft
Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254
Last updated: 2026-07-28

## 范围

本文固定 DIE-engine 的 NPM 检测器、公共自动扫描和显式强制分派三层行为。
结论只适用于上面的主仓库 commit 及以下组件：

- Formats `1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XArchive `0fcd4e8d3e9933baac3b12246d82ac026557ffd0`
- XScanEngine `dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- die_script `5d82316c110abf0eb863b50bc679d330e05067b6`

本实验回答的是 NPM 能力是否能从公共 CLI 自然到达，而不只是源码中是否存在
`XNPM` 类和 NPM 规则。通用 Archive、archive aggressive 的 100000 边界、
压缩/加密/畸形语料和跨平台行为仍归 `CAP-GAP-006`。

## 结论

固定版本存在完整的 NPM 直接检测器、扫描分支和规则宿主，但公共 GZIP 自动识别
路径不会调用 TGZ/NPM 细分。因此一个结构有效、包含精确
`package/package.json` 的 `.tgz` 在公共 CLI 中仍表现为
`Binary: Unknown`。

需要区分三层契约：

1. `XNPM::isValid(records)` 只检查是否存在大小写敏感的精确归档记录
   `package/package.json`，不解析 JSON 内容。
2. 公共自动检测只产生 `BINARY|ARCHIVE|GZIP`；扫描分派没有 GZIP 或通用
   Archive 的专用分支可将其进一步提升为 NPM，最终初始化为 `Binary`。
3. 显式设置设备属性 `filetypes=NPM` 时，`FT_NPM` 扫描分支和 NPM 语言规则
   可达。这是研究控制面，不是当前公共 CLI 对 `.tgz` 的自然行为。

Rust 实现若以该 commit 为兼容基线，公共自动扫描必须先保留这一可观察结果。
内部可以实现 NPM 检测器，也可以为测试或未来 API 提供显式格式提示，但不能把
“内部检测器为真”直接等同于公共自动扫描应报告 NPM。将来若有意修复上游不可达
路径，属于兼容性偏离，必须建立 ADR 和独立回归模式。

## 源码证据

以下行号来自报告绑定的固定容器源码：

- `XArchive/xnpm.cpp:53-59`：
  `XNPM::isValid(QList<RECORD> *)` 调用
  `isArchiveRecordPresent("package/package.json", ...)`。
- `Formats/xformats.cpp:1344-1356`：
  `getFileTypesTGZ` 会加入 `FT_TAR_GZ`，且在直接检测器为真时加入
  `FT_NPM`。
- `Formats/xformats.cpp:1439-1457`：
  `getFileTypesGZIP` 中解压首记录、识别 TAR 并调用 `getFileTypesTGZ`
  的整段代码被注释，函数返回空集合。
- `Formats/xformats.cpp:1629-1631`：
  活动的 GZIP 路径只加入 `FT_ARCHIVE` 和 `FT_GZIP`。
- `XScanEngine/xscanengine.cpp:2733-2735`：
  `scanProcess` 有显式 `FT_NPM` 分支并设置初始文件类型。
- `die_script/die_scriptengine.cpp:187-190`：
  `FT_NPM` 会创建 `XNPM` 与 `NPM_Script` 宿主。

固定规则也被报告逐文件哈希绑定：

- `db/NPM/package_PackageName.1.sg` 读取 `name` 和 `version`；
- `db/NPM/language_JavaScript.5.sg` 和
  `language_TypeScript.5.sg` 按归档记录名匹配语言；
- `db/NPM/_NPM.0.sg` 只在 verbose 模式产生格式记录。

有效 JSON 正例在本实验的强制 NPM 普通选项下只产生 JavaScript 语言记录，
没有包名/版本记录。本文将其固定为可观察事实；现有证据不足以把具体原因归结为
规则、宿主读取或扫描选项中的任一单点。

## 夹具

[`data/npm-dispatch-fixture.json`](data/npm-dispatch-fixture.json) 固定四个
3095 字节的项目生成 USTAR+GZIP 样本，不保存第三方包内容：

| 样本 | 控制条件 | 直接检测器 |
| --- | --- | --- |
| `npm-valid.tgz` | 精确路径、有效 name/version JSON、`.js` | true |
| `npm-invalid-json.tgz` | 精确路径、无效 JSON、`.ts` | true |
| `root-package-json.tgz` | `package.json` 位于归档根 | false |
| `case-package-json.tgz` | `package/Package.json` 大小写不同 | false |

生成器固定 USTAR 的 mode、uid、gid、mtime、uname/gname，使用确定性的
stored-deflate GZIP，头部 mtime 为 0、OS 为 255。测试以 Python `gzip` 和
`tarfile` 独立解析所有样本，并核对清单中的大小和 SHA-256。

## Oracle 设计

[`data/npm-dispatch-engine-qt5.json`](data/npm-dispatch-engine-qt5.json)
是内容寻址报告，SHA-256 为
`d23168aff29696f46d3579f6d914353865035bd02a8bbbcf9af065475c036ce7`。
它绑定：

- 固定 CMake 探针镜像和固定 qmake release 镜像的 image ID、revision；
- 探针、CMake release、qmake release 三个二进制的大小和 SHA-256；
- Formats、XArchive、XScanEngine、die_script 组件 HEAD；
- 四个调度源码和四个 NPM 规则文件的完整 SHA-256 及必要源码模式；
- 夹具清单、生成器、探针、C++ harness 和 Dockerfile 的 SHA-256；
- 每次执行的原始 stdout/stderr，经 `zlib+base64` 内容寻址保存；
- 1 CPU、512 MiB、128 PID、无网络、只读根文件系统和只读夹具挂载。

CMake 与 qmake release 对四个样本的 stdout/stderr 逐字节相等。探针的自动
扫描摘要与 release CLI 也一致，避免把替换 `main` 的研究 harness 当作唯一
oracle。

报告固定以下机器可检验事实：

- `direct_detector_accepts_exact_package_json_path`
- `direct_detector_rejects_path_and_case_controls`
- `direct_detector_does_not_parse_package_json`
- `automatic_detection_never_emits_npm`
- `automatic_scan_falls_back_to_binary_unknown`
- `forced_property_reaches_npm_language_rules`
- `valid_package_metadata_is_not_reported_by_default_options`
- `qmake_and_cmake_release_outputs_are_byte_equal`
- `release_and_harness_automatic_semantics_agree`

## 复现

从已经按
[`upstream-baseline.md`](upstream-baseline.md) 构建的固定 Qt5 镜像开始：

```text
python tools/corpus/generate_npm_dispatch_fixture.py \
  /tmp/diec-npm-dispatch-fixture

docker build --provenance=false \
  --file tools/upstream/Dockerfile.npm-dispatch-harness-qt5 \
  --tag diec-rust/npm-dispatch-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_npm_dispatch_harness.py \
  --fixture-dir /tmp/diec-npm-dispatch-fixture \
  --output docs/research/data/npm-dispatch-engine-qt5.json
```

探针每次执行均由脚本设置资源限制。重新生成后必须核对报告 SHA-256，且相关测试
必须通过；镜像 ID、二进制、源码、规则、夹具或原始输出任一变化都会使测试失败。

## 剩余缺口

本实验收窄了 `CAP-DISPATCH-004` 中的 NPM 子项，但不关闭
`CAP-GAP-006`。仍需补齐：

- 通用 Archive 顶层分派现由
  [`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)
  固定；
- archive aggressive 的 100000 记录/迭代边界；
- 压缩、加密、高压缩比和畸形 archive；
- Linux Qt6、Windows、macOS 的对应行为。
