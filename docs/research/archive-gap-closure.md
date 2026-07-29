# Archive corpus gap 闭合审计

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

`CAP-GAP-006` 在固定 Linux x86_64 Qt5 基线上可以关闭。该结论不是因为继续
增加了任意数量的 archive 样本，而是因为缺口的三个维度现在都有可判定闭集：

1. 固定 `XScanEngine::scanProcess()` 的成员解包 gate 只允许
   `ZIP / 7Z / RAR / CAB / ISO9660` 五类；
2. 五类在固定 engine 中都有“默认不展开、显式 archive 后产生 PDF child”的
   成对运行证据，并映射到 `XFormats::createClass()` 的确切 adapter；
3. archive 记录循环已固定 `99999 / 100000 / 100001` 三点，证明第 100000 条
   可达而第 100001 条不可达；
4. 深度与累计展开量分别观察到 64 层和 33,554,546 bytes，同时源码窗口中没有
   独立 depth/total budget token。这里的结论严格是“固定上游没有独立上限且至少
   可达已测边界”，不是“更大输入安全”。

机器报告
[`archive-gap-closure.json`](data/archive-gap-closure.json) 的 SHA-256 为
`1b727c06c87a14fcb217e0fd69b3b8f935e1f2b7930461ff2a76dc3ffa8996b5`。
连续两次生成逐字节相同。

该报告将以下四项从 `observed_with_gaps` 收敛为 `observed`：

| Capability | 闭合证据 |
| --- | --- |
| `CAP-DISPATCH-004` | 公共分派已有固定 evidence set；成员解包 family 由源码证明为五项闭集，五项均有运行正反控制 |
| `CAP-NEST-003` | 五类默认扫描均为 0 child，显式 archive 均产生 1 个 PDF child |
| `CAP-NEST-004` | archive 第 99999、100000 条可达，第 100001 条不可达；resource 的 20/21 与 1000/1001 边界已由既有 option oracle 固定 |
| `CAP-NEST-009` | 源码没有独立深度/累计展开量预算；运行到达 64 层和 33,554,546 bytes |

该表是 Qt5 corpus-gap 闭环，不是跨 Qt major 的原始输出等价声明。后续固定
Qt6 复验发现 ISO9660 单 NUL dot entry 多占一次 archive iteration：第 99999
条 PDF 可达，第 100000/100001 条不可达；resource 21/2001 与 Qt5 相同。
根因和完整机器证据见
[`qt6-count-boundary-runtime-evidence.md`](qt6-count-boundary-runtime-evidence.md)。

## 三个集合不能混淆

固定 `Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201` 的
`XFormats::createClass()` 能构造很多 archive/compression parser，例如 TAR、
GZIP、BZIP2、XZ、LZIP、LHA、ARJ、ACE、CPIO、UDF 和 WIM。parser 存在不等于
DIE engine 会递归展开它。

必须区分：

- **格式检测集合**：`XFormats::_getFileTypes()` 可识别的类型；
- **adapter 构造集合**：`XFormats::createClass()` 可实例化的类型；
- **engine 成员解包集合**：`XScanEngine::scanProcess()` 在
  `bIsArchivesScan` 下明确加入 `bScanableArchive` 的类型。

第三个集合才是 `CAP-NEST-003/004/009` 的成员解包范围。固定源码中它是：

| 顺序 | File type | Adapter | 正向 oracle |
| ---: | --- | --- | --- |
| 1 | `FT_ZIP` | `XZip` | `deflate-valid.zip` |
| 2 | `FT_7Z` | `XSevenZip` | `pdf-member.7z` |
| 3 | `FT_RAR` | `XRar` | `pdf-member.rar` |
| 4 | `FT_CAB` | `XCab` | `pdf-member.cab` |
| 5 | `FT_ISO9660` | `XISO9660` | `pdf-member.iso` |

