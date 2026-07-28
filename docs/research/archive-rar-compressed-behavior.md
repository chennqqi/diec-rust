# RAR3/RAR5 压缩与 solid 解包行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 engine 对四个外部、固定、非 SFX 的 RAR 样本执行了
4 样本 × 2 模式 × 2 重复 = 16 次禁网 oracle：

- RAR3 unpack version 29、method `0x35` 单成员在普通 archive 模式无 child，
  aggressive 模式展开 12-byte `Binary / Plain text`；
- RAR3 method `0x35` solid 双成员在 aggressive 模式按物理顺序展开
  87-byte PNG、220-byte JPEG，第二项设置 solid 位；
- RAR5 algorithm version 0、method 5 非 solid 双成员在 aggressive 模式按物理
  顺序展开 220-byte JPEG、87-byte PNG；creator 对第二个不可获益成员自动回退
  Store method 0；
- RAR5 method 5 solid 双成员在 aggressive 模式同样展开 JPEG、PNG，第二项设置
  solid 位并依赖前一成员的 dictionary 状态；
- 四个样本的普通 archive 模式都只保留顶层 `RAR / Unknown`。

这首次给 `CAP-GAP-006` 增加真实 RAR 压缩流和跨成员 solid 状态的运行证据，
证明固定 XArchive 可达 RAR29 与 RAR5 `Unpack5` 正常路径。它不证明 RAR15、
RAR20、RAR7 algorithm version 1、加密、multi-volume、recovery、损坏流或资源
极值。后续
[`archive-gap-closure.md`](archive-gap-closure.md)
已按 engine family、记录、深度与累计展开量的明确关闭标准关闭该 corpus gap；
这些未测 RAR method/feature 仍是扩展差分范围，不被闭合结论覆盖。

机器报告：

- 来源/结构清单
  [`rar-compressed-fixture-source.json`](data/rar-compressed-fixture-source.json)，
  SHA-256
  `b8993312c8fd9043b4c17f0dddfebd2483809e7159b9cd9a663ba3c864ee354a`；
- oracle
  [`rar-compressed-engine-qt5.json`](data/rar-compressed-engine-qt5.json)，
  SHA-256
  `9c71a16f5434454d94ed85a5e88a9f81496f909be7a2f7c27de79e5e7a4d4f9d`。

第二次完整生成的 oracle 报告与提交版本逐字节相同。

## 语料来源与再分发边界

四个样本来自
`ssokolow/rar-test-files@16b785c2b1b504e99fc307676e5369a26d3ce060`：

| 样本 | bytes | SHA-256 | 结构 |
| --- | ---: | --- | --- |
| `build/testfile.rar3.rar` | 98 | `dce342bc0c2852fcaa36a03da5e55abb7dd69c045bbd812faebebc1a3844f5a4` | RAR3 method `0x35`，单 text |
| `build/testfile.rar3.solid.cbr` | 381 | `610376cfa11ec11bf55cd117f5d5b83dd11dded6aad2f825b41dbe84d7f3098d` | RAR3 method `0x35`，PNG → solid JPEG |
| `build/testfile.rar5.cbr` | 410 | `e8b106048f18e6fb9a5f8ec6a95346e76906e7e4e9ca15ec97e4f926159cb398` | RAR5 method 5 JPEG → Store PNG |
| `build/testfile.rar5.solid.cbr` | 407 | `23ef370c58b7646d527106829410700ac314d86380b9c968a37066f39fe6c70b` | RAR5 method 5 JPEG → solid PNG |

候选仓库的 README：

- 声明这些是用于 test suite 的 minimal、legally redistributable RAR/CBR；
- 声明作者购买了 WinRAR license，并保存 `purchase_evidence.png`；
- 说明绝大多数输出由固定 Makefile 生成，统一使用 `-m5`；
- 对作者拥有的 archive 内容应用 CC0。

固定 RARLAB EULA 说明，license owner 创建并分发 RAR archive 不收额外
royalties。机器清单绑定 README、`LICENSE.md`、完整 `LICENSE.cc0`、Makefile、
purchase evidence、三个源 payload 和四个 archive 的 hash，并解析每个 RAR
header CRC、method、size、name、solid 位和 packed data hash。

这些是充分的候选来源证据，但 purchase screenshot 的真实性及 EULA 适用性仍需
发布/法律责任人确认。因此报告保持：

