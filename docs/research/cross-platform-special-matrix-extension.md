# Linux Qt5/Qt6 与 Windows special 全 baseline 差分

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

既有 Linux Qt5/Qt6 special matrix 和 Windows 首轮矩阵都只覆盖 5 个代表样本。
Windows 后续已把 19 个 entropy/info/struct case 扩展到剩余 21 个 baseline
样本。本实验用固定 Linux Qt5/Qt6 CMake oracle 对同一 21 × 19 矩阵各执行
一次，共 399 对、798 次容器执行，并与 Windows 双轮报告的结构化 projection
交叉验证。

结果为：

- Linux Qt5/Qt6 的 399/399 对 exit code、raw stdout、raw stderr 逐字节相同；
- 798 次执行全部退出 `0`、stderr 为空，JSON/XML/非空 UTF-8 有效性全部通过；
- 21 样本 × 11 个 JSON/XML case = 231 个结构化 projection 在 Qt5/Qt6 间
  全部相同；
- 同 231 个 Linux Qt5 projection 在唯一允许的文件名字段规范化后与 Windows
  Qt5 全部相同；
- 4 个 priority relationship × 21 样本 × 2 个 Linux Qt 版本 = 168 个 raw
  observation 关系全部成立。

与既有 5-sample 报告合并后，Linux Qt5、Linux Qt6 和 Windows Qt5 的
19-case special baseline matrix 都覆盖全部 26 个样本。macOS、更多格式专用
struct method 和剩余 21 样本的普通 output 跨平台矩阵仍不在本结论内。

## 唯一规范化字段

首轮三方比较准确发现 42 个 Windows/Linux projection mismatch：21 个样本的
`info_json` 和 `info_all_output_flags` 各一项。逐字段 diff 证明唯一差异都是：

```text
data.Info["File name"]
```

- Linux 容器值为 `/corpus/<sample>`；
- Windows 原值为执行机的盘符绝对路径；
- 其他字段、类型、层级和顺序没有差异。

采集器现在只在 `info_json`/`info_all_output_flags` 上处理该字段，并先验证原值
以 `/<sample>` 结尾；不满足预期结构或 basename 时立即失败。通过验证后，
projection 使用 `<corpus>/<sample>`。raw stdout 的 length/SHA-256 完全不变，
因此该规范化不会隐藏其他字节差异。

这一修正还消除了首版 Windows 机器报告中意外保留的正斜杠本机路径。加强后的
测试同时拒绝 `I:\`、`I:/` 和固定临时目录名。修正后的 Windows 报告 SHA-256
为
`194f1a1610a18f8fe22814315e67e345ed967c3f61df2604ac3089abbc538cc2`。

## 固定身份

Linux 两个 oracle 都绑定主仓库 commit
`74eaf505c250ab47e709024e9dc41657cd8f2254`：

| Oracle | Image | Image ID | Binary |
| --- | --- | --- | --- |
| Linux Qt5 | `diec-rust/upstream-oracle-cmake:74eaf505` | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` | `/opt/die-build/src/console/diec` |
| Linux Qt6 | `diec-rust/upstream-oracle-cmake-qt6:74eaf505` | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` | `/opt/die-build/src/console/diec` |

采集器在执行前验证 image ID、revision label、26-sample manifest、Windows
report、Windows collector 和共享 `SPECIAL_MATRIX` 的 SHA-256。

复现命令：

```powershell
python tools\upstream\collect_linux_cli_special_remaining.py `
  --corpus-dir <generated-baseline-corpus> `
  --output docs\research\data\linux-qt5-qt6-cli-special-remaining.json
```

机器报告
[`linux-qt5-qt6-cli-special-remaining.json`](data/linux-qt5-qt6-cli-special-remaining.json)
SHA-256 为
`855dabb5acaae22eef3a05da1039dfae0d0ed7244130c229b77f29748e371c81`。
报告保存两侧 raw stream 摘要、解析 projection、三方相等关系和 priority
关系，不保存 raw bytes 或本机绝对路径。

## 尚未覆盖

- Linux/Windows 剩余 21 样本的 7-case 普通 output 跨平台矩阵；
- macOS Qt5 的相同 output/special matrix；
- Windows 非结构化 text/CSV/TSV 的语义比较；Windows 报告只保留 raw hash，
  且 CRLF/LF 已知不同；
- PE/ELF/Mach-O/DEX 等格式专用 struct method 的完整三平台矩阵；
- 每个 Linux image/case 的同镜像双轮确定性；本报告依赖固定 image ID 并各
  执行一次，Windows 对应 case 保留双轮证据。
