# RAR5 Store 与 solid 成员行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 engine 对两个项目生成的 RAR5 Store 样本执行了 8
次受限 oracle：

- `rar5-store-single.rar` 在默认模式和固定 release CLI 中只得到顶层
  `RAR / Unknown`；启用 archive 后展开一个 331-byte `PDF / Stream`，
  命中 `PDF` 与 `HeaderComment`；
- `rar5-store-solid-pair.rar` 的 main header 设置 solid archive 位，第一项
  不设置 per-file solid 位，第二项设置该位。archive 模式按原顺序展开两个
  331-byte PDF，两项都命中相同规则；
- 对两个样本，archive+aggressive 的 stdout/stderr 与普通 archive
  逐字节相同；
- harness 默认输出与使用相同固定数据库的 release CLI 输出逐字节相同。

这证明固定版本的公共 engine 可达 RAR5 Store，并固定了 Store 成员进入 RAR
solid streaming 分支时的双成员可观察结果。它不证明 RAR15/20/29/50/70
专有压缩算法、加密、filter、分卷或资源耗尽行为，因此本实验单独没有关闭
`CAP-GAP-006`。后续闭合集合与 disposition 见
[`archive-gap-closure.md`](archive-gap-closure.md)。

## 安全且可追溯的语料

生成器
[`generate_rar5_store_fixture.py`](../../tools/corpus/generate_rar5_store_fixture.py)
仅构造 RAR5 signature、main/file/end headers、ULEB128 字段、CRC32 和 Store
data。payload 是项目已有的 canonical 331-byte PDF：

| 样本 | 结构 | Size | SHA-256 |
| --- | --- | ---: | --- |
| `rar5-store-single.rar` | RAR5 Store，单 PDF | 388 | `4ef16656e5ac5f95659d9ff1dd79706adda0b7df91e720b7461a58cb87d5fc7e` |
| `rar5-store-solid-pair.rar` | RAR5 solid，boundary PDF + solid-following PDF | 749 | `b7c5931d203f3146e38aebe64b9b6ef8cce8489003034ab036331818b4222a7f` |

机器清单
[`rar5-store-corpus.json`](data/rar5-store-corpus.json)逐成员记录名称、大小、
solid 位和 payload SHA-256。清单许可证字段为 `project-generated`，范围明确为
RAR5 container header 与 Store data；**不包含专有压缩算法，也不包含第三方
binary**。字段布局参考 RARLAB 公开的
[RAR 5.0 archive format](https://www.rarlab.com/technote.htm)，但生成结果及
payload 均由本项目控制。

生成器测试逐 header 重算从 header-size ULEB128 开始的 CRC32，校验 header
类型序列、data size、成员数量、名称、payload 次数和非法 solid 组合拒绝。
仓库只保存生成器与 JSON 清单，不保存生成出的 `.rar`。

## 固定 oracle 身份

| 项目 | 固定值 |
| --- | --- |
| 主仓库 commit | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| XArchive commit | `0fcd4e8d3e9933baac3b12246d82ac026557ffd0` |
| XScanEngine commit | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| 平台 | `linux-x86_64-qt5` |
| 镜像 | `diec-rust/upstream-archive-harness:74eaf505` |
| 镜像 ID | `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc` |
| Harness binary | `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e` |
| Release binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| Fixture manifest | `f240550330f17900ba49001f344366c979d1c8f06ab49bb78d70184a89d2110f` |

机器报告
[`rar5-store-engine-qt5.json`](data/rar5-store-engine-qt5.json) SHA-256 为
`788100fd4bb2d2009b9a4531c7b8880c1a0369bacca2ed1adf8700983ce4d264`。
报告保存 8 次执行的原始 stdout/stderr（`zlib+base64`）、结构化摘要、镜像、
二进制、fixture 和以下固定源码契约：

- `/opt/die-source/XScanEngine/xscanengine.cpp`：
  ZIP/7Z/RAR/CAB archive gate；
- `/opt/die-source/XArchive/xrar.cpp`：
  `XRar::initUnpack`、RAR5 Store method mapping、per-file solid 检测和 folder
  index；
- `/opt/die-source/XArchive/xdecompress.cpp`：
  带 `SOLIDFOLDERINDEX` 且无 `SUBSTREAMOFFSET` 的 RAR Store 成员进入
  `decompressRarSolid` 的分派条件。

报告同时绑定各源码文件 SHA-256 和 required-pattern 次数，不能从相邻版本或
其他 archive adapter 外推。

## 复现

前置条件是固定 archive harness 镜像已按
[`Dockerfile.archive-harness-qt5`](../../tools/upstream/Dockerfile.archive-harness-qt5)
构建：

```powershell
python tools/corpus/generate_rar5_store_fixture.py I:\tmp\rar5-store-fixture `
  --manifest docs/research/data/rar5-store-corpus.json

python tools/upstream/probe_rar5_store_harness.py `
  --fixture-dir I:\tmp\rar5-store-fixture `
  --output I:\tmp\rar5-store-engine-qt5.json
```

探针为每次容器执行设置：无网络、只读 root/fixture、1 CPU、512 MiB memory、
128 PID 和 60 秒 timeout。重新生成的报告应与受控报告逐字节相同。

## 剩余边界

本实验刻意不使用 RAR/WinRAR trial creator，也不导入来源或授权不清的 archive
样本。相应代价是仍未覆盖：

- RAR 1.5/2.x/3.x 压缩流；
- RAR5/RAR7 压缩、solid 压缩状态跨成员传递和 dictionary 极值；
- file/header encryption、password、filter、recovery 和 multi-volume；
- 损坏压缩流、真实内存/CPU 耗尽以及其他平台。

这些仍作为 RAR method/feature 扩展与安全风险保留；本报告只收窄 RAR5 Store
与 Store-solid 可观察行为，不把“容器可生成”误报为“RAR 压缩兼容已完成”。
`CAP-GAP-006` 的后续关闭只表示 engine family/记录/深度/总量闭集达到明确
标准，不把本段未测项改写为已验证。
