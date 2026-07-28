# 上游 ZIP 压缩、加密与畸形成员行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 oracle 对 12 个项目生成 ZIP、4 种执行模式共 48 次
运行得到：

- stored 与 deflate PDF 都能在显式 archive 模式进入相同的
  `PDF / Stream` 规则链；
- 1 MiB 展开、1243 bytes raw deflate、压缩比约 `843.58:1` 的 PDF-prefix
  成员仍完整展开为 1,048,576-byte Stream，没有观察到 ratio 或累计字节 cutoff；
- 有效 traditional ZipCrypto 成员在 scanner 没有 password API 时只保留 ZIP
  root，不产生 child，也不产生 stderr 或结构化 error；
- 错误 CRC、损坏 deflate、截断 deflate、越界 local-header offset 和未知 method
  99 均不产生 child；
- 缺少 central directory 与 EOCD 的 stored ZIP 会走 XZip
  `local-header fallback`，仍展开并识别 PDF；
- 越界 local-header offset 的唯一附加诊断是 stderr 中两条相同
  `QBuffer::seek: Invalid pos: 4294967070`，进程仍 exit 0；
- `../escape.pdf` 名称不会阻止成员被扫描；当前 formatter 输出不包含原始成员名，
  因而本实验不声称上游已规范化、拒绝或安全提取该路径；
- 两成员 ZIP 在 normal archive 模式只扫描可识别 PDF；aggressive 还扫描
  1-byte 成员并产生 `Binary / Plain text` child；
- 所有 12 个 default harness 输出与固定发布 CLI 逐字节相同，且都不展开成员。

这些结果关闭 `CAP-GAP-006` 中 ZIP deflate、ZipCrypto 无密码、CRC、压缩流损坏、
截断、central-directory 缺失、越界 offset、未知 method、路径 metadata、
mixed-member filter 和 1 MiB/843.58:1 压缩比测试点。该 gap 仍因更高资源边界、
ZIP AES、其他 ZIP 压缩算法、RAR15/RAR20、RAR7 algorithm version 1、RAR
加密/multi-volume/recovery/损坏压缩流、剩余结构字段、ISO path-table
location/多字段组合冲突、算术 wrap、更大或混合失败记录图和跨平台行为保持
开放。RAR3 unpack29 method `0x35` 与 RAR5 method 5 压缩/solid 正例已由
[`archive-rar-compressed-behavior.md`](archive-rar-compressed-behavior.md)
固定。7Z、RAR4、CAB、ISO9660 的系统化
EOF 前缀截断阶梯已由
[`archive-truncation-behavior.md`](archive-truncation-behavior.md) 固定。
同四格式的首轮 CRC/size/offset/method/record-field 突变已由
[`archive-structure-behavior.md`](archive-structure-behavior.md) 固定。
同四格式的两记录顺序、重名和空成员过滤已由
[`archive-multirecord-behavior.md`](archive-multirecord-behavior.md) 固定。
ISO9660 的 17-field 单侧双端序冲突已由
[`iso9660-endian-behavior.md`](iso9660-endian-behavior.md) 固定。
CAB Quantum 的合法方法边界已由
[`archive-format-behavior.md`](archive-format-behavior.md) 单独固定。

机器报告：
[`archive-adversarial-engine-qt5.json`](data/archive-adversarial-engine-qt5.json)。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| harness image | 报告 `image.id` 与 revision |
| release/harness binaries | 报告 `binaries.*.sha256` |
| XScanEngine archive loop | 报告 `source_contract.engine` |
| XZip parser | 报告 `source_contract.zip` |
| XArchive unpack wrapper | 报告 `source_contract.archive` |
| XDecompress CRC path | 报告 `source_contract.decompress` |

报告同时绑定本地 fixture generator、baseline generator、harness source 和
Dockerfile 的 SHA-256。所有 stdout/stderr 经 zlib+base64 内容寻址保存；重复输出
只存一份 artifact。

## 夹具矩阵

生成器
[`generate_archive_adversarial_fixture.py`](../../tools/corpus/generate_archive_adversarial_fixture.py)
只使用项目生成的最小 PDF、零字节和固定字符串，不含第三方或恶意样本字节。
清单见
[`archive-adversarial-corpus.json`](data/archive-adversarial-corpus.json)。

| 样本 | 变量 | 独立控制 |
| --- | --- | --- |
| `stored-valid.zip` | stored 正例 | Python `zipfile` 可读 |
| `deflate-valid.zip` | raw deflate 正例 | Python `zipfile` 可读 |
| `deflate-high-ratio.zip` | 1 MiB / 1243-byte deflate | Python `zipfile` 可读，ratio > 800 |
| `zipcrypto-stored.zip` | traditional ZipCrypto | 无密码读取失败，固定密码 `diec-rust` 可还原 PDF |
| `stored-bad-crc.zip` | CRC 低位翻转 | Python 报 `BadZipFile` |
| `deflate-corrupt.zip` | compressed byte 翻转 | Python 报 `BadZipFile` |
| `deflate-truncated.zip` | payload 截半、声明长度不变 | Python 报 overlapping/possible zip bomb |
| `stored-local-only.zip` | 无 central directory/EOCD | Python 拒绝；上游 local fallback 正控制 |
| `stored-invalid-local-offset.zip` | central offset 指向 `0xFFFFFF00` | Python 报 truncated header |
| `unsupported-method-99.zip` | 未知 method、CRC=0 | Python 报 unsupported method |
| `stored-traversal-name.zip` | `../escape.pdf` metadata | Python 可读且保留原名 |
| `mixed-members.zip` | PDF + 1-byte member | Python 精确还原两成员和顺序 |

