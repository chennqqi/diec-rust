# Mach-O 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已把第三个原样格式规则连接到 Rust 解析出的真实 context。
固定 `MACH/compiler_Rust.4.sg` 在项目生成的 Mach-O64 x86_64/arm64 正例、
x86_64 反例和截断输入上，与 Qt 5.15.13
`QScriptEngine + XMACH + MACH_Script` oracle 4/4 一致：

| Case | XMACH valid | Qt/Rust EP | compareEP fast/generic | Detection |
| --- | --- | ---: | ---: | --- |
| x86_64 match | true | 256 | 5 / 0 | `compiler / Rust` |
| arm64 match | true | 256 | 6 / 0 | `compiler / Rust` |
| x86_64 mismatch | true | 256 | 9 / 0 | none |
| x86_64 truncated | true | 256 | 0 / 9 | none |

CPU type、入口点、安全 matcher map、detect boolean、完整四元 detection 和
每例调用路径均一致，所有 `MACH.compareEP` 调用零错误。该结果把代表性格式闭环
从 PE、ELF 扩展到 Mach-O，并同时抵达原样规则的 x86_64 与 arm64 pattern
分支；仍不能外推到全部 Mach-O HostApi、Mach-O32、big-endian 或 fat binary。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：`MACH/compiler_Rust.4.sg`，1331 bytes，SHA-256
  `70fec4e86cd1a1a5b3e7663521cb45e3c4ce85d1e1f8ed80cf1d80f6d8268d84`
- 生成语料：
  [`macho-rule-fixture.json`](data/macho-rule-fixture.json)，SHA-256
  `d1e691bcd72942916dcabb75177f6e411b7d78483bdd0d1635c4a0c89619188d`
- Qt5 baseline：
  [`macho-rule-qt5.json`](data/macho-rule-qt5.json)，SHA-256
  `ec6b9f373d598f41cf7d51550eae020307c2a41b27f569135c022aeda54045f4`

规则由 harness 从固定 rules subtree 读取并校验 hash，不复制、格式化或修改。
[`generate_macho_rule_fixture.py`](../../tools/corpus/generate_macho_rule_fixture.py)
只生成最小 Mach-O64 header、`LC_SEGMENT_64`、`LC_MAIN` 和受控 EP bytes，
不包含第三方样本。

## Oracle 与复现

[`macho_rule_harness_main.cpp`](../../tools/upstream/macho_rule_harness_main.cpp)
直接构造固定 `XMACH`/`MACH_Script`，保存 parser valid、CPU/输入身份、入口点、
完整 memory map、detect boolean、完整 tuple 和 `PDSTRUCT` error。
[`probe_macho_rule_harness.py`](../../tools/upstream/probe_macho_rule_harness.py)
在断网、512 MiB、1 CPU、128 PID 容器中绑定 image revision、harness binary、
规则、fixture 和 baseline hash。

```sh
python tools/corpus/generate_macho_rule_fixture.py \
  docs/research/data/macho-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.macho-rule-harness-qt5 \
  -t diec-rust/macho-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_macho_rule_harness.py \
  --image diec-rust/macho-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-macho-rule-harness \
  --fixture docs/research/data/macho-rule-fixture.json \
  --baseline docs/research/data/macho-rule-qt5.json
```

## 映射边界

完整输入的 XMACH map 包含一个 `offset=256, size=64` 的 `__TEXT` physical
record，以及 `address=UINT64_MAX` 的 overlay record。截断到 256 bytes 后，
parser 仍有效、入口仍为 256、声明 segment record 仍保留，但 overlay 消失。

差分保留原始 Qt map，并只为 signature matcher 构造明确的安全投影：过滤
virtual、负 offset、非正 size 和 overlay sentinel，同时逐类报告丢弃数量。
Rust context 保留声明 segment，截断例报告一个 out-of-bounds segment；matcher
实际读 byte 时仍受输入长度约束，因此九次 generic 调用全部安全返回 false。

## Rust spike

受控 `MachoRuleContext`：

- 识别 32/64-bit 与大小端 magic，并端序感知读取 header/load commands；
- command count 暂限 1024，`sizeofcmds`、每个 `cmdsize` 和 segment 范围全部
  checked；
- 解析 `LC_SEGMENT`/`LC_SEGMENT_64` physical records 与 `LC_MAIN` entryoff；
- 入口必须落入声明 segment；声明范围超出 EOF 时计数而不按声明分配；
- 通过共用 entry-point adapter 暴露 `MACH.compareEP`。

边界回归还验证空输入、过多 commands、过小 command、segment range overflow
和无非空 segment 均明确失败，不 panic。

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-macho-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/macho-rule-fixture.json \
  docs/research/data/macho-rule-qt5.json
```

命令绑定 rule/fixture/baseline SHA-256，只有 parser facts、安全 map、完整结果和
精确 compareEP 调用路径全部一致才退出 0。本次
`matched_count = 4`、`all_match = true`。

## 未覆盖

- 其他 Mach-O rules 和 `MACH` receiver method/arity/转换；
- Mach-O32、big-endian、`LC_UNIXTHREAD`、多个/重叠 segment、sections、dylib；
- fat Mach-O 调度与 slice identity；
- 更早截断、极值 command graph、fuzz/sanitizer/取消；
- Qt 6、Windows、macOS oracle。

ADR 0006 仍为 Proposed，R-001 仍为 Open；DEX/APK、Archive 和 PDF 代表规则
仍未闭合。
