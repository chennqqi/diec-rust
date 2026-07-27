# APK 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已把第五个原样格式规则连接到 Rust 解析出的真实
context。固定 `APK/protector_QDBH.2.sg` 在项目生成的 APK/ZIP 正例、大小写
反例和移除全部 local file records 的截断输入上，与 Qt 5.15.13
`QScriptEngine + XAPK + APK_Script` oracle 3/3 一致：

| Case | XAPK valid | Central record names | Detection |
| --- | --- | --- | --- |
| match | true | `classes.dex`, `assets/qdbh` | `protector / QDBH` |
| case mismatch | true | `classes.dex`, `assets/QDBH` | none |
| local records removed | true | `classes.dex`, `assets/qdbh` | `protector / QDBH` |

三例的 record 数量与顺序、native 返回、`detect()` boolean、完整四元 detection
和一次 HostApi 调用均一致。固定上游的查询是大小写敏感的 `QString` 精确相等；
它只依赖 central-directory record name。截断例的两个 central entry 都缺少
有效 local-header signature，但 XZip/XAPK 仍判有效，规则仍命中且
`PDSTRUCT` 没有 error。

该结果不能外推到完整 ZIP 解析、payload、decompression、Android manifest 或
全部 APK 规则。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- XArchive：`0fcd4e8d3e9933baac3b12246d82ac026557ffd0`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：`APK/protector_QDBH.2.sg`，283 bytes，SHA-256
  `cc20faadf1aec677679151a1997ea95184b265db2dbb1d4fcf56f0b62cead752`
- 生成语料：
  [`apk-rule-fixture.json`](data/apk-rule-fixture.json)，SHA-256
  `531112ec3a4af5a9736c11774c7df6c26819165a6962b5a168bfd70f47c5ee94`
- Qt5 baseline：
  [`apk-rule-qt5.json`](data/apk-rule-qt5.json)，SHA-256
  `41d75dae86b0f4a57b0159a3cc92fa0ad4cae1ca1117bc5620da68faa98fc00c`

规则由 harness 从固定 rules subtree 读取并校验 hash，不复制、格式化或修改。
[`generate_apk_rule_fixture.py`](../../tools/corpus/generate_apk_rule_fixture.py)
只生成 stored ZIP local/central/EOCD records 和空 entry，不包含第三方样本。
截断例移除 local records，在 offset 0 放置上游接受的空 EOCD，并保留指向
central directory 的最后 EOCD。

## 上游语义证据

固定源码的实际调用链是：

1. `XArchive/xapk.cpp:XAPK::isValid` 先调用 `XZip::isValid`，再以最后一个有效
   EOCD 调用 `XZip::isAPK`。
2. `XZip::isValid` 只要求 offset 0 是 local-header 或 EOCD signature；
   `findECDOffset` 从最后 0x1000 bytes 搜索，并保留最后一个指向 central-header
   signature 的 EOCD。
3. `XZip::isAPK` 在最多 10,000 个 central entries 中精确查找 `classes.dex`
   或 `AndroidManifest.xml`。
4. `XScanEngine/modules/archive_script.cpp:Archive_Script::Archive_Script`
   对 `XZip` 调用 `getRecords(20000)` 并缓存 records。
5. `APK_Script` 继承 `Archive_Script`；
   `Archive_Script::isArchiveRecordPresent` 调用
   `XArchive::isArchiveRecordPresent`。
6. `XArchive::getArchiveRecord` 使用 record name 与查询字符串的
   `QString::operator==`；非空 record name 即 present。

`XZip::infoCurrent` 在 central 模式下从 central header 取得名称，随后读取
local header 只计算 stream offset/metadata，不用 local signature gate record
name。因此本实验把 local-header signature 缺失作为单独证据保存。

## Oracle 与复现

[`apk_rule_harness_main.cpp`](../../tools/upstream/apk_rule_harness_main.cpp)
直接构造固定 `XAPK`/`APK_Script`，保存 parser valid、公开 `getRecords(20000)`
所得名称、native 查询、detect boolean、完整 tuple 和 `PDSTRUCT` error。
[`probe_apk_rule_harness.py`](../../tools/upstream/probe_apk_rule_harness.py)
在断网、512 MiB、1 CPU、128 PID 容器中绑定 image revision、harness binary、
规则、fixture 和 baseline hash。

```sh
python tools/corpus/generate_apk_rule_fixture.py \
  docs/research/data/apk-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.apk-rule-harness-qt5 \
  -t diec-rust/apk-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_apk_rule_harness.py \
  --image diec-rust/apk-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-apk-rule-harness \
  --fixture docs/research/data/apk-rule-fixture.json \
  --baseline docs/research/data/apk-rule-qt5.json
```

## Rust spike

受控 `ApkRuleContext`：

- 只接受固定 XZip 认可的 offset-0 signature，并在最后 0x1000 bytes 搜索最后
  一个有效 EOCD；
- 按 little-endian central header 解析 record name，脚本列表暂限 20,000；
- APK marker 检查只观察前 10,000 个 records，与固定 `XZip::isAPK` 一致；
- 所有 header、name、extra、comment 和游标运算均 checked；
- record name 按 byte-to-char Latin-1 投影保留，当前差分只覆盖 ASCII；
- local-header signature 缺失只计数，不改变 central record presence；
- 通过专用 adapter 暴露 `APK.isArchiveRecordPresent`，只做精确相等匹配。

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-apk-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/apk-rule-fixture.json \
  docs/research/data/apk-rule-qt5.json
```

命令绑定 rule/fixture/baseline SHA-256，只有 record facts、完整结果、local-header
诊断和精确 HostApi 调用数全部一致才退出 0。本次 `matched_count = 3`、
`all_match = true`。

## 已知边界

- 未覆盖 UTF-8 flag、非 ASCII name、NUL、duplicate name、目录、extra/comment、
  data descriptor、ZIP64、multi-disk、加密、压缩或 CRC。
- 未覆盖 EOCD comment 中伪 signature、超过 0x1000 搜索窗口、重复 EOCD、
  central count/size/offset 冲突、fallback local-header enumeration。
- Rust 对畸形 central entry 返回明确诊断；固定上游大量字段读取会零填充或
  提前停止，完整异常兼容仍需专门 oracle。
- 未覆盖 `isArchiveRecordPresentExp`、Android manifest 解压/AXML decode、
  `getAndroidManifestRecord`、JAR/ZIP 继承 HostApi。
- 未覆盖真实 `classes.dex` 嵌套扫描 identity、Qt 6 和跨平台 oracle。

ADR 0006 仍为 Proposed，R-001 仍为 Open；DEX 与 APK 代表规则已经分别闭合，
Archive 和 PDF 代表规则仍未闭合。
