# 上游 archive 深度与累计展开量边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

`CAP-NEST-009` 已从纯源码结论提升为固定 Linux Qt5 的
`runtime_observed_with_corpus_gaps`：

- 固定 `XScanEngine@dfe4a419...` 的 archive 循环只有每层 scanable entry
  数量 `20/100000` 和循环 `100000` 次上限；它按成员声明的 uncompressed size
  分配 buffer，然后把完整 `SCAN_OPTIONS` 复制给递归 `scanProcess()`。该源码块没有
  独立 depth 或全 scan 累计展开字节状态。
- 每层严格 1 个成员、叶子大小不变的 ZIP 序列从 1 增长到 64 层。固定 engine
  在每个 case 都到达最深 PDF，`Stream` node 数和最深 parent 链均精确等于声明
  depth。
- depth 固定为 2 时，累计成员展开量从 2,162 增长到 33,554,546 bytes。六个 case
  都到达第二层 PDF，没有观察到累计字节截断。
- 第一次 upstream progress callback 在扫描线程内设置 stopped，会保留 1 条 root
  record、产生 0 个 Stream child；同输入未取消时产生 18 records 和 16 个
  Stream nodes。这证明取消会返回可观察的部分前缀，且实验没有异步写
  `PDSTRUCT::bIsStop` 的数据竞争。

这些结果只证明“固定源码没有独立字段，且在测试上界内没有观察到 cutoff”，不证明
任意深度/大小都能成功，也不把资源耗尽视为兼容要求。Rust 侧有界偏离由
[`ADR 0012`](../design/decisions/0012-bounded-nested-scan-budget.md) 提议。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| XScanEngine gitlink | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| `xscanengine.cpp` SHA-256 | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| harness binary SHA-256 | 见机器报告 `harness_binary.sha256` |
| rules/database | `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |

机器报告：
[`archive-limit-engine-qt5.json`](data/archive-limit-engine-qt5.json)。
SHA-256 为
`e4786dcc578fb0714c86f71955161f981a06be26aefe663281d74202f5372ecd`。
报告同时保存 image ID、binary/source hash、每次原始 stdout/stderr 及其 hash、
退出码、timeout、possible OOM、扫描耗时和进程 peak RSS。

## 源码证据

固定源码
[`xscanengine.cpp` archive block](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2835-L2931)
显示：

1. `bIsArchivesScan` 开启后，normal/aggressive 每层 scanable entry limit 分别为
   20/100000；`nCurrentIndex > nLimit` 使 normal 的实际可扫描边界为 21。
2. 每个成员通过 `FPART_PROP_UNCOMPRESSEDSIZE` 创建完整 file buffer。
3. child 使用复制的 options 直接再次调用 `scanProcess()`。
4. archive block 没有 depth、cumulative、total extracted/decompressed token 或
   对应共享计数器。

probe 不是仅对关键词作负向推断：它先把完整源码绑定到 SHA-256，再固定 archive
block 行范围和正向控制（entry limit、allocation、递归调用）出现次数。运行时双
序列为负向源码结论提供测试上界，而不是把一次小样本写成无限性证明。

## 语料

生成器
[`generate_archive_limit_fixture.py`](../../tools/corpus/generate_archive_limit_fixture.py)
创建 store-only、无时间戳/扩展字段的单成员 ZIP。叶子复用项目生成的最小 PDF，
不包含第三方或恶意样本字节。

机器清单：
[`archive-limit-corpus.json`](data/archive-limit-corpus.json)。

两个序列隔离变量：

| 序列 | 固定项 | 变化项 | 测试范围 |
| --- | --- | --- | --- |
| `depth` | 每层 1 member、leaf 331 bytes | archive depth | 1, 2, 4, 8, 12, 16, 32, 64 |
| `expanded_bytes` | depth 2、每层 1 member | leaf/cumulative bytes | leaf 1 KiB—16 MiB；累计 2,162—33,554,546 |

`cumulative_expanded_bytes` 定义为引擎沿链为每个 archive member 请求的
uncompressed size 之和；生成器测试通过逐层解包重新计算该值。store-only 避免把
压缩比或 decompressor 算法混入本实验。

## 受限 oracle

[`archive_limits_harness_main.cpp`](../../tools/upstream/archive_limits_harness_main.cpp)
只替换固定 CMake console target 的 `main_console.cpp.o`，其余 engine、format、
archive 和 rule runtime objects 均来自固定基础镜像。harness 在 database load
完成后：

- 开启 engine-only `bIsArchivesScan`；
- 从 `SCANSTRUCT.id/parentId` 汇总 unique node 与最深 Stream/PDF depth；
- 用 `QElapsedTimer` 记录 scan interval；
- 用 Linux `getrusage(RUSAGE_SELF).ru_maxrss` 记录扫描前后进程高水位；
- 用同线程 `PDSTRUCT_CALLBACK` 实现确定性取消控制。

每个 case 都在独立进程执行，容器固定为：

```text
--network none --cpus 1 --memory 256m --pids-limit 128
wall timeout: 30 seconds
```

复现：

```powershell
$corpusDir = Join-Path $env:TEMP diec-archive-limit-corpus
python tools\corpus\generate_archive_limit_fixture.py $corpusDir
docker build -f tools\upstream\Dockerfile.archive-limits-harness-qt5 `
  -t diec-rust/upstream-archive-limits-harness:74eaf505 tools\upstream
python tools\upstream\probe_archive_limits_harness.py `
  --image diec-rust/upstream-archive-limits-harness:74eaf505 `
  --corpus-dir $corpusDir
```

