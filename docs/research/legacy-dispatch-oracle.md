# Amiga Hunk / Atari ST 分发 oracle

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Formats: `horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`

Last updated: 2026-07-27

## 1. 结论

`CAP-DISPATCH-003` 的确定性语料和双 Qt5 oracle probe 已就绪，但尚未获得顶层
CLI runtime report。当前只能证明：

- 固定 Formats 源码中的有效性边界和分发顺序；
- Amiga 正例已被既有 XAmigaHunk parser harness 判为 valid；
- 8 个项目生成样本可重复、受 SHA-256 约束，正负控制跨越精确源码边界；
- probe 会验证 qmake/CMake 输出相同，并强制检查预期 filetype 的存在/缺失。

Docker Desktop daemon 当前不可用，未执行 probe。因此本文不提升 capability
coverage，`CAP-DISPATCH-003` 仍是 `source_only_runtime_corpus_missing`。

## 2. 固定源码事实

证据均来自固定 `Formats` commit：

- `exec/xamigahunk.cpp:62-76`：文件大小必须大于 8，首个大端 32 位值只能是
  `HUNK_HEADER` 或 `HUNK_UNIT`；
- `exec/xamigahunk_def.h:28-40`：两者分别为 `0x03F3`、`0x03E7`；
- `exec/xatarist.cpp:36-50`：文件至少覆盖 28-byte `HEADER`，首个大端 16 位值
  必须为 `MAGIC`；
- `exec/xatarist_def.h:26-38`：magic 为 `0x601A`，header 包含 2-byte magic、
  六个 32-bit 字段和 2-byte relocation flag；
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
| positive | 52-byte HUNK image | 28-byte header-only image | 命中自身、不得借用另一格式 |
| truncated | 8 bytes | 27 bytes | 两种 filetype 均不得出现 |
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
- 三层固定规则数据库和 `--json`；
- 每个样本在两套 oracle 中都要满足 manifest 的 present/absent filetype；
- 两侧 exit code、stdout、stderr 和结构化 detect tree 必须相同；
- 每次 raw stdout/stderr 写入调用方指定的未跟踪目录，report 保存路径、大小和
  SHA-256。

执行命令：

```text
python tools/corpus/generate_legacy_dispatch_corpus.py <corpus-dir>
python tools/upstream/probe_legacy_dispatch.py \
  --corpus-dir <corpus-dir> \
  --raw-dir <raw-dir> \
  --output <report.json>
```

只有 probe 返回 `result: pass`、原始工件可复核并将 report 提交到
`docs/research/data/` 后，才可更新 traceability/coverage，将
`CAP-DISPATCH-003` 提升为 runtime-observed。
