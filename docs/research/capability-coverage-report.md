# Phase 0 能力覆盖报告

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 目的

本报告把 [`capability-traceability.json`](data/capability-traceability.json)
中的 68 个稳定 `CAP-*` 投影为能力 × 平台闭集，回答三个不同问题：

1. 每个能力是否都有分类，避免遗漏未测试能力；
2. Linux Qt5 证据是 runtime observation 还是 source-only；
3. 哪些缺口属于语料边界，哪些属于平台基线缺失。

机器报告为
[`data/capability-coverage.json`](data/capability-coverage.json)，由
[`build_capability_coverage.py`](../../tools/research/build_capability_coverage.py)
确定性生成。报告绑定 traceability 原始文件 SHA-256、上游 commit 和规则 commit。

## 2. 目标平台闭集

Phase 0 报告固定四个平台：

- `linux-x86_64-qt5`
- `linux-x86_64-qt6`
- `windows-x86_64-qt5`
- `macos-x86_64-qt5`

当前只有 Linux x86_64 Qt5 被 traceability manifest 接纳为完整 runtime baseline
平台。已有 Linux Qt6 spot differential 不等于 68 项能力基线，因此在本报告中
仍统一分类为 `platform_missing`。Windows 与 macOS 同理。

## 3. 分类语义

| 分类 | 含义 |
| --- | --- |
| `runtime_observed` | 固定 oracle 对 hash-bound 输入观察到命名行为 |
| `runtime_observed_with_corpus_gaps` | 有 runtime observation，但明确边界语料仍缺失 |
| `source_only_runtime_corpus_missing` | 只有固定源码证据，缺少 runtime corpus |
| `source_only_with_corpus_gaps` | 只有源码证据，且另有明确边界缺口 |
| `platform_missing` | 该平台未接纳完整能力基线 |

`source_only` 不能提升为 runtime compatibility；一项能力有某个正例，也不能消除
其 negative、boundary、resource 或 encoding 缺口。

## 4. 当前结果

报告包含 68 行、4 个平台、272 个 cell：

| 平台 | Runtime observed | Observed + corpus gaps | Source-only | Source-only + gaps | Platform missing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Linux x86_64 Qt5 | 65 | 3 | 0 | 0 | 0 |
| Linux x86_64 Qt6 | 0 | 0 | 0 | 0 | 68 |
| Windows x86_64 Qt5 | 0 | 0 | 0 | 0 | 68 |
| macOS x86_64 Qt5 | 0 | 0 | 0 | 0 | 68 |

所有 68 个能力行和 272 个平台 cell 都已分类，未分类计数为 0。这只证明审计
清单没有“消失的行”，**不表示覆盖完成**：

- Linux Qt5 source-only 能力已清零；
- 4 行至少关联一个已命名 corpus gap；
- 三个尚未接纳的平台各有 68 个 `platform_missing`；
- `phase_0_coverage_complete` 必须保持 `false`。

## 5. 缺口映射

traceability 中三个开放 `CAP-GAP-*` 现在显式映射到受影响能力；

| Gap | 类型 | 能力行数 | 范围 |
| --- | --- | ---: | --- |
| `CAP-GAP-006` | corpus | 4 | archive 格式、深度和总解压限制 |
| `CAP-GAP-007` | platform | 68 | 完整 Qt5/Qt6 capability matrix |
| `CAP-GAP-008` | platform | 8 | Windows/macOS path 与 encoding |
映射是保守的审计范围，不是“这些能力除此之外都已完备”的声明。

原 `CAP-GAP-003` 已由五组固定 Linux Qt5 双 Oracle 子矩阵闭合。23-case
[`special-path-behavior.md`](special-path-behavior.md)：NFC/NFD、中文、emoji、
非 UTF-8 目录/显式 argv、tab/newline、colon/backslash、hidden、leading-dash
与精确目录顺序均已有 raw-byte 证据；9-case
[`path-filesystem-behavior.md`](path-filesystem-behavior.md) 又固定 file/
directory/dangling symlink、alias 重复、mode-000 权限、depth-64 与 self-cycle
OS 上限；5-case
[`large-directory-behavior.md`](large-directory-behavior.md) 固定 flat/nested
4096 项完整顺序、描述性资源和发布 CLI 默认 null `PDSTRUCT` 的 cancellation
不可达边界；4-case
[`path-toctou-behavior.md`](path-toctou-behavior.md) 用 SIGSTOP 同步固定
stable old/new、old→new 原子替换和 unlink，证明第二项按打开时当前 path 解析；
最终
[`path-locale-filesystem-behavior.md`](path-locale-filesystem-behavior.md)
覆盖固定镜像的全部 `C`/`C.utf8`/`POSIX` locale 与 tmpfs/`ext2/ext3`
volume，冻结两个大小写排序 profile。Windows/macOS 仍由 `CAP-GAP-008`
单独跟踪，不属于已闭合的 Linux Qt5 corpus gap。