```text
project_legal_review_complete=false
project_redistribution_approved=false
```

本仓库不提交四个二进制，只保存固定远端、commit、hash、结构、许可证证据和
oracle 原始输出。oracle 从临时只读 checkout 运行，避免在评审完成前扩大项目
发布物。所有 `.exe/.bin` SFX、authenticity、recovery 和 locked 样本均排除。

## 固定结构

来源审计按公开 RAR3/RAR5 header 结构解析，不使用文件扩展名猜测：

| 样本 | member | packed → unpacked | method | solid |
| --- | --- | ---: | ---: | --- |
| RAR3 single | `testfile.txt` | 27 → 12 | `0x35` | false |
| RAR3 solid | `testfile.png` | 84 → 87 | `0x35` | false |
| RAR3 solid | `testfile.jpg` | 182 → 220 | `0x35` | true |
| RAR5 mixed | `testfile.jpg` | 214 → 220 | 5 | false |
| RAR5 mixed | `testfile.png` | 87 → 87 | 0 | false |
| RAR5 solid | `testfile.jpg` | 236 → 220 | 5 | false |
| RAR5 solid | `testfile.png` | 62 → 87 | 5 | true |

RAR3 file headers 声明 unpack version 29，因而对应 XArchive
`HANDLE_METHOD_RAR_29`/`rar_Unpack::Unpack29`。RAR5 compression info 的
algorithm version 为 0，method bits 为 5，对应
`HANDLE_METHOD_RAR_50`/`rar_Unpack::Unpack5`。RAR5 mixed 的 Store 第二项是
creator 的真实自动选择，不应把整个 archive 简化成“method 5 only”。

## Oracle 矩阵

| case | 普通 archive | archive + aggressive |
| --- | --- | --- |
| RAR3 method35 single | 0 child | `Binary:12` |
| RAR3 method35 solid pair | 0 child | `PNG:87`, `JPEG:220` |
| RAR5 method5 mixed pair | 0 child | `JPEG:220`, `PNG:87` |
| RAR5 method5 solid pair | 0 child | `JPEG:220`, `PNG:87` |

每个 cell 连续运行两次，原始 stdout 的 SHA-256 在 cell 内相同；报告保留全部
stdout base64、hash、命令、exit code、空 stderr 和结构化 projection。固定
image 为
`sha256:adf8e09f3ed7c15a54f3486c482599e1bcb122308a0b27396de1baf2ee634daf`，
OCI revision 与上游 commit 相同。fixture mount 只读且容器禁网。

结果中的 aggressive 差异不是解压能力差异：四个 archive 在普通模式均未把
成员加入结果树；aggressive 后才为 text/image 成员生成可观察 child。Rust
差分测试必须同时保留两种模式，不能仅用“解压成功”布尔值归一化。

## 可重复方法

取得固定外部 checkout：

```powershell
git clone https://github.com/ssokolow/rar-test-files.git rar-test-files
git -C rar-test-files checkout 16b785c2b1b504e99fc307676e5369a26d3ce060
```

生成来源清单：

```powershell
python tools\corpus\audit_rar_compressed_fixture_source.py `
  --source-root <rar-test-files-checkout> `
  --output docs\research\data\rar-compressed-fixture-source.json
```

运行固定 oracle：

```powershell
python tools\upstream\probe_rar_compressed_harness.py `
  --fixture-root <rar-test-files-checkout> `
  --output docs\research\data\rar-compressed-engine-qt5.json
```

两个工具都拒绝错误 remote、commit、dirty checkout 或文件 hash。来源审计还拒绝
坏 header CRC、截断 vint、越界 size 和路径穿越名称；oracle 绑定 fixture 清单、
审计器、harness 源码/Dockerfile/二进制、五个固定 RAR 调用链源码 hash 和 image。

## 剩余边界

- RAR 1.5 与 2.x (`Unpack15`/`Unpack20`)；
- RAR7 algorithm version 1、80-distance-code 和非 2 次幂 dictionary；
- encrypted data/header、错误/缺失密码；
- multi-volume、split-before/after、missing volume；
- recovery/authenticity/locked/service/quick-open records；
- CRC、packed/unpacked size、dictionary、distance 和 PPM/VM 损坏矩阵；
- 解压炸弹、超大 dictionary、取消、时间/内存上限；
- Windows、macOS、Qt6，以及最终 Rust backend 差分；
- 四个外部 fixture 的项目再分发书面结论。
