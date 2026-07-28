# ISO9660 双端序冲突行为

Status: In Review
Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254
Last updated: 2026-07-28

## 结论

ISO9660 用相邻 little-endian/big-endian 半字段冗余编码多个 16/32-bit 值。固定
Linux x86_64 Qt5 上游镜像对 17 个字段分别执行“只改 LE、BE 保持控制值”和
“只改 BE、LE 保持控制值”，加一个合法控制，共 35 个样本、140 次执行：

- 35 个样本在 default、archive、archive+aggressive 和发布 CLI default 中均
  exit 0、stderr 为空，并保留 `ISO 9660 / Unknown` root；
- 17 个只修改 BE 半字段的样本在 archive 中都仍输出控制的 331-byte PDF child；
- 只修改 LE `logical block size`、PVD root extent 或 payload extent 时不产生
  child；
- 只修改 LE payload size `331→332` 时产生声明大小为 332 的 PDF child；
- 其余 13 个只修改 LE 半字段的样本在当前单目录单文件路径上仍输出
  331-byte PDF；
- archive 与 archive+aggressive 原始输出逐字节相同；harness default 与发布
  CLI default 原始输出逐字节相同。

因此，对本实验中确实影响可观察结果的 block/extent/size 字段，上游 legacy 路径
读取 LE 半字段且不要求 BE 副本一致；BE 半字段冲突不会阻止格式识别或成员展开。
对其余字段只能证明“当前路径没有可观察差异”，不能据此断言上游完全不读取或永远
忽略它们。

这关闭 `CAP-GAP-006` 中 ISO9660 首轮 17-field `both16`/`both32` 双端序冲突
子项，但不关闭整个 gap。

## 固定身份

- fixture manifest：
  [`data/iso9660-endian-corpus.json`](data/iso9660-endian-corpus.json)
  - SHA-256:
    `0075dfcde4d33571d2b71b5db2738e81f46dc1cb67ca5883b86919233d6365c7`
  - 35 个项目生成样本，不含第三方样本；
- oracle：
  [`data/iso9660-endian-engine-qt5.json`](data/iso9660-endian-engine-qt5.json)
  - SHA-256:
    `6bcd987b0dd4d14e2280f2ac86790ece3e8008b17b84fe823691760405d9e306`
  - image ID:
    `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc`
  - 35 samples × 4 modes = 140 executions；