因此 TAR/GZIP 等公共 Binary fallback、NPM 的不可达自动分支和 IPA 的 Binary
quirk 仍属于公共分派兼容行为，但不是“缺少第六种 engine 解包 family”。
对应行为已经分别由
[`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)、
[`npm-dispatch-reachability.md`](npm-dispatch-reachability.md) 和
[`behavior-baseline.md`](behavior-baseline.md) 固定。

## 运行证据

五个正向控制全部满足：

- 未设置 engine archive option 时不产生 Stream child；
- 设置 archive option 后产生一个 `PDF` Stream child；
- 顶层类型和名称仍按各自公共分派契约保留，不能把 child 成功归一化成相同顶层
  输出。

ZIP 使用
[`archive-adversarial-engine-qt5.json`](data/archive-adversarial-engine-qt5.json)
的 deflate 正例，并以
[`archive-limit-engine-qt5.json`](data/archive-limit-engine-qt5.json)
的 depth-1 case 复核递归 child。7Z/RAR/CAB/ISO9660 使用
[`archive-format-engine-qt5.json`](data/archive-format-engine-qt5.json)。

机器 closure 报告固定六份输入报告的 path、bytes 与 SHA-256：

- archive adversarial：
  `f00210b660cbc45f6afb66599ea48b9285b392dd06fd9d686fef95148cc67937`；
- archive format：
  `d27ee4aa9c03be0939d495e6b9ab062f669f123eeff36ccfac16062d3089a784`；
- archive iteration：
  `57a78308860d6842bf2b33367451d696a7c3252d1411de2ed5c32d9659c29533`；
- archive limit：
  `e4786dcc578fb0714c86f71955161f981a06be26aefe663281d74202f5372ecd`；
- generic dispatch：
  `960fca28122af3bddb2fcd22706f5350ee8f4753a79a61cc2338aba7d1f53c04`；
- NPM dispatch：
  `d23168aff29696f46d3579f6d914353865035bd02a8bbbcf9af065475c036ce7`。

## 记录、深度与累计展开量

固定 archive 循环先执行：

```text
for (qint32 i = 0; (i < 100000) && not-canceled; i++)
```

然后才按已扫描 child 数比较普通模式 20 或 aggressive 100000。因此在
aggressive 模式中，外层 `i < 100000` 会先于 `nCurrentIndex > 100000` 生效。
ISO9660 sentinel oracle 观察到：

| Sentinel record | PDF child |
| ---: | ---: |
| 99999 | 1 |
| 100000 | 1 |
| 100001 | 0 |

深度/累计展开量 oracle 的最大成功点为：

| 维度 | 最大观察值 | 结果 |
| --- | ---: | --- |
| ZIP nesting depth | 64 | leaf PDF depth 64 |
| cumulative expanded bytes | 33,554,546 | depth-2 leaf PDF 可达 |

源码审计窗口同时固定递归 `scanProcess()` 调用、按声明 uncompressed size 创建
buffer，以及 `depth`、`cumulative`、`totaldecompressed`、`totalextracted`
token 计数均为 0。这证明固定版本没有相应独立 budget；不证明任意更大输入不会
OOM、超时或触发平台资源限制。

## 剩余风险与边界

关闭 corpus gap 不会关闭安全和平台风险：

- Rust 设计仍必须为深度、总展开量、时间、单项/总分配和记录数提供显式预算；
- 64 层与 33,554,546 bytes 是兼容观察点，不是建议的默认安全上限；
- RAR15/RAR20、RAR7 algorithm version 1、加密、多卷、恢复记录和损坏压缩流
  仍是具体 format/method 的扩展差分范围，但不再是“未知 engine family”；
- 本闭集生成时 Windows、macOS 和 Linux Qt6 baseline 仍由
  `CAP-GAP-007/008` 跟踪；后续
  [`qt6-capability-closure-plan.md`](qt6-capability-closure-plan.md)
  已关闭 Linux Qt6 `CAP-GAP-007`；后续 Windows 68 行 closure 也已关闭
  `CAP-GAP-008` 的 Windows 部分，macOS 仍开放；
- 历史 oracle 中的 `remaining_gap: CAP-GAP-006` 保留原始生成时结论，不修改
  固定报告；本 synthesis 报告及当前 traceability 是后续闭合证据。

## 可重复方法

检出固定组件：

```powershell
git clone https://github.com/horsicq/Formats.git formats
git -C formats checkout --detach 1151e7254fdee3c0294ff7095edbdd7bfccf8201

git clone https://github.com/horsicq/XScanEngine.git xscanengine
git -C xscanengine checkout --detach dfe4a419e4f491bb23688ba03c5a5bf39e34da83
```

生成 closure 报告：

```powershell
python tools\research\build_archive_gap_closure.py `
  --formats-root <formats> `
  --xscanengine-root <xscanengine> `
  --output docs\research\data\archive-gap-closure.json
```

生成器拒绝错误 remote/commit、dirty checkout、源码或输入报告 hash 漂移、
family gate 额外谓词、重复 family、adapter 映射变化、失败 assertion 以及边界
case 漂移。严格测试还固定生成器自身和最终报告 hash。
