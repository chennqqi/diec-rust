# PE 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已首次把一个原样、格式专用的 PE 规则连接到 Rust 解析出的
PE context，而不是向规则注入预设返回值。固定
`PE/compiler_Cygwin32.4.sg` 在项目生成的正例、反例和截断 PE32 上，与
Qt 5.15.13 `QScriptEngine + XPE + PE_Script` oracle 3/3 一致：

| Case | XPE valid | Qt/Rust EP offset | Qt/Rust detection |
| --- | --- | ---: | --- |
| `cygwin32_entry_point_match` | true | `512` | `compiler / Cygwin32` |
| `cygwin32_entry_point_mismatch` | true | `512` | none |
| `cygwin32_entry_point_truncated` | true | `-1` | none |

三例的非 virtual、非零 physical memory records 也逐字段一致。正/反例走固定
`Binary_Script::compareEP` 的 256-byte cache fast path；截断例没有有效入口点，
走 generic path 并返回 false。三次调用均无 fallback、parse/match error 或脚本
异常。

该结果关闭了“格式 parser → memory map/entry point → native `PE.compareEP` →
原样规则 → 完整 detection tuple”这一条代表性 PE 分支，但只覆盖一条规则和
PE32；不能外推到全部 PE HostApi、PE32+、畸形 PE 或其他格式。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：
  `PE/compiler_Cygwin32.4.sg`，240 bytes，
  SHA-256
  `de563e3333c54b966efb7aa3d678acd56ca5fa9b83a7b8356b3a4e71e47dc4cd`
- 生成语料：
  [`pe-rule-fixture.json`](data/pe-rule-fixture.json)，SHA-256
  `102eacfa044f838fb51992c65a2cf7e90cd346a493bffc77b08f4ec02f5159e1`
- Qt5 baseline：
  [`pe-rule-qt5.json`](data/pe-rule-qt5.json)，SHA-256
  `645fc9b13d500f1eda3203df90439cb5234f8eb850d820de119962b4778be03a`

规则由 harness 从固定 rules subtree 按路径读取并校验 hash；不复制、不格式化、
不修改规则字节。样本全部由
[`generate_pe_rule_fixture.py`](../../tools/corpus/generate_pe_rule_fixture.py)
生成，不包含第三方二进制样本。

## Oracle

[`pe_rule_harness_main.cpp`](../../tools/upstream/pe_rule_harness_main.cpp)
直接实例化固定上游 `XPE` 和 `PE_Script`，把后者作为 `PE` QObject 注册到
Qt 5 `QScriptEngine`，再执行原样规则的 `detect()`。输出保留：

- 原始输入 hex 与 SHA-256；
- `XPE::isValid()`；
- `getEntryPointOffset(getMemoryMap())`；
- 完整 memory map，包括 virtual records；
- `detect()` boolean、四元 detection 和 `PDSTRUCT` error。

容器层
[`Dockerfile.pe-rule-harness-qt5`](../../tools/upstream/Dockerfile.pe-rule-harness-qt5)
只复用本地固定 `upstream-oracle-cmake:74eaf505`，不下载依赖。验证器
[`probe_pe_rule_harness.py`](../../tools/upstream/probe_pe_rule_harness.py)
以 `--network=none`、512 MiB、1 CPU、128 PID 运行，校验 image revision、
harness binary hash、规则/样本身份和预期语义后才允许记录 baseline。

复现：

```sh
python tools/corpus/generate_pe_rule_fixture.py \
  docs/research/data/pe-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.pe-rule-harness-qt5 \
  -t diec-rust/pe-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_pe_rule_harness.py \
  --image diec-rust/pe-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-pe-rule-harness \
  --fixture docs/research/data/pe-rule-fixture.json \
  --baseline docs/research/data/pe-rule-qt5.json
```

## Rust spike

[`spikes/rquickjs-rule-runtime/`](../../spikes/rquickjs-rule-runtime/) 中的受控
`PeRuleContext` 只解析本实验所需的 DOS/COFF/optional/section fields，并执行：

- 所有 offset/size/address 运算都经过 checked conversion/addition；
- section count 暂限 96；
- optional header 和完整 section table 必须在输入内；
- 只为输入中实际可读的 bytes 建立 physical records；
- entry RVA 必须可映射到实际存在的 raw byte，否则为无入口点；
- `PE.compareEP` 调用
  `diec-signature-parser-spike` 的兼容 wrapper，并保留 fast/generic/error 计数。

截断例暴露固定 XPE 的一个别名行为：第二节 raw offset `0x400` 超出 512-byte
文件时，其 physical record 被映射为 file offset `0`、size `512`。spike 为保持
差分而有界复现该 record，并报告 `bounded_upstream_alias_count = 1`；所有 size
仍裁剪到实际输入，未产生越界读取或额外分配。正式 parser 是否把该行为限定为
兼容 projection，必须在格式设计评审中决定，不能无记录地“修正”或全局复制。

Rust 差分复现：

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-pe-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/pe-rule-fixture.json \
  docs/research/data/pe-rule-qt5.json
```

命令对 fixture、baseline、rule 逐一校验固定 SHA-256；只有入口点、physical map、
detect boolean、完整 detection tuple、一次 `PE.compareEP` 调用且零 error 全部
一致时才退出 0。本次结果为 `matched_count = 3`、`all_match = true`。

## 未覆盖

- 其他 PE rules 和 `PE` receiver 的全部 method/arity/转换；
- PE32+、重叠节、virtual-only 节、畸形 section count/optional header；
- generic `compareEP` 中 relative/absolute control pattern 的规则级差分；
- PE global/type init、完整规则顺序、heuristic 与 nested resource 调度；
- Qt 6、Windows、macOS oracle；
- fuzz、sanitizer、取消和资源上限压力测试。

因此 ADR 0006 仍为 Proposed，R-001 仍为 Open。下一组格式差分应沿用同一证据
结构扩展 ELF、Mach-O、DEX/APK、Archive 和 PDF，而不是用预设 HostApi 返回值
代替真实 parser/context。
