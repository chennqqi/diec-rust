# Archive 多记录顺序与重名行为

Status: In Review
Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254
Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 上游镜像中，项目生成的 7Z Copy、RAR4 Store、CAB
Store 和 ISO9660 各自呈现相同的两记录契约：

- 显式 `archive` 按归档物理记录顺序输出两个可扫描 PDF child；把 331/332-byte
  PDF 的记录顺序交换后，child 顺序也同步交换；
- 两条记录使用相同成员名时，两个 child 均保留且仍按记录顺序输出，不按成员名
  去重；
- 首记录为空、次记录为 PDF 时，普通 `archive` 跳过空记录但继续输出后续 PDF；
  `archive+aggressive` 则先输出 0-byte `Binary / Empty file`，再输出 PDF；
- 非空样本的普通与 aggressive archive 原始 stdout/stderr 逐字节相同；
- harness default 与发布 CLI default 原始输出逐字节相同，均不展开成员；
- 16 个样本的四种模式共 64 次执行全部 exit 0，stderr 为空。

这关闭 `CAP-GAP-006` 中首轮四格式“两记录顺序、重名、空记录后续可达性”
子项，但不关闭整个 gap。上游 JSON child 不投影 archive member name，因此本实验
只能证明“fixture 中的同名两记录产生两个不同大小的 child”，不能声称公共 JSON
保留了成员名。

## 固定身份

- fixture manifest：
  [`data/archive-multirecord-corpus.json`](data/archive-multirecord-corpus.json)
  - SHA-256:
    `8079968fed78bfcd108e0e91bd153dc9270ad3777bc1b78ca05cb515eb919727`
  - 16 个项目生成样本，不含外部或专有压缩语料；
- oracle：
  [`data/archive-multirecord-engine-qt5.json`](data/archive-multirecord-engine-qt5.json)
  - SHA-256:
    `896a452aa9bb8c2c64536a45fcafea4247b130b3cce8c6105a0e6646aaf4b522`
  - image ID:
    `sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae885a894695abfa959bab5dc`
  - harness SHA-256:
    `b7ea9b151b58b630c017e9989333fa035b7d86ffab366a5d3a1f74bab9f1e96e`
  - release SHA-256:
    `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf`
  - 16 samples × 4 modes = 64 executions；
