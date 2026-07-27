# DEX 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已把第四个原样格式规则连接到 Rust 解析出的真实
context。固定 `DEX/protector_QDBH.2.sg` 在项目生成的 DEX035 正例、反例和
string-data 恰在 EOF 的截断输入上，与 Qt 5.15.13
`QScriptEngine + XDEX + DEX_Script` oracle 3/3 一致：

| Case | XDEX valid | Qt/Rust strings | `isDexStringPresent` | Detection |
| --- | --- | --- | --- | --- |
| match | true | `["/qdbh"]` | true | `protector / QDBH` |
| mismatch | true | `["/nope"]` | false | none |
| string data at EOF | true | `[""]` | false | none |

三例的 map item 数、解析字符串、native 返回、`detect()` boolean、完整四元
detection 和一次 HostApi 调用均一致。截断例证明固定 XDEX 只按 magic/version
判有效；string-id 指向 EOF 时，`getStrings` 仍保留一个空 `QString`，规则不命中
且 `PDSTRUCT` 没有 error。

这不能外推到全部 DEX 规则、MUTF-8、type/item strings、map hash 或 APK。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- XDEX：`035c61966d3a9018edf80cd0013083ee32626e71`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：`DEX/protector_QDBH.2.sg`，273 bytes，SHA-256
  `5280ae0425f47c03ca037002b29964fe59eb898e871a00ad266475856f0e7ba7`
- 生成语料：
  [`dex-rule-fixture.json`](data/dex-rule-fixture.json)，SHA-256
  `7c312742257d365a49f399036e9ce62784e819f13a27831acfadd7625025cbc8`
- Qt5 baseline：
  [`dex-rule-qt5.json`](data/dex-rule-qt5.json)，SHA-256
  `881988e4c85686489fcf05235b686656ea3dcfaa487cbd7b36259f98614b7bf5`

规则由 harness 从固定 rules subtree 读取并校验 hash，不复制、格式化或修改。
[`generate_dex_rule_fixture.py`](../../tools/corpus/generate_dex_rule_fixture.py)
只生成 112-byte header、一个 string-id、三项 map-list 和受控 ASCII
string-data，不包含第三方样本。

## 上游语义证据

固定源码的实际调用链是：

1. `XScanEngine/modules/dex_script.cpp:DEX_Script::DEX_Script` 调用
   `XDEX::getMapItems`、`isStringPoolSorted`、`getStrings` 和
   `getTypeItemStrings`，在脚本执行前缓存列表。
2. 同文件 `DEX_Script::isDexStringPresent` 调用
   `XDEX::isStringInListPresent`。
3. `XDEX/xdex.cpp:XDEX::getMapItems` 从 header `map_off` 读取最多
   `min(declared, bytes/12, 0x10000)` 项。
4. 同文件 `XDEX::getStrings` 只使用 map 中的 `TYPE_STRING_ID_ITEM`；
   `_getString` 从 string-id 取 data offset，并只在 header data range 内读取。
5. `Formats/xbinary.cpp:XBinary::_read_utf8String` 把 ULEB 值作为读取字节数，
   再调用 `QString::fromUtf8`；源码明确留有 `TODO mutf8`。
6. `XBinary::getStringNumberFromList` 使用 `QString::operator==` 精确匹配。

`XDEX::isValid` 只比较 `dex\n`、终止 NUL 并要求数值 version 至少 35，源码也有
“more checks” TODO。因此本实验分别保存 parser validity、map 和 string-list，
而不是用 valid 一项代替结构行为。

## Oracle 与复现

[`dex_rule_harness_main.cpp`](../../tools/upstream/dex_rule_harness_main.cpp)
直接构造固定 `XDEX`/`DEX_Script`，保存 parser valid、map count、解析字符串、
native 查询结果、detect boolean、完整 tuple 和 `PDSTRUCT` error。
[`probe_dex_rule_harness.py`](../../tools/upstream/probe_dex_rule_harness.py)
在断网、512 MiB、1 CPU、128 PID 容器中绑定 image revision、harness binary、
规则、fixture 和 baseline hash。

```sh
python tools/corpus/generate_dex_rule_fixture.py \
  docs/research/data/dex-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.dex-rule-harness-qt5 \
  -t diec-rust/dex-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_dex_rule_harness.py \
  --image diec-rust/dex-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-dex-rule-harness \
  --fixture docs/research/data/dex-rule-fixture.json \
  --baseline docs/research/data/dex-rule-qt5.json
```

## Rust spike

受控 `DexRuleContext`：

- 验证 magic、数值 version、完整 112-byte header 和 endian tag；
- 端序感知解析 map-list 与首个 string-id map；
- map 和 string 数均暂限 65,536，所有乘加、data range 和 table offset 均
  checked；
- string-id 越过 header data range 时保留空字符串并计数，不按声明偏移分配；
- ULEB128 最多读取五字节，未终止或过长时明确报错；
- 按固定 XDEX 当前行为把 ULEB 值作为 UTF-8 byte count，并通过
  `String::from_utf8_lossy` 构造本 spike 的字符串；
- 通过专用 adapter 暴露 `DEX.isDexStringPresent`，只做精确相等匹配。

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-dex-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/dex-rule-fixture.json \
  docs/research/data/dex-rule-qt5.json
```

命令绑定 rule/fixture/baseline SHA-256，只有 map/string facts、完整结果和精确
HostApi 调用数全部一致才退出 0。本次 `matched_count = 3`、
`all_match = true`。

## 已知边界

- 当前只执行一条 ASCII string 规则，未证明 Qt `QString::fromUtf8` 与 Rust
  lossy UTF-8 对每个无效序列一致，也未实现 DEX MUTF-8。
- 未覆盖多字节 ULEB、supplementary code point、嵌入 NUL、重复/未排序字符串、
  big-endian、多个/重叠 map、header/map 不一致或 checksum/signature 验证。
- 65,536 string 上限和五字节 ULEB 拒绝是 spike 的安全门禁；固定上游在畸形
  string count/ULEB 上缺少等价资源限制，正式策略必须记录差异并建立 oracle。
- 未覆盖 `isDexItemStringPresent`、`isStringPoolSorted`、`getMapItemsHash` 以及
  其他 `DEX`/继承 HostApi。
- 未覆盖 APK/ZIP 调度、`classes.dex` 嵌套 identity、Qt 6 和跨平台 oracle。

ADR 0006 仍为 Proposed，R-001 仍为 Open；DEX 代表规则已经闭合，但 APK、
Archive 和 PDF 代表规则仍未闭合。