- 上游组件固定到主仓库对应 gitlink：
  - XScanEngine@`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
  - XArchive@`0fcd4e8d3e9933baac3b12246d82ac026557ffd0`

报告绑定 harness/release 二进制、镜像 revision、容器内
`XScanEngine/xscanengine.cpp` archive buffer 创建点以及
`XArchive/xiso9660.cpp::initUnpack`；同时保留探针、fixture generator、基础
archive generator、harness source/Dockerfile 的 SHA-256。

## 字段矩阵

生成器
[`generate_iso9660_endian_fixture.py`](../../tools/corpus/generate_iso9660_endian_fixture.py)
从同一个 21-block、2048-byte logical block 的项目生成控制镜像出发，覆盖：

| 结构 | 双端序字段 |
| --- | --- |
| Primary Volume Descriptor | volume space size、volume set size、volume sequence number、logical block size、path table size |
| PVD root directory record | extent、size、volume sequence number |
| root `.` record | extent、size、volume sequence number |
| root `..` record | extent、size、volume sequence number |
| payload record | extent、size、volume sequence number |

每个 mutation 只改一侧半字段：

- `little-alternate`：LE 写入精确 alternate，BE 保持 control；
- `big-alternate`：BE 写入同一 alternate，LE 保持 control。

alternate 选择为最小、可解释且不改变文件长度的值：volume/block/record 字段使用
`±1` 或 `2048→1024`；payload size 使用 `331→332`。manifest 保存字段逻辑
offset、宽度、control/alternate、实际 changed-byte 范围、控制与样本哈希。

## 精确可观察分类

| field | LE alternate | BE alternate | 解释边界 |
| --- | --- | --- | --- |
| PVD logical block size | 无 child | PDF 331 | LE block size 参与 extent 定位 |
| PVD root extent | 无 child | PDF 331 | LE root extent 决定目录位置 |
| payload extent | 无 child | PDF 331 | LE payload extent 决定成员位置 |
| payload size | PDF 332 | PDF 331 | LE 声明长度决定 child size |
| 其余 13 字段 | PDF 331 | PDF 331 | 当前路径无可观察变化 |

“无 child”不是 top-level failure：root 仍为 ISO9660，进程 exit 0 且没有结构化
error 或 stderr。payload size 332 也不是安全实现可越界读取的许可；输入尾部有
零填充，实验只证明上游 projection 采用 LE 声明长度。

## Oracle 与事实字段

报告保存 zlib+base64 原始 stdout/stderr，并要求以下字段全部为 `true`：

- `all_endian_conflict_cases_exit_zero_without_stderr`
- `release_and_harness_default_outputs_are_equal`
- `all_conflicts_keep_iso9660_root_detection`
- `all_big_endian_alternates_keep_control_child_projection`
- `little_endian_offsets_and_block_size_control_child_reachability`
- `little_endian_payload_size_controls_declared_child_size`
- `other_little_endian_alternates_keep_control_child_projection`
- `archive_and_aggressive_outputs_are_equal`

运行环境固定为只读 container root、只读 fixture mount、无网络、1 CPU、
512 MiB memory、128 PID 和单次 60 秒 timeout。报告不写入 wall-clock 时间，
相同工具、fixture 和镜像重跑必须逐字节一致。

## Rust 安全与兼容要求

- parser 必须同时读取并比较 ISO9660 双端序副本；不一致产生 typed diagnostic，
  不能静默当作规范合法输入；
- legacy projection 对本页四个可观察字段采用 LE 值，以保持 root/child、顺序和
  声明 size 兼容；canonical API 同时保留 LE、BE 与 chosen value；
- extent×logical-block-size、offset+size 和目录迭代全部使用 checked arithmetic，
  在 seek、slice 和分配前执行 range/budget 校验；
- mismatch diagnostic 不得自动升级为 top-level failure；是否继续按 LE 解析由
  compatibility policy 决定；
- Phase 2 为 35-case 全矩阵建立 Rust-vs-upstream 差分，并额外断言 canonical
  diagnostic，防止 legacy formatter 隐藏安全信息。

## 复现

```powershell
$fixtureDir = Join-Path $env:TEMP diec-iso9660-endian-v1
python tools\corpus\generate_iso9660_endian_fixture.py $fixtureDir `
  --manifest-output docs\research\data\iso9660-endian-corpus.json
python tools\upstream\probe_iso9660_endian_harness.py `
  --fixture-dir $fixtureDir `
  --output docs\research\data\iso9660-endian-engine-qt5.json
```

然后运行：

```powershell
python tools\tests\test_generate_iso9660_endian_fixture.py
python tools\tests\test_probe_iso9660_endian_harness.py
```

## 限制

- 只覆盖 control image 中 17 个 `both16`/`both32` 字段，没有覆盖 path table
  自身分开的 L/M table location、multi-extent、Joliet 或 Rock Ridge；
- 只使用单层 root directory 和单个 PDF member；其他目录图可能读取当前无可观察
  差异的字段；
- alternate 是小幅偏离，不替代 0/max、EOF 截断或组合冲突矩阵；对应 0/max 已由
  [`archive-structure-behavior.md`](archive-structure-behavior.md) 部分固定；
- 没有覆盖多个字段同时冲突、算术 wrap、真实资源耗尽或 malformed directory
  graph；
- Windows、macOS 和 Linux Qt6 尚未执行同一 140-case oracle。
