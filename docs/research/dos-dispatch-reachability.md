# DOS/COM 分发可达性

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Formats: `horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`

XScanEngine: `horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-29

## 1. 结论

`CAP-DISPATCH-002` 不能按“八个文件均由 CLI 自动识别”关闭。固定版本实际分成：

- 公共 `XFormats::getFileTypes` 自动检测的七项：MSDOS、NE、LE、LX、DOS16M、
  DOS4G、COM；
- `XScanEngine::scanProcess` 有分支、但公共 detector 不产生的
  `BW DOS16M`。

BW DOS16M 的 magic 检测仍存在于旧 `XBinary::getFileTypes`，但活动扫描路径调用
的是 `XFormats::getFileTypes`。`XFormats` 支持读取外部设置的 QIODevice
`filetypes` property，因此 private/engine harness 可以强制到达 BW 分支；普通
文件 CLI 不会设置该 property。

因此关闭路径必须拆分：七项用生成文件跑双 CLI oracle；BW 用显式 property
harness，或者通过 review 明确排除这个不可从本项目 CLI/FFI 表达的内部入口。

两部分 runtime 实验现均通过。公共 CLI 输出使用 `DOS/16M`、`DOS/4G`
显示字符串，而内部 enum/set token 为 `DOS16M`、`DOS4G`；兼容实现必须区分。

相同公共矩阵和 BW harness 又在固定 Qt6 CMake oracle 上完成复验：

- 19 个公共 case 的规范化 detection tree 全部与 Qt5 CMake 相同；
- Qt6 JSON 每例新增两个空 `info` 和一个派生 `string` 字段，8 个 MSDOS
  fallback case 还追加两条地址相关 TypeError；所有 raw bytes 均保留，地址只在
  独立 diagnostic projection 中规范化；
- BW automatic/forced-property 两个 case 的完整 harness JSON 和 raw streams
  与 Qt5 逐字节相同。

因此 `CAP-DISPATCH-002` 现达到 Linux Qt6 `evidence_complete`，但这仍不表示
普通 CLI 能自动到达 BW。

## 2. 可重复源码审计

机器证据：
[`dos-dispatch-source-audit.json`](data/dos-dispatch-source-audit.json)

生成/复核工具：
[`probe_dos_dispatch_source_audit.py`](../../tools/upstream/probe_dos_dispatch_source_audit.py)

审计绑定三份固定源码的 SHA-256 和精确行号：

- `Formats/xformats.cpp`：活动 detector、七项 parser 入口和 property reader；
- `Formats/xbinary.cpp`：旧 BW signature 与 `FT_BWDOS16M` insert；
- `XScanEngine/xscanengine.cpp`：活动 detector 调用与 BW dispatch branch。

审计还要求以下计数严格为零：

- `xformats.cpp` 中的 `FT_BWDOS16M` token；
- `xformats.cpp`/`xscanengine.cpp` 内部对 `filetypes` property 的 setter；
- `xscanengine.cpp` 中的 `"BW DOS16M"` database-path token。

这是一项固定源码的负向结论；任意上游同步改变 token、行号或文件 hash 都会使
审计失败并要求重新研究。

Docker oracle 可用时复核：

```text
python tools/upstream/probe_dos_dispatch_source_audit.py \
  --image diec-rust/upstream-oracle:74eaf505-repro \
  --baseline docs/research/data/dos-dispatch-source-audit.json
