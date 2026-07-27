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
匹配。

后续 selected lifecycle probe 又按固定 Linux Qt 5 顺序加载全部 292 条 Binary
规则，执行 30 次真实 include，并只调用与本语料预期结果直接相关的三个
`detect`：

1. `archive_DEFLATE.1.sg`
2. `audio_EXA.1.sg`
3. `format_bin.Nintendo-certified-file.1.sg`

这里的第一条不是检测结果组成部分，而是必要的共享状态前置步骤：
`archive_DEFLATE` 无条件创建隐式全局变量 `bad`，后续 `audio_EXA` 会读取并更新
它。缺少该调用时 Vita 样本会以 `bad is not defined` 失败。这说明跨规则依赖不只
存在于顶层声明，也可能由先前 `detect()` 动态建立，不能仅靠顶层 AST 审计排除。

该 probe 对三个选定 `detect` 设置“零 fallback HostApi”硬门禁，14 个样本均通过：

- PS3 只得到 Nintendo `format`；
- Vita 的实际调用结果按规则执行顺序为 `audio`、`format`；
- 按上游目标输出的类型顺序投影后为 `format`、`audio`，与 Qt 5 baseline
  14/14 完整匹配；
- Nintendo `info` 全部保持 `fSELF`；
- 每个样本只应用一次 Nintendo compatibility overlay。

其余规则只执行顶层代码，没有调用 `detect`。为完成非目标规则顶层加载，probe
对 `shell-script` include 缺失的 `Binary.getString().replace().match()` 使用了
可追踪链式 fallback；三个选定 `detect` 均未使用 fallback。因此本结果证明的是
固定全库加载环境中的目标生命周期，而不是完整 Binary 扫描。

剩余门禁是：

- 扩大 invalid/heuristic 边界；
- Qt 6 对照；
- 为其他 Binary 规则分别提供能抵达有效分支的正/反例，而不只使用 Nintendo
  header 语料；
- 扩展到其他格式/file-part 的完整 HostApi context。

新的 `verify-binary-corpus` 已在每个 14 个生成样本上逐条调用全部 292 个
Binary `detect`，合计 4088/4088 无异常、0 fallback；完整有序
type/name/version 与双 Qt5 CLI baseline 14/14 一致，Nintendo info 14/14 为
`fSELF`。这闭合了此前“只调用三个选定规则”的缺口，但仍不能证明每条规则在其
有效输入和专用 HostApi context 下兼容。

## 尚未覆盖

- unknown `tp` 的 heuristic/default 分支。
- invalid endian、header size、pointer relationship、offset/size 边界。
- `attr != 0x8000` 和 `fofs/fsz` 的显示/拒绝边界。
- Qt 6 oracle。
- 其余 Binary 规则各自的有效正/反例；全部 292 个 `detect` 已在 14 个 Nintendo
  header 样本上逐样本调用，但多数规则未抵达正例分支。
- 完整扫描选项矩阵；一次全矩阵运行超过本轮 120 秒执行窗口，未将超时计为行为
  结果。
