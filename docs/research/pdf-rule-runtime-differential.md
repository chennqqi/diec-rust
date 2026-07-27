# PDF 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已把第七个原样格式规则连接到 Rust 从 PDF 字节解析出的
真实 object/string context。固定 `PDF/format_Tools.2.sg` 在项目生成的工具
metadata 正例、非 string 类型反例和缺失 `endobj` 的截断输入上，与 Qt 5.15.13
`QScriptEngine + XPDF + PDF_Script` oracle 3/3 一致：

| Case | XPDF valid | Objects | String values | Detections |
| --- | --- | --- | --- | --- |
| literal strings | true | 2 | Creator ×2, Producer ×1 | 3 |
| hex/name values | true | 1 | none | none |
| missing `endobj` | true | 0 | none | none |

正例精确保留两个 object 的 ID、offset 和 token；重复 `Tool A` Creator 被去重，
转义 `(Tool\)B)` 投影为 `Tool)B`，hex Producer 被 string API 过滤。binary
header comment `E2 E3 CF D3` 投影为小写 `e2e3cfd3`，并进入三条完整 detection
tuple。三例的 `detect()` 都返回 `undefined`，符合该规则没有 return 的事实。

Rust adapter 每例调用两次 `getStringValuesByKey`；只有正例的三次结果循环调用
`getHeaderCommentAsHex`。该结果不能外推到完整 PDF grammar、xref/object stream、
decompression 或全部 PDF HostApi。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- XPDF：`cdcee54dce97f566f2c023f400a457f4e6278de2`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：`PDF/format_Tools.2.sg`，557 bytes，SHA-256
  `982869432394292415be6c3c2ef9408ac1943c4d7571e19f767ffe87314c23da`
- 生成语料：
  [`pdf-rule-fixture.json`](data/pdf-rule-fixture.json)，SHA-256
  `28ae4bbe1b02c0ba303ad08fd075a7f01ff0ca7f9ec5fbf77f8b751c7d8c1f65`
- Qt5 baseline：
  [`pdf-rule-qt5.json`](data/pdf-rule-qt5.json)，SHA-256
  `af31dc57c04974af5fb74b0a4dea42b01ac0aa9460f541b70d60a107d370dbd8`

规则由 harness 从固定 rules subtree 读取并校验 hash，不复制、格式化或修改。
[`generate_pdf_rule_fixture.py`](../../tools/corpus/generate_pdf_rule_fixture.py)
只拼接项目自有 PDF header、dictionary、literal/hex/name token 和 object 边界。

## 上游语义证据

固定源码的实际调用链是：

1. `PDF_Script` 构造时调用 `XPDF::getParts(20)` 并缓存 object parts。
2. 没有有效 `startxref` 时，`XPDF::getParts` 使用
   `findObjects(0, -1, false)` 从文件开头按行扫描。
3. `XPDF::isValid` 只要求 size 大于 4 且前四字节为 `%PDF`；缺 `endobj`
   不改变 format valid。
4. `findObjects` 只有找到并验证 `endobj` 才保存 object；因此截断例返回零
   object，而不是半个 object。
5. `handleXpart` 每个 object 最多保存 20 个 token，并跟踪 dictionary/array
   nesting；literal string tokenizer 去除反斜杠但保留被转义字符。
6. `XPDF::getValuesByKey` 按 object/token 顺序扫描相邻 key/value，以值的
   `QString` 做全局去重并保留首次结果。
7. `PDF_Script::getStringValuesByKey` 只保留 `VT_STRING`；hex 和 name/value
   类型不会进入返回数组。
8. `XPDF::getHeaderCommentAsHex` 读取 header 后紧随的 `%` comment，最多
   40 bytes，遇 CR/LF/NUL 停止并返回 lowercase hex。
9. `format_Tools.2.sg` 先遍历 Creator，再遍历 Producer；每个值都重新读取
   header comment，并直接调用 `_setResult`。

源码位置为固定 XPDF 的 `xpdf.cpp:findObjects`、`_readPDFStringPart`、
`handleXpart`、`getParts`、`getValuesByKey`、`getHeaderCommentAsHex`，以及固定
XScanEngine 的 `modules/pdf_script.cpp`。

## Oracle 与复现

[`pdf_rule_harness_main.cpp`](../../tools/upstream/pdf_rule_harness_main.cpp)
直接构造固定 `XPDF`/`PDF_Script`，保存 object parts、native arrays、header
comment、detect 类型、完整 tuple 和 `PDSTRUCT` error。
[`probe_pdf_rule_harness.py`](../../tools/upstream/probe_pdf_rule_harness.py)
在断网、512 MiB、1 CPU、128 PID 容器中绑定 image revision、harness binary、
规则、fixture 和 baseline hash。

```sh
python tools/corpus/generate_pdf_rule_fixture.py \
  docs/research/data/pdf-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.pdf-rule-harness-qt5 \
  -t diec-rust/pdf-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_pdf_rule_harness.py \
  --image diec-rust/pdf-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-pdf-rule-harness \
  --fixture docs/research/data/pdf-rule-fixture.json \
  --baseline docs/research/data/pdf-rule-qt5.json
```

## Rust spike

受控 `PdfRuleContext`：

- 验证 `%PDF` signature，按 XPDF 的 CR/LF line 和 space 规则推进；
- 无 xref 分支只保存具备有效 `endobj` 的 object，object 上限为 4096；
- 每个 object 最多读取 20 个 token，游标必须前进，dictionary/array underflow
  明确失败；
- 支持本差分可达的 name、literal string、hex、dictionary 和 array token；
- literal string 复刻固定 XPDF 的反斜杠处理，string value 按首次出现去重；
- header comment 最多读取 40 bytes；
- NUL line termination 和未覆盖 token 产生明确诊断，不静默忽略；
- adapter 暴露 `PDF.getStringValuesByKey` 与 `PDF.getHeaderCommentAsHex` 并记录
  调用次数。

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-pdf-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/pdf-rule-fixture.json \
  docs/research/data/pdf-rule-qt5.json
```

命令绑定 rule/fixture/baseline SHA-256，只有 object/token、native arrays、
header comment、完整结果和调用次数全部一致才退出 0。本次
`matched_count = 3`、`all_match = true`。默认 Rust 1.97.1 与 MSRV 1.88.0
均通过 38 项单元测试、`fmt`、`clippy -D warnings` 和 release 差分。

## 已知边界

- 未覆盖有效 xref、xref stream、incremental update、object stream、indirect
  reference、stream `/Length`、filter/decompression 或 encrypted PDF。
- 未覆盖 nested literal parentheses、octal escapes、UTF-16 BOM、跨 4 KiB
  string、跨 64 KiB hex、comments inside dictionaries 或完整 whitespace 集。
- 未覆盖超过 20 token 时固定上游的部分结果、超过 4096 object 或 adversarial
  `endobj` substring。
- 未覆盖 `getValuesByKey`、`isValuesHexByKey`、通用 Binary methods 和其余
  六条 PDF 规则。
- Rust 对未覆盖/NUL/underflow 明确失败；固定上游的宽松或停滞行为仍需专门
  oracle。
- 未覆盖 Qt 6 和跨平台 oracle。

七个计划中的代表格式规则闭环均已建立，但 ADR 0006 仍为 Proposed、R-001
仍为 Open；完整 HostApi、全部规则和跨平台差分仍未完成。