`CAP-GAP-006` 已新增六组固定证据：单成员 ZIP 链已到达 64 层，固定两层
累计展开量达到 33,554,546 bytes；7Z
Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 与
x86 BCJ+LZMA2、BCJ2+LZMA2 no-branch/E8/E9/JCC、ARM64-BCJ+LZMA2 BL/ADRP、
RAR4 store、CAB Store/MSZIP 与
ISO9660 单 PDF 在显式 archive 后各产生一个 PDF Stream child；CAB LZX:15
普通 archive 无 child、aggressive 扫描一个 331-byte Binary/Unknown Stream；
CAB Quantum 18 普通 archive 同样无 child、aggressive 扫描一个 59-byte
Binary/Unknown Stream；
7Z LZMA2+AES 在公共 archive 路径因无密码不产生 child，直接 `XSevenZip`
正确密码还原 331-byte PDF，缺失/错误密码均失败；
官方 BCJ2+LZMA2+4×AES 图在 7-Zip 26.02 正确密码验证成功，但固定 DIE
直接 `XSevenZip` 正确密码仍失败并输出 0 bytes；
NPM 精确路径直接检测为真，但公共自动
扫描回退 `Binary / Unknown`，强制属性才进入 NPM 语言规则；generic Archive
自然检测不满足 singleton 门控，强制 quiet/verbose 后则分别得到 Unknown 和
具体 ZIP/TAR/GZIP adapter；aggressive archive 的第 100000 条记录可达，第
100001 条不可达；ZIP deflate/ZipCrypto/CRC/压缩流/offset/method 畸形、
local-header fallback、1 MiB/843.58:1 和 mixed filter 也已固定。六组增量见
[`archive-limit-behavior.md`](archive-limit-behavior.md)、
[`archive-format-behavior.md`](archive-format-behavior.md) 和
[`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)、
[`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)、
[`archive-iteration-boundary.md`](archive-iteration-boundary.md)、
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)。
其他格式/算法、系统化畸形、真实资源耗尽和跨平台仍缺，因此 gap 行数与状态
均不变。

原 `CAP-GAP-005` 已由
[`scan-option-boundaries.md`](scan-option-boundaries.md)
闭合：项目生成的最小规则与 1/22/2002-resource PE 在 16 次双 Qt5 执行中固定
deep 的 `DS`/`EP` 增量、aggressive/recursive gate、默认 21 与 aggressive
2001 的精确 child count、枚举顺序，以及 PE parser 每目录 1000 项的前置限制。

原 `CAP-GAP-004` 已由
[`cli-output-boundaries.md`](cli-output-boundaries.md)
闭合：10-case 双 Qt5 oracle 固定 Unicode、控制字符、分隔符和 XML 特殊字符，
并验证 JSON 树与顺序、flat XML escaping、nested XML 非良构、CSV/TSV 无引用
导致的歧义、嵌套 leaf flattening，以及 plain text 层级和断行行为。

原 `CAP-GAP-002` 已由
[`database-archive-cache.md`](database-archive-cache.md)
闭合：固定非特权 Qt5 engine harness 覆盖 bad version、0/4/8-byte header、
record 中部/尾部截断、cache 写失败与恢复、不可读 database file/directory，
以及 8 个同输入同步并发 writer；十九个 case 两次运行的原始输出逐字节相同。

原 `CAP-GAP-001` 已由
[`cli-special-modes.md`](cli-special-modes.md)
闭合：28-case 双 oracle 固定临界 entropy、通用及 PE/ELF/Mach-O/DEX struct
方法、层级 filter 和多目标 framing；既有 profiling oracle 固定 292 条真实规则
顺序，并证明 messages gate。

原 `CAP-GAP-011` 已由
[`engine-contract-behavior.md`](engine-contract-behavior.md)
闭合：首条/中间/末条 callback false、同步跨线程 stop、预停止、规则内
`_breakScan()` 及 fresh-state engine 恢复均有固定证据；未同步跨线程读写因上游
plain `bool` 数据竞争而明确排除在可移植 compatibility golden 之外。

原 `CAP-GAP-012` 已由
[`image-dispatch-behavior.md`](image-dispatch-behavior.md)
闭合：七种非 JPEG/PNG variant 的自然 Binary fallback、强制 generic Image
分支及其 null-adapter error 均有固定机器证据。

原 `CAP-GAP-010` 已由
[`rule-orchestration.md`](rule-orchestration.md)
闭合：同 priority、字符串 priority、缺失/空 priority 段、跨层 append 与
`_init` 比较环均有固定双 Qt5 oracle 证据。

原 `CAP-GAP-009` 已由
[`engine-contract-behavior.md`](engine-contract-behavior.md)
闭合：direct/subdevice 的 chunked、EOF、read/seek error、sequential、position
和合法/非法 range 均有固定 37-case Qt5 engine 证据；不安全的 silent success
由 ADR 0013 管理，不被 normalizer 隐藏。

## 6. 可重复验证

生成：

```text
python tools/research/build_capability_coverage.py
```

验证：

```text
python tools/tests/test_capability_coverage.py
```

测试要求 committed report 与生成结果逐字节一致；68 个 ID 与 traceability 完全
相等；全部平台 cell 有已知状态；Linux 四类计数保持 65/3/0/0；其他三个平台
各保持 68 个 `platform_missing`；三个开放 gap 均映射到已知能力；所有
`with_corpus_gaps` 状态都至少关联一个具名 corpus gap。

## 7. 对 Phase 0 门禁的影响

该报告关闭了 `P0-BLOCK-005` 中“没有完整 coverage report”的审计缺口，但没有
关闭 blocker 本身。要关闭 `P0-BLOCK-005`，仍须：

1. 保持
   [`source-only-closure-plan.md`](source-only-closure-plan.md)
   的 Linux source-only 闭集为空，新增或降级能力必须重新进入 closure catalog；
2. 逐项收敛剩余四个 corpus/platform gap，而不是只增加 happy-path 样本；
3. 固定 Windows、macOS 和完整 Linux Qt6 oracle；
4. 重新生成报告，且经评审确认 Phase 0 所需行不再为 source-only、
   corpus-missing 或 platform-missing。
