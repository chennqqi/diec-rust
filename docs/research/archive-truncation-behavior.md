# 上游多格式归档截断边界行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 oracle 对 7Z、RAR4、CAB 和 ISO9660 的 26 个项目生成
前缀样本执行 default、archive、archive-aggressive 与发布 CLI default，共 104
次运行。所有进程 exit 0、stderr 为空；harness default 与发布 CLI 原始输出逐字节
相同，archive 与 archive-aggressive 原始输出也逐字节相同。

观察到的关键边界是：

- 7Z 到 packed-data 末尾时已报告 `Binary / 7-Zip`，但缺少完整 next header
  时不产生 child；仅完整 427-byte 控制样本产生 331-byte PDF child；
- CAB 到 CFDATA 起点时已报告 `Binary / CAB`，完整样本少最后一个 byte 仍不产生
  child；仅完整 411-byte 控制样本产生 PDF child；
- RAR4 在 file header 完整时报告 `RAR / Unknown`；到声明 payload 末尾即产生
  PDF child，不需要最后 7-byte end-of-archive header，少最后一个 byte 也保持
  child；
- ISO9660 在仅包含 primary descriptor 的早期前缀就报告
  `ISO 9660 / Unknown`；到完整目录区仍无 child，但完整样本少最后一个 byte 时
  已产生声明大小为 331 bytes 的 PDF child；
- signature 或 partial-header 前缀均不产生 child；其中 CAB 的 4-byte `MSCF`
  前缀被规则层投影为 `Binary / Plain text`，其余相关早期前缀为 Unknown。

机器报告：
[`archive-truncation-engine-qt5.json`](data/archive-truncation-engine-qt5.json)，
SHA-256
`2bddd90d5670c4e91e8147cf22395c914804c547d487ac29d4bd1da38f773e30`。

这些结果固定了 `CAP-GAP-006` 的多格式系统化 EOF 截断子集；RAR 压缩/加密、
solid/multi-volume 和更多结构字段畸变仍是扩展差分范围，跨平台行为由独立
gap 跟踪。该 corpus gap 后续已由
[`archive-gap-closure.md`](archive-gap-closure.md)
按五类 engine family、记录、深度与累计展开量标准关闭。

## 固定身份与证据链

| 项目 | 固定证据 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| harness image | 报告 `image.id` 与 OCI revision |
| release/harness binaries | 报告 `binaries.*.sha256` |
| XScanEngine archive loop | 报告 `source_contract.engine` |
| XSevenZip unpack path | `XArchive/xsevenzip.cpp`, `XSevenZip::initUnpack` |
| XRar unpack path | `XArchive/xrar.cpp`, `XRar::initUnpack` |
| XCab unpack path | `XArchive/xcab.cpp`, `XCab::initUnpack` |
| XISO9660 unpack path | `XArchive/xiso9660.cpp`, `XISO9660::initUnpack` |

报告同时绑定语料生成器、其来源格式生成器、harness source、Dockerfile 和清单
SHA-256。stdout/stderr 使用 SHA-256 内容寻址，并以 zlib+base64 原样保存；
结构摘要只抽取 root 与 Stream child 的 filetype、size 和 detection names。

## 语料

生成器
[`generate_archive_truncation_fixture.py`](../../tools/corpus/generate_archive_truncation_fixture.py)
复用项目生成的 7Z Copy、RAR4 store、CAB store 和 ISO9660 完整控制样本。
每个截断样本都是相应完整样本从 byte 0 开始的精确前缀，不导入第三方或未知
来源内容。版本化清单见
[`archive-truncation-corpus.json`](data/archive-truncation-corpus.json)。

| 格式 | 截断阶梯 |
| --- | --- |
| 7Z | signature 6、header−1 31、header 32、packed-data 363、full−1 426、full 427 |
| RAR4 | signature 7、main-header−1 19、main header 20、file header 63、payload 394、full−1 400、full 401 |
| CAB | signature 4、header−1 35、header 36、folder 44、data start 72、full−1 410、full 411 |
| ISO9660 | descriptor signature 32774、version 32775、primary descriptor 34816、directory end 40960、full−1 43007、full 43008 |

生成器测试要求两次输出逐字节一致、清单完全相等、26 个样本身份固定，并验证
每条阶梯严格递增且每个文件都是完整控制的精确前缀。二进制语料不提交仓库。

## Oracle 契约

每个样本执行：

1. archive harness default；
2. archive harness `--archive`；
3. archive harness `--archive --aggressive`；
4. 固定发布 CLI `--json` default。