```

## 3. 七个公共成员的格式边界

固定 parser 源码给出首批生成条件：

- COM：`XCOM::isValid` 只要求大小不超过 `0x10000 - 0x100`，但
  `XFormats` 还要求文件后缀为 `.COM`；
- MSDOS：首个 little-endian word 为 `MZ` 或 `ZM`；
- NE：MZ、有效正 `e_lfanew`，目标处为 `NE`；
- LE/LX：MZ、有效正 `e_lfanew`，目标处分别为 `LE\0\0`/`LX\0\0`；
- DOS16M/DOS4G：`XDOS16` 要求文件大于 1024 bytes，根 MZ 的页尾指向 `BW`
  header，再由嵌套 MZ 的 NE 或 LE/LX signature 区分 16M 与 4G。

既有 signature parser 语料已经包含 COM、MSDOS 的 parser-derived memory map
正例，但没有覆盖 diec 顶层分发；它们只能复用字节构造，不能直接提升本能力。

## 4. 公共成员语料与 oracle

[`generate_dos_dispatch_corpus.py`](../../tools/corpus/generate_dos_dispatch_corpus.py)
和 [`dos-dispatch-corpus.json`](data/dos-dispatch-corpus.json) 已固定 19 个 case：

- MZ/ZM、`e_lfanew`、NE/LE/LX magic 的截断和近似值；
- DOS16M/DOS4G 的 1024-byte 边界、BW chain 和嵌套 signature；
- COM 的后缀与 65280/65281-byte 大小边界。

每个公共 filetype 都有正例。控制包含 `e_lfanew` 截断、近似 magic、DOS chain
恰好 1024 bytes、错误 BW、COM 错误后缀和上限加一。特别地，
`dos4g-near-nested-magic.exe` 必须回落到 DOS16M，显式检查相邻分发。

[`probe_dos_dispatch.py`](../../tools/upstream/probe_dos_dispatch.py) 复用
Amiga/Atari probe 的双 oracle 执行层；它要求临时 manifest 与提交清单逐字节
相同，对两套 Qt5 oracle 分别执行 19 case，强制检查 present/absent filetype，
并把每次 raw stdout/stderr 保存到外部目录。

固定报告
[`dos-dispatch-linux-qt5.json`](data/dos-dispatch-linux-qt5.json)
在 qmake/CMake 两套 oracle 上均通过全部 19 case，failures 为空：

- 七个正例分别产生 `MSDOS`、`NE`、`LE`、`LX`、`DOS/16M`、`DOS/4G`、
  `COM`；
- 1024-byte DOS chain 控制回落 `MSDOS`；
- DOS/4G 近似嵌套 magic 按预期相邻分发到 `DOS/16M`；
- 65,280-byte COM 命中，65,281-byte 和错误后缀控制不命中。

38 次 CLI 扫描的 raw stdout/stderr 共 17,810 bytes，stderr 均为空；逐流
大小/SHA-256、两套 image ID、generator 和 manifest SHA-256 均保存在报告中。

Qt5/Qt6 公共报告为
[`dos-dispatch-linux-qt5-qt6.json`](data/dos-dispatch-linux-qt5-qt6.json)，
150497 bytes，SHA-256
`cb65823f885ce96b1356f6d9f657b7fba735891996009289f533060398c544f9`。
19 case × 2 repetitions 共 38 次受限 Qt6 调用，使用禁网、1 CPU、512 MiB、
128 PIDs、只读 root/corpus mount。43 个唯一 raw stream 以内容寻址保存。

19 例的 raw JSON 都因 Qt6 `info/string` 字段而不同；其中以下 8 例另有同一
normalized diagnostic SHA-256
`c6656b6859b2ae4f2f9db8bdddfa7129587757ec933bc89de232c84daade95c1`：

- `minimal-msdos.exe`；
- `ne-truncated.exe`、`ne-near-magic.exe`；
- `le-near-magic.exe`、`lx-near-magic.exe`；
- `dos16m-truncated.exe`、`dos16m-near-bw.exe`；
- `dos4g-truncated.exe`。

两条诊断分别是 Qt6 对 `_init` 写只读 `getEntryPointOffset` 的 TypeError，
以及 `MSDOS_Script(0x<address>)` 缺少 `getNEOffset` 的 TypeError。报告保留
每轮真实地址 raw stdout；只有比较 projection 替换地址。所有 stderr 为空。

```text
python tools/corpus/generate_dos_dispatch_corpus.py <corpus-dir>
python tools/upstream/probe_dos_dispatch.py \
  --corpus-dir <corpus-dir> \
  --raw-dir <raw-dir> \
  --output <report.json>
