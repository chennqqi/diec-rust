# Amiga Hunk / Atari ST 分发 oracle

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Formats: `horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`

Last updated: 2026-07-29

## 1. 结论

`CAP-DISPATCH-003` 的确定性语料和双 Qt5 oracle probe 已就绪。首次执行还发现
Atari `HEADER` 的字段宽度之和不是 Linux C++ `sizeof(HEADER)`；语料现已按实际
ABI 边界修正，最终 runtime 结论见第 5 节。

- 固定 Formats 源码中的有效性边界和分发顺序；
- Amiga 正例已被既有 XAmigaHunk parser harness 判为 valid；
- 8 个项目生成样本可重复、受 SHA-256 约束，正负控制跨越精确源码边界；
- probe 会验证 qmake/CMake 输出相同，并强制检查预期 filetype 的存在/缺失。

相同 8-case matrix 又在固定 Qt6 CMake oracle 上执行两轮。32 次 Qt6
scan/info 调用的 raw streams 在两轮间逐字节稳定，并与 Qt5 CMake 的全部
raw stream、detector filetype 和 scanner detection tree 相同。因此
`CAP-DISPATCH-003` 现已达到 Linux Qt6 `evidence_complete`。

## 2. 固定源码事实

证据均来自固定 `Formats` commit：

- `exec/xamigahunk.cpp:62-76`：文件大小必须大于 8，首个大端 32 位值只能是
  `HUNK_HEADER` 或 `HUNK_UNIT`；
- `exec/xamigahunk_def.h:28-40`：两者分别为 `0x03F3`、`0x03E7`；
- `exec/xatarist.cpp:36-50`：文件大小至少为本机构建的 `sizeof(HEADER)`，首个
  大端 16 位值必须为 `MAGIC`；
- `exec/xatarist_def.h:26-38`：magic 为 `0x601A`，header 包含 2-byte magic、
  六个 32-bit 字段和 2-byte relocation flag。字段共 28 bytes，但固定 Linux
  amd64 C++ ABI 的尾部对齐使 `sizeof(HEADER)==32`；
- `xformats.cpp:1581-1590`：主格式分发在已有结果不超过一项时先检查 Amiga，
  再检查 Atari。

既有 [`signature-oracle-qt5.json`](data/signature-oracle-qt5.json) 的
`amigahunk_parser_memory_map_relative_jump` 使用与本语料相同的 52-byte Amiga
正例，固定 Qt5 harness 返回 `format_valid: true`、大端 memory map 和
`file_type: amigahunk`。这证明格式 parser 可接受该字节串，但不代替 diec
顶层扫描分发证据。

## 3. 语料

生成器：
[`generate_legacy_dispatch_corpus.py`](../../tools/corpus/generate_legacy_dispatch_corpus.py)

版本化清单：
[`legacy-dispatch-corpus.json`](data/legacy-dispatch-corpus.json)

每种格式各有四个 case：

| case | Amiga Hunk | Atari ST | 预期 |
| --- | --- | --- | --- |
| positive | 52-byte HUNK image | 32-byte padded header image | 命中自身、不得借用另一格式 |
| truncated | 8 bytes | 31 bytes | 两种 filetype 均不得出现 |
| wrong endian | `f3030000` | `1a60` | 两种 filetype 均不得出现 |
| near magic | `000003f4` | `601b` | 两种 filetype 均不得出现 |

语料完全由常量和结构字段生成，不复制第三方样本字节；仓库只提交清单，不提交
二进制。生成器测试要求两次输出逐字节一致，并要求 manifest 与提交版本完全
一致。

## 4. Probe 契约

[`probe_legacy_dispatch.py`](../../tools/upstream/probe_legacy_dispatch.py) 固定使用：

