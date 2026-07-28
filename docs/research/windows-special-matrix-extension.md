# Windows entropy/info/struct 全 baseline 样本扩展

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

首轮 Windows special matrix 只覆盖 5 个代表样本。本实验把相同 19 个
entropy/info/struct case 扩展到 baseline corpus 剩余 21 个样本，每项连续运行
两次，共 399 case、798 次原生 Windows Qt5 进程执行。

结果为：

- 798 次执行均退出 `0`、stderr 为空，双轮退出码及原始 stdout/stderr 无漂移；
- 9 类 JSON、2 类 XML 和 8 类非空 UTF-8 输出在 21/21 样本上均通过对应解析或
  编码校验；
- 同时传入全部 formatter 时，entropy 和 info 都逐字节等于各自 JSON 输出；
- `--entropy --info --struct Hash --json` 逐字节等于 entropy JSON；
- `--info --struct Hash --json` 逐字节等于 `struct Hash` JSON。

与首轮 5-sample 报告合并后，Windows 的 19-case special matrix 现覆盖全部
26 个 baseline 样本。这关闭的是 baseline corpus 的 generic entropy/info、
`Hash`/`Hash#MD5`/unknown struct 与模式优先级；不把它外推为所有格式专用
struct method、畸形输入或跨平台 raw-byte 等价。

后续 Linux Qt5/Qt6 同矩阵及 Windows structured projection 三方差分见
[`cross-platform-special-matrix-extension.md`](cross-platform-special-matrix-extension.md)。

## Case 与结构化证据

19 个 case 直接复用
[`compare_cli_oracles.py`](../../tools/upstream/compare_cli_oracles.py) 的
`SPECIAL_MATRIX`，没有在采集器内复制命令表：

- entropy：text、plaintext、JSON、XML、CSV、TSV、all-output-flags；
- info：text、plaintext、JSON、XML、CSV、TSV、all-output-flags；
- struct：`Hash`、`Hash#MD5`、unknown method；
- 组合优先级：entropy/info/struct 与 info/struct。

机器报告不仅保存 raw stream 的 byte length 与 SHA-256，还保存 JSON 解析值和
XML root tag 的两轮 projection。这样确定性检查不会把“两个同样无效的结构化
文档”误判为成功；非结构化输出则至少要求非空且可按 UTF-8 解码。

四个固定优先级关系在每个样本上逐字节比较完整 observation，包括 exit code、
stdout 和 stderr：

| Case | 必须等于 |
| --- | --- |
| `entropy_all_output_flags` | `entropy_json` |
| `info_all_output_flags` | `info_json` |
| `entropy_over_info_struct_json` | `entropy_json` |
| `struct_over_info_json` | `struct_hash_json` |

84 个关系全部成立。该结果再次证明 special branch 的 formatter 优先级不同于
普通 scan 的 CSV-first 行为，Rust legacy CLI 不能把两者实现成一个共享的全局
优先级表。

## 身份与采集

采集器
[`collect_windows_cli_special_remaining.py`](../../tools/upstream/collect_windows_cli_special_remaining.py)
在执行前验证：

- 固定主仓库、规则仓库和 58 个递归 submodule；
- Qt 5.15.2 `qmake.exe`、`Qt5Core.dll`、`Qt5Script.dll`；
- clean qmake CLI 的固定 SHA-256；
- 26-sample corpus manifest、Windows 默认 baseline 和首轮 Windows matrix；
- case definitions 与两个 helper 的 SHA-256。

复现命令：

```powershell
python tools\upstream\collect_windows_cli_special_remaining.py `
  --binary <source>\build\release\diec.exe `
  --source-dir <source> `
  --qt-dir <qt-root>\5.15.2\msvc2019_64 `
  --corpus-dir <generated-baseline-corpus> `
  --expected-binary-sha256 e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e `
  --output docs\research\data\windows-qt5-cli-special-remaining.json
```

机器报告
[`windows-qt5-cli-special-remaining.json`](data/windows-qt5-cli-special-remaining.json)
SHA-256 为
`194f1a1610a18f8fe22814315e67e345ed967c3f61df2604ac3089abbc538cc2`。
info projection 的 `data.Info["File name"]` 在验证 basename 后固定为
`<corpus>/<sample>`；其他 projection 不规范化。报告只保存去本机路径 argv、
原始流摘要和结构化 projection，不保存本机绝对路径或 raw stream bytes。

## 尚未覆盖

- 这 21 个样本的 Linux/macOS 同 case special matrix，因此不能比较跨平台 raw
  stream 或语义 projection；
- Windows 上 PE/ELF/Mach-O/DEX 等格式专用 struct method 的完整矩阵；
- entropy 的更多浮点边界、超大输入、短读/I/O error 与资源上限；
- 多目标、目录和错误 framing 的跨平台扩展；已有代表边界仍见
  [`cli-special-modes.md`](cli-special-modes.md)。