python tools/upstream/probe_qt6_dos_dispatch.py \
  --corpus-dir <corpus-dir> \
  --output docs/research/data/dos-dispatch-linux-qt5-qt6.json
```

## 5. BW forced-property harness

[`bw_dispatch_harness_main.cpp`](../../tools/upstream/bw_dispatch_harness_main.cpp)
和 [`probe_bw_dispatch_harness.py`](../../tools/upstream/probe_bw_dispatch_harness.py)
已固定同一 10-byte `BW` 输入的成对控制：

- automatic case 不设置 property，要求 detector 和 `ftInit` 均不是 BW；
- forced case 设置 `filetypes=BWDOS16M`，要求 detector、`ftInit` 和结果 record
  均为 BW；
- 因 `XFormats::createClass` 没有 BW factory、规则加载也没有 BW database path，
  forced case 当前应产生单条显式 `Unknown`，该 quirk 同样进入断言。

compact token 是上游 parser 契约而非任意选择：
`XCONVERT_ftStringToId` 会对表项删除空格/连字符，却只把输入转大写，因此显示
字符串 `BW DOS16M` 反向解析失败，必须传 `BWDOS16M`。另外，
`scanProcess` 会把小设备复制到新 QBuffer 且不传播任意 property；harness 按
上游内存设备约定设置真实 `Memory` 指针，才能让同一个 `filetypes` property
进入 scanner。

Dockerfile 直接继承固定 CMake Qt5 oracle，通过替换 `main_console.cpp.o` 链接
未修改的上游 objects，不执行网络下载：

```text
docker build \
  -f tools/upstream/Dockerfile.bw-dispatch-harness-qt5 \
  -t diec-rust/bw-dispatch-harness-qt5:74eaf505 \
  tools/upstream
python tools/upstream/probe_bw_dispatch_harness.py \
  --raw-dir <raw-dir> \
  --output <report.json>

docker build --network=none --provenance=false \
  -f tools/upstream/Dockerfile.bw-dispatch-harness-qt6 \
  -t diec-rust/bw-dispatch-harness-qt6:74eaf505 \
  tools/upstream
python tools/upstream/probe_qt6_bw_dispatch_harness.py \
  --output docs/research/data/bw-dispatch-engine-qt5-qt6.json
```

固定报告
[`bw-dispatch-engine-qt5.json`](data/bw-dispatch-engine-qt5.json)
的六项关系断言全部通过：automatic detector 为 `BINARY|TEXT|UTF8` 且扫描
初始化 `Binary`；forced detector 为 `BWDOS16M`，扫描初始化和唯一 record
均为 `BW DOS16M`，record 是显式 Unknown。两次扫描成功、错误数为 0；原始
stdout 1,335 bytes，stderr 为空。

公共矩阵与 branch-only harness 同时通过后，`CAP-DISPATCH-002` 的 Linux Qt5
状态提升为 runtime-observed。该状态不表示普通 CLI 可以自动到达 BW。

Qt5/Qt6 BW 报告
[`bw-dispatch-engine-qt5-qt6.json`](data/bw-dispatch-engine-qt5-qt6.json)
为 5195 bytes，SHA-256
`8bf95a3f81855e751880dd54d2747c2aac6c8458378c5a80c411561080143a6a`。
Qt6 harness image ID 为
`sha256:f71568facffa71c29420f9f0701e58bce15db54ee1cb12603938bc19804f893e`，
binary SHA-256 为
`556c8ff8ed0b2f3a534305aa15184fd7ad33408068cdd6be1f3992de92c23f32`。
双轮 Qt6 stdout/stderr 完全相同，并与 Qt5 raw SHA、完整 harness JSON 和六项
关系逐项相同。