- qmake image `diec-rust/upstream-oracle:74eaf505-repro`；
- CMake image `diec-rust/upstream-oracle-cmake:74eaf505`；
- 两个 image 的 OCI revision 必须等于固定 DIE-engine SHA；
- normal scan 使用三层固定规则数据库和 `--json`；
- info scan 使用 `--info --json`，作为 `XFormats` detector 的独立投影；
- 每个样本在两套 oracle 中都要满足 manifest 的 scanner present/absent
  filetype 和 info filetype；
- 两侧两种模式的 exit code、stdout、stderr 和结构化投影必须相同；
- 每次 raw stdout/stderr 写入调用方指定的未跟踪目录，report 保存路径、大小和
  SHA-256。

执行命令：

```text
python tools/corpus/generate_legacy_dispatch_corpus.py <corpus-dir>
python tools/upstream/probe_legacy_dispatch.py \
  --corpus-dir <corpus-dir> \
  --raw-dir <raw-dir> \
  --output <report.json>

python tools/upstream/probe_qt6_legacy_dispatch.py \
  --corpus-dir <corpus-dir> \
  --output docs/research/data/legacy-dispatch-linux-qt5-qt6.json
```

## 5. Runtime 观察

固定报告为
[`legacy-dispatch-linux-qt5.json`](data/legacy-dispatch-linux-qt5.json)，
8 个 case 在 qmake/CMake 两套 oracle 的结果完全相同：

| case | info detector | normal scanner |
| --- | --- | --- |
| Amiga positive | `Amiga Hunk` | `Amiga Hunk` |
| Atari positive | `Atari ST` | `Binary` |
| 六个 truncated/wrong-endian/near-magic 控制 | `Binary` | `Binary` |

Atari 的差异不是 formatter 误标：`XFormats::_getFileTypes` 在
`Formats/xformats.cpp:1586-1590` 可插入 `FT_ATARIST`，而
`XScanEngine::scanProcess` 的选择链在 `xscanengine.cpp:2741-2745` 处理
`FT_AMIGAHUNK` 后直接进入 `FT_PDF`，直到 `:2812-2831` 的 fallback 都没有
Atari 分支，最终将 `ftInit` 设为 `FT_BINARY`。Rust 兼容层必须保留这项上游
可观察不对称，除非未来 ADR 明确接受偏离。

报告保存 8 × 2 oracle × 2 mode 的 32 对 stdout/stderr 元数据；本次 raw stream
总计 12,066 bytes，所有 stderr 为空。每个流的大小和 SHA-256、两套 image ID、
固定 revision、generator SHA-256 与 corpus manifest SHA-256 都在报告中。
报告 `result: pass` 且 failures 为空，因此 `CAP-DISPATCH-003` 的 Linux Qt5
状态提升为 runtime-observed。

Qt5/Qt6 报告为
[`legacy-dispatch-linux-qt5-qt6.json`](data/legacy-dispatch-linux-qt5-qt6.json)，
55781 bytes，SHA-256
`8ecbfe6502de89de58b56316cf5d27274cb9fecccc0f523aa9377d302a7bebfa`。
Qt6 固定身份为：

- image ID
  `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`；
- binary SHA-256
  `e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e`；
- `xamigahunk.cpp` / `xatarist.cpp` / `xformats.cpp` / `xscanengine.cpp`
  均绑定报告内的完整 SHA-256。

Qt6 probe 执行 8 样本 × 2 mode × 2 repetitions，共 32 次受限容器调用；
禁网、1 CPU、512 MiB、128 PIDs、只读 root 和只读 corpus mount。15 个唯一
raw stream 以 `zlib+base64` 内容寻址保存，所有引用均可逆校验。最终
`known_differences` 为空：

- Amiga positive 的 info/scanner 均为 `Amiga Hunk`；
- Atari positive 的 info 为 `Atari ST`，scanner 仍回退 `Binary`；
- 六个 truncated/wrong-endian/near-magic 控制的 info/scanner 均为 `Binary`；
- 两轮 Qt6 及 Qt5 CMake/Qt6 的每个 stdout/stderr 都逐字节相同。
