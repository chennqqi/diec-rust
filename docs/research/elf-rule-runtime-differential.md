# ELF 规则运行时端到端差分

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 结论

Phase 0 rquickjs spike 已把第二个原样、格式专用规则连接到 Rust 解析出的真实格式
context。固定 `ELF/protector_Burneye.2.sg` 在项目生成的 ELF32/ELF64 正例、
反例和截断输入上，与 Qt 5.15.13
`QScriptEngine + XELF + ELF_Script` oracle 6/6 一致：

| Class | Case | XELF valid | Qt/Rust EP offset | Qt/Rust detection |
| --- | --- | --- | ---: | --- |
| ELF32 | match | true | `256` | `protector / Burneye / 1.0` |
| ELF32 | mismatch | true | `256` | none |
| ELF32 | truncated | true | `256` | none |
| ELF64 | match | true | `256` | `protector / Burneye / 1.0` |
| ELF64 | mismatch | true | `256` | none |
| ELF64 | truncated | true | `256` | none |

入口点、ELF class、安全 matcher memory-map 投影、detect boolean 和完整四元
detection 均一致。完整输入各走一次 256-byte EP cache fast path；截断输入入口
点恰好位于 EOF，走 generic path 并安全返回 false。六次 `ELF.compareEP` 均无
错误。

这证明 PE 闭环不是格式特例，并关闭“ELF parser → normalized PT_LOAD map/entry
point → native `ELF.compareEP` → 原样规则 → detection tuple”的一条代表性
ELF32/ELF64 分支。它不代表全部 ELF HostApi、端序、扩展 program count 或畸形
ELF 已兼容。

## 固定身份

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- Detect-It-Easy rules：`c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
- 规则：`ELF/protector_Burneye.2.sg`，282 bytes，SHA-256
  `35461b495f056d98de9af44eda91df3c6412d22555b182834af9b6a68842d44c`
- 生成语料：
  [`elf-rule-fixture.json`](data/elf-rule-fixture.json)，SHA-256
  `b3547482b2013a993a36262860f82dbda69b1588898cd2a8020124c6b9aad5b4`
- Qt5 baseline：
  [`elf-rule-qt5.json`](data/elf-rule-qt5.json)，SHA-256
  `edf2d32cde44c8fcf010190e48cc33076dcb1dc0ea81830996eeab7a57f89410`

规则由 harness 从固定 rules subtree 按路径读取并校验 hash，不复制、不格式化、
不修改。样本全部由
[`generate_elf_rule_fixture.py`](../../tools/corpus/generate_elf_rule_fixture.py)
生成，不包含第三方二进制样本。

## Oracle

[`elf_rule_harness_main.cpp`](../../tools/upstream/elf_rule_harness_main.cpp)
直接实例化固定上游 `XELF` 和 `ELF_Script`，把后者作为 `ELF` QObject 注册到
Qt 5 `QScriptEngine`，执行原样 `detect()`。输出保留输入 hex/hash、parser
valid、entry-point offset、完整 XELF memory map、detect boolean、完整四元
detection 和 `PDSTRUCT` error。

[`Dockerfile.elf-rule-harness-qt5`](../../tools/upstream/Dockerfile.elf-rule-harness-qt5)
只复用本地固定 `upstream-oracle-cmake:74eaf505`，不下载依赖。
[`probe_elf_rule_harness.py`](../../tools/upstream/probe_elf_rule_harness.py)
以 `--network=none`、512 MiB、1 CPU、128 PID 运行，校验 image revision、
harness binary、规则和输入身份后才允许记录 baseline。

复现：

```sh
python tools/corpus/generate_elf_rule_fixture.py \
  docs/research/data/elf-rule-fixture.json

docker build --network=none \
  -f tools/upstream/Dockerfile.elf-rule-harness-qt5 \
  -t diec-rust/elf-rule-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_elf_rule_harness.py \
  --image diec-rust/elf-rule-harness-qt5:74eaf505 \
  --binary /opt/die-build/src/console/diec-elf-rule-harness \
  --fixture docs/research/data/elf-rule-fixture.json \
  --baseline docs/research/data/elf-rule-qt5.json
```

## XELF 截断映射与安全投影

完整输入的 XELF map 包含两个 PT_LOAD physical records，以及一个
`address = UINT64_MAX` 的 overlay record。截断到 256 bytes 后，XELF 仍判定
有效并返回入口偏移 256；每个声明的 PT_LOAD 又产生：

- 一个保持声明 offset/size 的 physical record；
- 一个负 size physical record；
- 一个 `offset = -1` 的 virtual record。

项目 `MemoryMap` 使用非负 `u64` 范围，不能也不应伪装成完整复刻这些负值。
差分 verifier 因而同时保留原始 Qt baseline，并构造明确命名的
`qt5_safe_projection`：只保留 non-virtual、offset 非负、size 正数且 address
不是 overlay sentinel 的 records。被排除的 virtual、nonpositive-size、
negative-offset、overlay-sentinel 数量逐类进入报告；规范化不能隐藏它们。

Rust context 保留两个声明的 PT_LOAD records，即使截断时声明范围超出 EOF，并
报告 `rust_declared_out_of_bounds_loads = 2`。signature matcher 的所有实际 byte
访问仍由输入边界控制，因此入口位于 EOF 时不会越界读取、分配或 panic。

## Rust spike

[`spikes/rquickjs-rule-runtime/`](../../spikes/rquickjs-rule-runtime/) 的受控
`ElfRuleContext`：

- 验证 ELF magic、class、endianness、ident version 和最小 header size；
- 用端序感知的有界读取解析 ELF32/ELF64 entry 与 program table；
- program header count 暂限 1024，所有 table/segment 运算使用 checked
  conversion/addition；
- 只选非空 PT_LOAD，并按最低 load virtual address 规范化 address；
- 保留声明的 file ranges，同时显式计数超出输入的 ranges；
- 用共用 entry-point host adapter 暴露 `ELF.compareEP`，与 PE 共享同一
  signature wrapper 和 fast/generic/error 计数。

独立边界回归还验证空输入、过小 program-entry size、超过 1024 的 count、
segment range overflow 和无非空 PT_LOAD 都返回明确错误，不 panic 或分配声明
大小的 segment。

Rust 差分复现：

```sh
cargo +1.88.0 run --release --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml -- \
  verify-elf-rule \
  upstream/Detect-It-Easy/db \
  docs/research/data/elf-rule-fixture.json \
  docs/research/data/elf-rule-qt5.json
```

命令逐一校验 fixture、baseline、rule 的固定 SHA-256；只有 class、入口点、安全
map 投影、detect boolean、完整 detection tuple、一次 `ELF.compareEP` 且零 error
全部一致时才退出 0。本次为 `matched_count = 6`、`all_match = true`。

## 未覆盖

- 其他 ELF rules 以及 `ELF` receiver 的全部 method/arity/转换；
- big-endian oracle、extended program-header count、section headers、dynamic
  metadata、symbols/relocations；
- 重叠 PT_LOAD、`p_filesz > p_memsz`、整数极值及更早位置截断；
- generic `compareEP` 的 relative/absolute control pattern 规则级差分；
- ELF init、完整规则顺序、nested/archive 调度；
- Qt 6、Windows、macOS oracle，以及 fuzz/sanitizer/资源压力。

ADR 0006 仍为 Proposed，R-001 仍为 Open。下一组格式闭环仍需扩展 Mach-O、
DEX/APK、Archive 和 PDF；不能从本次 6 个受控案例外推总体兼容率。
