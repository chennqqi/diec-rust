# Nintendo Certified File 规则行为基线

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-26

## 范围

本文为两个现代 JavaScript runtime 唯一拒绝的
`db/Binary/format_bin.Nintendo-certified-file.1.sg` 建立真实上游 detect 基线。
所有输入由项目生成，只包含该规则读取的 header/pointer 字段，不包含第三方或
可执行 payload。

语料 manifest 为
[`data/nintendo-certified-corpus.json`](data/nintendo-certified-corpus.json)，
oracle 结果摘要为
[`data/nintendo-certified-baseline.json`](data/nintendo-certified-baseline.json)。

## 规则语义

规则先识别 `SCE\0`，再用 offset 4 的 discriminator 选择：

- `00 00 00 02`：PS3 / big endian，payload header 从 `0x20` 开始；
- `03 00 00 00`：PS Vita / little endian，payload header 从 `0x30` 开始。

offset `0x0A` 的 `tp` 分派：

| tp | 名称 |
| ---: | --- |
| 1 | signed ELF/PRX，区分有 ELF header 与 headerless |
| 2 | signed revoke list `.SRVK` |
| 3 | signed package `.SPKG` |
| 4 | signed security policy profile `.SSPP` |
| 5 | signed diff `.SDIFF` |
| 6 | signed `param.sfo` |

fixture 把 attr 设为 `0x8000`，因此 Nintendo detection 的 `info` 均为 `fSELF`。
type 1 还满足 `progidhdp + 0x20 == ehdrp`、`ehdrp + 0x40 == phdrp` 和各平台
`eexhdsz` 条件。

## 确定性语料

生成：

```sh
python3 tools/corpus/generate_nintendo_certified_corpus.py \
  /tmp/diec-nintendo-certified-corpus
```

共 14 个文件：PS3/PS Vita 分别覆盖 type 2–6，type 1 分为 ELF/headerless。
type 1 为 512 bytes，其余为 128 bytes。生成器测试验证：

- 两次生成 manifest 和 bytes 相同；
- 两种 endian discriminator；
- 全部 `tp` 分支；
- type 1 pointer relationship 和 ELF marker；
- manifest size/SHA-256。

二进制文件不提交仓库，只提交生成器和 hash manifest。

## 双 oracle 实验

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --corpus-dir /tmp/diec-nintendo-certified-corpus
```

qmake/CMake 对 14 个样本的 exit、原始 stdout 和 stderr 全部逐字节相同：

- 全部 exit `0`；
- 全部 stderr 为空；
- 每个样本都产生预期 Nintendo `format` detection；
- PS3 version 为 `PS3`，PS Vita version 为 `PSVita`；
- type 1 的 ELF/headerless 名称按 marker 分支；
- 每条 Nintendo detection 的 `info` 为 `fSELF`。

逐样本 stdout SHA-256 和稳定 detection 列表保存在 machine baseline，不在正文
复制全部 14 个 hash。

## 额外规则命中

全部 7 个 PS Vita 样本还在 Nintendo detection 之后产生：

```text
Audio: Electronic Arts' EA-XA stream (.EXA)(v0#unk.platform/le)
```

PS3 样本没有该记录。这是固定规则库对生成字节的可观察结果，不应从 Nintendo
专项 differential 中删除或作为“无关 false positive”规范化。未来 QuickJS
HostApi 测试必须比较完整有序 detection list，而不只断言目标规则命中。

## Unicode 边界

规则名称包含 U+014D LATIN SMALL LETTER O WITH MACRON，原始 UTF-8 bytes 为
`C5 8D`。Windows 当前控制台呈现可能显示 mojibake，但 oracle stdout bytes 和
JSON decode 的 code point 是 U+014D。差分以 raw bytes/code point 为准，不以
终端截图或字体呈现为准。

## 与 runtime overlay 的关系

[`rquickjs-rule-runtime-spike.md`](rquickjs-rule-runtime-spike.md) 已证明
`nintendo-unused-var-tp-v1` 可以让规则在 QuickJS 顶层 eval 成功，并已用 Rust
最小 Byte HostApi 已在每个共享 context 中执行真实 global/Binary init 和四个
include，并让目标 Nintendo detection 在 14 个样本上与 Qt baseline 逐字段
匹配。剩余门禁是：

- 扩大 invalid/heuristic 边界；
- Qt 6 对照；
- 执行完整 Binary signature sequence，保留 EA-XA 等相邻规则结果；
- 扩展至完整 HostApi，而不是保留 Nintendo 专项方法集合。

只让目标规则返回正确值仍不能证明完整 Binary rule set 兼容。

## 尚未覆盖

- unknown `tp` 的 heuristic/default 分支。
- invalid endian、header size、pointer relationship、offset/size 边界。
- `attr != 0x8000` 和 `fofs/fsz` 的显示/拒绝边界。
- Qt 6 oracle。
- QuickJS 完整 Binary signature sequence；init/include 生命周期和目标 Nintendo
  rule 的最小 HostApi detect 已完成。
- 完整扫描选项矩阵；一次全矩阵运行超过本轮 120 秒执行窗口，未将超时计为行为
  结果。
