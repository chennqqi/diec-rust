# DOS/COM 分发可达性

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Formats: `horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`

XScanEngine: `horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-27

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

```text
python tools/corpus/generate_dos_dispatch_corpus.py <corpus-dir>
python tools/upstream/probe_dos_dispatch.py \
  --corpus-dir <corpus-dir> \
  --raw-dir <raw-dir> \
  --output <report.json>
```

## 5. BW forced-property harness

[`bw_dispatch_harness_main.cpp`](../../tools/upstream/bw_dispatch_harness_main.cpp)
和 [`probe_bw_dispatch_harness.py`](../../tools/upstream/probe_bw_dispatch_harness.py)
已固定同一 10-byte `BW` 输入的成对控制：

- automatic case 不设置 property，要求 detector 和 `ftInit` 均不是 BW；
- forced case 设置 `filetypes=BW DOS16M`，要求 detector、`ftInit` 和结果 record
  均为 BW；
- 因 `XFormats::createClass` 没有 BW factory、规则加载也没有 BW database path，
  forced case 当前应产生单条显式 `Unknown`，该 quirk 同样进入断言。

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
```

公共七成员和 BW harness 都尚无 runtime report。当前 Docker daemon 已由
legacy dispatch 实验确认可用，因此这是下一项可执行实验，不再是环境阻塞。
在两份报告实际通过前，`CAP-DISPATCH-002` 保持 source-only。