每次执行使用 `--network none`、1 CPU、512 MiB memory、128 pids、只读容器根、
只读 fixture mount 和 60 秒超时。探针在写报告前严格验证：

- `all_truncation_cases_exit_zero_without_stderr`
- `release_and_harness_default_outputs_are_equal`
- `archive_and_aggressive_outputs_are_equal`
- `sevenzip_full_minus_one_detects_but_has_no_child`
- `cab_full_minus_one_detects_but_has_no_child`
- `rar4_payload_boundary_reaches_pdf_without_end_header`
- `iso9660_full_minus_one_reaches_declared_pdf_child`
- `signature_or_partial_headers_do_not_produce_children`

任一输入身份、镜像 revision、源码锚点、退出码、stderr、root 检测、child 数量、
child 大小或 detection 顺序变化都会使探针失败，而不是生成新的“成功”基线。

## 可观察结果

| 格式 | 最早格式识别前缀 | 最早 PDF child 前缀 | EOF−1 行为 |
| --- | --- | --- | --- |
| 7Z | packed-data，363 bytes | full，427 bytes | 识别 7-Zip，无 child |
| RAR4 | file-header，63 bytes | payload，394 bytes | PDF child |
| CAB | data-start，72 bytes | full，411 bytes | 识别 CAB，无 child |
| ISO9660 | descriptor-signature，32774 bytes | full−1，43007 bytes | 331-byte PDF child |

default 模式对所有样本均不展开归档成员，因此格式 root 检测与 child 展开是两个
独立可观察维度。所有失败截断都没有结构化 error 或 stderr，不能通过退出码区分
“尚未达到记录边界”和“解包失败”。

## Rust 兼容与安全约束

- legacy 差分投影必须分别比较 root filetype/detection 与 child 列表，不能用
  “识别了归档”替代“成功展开成员”；
- 7Z/CAB 的 EOF−1 静默无 child、RAR4 对缺失 end header 的容忍以及 ISO9660
  EOF−1 仍产生声明大小 child 都需要回归向量；
- canonical Rust API 应对截断记录、缺失 trailer 和 short read 产生结构化
  diagnostic；legacy projection 可以保持上游的 exit 0/空 stderr 结果；
- 所有 offset、声明长度与加法必须 checked，读取不足不得 panic、越界、无限循环
  或按攻击者声明执行无界分配；
- ISO9660 EOF−1 的 child size 是上游可观察兼容事实，不是允许 Rust parser
  读取输入边界之外的理由；安全实现需要明确 short-read 状态并在兼容投影中记录
  必要 waiver。

## 复现

```powershell
$fixtureDir = Join-Path $env:TEMP diec-archive-truncation-v1
python tools\corpus\generate_archive_truncation_fixture.py $fixtureDir
docker build -f tools\upstream\Dockerfile.archive-harness-qt5 `
  -t diec-rust/upstream-archive-harness:74eaf505 tools\upstream
python tools\upstream\probe_archive_truncation_harness.py `
  --fixture-dir $fixtureDir `
  --output docs\research\data\archive-truncation-engine-qt5.json
```

因为报告不保存 wall-clock 时间，同一镜像、源码、生成器和输入下重复运行必须生成
逐字节相同的报告。

## 限制与剩余缺口

- 本实验仅系统化 EOF 前缀截断，没有翻转 size、offset、CRC、method 或
  record count；
  首轮 CRC/size/offset/method/record-field mutation 已由
  [`archive-structure-behavior.md`](archive-structure-behavior.md) 固定，但
  已列字段的 0/max 见
  [`archive-structure-behavior.md`](archive-structure-behavior.md)；两记录顺序、
  重名与空成员过滤由
  [`archive-multirecord-behavior.md`](archive-multirecord-behavior.md) 固定；
  ISO9660 首轮 17-field 双端序冲突由
  [`iso9660-endian-behavior.md`](iso9660-endian-behavior.md) 固定；
  path-table location/多字段组合冲突、arithmetic wrap 与更大或混合失败记录图
  仍缺；
- 7Z 仅覆盖 Copy 控制，其他 coder 的正向/密码行为由
  [`archive-format-behavior.md`](archive-format-behavior.md) 覆盖，但尚无同等
  截断阶梯；
- RAR4 仅 stored 单成员，没有压缩、加密、solid、multi-volume 或恢复记录；
- CAB 仅 store，未对 MSZIP/LZX/Quantum 建立截断阶梯；
- ISO9660 仅单文件、单目录的最小控制；
- Windows、macOS、Linux Qt6 的相同 104-case oracle 尚未固定。