生成器测试要求两次输出逐字节一致，并用 Python 标准库对所有合法/畸形控制执行
独立验证。二进制 fixture 不提交仓库，只提交生成器和 hash manifest。

## Oracle 与模式

复用
[`archive_harness_main.cpp`](../../tools/upstream/archive_harness_main.cpp) 和固定
archive harness 镜像。每个样本执行：

1. harness default；
2. harness `--archive`；
3. harness `--archive --aggressive`；
4. 固定 release CLI `--json` default。

每次执行使用：

```text
--network none
--cpus 1
--memory 512m
--pids-limit 128
--read-only
fixture bind mount: read-only
timeout: 60 seconds
```

probe 保留原始 stream 后再生成结构摘要；摘要只抽取 root filetype/detection 和
Stream child 的 filetype、size、detection names，不删除或改写原始输出。

## 结果

| 类别 | normal archive | archive aggressive |
| --- | --- | --- |
| stored/deflate 正例 | PDF child | 相同 |
| 1 MiB 高压缩比 | 1,048,576-byte PDF child | 相同 |
| ZipCrypto 无密码 | 无 child | 无 child |
| bad CRC/corrupt/truncated | 无 child | 无 child |
| local-only | PDF child | 相同 |
| invalid local offset | 无 child；两条 seek warning | 相同 |
| method 99 | 无 child | 无 child |
| `../escape.pdf` | PDF child | 相同 |
| PDF + 1-byte | 仅 PDF child | PDF + Binary child |

除 mixed-member filter 外，archive 与 archive-aggressive 原始 stdout/stderr
逐字节相同。所有进程 exit 0；因此“无 child”不能由退出码区分为 encrypted、
CRC、deflate、offset 或 unsupported-method 原因。上游公共结果也没有为这些成员
生成结构化 diagnostic。

## Rust 兼容与安全要求

- legacy compatibility projection 需要保留“root 成功但成员静默缺失”的可观察结果，
  差分比较不能把它擅自转换成 top-level failure；
- canonical Rust API 必须为 encrypted/no-password、CRC mismatch、truncated
  compressed stream、invalid offset 和 unsupported method 提供结构化 member
  diagnostic，不能只写 stderr；
- 解压前必须同时预留成员数、声明展开字节、累计展开字节、ratio、时间和内存预算；
- archive metadata 不得直接用于文件系统写入；`../`、绝对路径、盘符、UNC、
  NUL 和分隔符变体需要独立安全测试；
- central-directory 缺失的 local-header fallback 属于兼容行为，但 parser 必须用
  checked arithmetic 前进，禁止无限循环和越界；
- aggressive 只改变 scanable filter，不得绕过 hard safety budget。

安全 API 与 legacy projection 的差异应按
[`ADR 0012`](../design/decisions/0012-bounded-nested-scan-budget.md) 和测试 waiver
机制记录，而不是把安全诊断隐藏为兼容成功。

## 复现

```powershell
$fixtureDir = Join-Path $env:TEMP diec-archive-adversarial
python tools\corpus\generate_archive_adversarial_fixture.py $fixtureDir
docker build -f tools\upstream\Dockerfile.archive-harness-qt5 `
  -t diec-rust/upstream-archive-harness:74eaf505 tools\upstream
python tools\upstream\probe_archive_adversarial_harness.py `
  --fixture-dir $fixtureDir `
  --output docs\research\data\archive-adversarial-engine-qt5.json
```

## 限制与剩余缺口

- 高压缩比仅到 1 MiB/843.58:1，不代表可接受任意展开量；
- 未测试 Zip AES、错误密码 API，因为固定 `SCAN_OPTIONS` 没有 archive password
  字段；
- 未覆盖 data descriptor、ZIP64、extra fields、symlink、重复名称、绝对路径、
  NUL/编码和多磁盘；
- 7Z/RAR4/CAB/ISO9660 的 EOF 前缀阶梯已由
  [`archive-truncation-behavior.md`](archive-truncation-behavior.md) 固定，
  首轮 size/offset/CRC/method/record-field 突变也已由
  [`archive-structure-behavior.md`](archive-structure-behavior.md) 固定，
  但 0/max/overflow、多记录和字段组合仍未系统化；
- 7Z LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64、x86/ARM64 BCJ+LZMA2
  与 CAB MSZIP
  正例及 7Z 七种基础 coder+AES、完整 x86/ARM64
   filter × 七种基础 coder × AES 的公共无密码、直接
   正确/缺失/错误密码边界已由后续
   [`archive-format-behavior.md`](archive-format-behavior.md) 固定；RAR3
   unpack29 method `0x35` 与 RAR5 method 5 压缩/solid 正例也已由
   [`archive-rar-compressed-behavior.md`](archive-rar-compressed-behavior.md)
   固定；仍未覆盖 RAR15/RAR20、RAR7 algorithm version 1、加密、多卷、恢复
   和损坏压缩流；
- 未测真实磁盘耗尽、16 MiB 临时文件分支、OOM、长时间取消与并发；
- Windows、macOS 和 Linux Qt6 仍需固定对应 oracle。
