# 上游多格式归档结构字段畸变行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 oracle 对 7Z、RAR4、CAB 和 ISO9660 的 33 个项目生成
control/结构字段突变样本执行 default、archive、archive-aggressive 与发布 CLI
default，共 132 次运行。所有进程 exit 0、stderr 为空；harness default 与发布
CLI 原始输出逐字节相同。

关键观察如下：

- 7Z 的 start-header CRC、next-header CRC 和 packed CRC 各自位翻转后仍展开
  331-byte PDF；next-header offset/size 指向 EOF 之后或 unpacked size 加一则
  保留 `Binary / 7-Zip` root，但静默抑制 child；
- RAR4 的 main/file header CRC 位翻转不阻止展开；packed size 或 name size
  加一也仍展开 PDF；data CRC 位翻转、未知 method `0x7f` 或 unpacked size
  加一则不产生 child；
- CAB 的 `cbCabinet−1` 和 CFDATA `cbUncomp+1` 仍展开 331-byte PDF；
  data offset、file size、folder offset 或 compressed size 加一均静默无 child；
  files offset 加一与未知 method 在 normal archive 无 child，但 aggressive
  分别扫描 1-byte 和 331-byte `Binary / Unknown` 输出；
- ISO9660 descriptor ID 位翻转使顶层从 `ISO 9660` 回退为 `Binary`；volume
  size 少一 block 和 root directory size 少一仍展开 PDF；logical block size、
  root/payload extent 或 payload record length 畸变抑制 child；payload size
  加一直接产生声明大小为 332 bytes 的 PDF child。

机器报告：
[`archive-structure-engine-qt5.json`](data/archive-structure-engine-qt5.json)，
SHA-256
`f979b55fa9e48e9c40bbc7cfcc353e3ee3c574eb6e1d6b9144b26f0c0bbcb176`。

本实验关闭 `CAP-GAP-006` 的首轮 7Z/RAR4/CAB/ISO9660 CRC、size、offset、
method 和 record-field 突变子集，但不关闭该 gap；压缩/加密 RAR、更多 coder、
极值/整数溢出、multi-record/solid/multi-volume、恢复记录和跨平台行为仍缺。

## 语料与隔离策略

生成器
[`generate_archive_structure_fixture.py`](../../tools/corpus/generate_archive_structure_fixture.py)
复用项目生成的 7Z Copy、RAR4 store、CAB store 与 ISO9660 单 PDF 控制。
版本化清单见
[`archive-structure-corpus.json`](data/archive-structure-corpus.json)。

| 格式 | 样本数 | 目标字段 |
| --- | ---: | --- |
| 7Z | 7 | start CRC、next offset/size/CRC、packed CRC、unpacked size |
| RAR4 | 8 | main/file header CRC、packed/unpacked size、data CRC、method、name size |
| CAB | 9 | cabinet/files/data offset、method、file/folder offset、compressed/uncompressed size |
| ISO9660 | 9 | descriptor ID、volume/block/root/payload extent/size、record length |

每个 mutation 与相应 control 等长。manifest 保存 control hash、结果 hash、
changed-byte count 和最小/最大变更 offset。生成器测试逐字节重建差分，并验证：

- 7Z 除目标 start CRC 外均保持 start-header CRC 有效；
- packed CRC/unpacked size mutation 重算 next-header CRC 和 start CRC；
- next-header CRC mutation 仅使目标 CRC 无效，同时重算 start CRC；
- RAR 除目标 header CRC case 外均重算对应 file header CRC；
- 所有字段写入值和大小端编码与声明 mutation 一致。

这使 CRC 观察不会被更外层 CRC 提前拒绝。语料只含项目生成内容，二进制文件不
提交仓库。

## 固定身份与 Oracle

| 项目 | 固定证据 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| harness image | 报告 `image.id` 与 OCI revision |
| release/harness binaries | 报告 `binaries.*.sha256` |
| scanner/archive adapters | 报告 `source_contract` 中五个源码文件及 symbol pattern |
| 本地生成器和 harness | 报告 `local_sources` 的逐文件 SHA-256 |

每个样本执行 harness default、`--archive`、`--archive --aggressive` 和固定
release `--json` default。每次运行使用无网络、1 CPU、512 MiB、128 pids、
只读容器根、只读 fixture mount 和 60 秒超时。

