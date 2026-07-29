# Linux Qt5/Qt6 与 Windows 普通输出全 baseline 差分

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

既有 Linux Qt5/Qt6 和 Windows 普通 output matrix 都只对 5 个代表样本执行
text、plaintext、JSON、XML、CSV、TSV 和 all-output-flags 7 个 case。
Windows 后续已覆盖剩余 21 个 baseline 样本。本实验用固定 Linux Qt5/Qt6
CMake oracle 对同一 21 × 7 矩阵各执行一次，共 147 对、294 次容器执行，并
与 Windows 双轮报告交叉验证。

结果为：

- 147 对中 140 对 exit/stdout/stderr 全部逐字节相同；
- 唯一 7 对 raw 差异恰好是 `minimal-pe64.exe` 的全部 7 个 case，且差异维度
  只有 Qt6 stderr；
- 147/147 stdout 在 Qt5/Qt6 间逐字节相同，所有 294 次执行都退出 `0`；
- 21/21 JSON detection tree 在 Qt5/Qt6 及 Windows/Linux Qt5 间相同；
- 21/21 all-output-flags 在两个 Linux Qt 版本上都逐字节等于 CSV；
- JSON 全部可解析；XML 的 17 个有效、4 个无效样本集合在 Linux Qt5、Linux
  Qt6 和 Windows Qt5 上完全相同；
- 其他 text/plaintext/CSV/TSV 输出均为非空 UTF-8。

与既有 5-sample 报告合并后，Linux Qt5、Linux Qt6 和 Windows Qt5 的普通
7-case output baseline matrix 都覆盖全部 26 个样本。macOS 和更广的 formatter
注入字符边界仍不在本结论内。

## 精确 Qt6 PE stderr 差异

`minimal-pe64.exe` 的 text/plaintext/JSON/XML/CSV/TSV/all-output-flags 七个
case 都保持：

- Qt5 stderr：0 bytes；
- Qt6 stderr：80 bytes，
  SHA-256 `b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`；
- Qt5/Qt6 stdout length 和 SHA-256 逐 case 相同；
- exit code 都为 `0`。

这与既有 PE32 Qt6 四行 `Unimplemented code.` warning 的根因和 raw contract
相同，见
[`qt6-cli-runtime-evidence.md`](qt6-cli-runtime-evidence.md) 和
[`upstream-qt6-differential.md`](upstream-qt6-differential.md)。

采集器把 7 个 `sample × case × ["stderr"]` 作为精确预期集合；新增 case、
缺失 warning、stdout/exit 差异或其他样本出现 warning 都会失败。报告不删除、
重写或归一化 stderr。

## 四个 invalid XML

Linux 两个 Qt 版本与 Windows 都在以下样本稳定产生非良构 XML：

- `minimal-fat.macho`：`Mach-O FAT`
- `Minimal.class`：`Java Class`
- `minimal.pyc`：`Python Bytecode`
- `minimal.iso`：`ISO 9660`

四个 filetype 都包含空格，并被 legacy formatter 直接用作动态 XML element
name。该集合与
[`windows-output-matrix-extension.md`](windows-output-matrix-extension.md)
一致；采集器要求其余 17 个 XML 全部可解析，不把“双方同样无效”当成一般成功。

## 固定身份与复现

Linux oracle 固定为：

| Oracle | Image ID | Binary |
| --- | --- | --- |
| Qt5 CMake | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` | `/opt/die-build/src/console/diec` |
| Qt6 CMake | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` | `/opt/die-build/src/console/diec` |

两个 image 的 revision label 都必须等于
`74eaf505c250ab47e709024e9dc41657cd8f2254`。采集器还绑定 26-sample manifest、
Windows output report、Windows collector、Linux identity helper 和共享
`OUTPUT_MATRIX` 的 SHA-256。

复现命令：

```powershell
python tools\upstream\collect_linux_cli_output_remaining.py `
  --corpus-dir <generated-baseline-corpus> `
  --output docs\research\data\linux-qt5-qt6-cli-output-remaining.json
```

机器报告
[`linux-qt5-qt6-cli-output-remaining.json`](data/linux-qt5-qt6-cli-output-remaining.json)
SHA-256 为
`86689b566f5cd1625593ff9f8fc716961288c35a22c0bd8fb0dc226773548df9`。
报告保存两侧 raw stream 摘要、精确差异集合、JSON detection tree、文档有效性
和 priority 关系，不保存 raw bytes 或本机绝对路径。

## 尚未覆盖

- macOS Qt5 的相同 26-sample output/special matrix；
- Windows text/plaintext/CSV/TSV 的跨平台语义比较；Windows 报告只保留 raw
  hash，且 CRLF/LF 是已知平台差异；
- formatter 注入字符边界之外的系统化 XML element-name 字符集合；
- 每个 Linux image/case 的同镜像双轮确定性；Windows 对应 case 保留双轮证据。