- 上游组件固定到主仓库对应 gitlink：
  - XScanEngine@`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
  - XArchive@`0fcd4e8d3e9933baac3b12246d82ac026557ffd0`

报告同时绑定容器内 `XScanEngine/xscanengine.cpp` 的 archive buffer 创建点及
`XArchive/xsevenzip.cpp`、`xrar.cpp`、`xcab.cpp`、`xiso9660.cpp` 的
`initUnpack` 入口、文件 SHA-256 和唯一源码模式计数，避免镜像标签漂移后继续
误用旧结论。

## 实验矩阵

每种格式都生成以下四个二记录样本：

| case | 记录 1 | 记录 2 | 普通 archive | aggressive archive |
| --- | --- | --- | --- | --- |
| `forward` | `first.pdf`, PDF 331 | `second.pdf`, PDF 332 | PDF 331, PDF 332 | 相同 |
| `reverse` | `second.pdf`, PDF 332 | `first.pdf`, PDF 331 | PDF 332, PDF 331 | 相同 |
| `duplicate-name` | `same.pdf`, PDF 331 | `same.pdf`, PDF 332 | PDF 331, PDF 332 | 相同 |
| `empty-first` | `empty.bin`, 0 bytes | `second.pdf`, PDF 331 | PDF 331 | Empty 0, PDF 331 |

格式编码全部由
[`generate_archive_multirecord_fixture.py`](../../tools/corpus/generate_archive_multirecord_fixture.py)
确定性产生：

- 7Z：两个独立 Copy packed stream、folder 和 file record；
- RAR4：两个 stored file header/payload；
- CAB：一个 Store folder/data block，两个 file entry 共享连续 payload；
- ISO9660：root directory 中两个 file record，分别指向独立 extent。

两种 PDF 只差尾部一个换行，使输出 size 足以区分记录顺序而无需依赖成员名。
生成器测试校验文件哈希、7Z start/next header CRC 和名称区、RAR file header
数、CAB `cFiles`、ISO directory record 数及四格式 × 四 case 笛卡尔积。

## Oracle 与事实字段

每个样本运行：

1. engine harness default；
2. engine harness `--archive`；
3. engine harness `--archive --aggressive`；
4. 发布 CLI `--json` default。

报告保存 zlib+base64 原始 stdout/stderr，并额外生成只用于精确断言的 root/stream
摘要。下列事实字段必须全部为 `true`：

- `all_multirecord_cases_exit_zero_without_stderr`
- `release_and_harness_default_outputs_are_equal`
- `all_formats_preserve_forward_record_order`
- `all_formats_preserve_reverse_record_order`
- `all_formats_keep_both_duplicate_name_records`
- `normal_archive_skips_empty_record_and_keeps_later_pdf`
- `aggressive_archive_keeps_empty_record_in_original_order`
- `nonempty_archive_outputs_ignore_aggressive_flag`

执行环境固定为只读 container root、只读 fixture mount、无网络、1 CPU、
512 MiB memory、128 PID 和单次 60 秒 timeout。报告不记录 wall-clock 时间，
因此相同输入、工具和镜像的重跑应逐字节一致。

## 兼容解释

顺序比较是语义字段，规范化不得排序 child。尤其是 `forward`/`reverse` 使用相同
payload 集合，只有物理记录顺序不同；若规范化排序，就会隐藏可观察差异。

重名成员也不能以 name 作为内部唯一键。公共 JSON 不含成员名，但两个不同大小
child 的存在证明扫描编排没有因同名而丢弃第二条记录。Rust canonical 模型应为
每条 archive record 分配稳定内部 identity，允许可选、重复或不可表示的名称；
legacy JSON 只按固定上游可观察字段投影。

普通模式跳过空成员并不终止枚举。aggressive 模式把空成员变为一个先于后续 PDF
的 child，说明 filter 决策必须逐记录执行，不能把“首记录不可扫描”误解释为整个
archive 失败。两种模式都必须在过滤前后维持同一相对记录顺序。

## Rust 安全与测试要求

- archive adapter 返回有序 record 序列；核心编排和所有输出层不得隐式排序或按名
  去重；
- record identity 与显示名称分离，重复名、空名和缺失名都不得覆盖既有结果；
- empty/member scanability 是模式相关决策，但不得绕过全局记录、展开字节、内存、
  时间和输出预算；
- 解包后 payload 的 declared/actual size、短读和 adapter diagnostic 进入 canonical
  结构化结果；legacy projection 再按固定 oracle 隐藏或映射；
- Phase 2 为四格式四 case 建立 Rust-vs-upstream 原始及规范化差分；顺序与重复项
  必须是不可忽略字段。

## 复现

```powershell
$fixtureDir = Join-Path $env:TEMP diec-archive-multirecord-v1
python tools\corpus\generate_archive_multirecord_fixture.py $fixtureDir `
  --manifest-output docs\research\data\archive-multirecord-corpus.json
python tools\upstream\probe_archive_multirecord_harness.py `
  --fixture-dir $fixtureDir `
  --output docs\research\data\archive-multirecord-engine-qt5.json
```

然后运行：

```powershell
python tools\tests\test_generate_archive_multirecord_fixture.py
python tools\tests\test_probe_archive_multirecord_harness.py
```

## 限制

- 每个 archive 仅两条记录；尚未覆盖更大记录图、目录/链接、嵌套路径、混合成功/
  失败记录或 record limit 交互；
- 7Z 仅独立 Copy stream，RAR4/CAB 仅 Store，ISO9660 仅单层 root directory；
- 未覆盖 solid/compressed/encrypted/multi-volume、多 extent、Joliet/Rock Ridge；
- 不验证成员名在 adapter 私有数据中的编码或归一化，仅验证公共扫描结果；
- 未测真实资源耗尽、arithmetic wrap、剩余字段/大小端冲突；
- Windows、macOS 和 Linux Qt6 尚未执行同一 64-case oracle。
