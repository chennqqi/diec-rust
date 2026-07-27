# Archive 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已把第六个原样格式规则连接到 Rust 从 ZIP 字节解析出的
真实 metadata context。固定 `Archive/_Archive.0.sg` 在项目生成的 stored ZIP、
同一输入的 quiet 反例和移除 local record 的 central-directory-only 边界上，
与 Qt 5.15.13 `QScriptEngine + XZip + Archive_Script` oracle 3/3 一致：

| Case | Verbose | XZip valid | Metadata | Detection |
| --- | --- | --- | --- | --- |
| stored ZIP | true | true | `ZIP / 2.0 / Store` | `format / ZIP / 2.0 / Store` |
| same stored ZIP | false | true | `ZIP / 2.0 / Store` | none |
| central directory only | true | true | `ZIP / 2.0 / Store` | `format / ZIP / 2.0 / Store` |

三例的四个 native 返回、`detect()` boolean 和完整四元 detection 均一致。
调用路径也一致：每例调用一次 `Archive.isVerbose()`；quiet 例不调用三个 metadata
getter，两个 verbose 例各调用一次。central-directory-only 例的 central header
仍指向已删除的 local record；Rust 单独记录一次 local-header signature mismatch，
但和固定 XZip 一样不把它作为 metadata 或 detection 的否决条件。

该结果只证明固定规则在单一 stored ZIP metadata 分支上的可达语义，不能外推到
完整 XArchive 格式族、全部 ZIP compression/encryption/options 或 archive 成员扫描。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- XArchive：`0fcd4e8d3e9933baac3b12246d82ac026557ffd0`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：`Archive/_Archive.0.sg`，421 bytes，SHA-256
  `97202e19118514bcd33ef40c2dea69822249406092eddcb61f56e3410278ec86`
- 生成语料：
  [`archive-rule-fixture.json`](data/archive-rule-fixture.json)，SHA-256
  `04ee27fe5741ad9b65098722213d67058f748416e7075256dacf26a3be4d6b6b`
- Qt5 baseline：
  [`archive-rule-qt5.json`](data/archive-rule-qt5.json)，SHA-256
  `92d33c5982fcb457c0a07b30dbe1ef262ac5ccf36ca00fa5151c7b2e3f10c97c`

规则由 harness 从固定 rules subtree 读取并校验 hash，不复制、格式化或修改。
[`generate_archive_rule_fixture.py`](../../tools/corpus/generate_archive_rule_fixture.py)
只生成一个 stored local header、central header 和 EOCD，不包含第三方样本。
边界例在 offset 0 放置空 EOCD，保留 central header 和指向它的最终 EOCD。

## 上游语义证据

固定源码的实际调用链是：

1. `Detect-It-Easy/db/Archive/_Archive.0.sg` 先调用 `Archive.isVerbose()`；
   仅 true 时依次读取 name、version、options，且只有非空 name 才检测。
2. `XArchive/xzip.cpp:XZip::isValid` 只要求 offset 0 是 local-header 或 EOCD
   signature。
3. `Formats/xbinary.cpp:XBinary::getFileFormatInfo` 在 valid 且 size 非零时读取
   file type、version、info、compression method 和 encryption。
4. `XZip::getFileType` 返回 `FT_ZIP`；固定 Formats table 将其映射为 `ZIP`。
5. `XZip::getVersion` 通过最后 0x1000 bytes 内最后一个有效 EOCD 找 central
   header，读取 creator version 的低字节并除以 10；本语料得到 `2.0`。
6. `XZip::getCompressMethodString` 最多检查 20 个 central headers，只对
   uncompressed size 非零的记录收集方法；本语料得到 `Store`。
7. `XScanEngine/modules/binary_script.cpp:Binary_Script` 构造时缓存
   `FILEFORMATINFO`；`getFileFormatName/Version/Options` 分别返回 file type
   映射、version 和 `getFileFormatInfoString`。
8. `Binary_Script::isVerbose` 直接返回 `OPTIONS.bIsVerbose`。

`Archive_Script` 构造时还会对 XZip 调用 `getRecords(20000)`，但本规则不读取
record API；因此本实验不把成员枚举结果误当作规则覆盖证据。

## Oracle 与复现

[`archive_rule_harness_main.cpp`](../../tools/upstream/archive_rule_harness_main.cpp)
直接构造固定 `XZip`/`Archive_Script`，保存 parser valid、四个 native 返回、
detect boolean、完整 tuple 和 `PDSTRUCT` error。
[`probe_archive_rule_harness.py`](../../tools/upstream/probe_archive_rule_harness.py)
在断网、512 MiB、1 CPU、128 PID 容器中绑定 image revision、harness binary、
规则、fixture 和 baseline hash。

```sh
python tools/corpus/generate_archive_rule_fixture.py \
  docs/research/data/archive-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.archive-rule-harness-qt5 \
  -t diec-rust/archive-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_archive_rule_harness.py \
  --image diec-rust/archive-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-archive-rule-harness \
  --fixture docs/research/data/archive-rule-fixture.json \
  --baseline docs/research/data/archive-rule-qt5.json
```

## Rust spike

受控 `ArchiveRuleContext`：

- 只接受固定 XZip 认可的 offset-0 signature，并在最后 0x1000 bytes 搜索最后
  一个指向 central header 的 EOCD；
- 用 checked offset/length 读取 record count、creator version、flags、method、
  sizes 和 local offset；
- metadata 方法扫描上限为 20，与固定 `XZip::getCompressMethodString` 一致；
- 当前只实现本差分覆盖的单一非加密 `Store` 方法；其他方法和多方法排序产生
  明确诊断，不静默降级；
- central header 指向无效 local signature 时只计数，不改变 metadata；
- 通过专用 adapter 暴露 `isVerbose` 和三个 metadata getters，并记录调用数。

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-archive-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/archive-rule-fixture.json \
  docs/research/data/archive-rule-qt5.json
```

命令绑定 rule/fixture/baseline SHA-256，只有 native facts、完整结果、调用次数和
local-header 诊断全部一致才退出 0。本次 `matched_count = 3`、
`all_match = true`。默认 Rust 1.97.1 与 MSRV 1.88.0 均通过 36 项单元测试、
`fmt`、`clippy -D warnings` 和 release 差分。

## 已知边界

- 未覆盖 Deflate、其他 compression、多个方法的 Qt `QSet` 顺序、encrypted、
  info/comment、空 payload、ZIP64、multi-disk、data descriptor 或 CRC。
- 未覆盖 EOCD comment 中伪 signature、超过 0x1000 搜索窗口、重复 EOCD、
  central count/size/offset 冲突或 fallback local-header metadata。
- 未覆盖 TAR/TAR.GZ/RAR/DOS16/Mach-O fat 等其他 `Archive_Script` receiver。
- 未覆盖 `isArchiveRecordPresent`/`isArchiveRecordPresentExp`、payload、
  decompression、recursive/archive scan；APK 成员 API 是独立闭环。
- Rust 对畸形 header/range 和未覆盖方法返回明确诊断；固定上游的零填充或
  宽松行为仍需逐项 oracle。
- 未覆盖 Qt 6 和跨平台 oracle。

ADR 0006 仍为 Proposed，R-001 仍为 Open；Archive 代表规则已闭合，PDF 代表
规则仍未闭合。