探针先校验 fixture 全字段、文件 inventory/hash、源生成器 hash、镜像 revision、
二进制和源码 symbol，再执行并严格比较 root、child、size、detection 顺序、
退出码与 stderr。stdout/stderr 以 SHA-256 内容寻址、zlib+base64 原样保存。

报告中的冻结事实是：

- `all_structure_cases_exit_zero_without_stderr`
- `release_and_harness_default_outputs_are_equal`
- `sevenzip_start_next_and_packed_crc_mutations_still_unpack`
- `sevenzip_past_eof_and_unpacked_size_mutations_suppress_child`
- `rar4_header_crc_mutations_still_unpack`
- `rar4_packed_and_name_size_plus_one_still_unpack`
- `rar4_data_crc_method_and_unpacked_size_mutations_suppress_child`
- `cabinet_size_and_uncompressed_size_mutations_still_unpack`
- `cab_files_offset_and_unknown_method_are_aggressive_only`
- `cab_data_file_folder_and_compressed_size_mutations_suppress_child`
- `iso9660_descriptor_id_mutation_falls_back_to_binary`
- `iso9660_volume_and_root_size_mutations_still_unpack`
- `iso9660_payload_size_controls_declared_child_size`
- `iso9660_block_extent_and_record_mutations_suppress_child`

## 兼容解释

CRC 字段存在不表示上游一定强制校验。当前固定路径可观察到：

- 7Z 三类被测 CRC mutation 均未阻止 Copy member；
- RAR4 header CRC 未阻止成员，但 data CRC mutation 阻止 child；
- 上游对失败原因均不产生结构化 error 或 stderr，进程仍 exit 0。

因此 Rust legacy projection 必须分别比较 root 与 child，且不能把所有 CRC
mismatch 统一投影为 top-level failure。canonical API 则应保留具体 field、
expected/actual value 和 member diagnostic，避免延续上游的静默失败。

CAB aggressive 的两条结果也不是成功解压证明：normal mode 无 child，
aggressive 只是继续扫描 adapter 产生的 1/331-byte Binary 输出。Rust 差分测试
必须保留 mode 差异，不能只比较“存在 child”。

ISO9660 payload size 加一时输出 size 332，而输入实际 PDF 仍为 331 bytes。这是
上游声明长度驱动的可观察行为，不是允许 Rust 从输入边界之外读取的理由。
安全实现必须使用 checked range/short-read，并通过显式 compatibility waiver
决定 legacy size projection。

## Rust 安全与测试要求

- parser 所有 size、offset、block multiplication 和 range addition 使用 checked
  arithmetic，并在分配前执行预算；
- CRC policy 必须按格式和层级建模，不能使用一个全局“忽略/强制”开关；
- unknown method、short read、invalid extent 和 record termination 产生 typed
  diagnostic；legacy formatter 可按固定 oracle 隐藏，但原始 canonical 结果不可丢失；
- aggressive 只改变 scanable filter，不得绕过 memory/time/output hard budget；
- Phase 2 为本页每个 mutation 建立 Rust-vs-upstream 差分回归，并扩展
  zero/max/endian-disagree/overflow、重复 record 与多成员 property/fuzz vectors。

## 复现

```powershell
$fixtureDir = Join-Path $env:TEMP diec-archive-structure-v1
python tools\corpus\generate_archive_structure_fixture.py $fixtureDir
python tools\upstream\probe_archive_structure_harness.py `
  --fixture-dir $fixtureDir `
  --output docs\research\data\archive-structure-engine-qt5.json
```

报告不记录 wall-clock 时间；固定输入和镜像下重复运行必须逐字节一致。

## 限制

- 每个字段仅有一个邻近或固定未知值，没有覆盖 0、最大值和 arithmetic wrap；
- 7Z 仅 Copy，RAR4/CAB 仅 stored control，未覆盖压缩或加密结构图；
- ISO9660 没有多目录、multi-extent、Joliet/Rock Ridge 或大小端冲突；
- 没有通过第三方 parser 把畸形样本声明为“标准合法”；测试目标是精确、可审计
  的单字段 mutation 与固定上游反应；
- Windows、macOS 和 Linux Qt6 尚未运行同一 132-case oracle。