## 结果摘要

所有 14 个 normal cases 与 1 个取消 control 均 exit 0、stderr 为空、未 timeout，
也未以 137 退出。normal cases 没有 engine error 或 tree cycle。最大 case：

- depth：64 层、64 个 Stream nodes、最深 PDF depth 64；
- cumulative expanded：33,554,546 bytes、最深 PDF depth 2；
- peak RSS：报告的是各独立进程“database 已加载后的进程高水位”和“scan 后进程
  高水位”，不是 archive allocation 的隔离增量；
- elapsed/RSS 是本次环境描述值，断言只要求它们有效且 high-watermark 不倒退，
  不要求随输入严格单调。

## 限制与剩余缺口

- 只验证 Linux x86_64 Qt5、ZIP store method、depth 64 和约 32 MiB 累计展开量。
- 7Z Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64、x86 BCJ+LZMA2、
  ARM64-BCJ+LZMA2 BL/ADRP、RAR4 store、CAB Store/MSZIP 与 ISO9660 的合法
  单成员正例已由
  [`archive-format-behavior.md`](archive-format-behavior.md) 固定；仍未验证
  7Z BCJ2/AES、RAR 压缩与 CAB LZX/Quantum 等
  压缩/加密/损坏边界。
  ZIP deflate、ZipCrypto 无密码、CRC/压缩流
  畸形和 1 MiB/843.58:1 已由
  [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md) 固定；
  更高展开量、欺骗声明长度、循环 container、真正 OOM 或超过 30 秒后的
  引擎内部清理仍未验证。
- Docker 外部 timeout 会终止进程，无法提供 cooperative partial result；因此
  partial/cancellation 使用 upstream 同线程 callback 单独验证。
- `ru_maxrss` 包含 database load 形成的历史高水位，不可解释为单个 sample 的精确
  allocation；性能/内存结论仍需专用 benchmark/profiler。
- Windows、macOS 和 Linux Qt6 仍为平台缺口。

resource filtering/count 已由
[`scan-option-boundaries.md`](scan-option-boundaries.md) 闭合；本能力仍保留
`CAP-GAP-006`，但不再是 source-only。aggressive 的精确记录边界已由
[`archive-iteration-boundary.md`](archive-iteration-boundary.md) 观察为
“第 100000 条可达、第 100001 条不可达”；剩余 gap 不再包含该子项。
