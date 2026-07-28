# 上游 Qt 6 CLI 基线与 Qt 5 差分

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-28

## 结论

固定上游无需修改源码即可用 CMake 和 Qt 6.4.2 构建 CLI。对 8 个基础 CLI
case、4 个不可读输入 case 和 15 个项目生成安全样本进行 Qt 5 CMake 与 Qt 6
CMake 原始差分后：

- 所有 exit code 和 stdout 原始字节相同；
- 所有解析后的 detection tree 相同；
- 26/27 个输入/case 的 stderr 相同；
- 唯一差异是 `minimal.exe` 在 Qt 6 stderr 输出四行
  `Unimplemented code.`，Qt 5 stderr 为空。

规则二分将四行输出缩小到一个未修改的固定规则
`PE/__GenericHeuristicAnalysis_By_DosX.7.sg`。这证明 Qt major/runtime profile
是 oracle identity 的组成部分，不能用“同一上游 commit + 同一规则”推断原始输出
完全相同；但本轮尚未定位到该规则内触发 Qt 6 内部诊断的精确表达式。

## 固定 Qt 6 构建

构建入口为
[`tools/upstream/Dockerfile.oracle-cmake-qt6`](../../tools/upstream/Dockerfile.oracle-cmake-qt6)。
它固定：

- Ubuntu base image digest
  `sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90`；
- DIE-engine commit `74eaf505c250ab47e709024e9dc41657cd8f2254`；
- 58 个递归初始化的直接 submodule，且拒绝 `-`、`+`、`U` 状态；
- CMake Release、`QT_DEFAULT_MAJOR_VERSION=6` 和 `diec` target；
- 链接结果包含 `libQt6Qml.so` 且不包含 `libQt5`。

本轮本地构建身份：

| 项目 | 值 |
| --- | --- |
| Image | `diec-rust/upstream-oracle-cmake-qt6:74eaf505` |
| Image ID | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` |
| OCI revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Platform | Linux amd64 |
| Qt | 6.4.2 |
| CMake | 3.28.3 |
| CLI | `die 4.0.0` |
| Binary | `/opt/die-build/src/console/diec` |
| Binary SHA-256 | `e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e` |
| Direct Qt evidence | `libQt6Qml.so.6`, `libQt6Core.so.6`; no `libQt5` |

主要构建包版本为：

| Package | Version |
| --- | --- |
| `build-essential` | `12.10ubuntu1` |
| `ca-certificates` | `20260601~24.04.1` |
| `cmake` | `3.28.3-1build7` |
| `file` | `1:5.45-3build1` |
| `git` | `1:2.43.0-1ubuntu7.3` |
| `qt6-base-dev` | `6.4.2+dfsg-21.1build5` |
| `qt6-declarative-dev` | `6.4.2+dfsg-4build3` |
| `qt6-svg-dev` | `6.4.2-4ubuntu3` |
| `qt6-tools-dev` | `6.4.2-3build3` |

Dockerfile 保存完整 package、CMake cache、link、ELF dynamic 和 `ldd` 证据到
镜像内 `/opt/die-evidence`。APT repository 没有固定 snapshot，因此上述 image ID
证明本轮实际执行身份，不等于 clean rebuild 的 bit-for-bit 承诺。

## CLI 差分

报告
[`data/qt5-qt6-cli.json`](data/qt5-qt6-cli.json)
（SHA-256
`30c4298f07f2aa64fc17a16c478f8554eb8eb9e4e5c13687cdddbfe3785b88fdd`）
由以下命令生成：

```powershell
python tools/upstream/compare_cli_oracles.py `
  --left-image diec-rust/upstream-oracle-cmake:74eaf505 `
  --left-binary /opt/die-build/src/console/diec `
  --right-image diec-rust/upstream-oracle-cmake-qt6:74eaf505 `
  --right-binary /opt/die-build/src/console/diec `
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 `
  --corpus-dir <generated-baseline-corpus> `
  --output docs/research/data/qt5-qt6-cli.json
```

`<generated-baseline-corpus>` 必须由
[`generate_baseline_corpus.py`](../../tools/corpus/generate_baseline_corpus.py)
生成并通过其 manifest 校验。工具因精确差异返回 1，这是差分失败而非 oracle
执行失败。

`minimal.exe` 的两侧 stdout 都是 467 bytes，SHA-256 都为
`c94fa4d2fa5742c41a67681779d3fc179aaf0f6558d74d385c648c2dae9dddde`；
检测都是 `PE32/Unknown`。Qt 6 stderr 是 80 bytes：

```text
Unimplemented code.
Unimplemented code.
Unimplemented code.
Unimplemented code.
```

其 SHA-256 为
`b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`。

## 规则 warning 最小化

[`minimize_qt6_rule_warnings.py`](../../tools/upstream/minimize_qt6_rule_warnings.py)
从固定 `db/PE` 的 834 个 `.sg` 候选、30 个根 helper 和 `PE/_init` 构造隔离
database，要求：

1. 仅 helper + `PE/_init` 时 warning 为 0；
2. 全部 PE 候选时 warning 精确为 4；
3. 每次二分两半的 warning 数之和等于父集合，拒绝相互作用被误判为独立来源；
4. 最小集合和单规则执行都复现相同 warning。

22 次 oracle observation 得到唯一来源：

| 项目 | 值 |
| --- | --- |
| Rule | `PE/__GenericHeuristicAnalysis_By_DosX.7.sg` |
| Rule SHA-256 | `c84a375fdc66508c66ae10440ab46be23d345d602b2ae6d79e26e66393ebadde` |
| Warning count | 4 |
| Raw stdout | 467 bytes / `c94fa4d2...9dddde` |
| Raw stderr | 80 bytes / `b303e691...8c51b` |

机器报告为
[`data/qt6-rule-warnings.json`](data/qt6-rule-warnings.json)
（SHA-256
`7426f071f4b1aa26c60956a2800bff007787a2c185fc379a3227206c78f8cf39`）。
第二次写入独立 raw 目录得到逐字节相同的报告。

源码中 `detect()` 调用 `main()`，`main()` 在选项分支前调用
`initializeCache()`；规则末部的 `log()` 只在 `_log` 存在时调用它。当前实验只把
来源缩小到整条规则：不能据此断言 `initializeCache()`、`_log` 或任一具体宿主
方法就是原因。

## Qt 整数桥接排除实验

项目生成的 fixture
[`qt-integer-bridge-fixture.json`](data/qt-integer-bridge-fixture.json)
（SHA-256
`739a30c021a03bcbf60e79d429168d4ca9715012759c826aee0bfae6844e7514`）
分别返回 `qint64`、`quint64`、`qint32` 和 `quint32`，再由规则记录
`typeof` 与 `String(value)`：

| Expression | Qt 5 | Qt 6 |
| --- | --- | --- |
| `PE.getSize()` | `number`, `512` | `number`, `512` |
| `PE.getImageFileHeader("Machine")` | `number`, `332` | `number`, `332` |
| `PE.getNumberOfImports()` | `number`, `0` | `number`, `0` |
| `PE.getSectionFileOffset(0)` | `number`, `0` | `number`, `0` |

四条规则两侧 exit/stdout/stderr 相同且 stderr 为空；单独加载 PE init 也无 warning。
这只排除了所测四个返回路径和 init-only 场景，不能证明所有 Qt 数字转换等价。

## 未定义 global 的 Qt 5/Qt 6 差异

固定两个可达拼写错误在三种 oracle 中都得到相同 `Binary/Unknown` detection、
exit 0、空 stderr 和“JSON document + trailing diagnostic” framing，但异常文本
取决于 JavaScript runtime：

```text
Qt 5: ReferenceError: Can't find variable: NAME
Qt 6: ReferenceError: NAME is not defined
```

三 oracle 报告为
[`data/global-typo-errors-qt5-qt6.json`](data/global-typo-errors-qt5-qt6.json)
（SHA-256
`59f9d28679513a939c70c3878ce8d39dcfa01e4b9006150e4b9aadb3311fba23`）。
检测相同不能用来规范化掉异常文本。

## 对兼容基线的约束

- 当前 Linux primary oracle 仍是上游官方 workflow 对应的 Qt 5 CMake profile；
  Qt 6 CMake 是独立 runtime profile，不是无差别替代品。
- oracle identity 必须包含 Qt major/minor、构建入口、binary/image hash 和平台。
- legacy raw 差分始终比较 stderr，即使 JSON stdout 和 detection tree 完全相同。
- runtime-specific exception wording 作为原始行为保存；若产品 profile 只承诺
  semantic error，必须通过 ADR 和精确 waiver 明示，不能由 normalizer 自动吞掉。
- 上游规则保持原样；本轮 fixture 位于项目生成的独立 database，没有修改规则
  subtree。

## 后续 CLI 矩阵扩展

后续实验已在相同固定 image 上执行 26 个安全格式样本、五样本七种普通
formatter，以及 escaping/nested 十个输出边界。所有退出码、stdout 和 JSON
detection tree 相同；PE32/PE64 与 nested PE 唯一保留差异仍是完全相同的四行
`Unimplemented code.` stderr。

机器证据和逐能力影响见
[`qt6-cli-runtime-evidence.md`](qt6-cli-runtime-evidence.md) 与
[`qt6-scan-nested-runtime-evidence.md`](qt6-scan-nested-runtime-evidence.md)，
special-mode 矩阵见
[`qt6-special-runtime-evidence.md`](qt6-special-runtime-evidence.md)。
基础 path 矩阵见
[`qt6-path-runtime-evidence.md`](qt6-path-runtime-evidence.md)。
database 矩阵见
[`qt6-database-runtime-evidence.md`](qt6-database-runtime-evidence.md)。
option/profiling 矩阵见
[`qt6-option-profiling-runtime-evidence.md`](qt6-option-profiling-runtime-evidence.md)。
首批 engine-contract harness 见
[`qt6-engine-contract-runtime-evidence.md`](qt6-engine-contract-runtime-evidence.md)。
规则编排差分见
[`qt6-rule-orchestration-runtime-evidence.md`](qt6-rule-orchestration-runtime-evidence.md)。
结果模型差分见
[`qt6-result-model-runtime-evidence.md`](qt6-result-model-runtime-evidence.md)。
signature-path 差分见
[`qt6-signature-path-runtime-evidence.md`](qt6-signature-path-runtime-evidence.md)。
十批实验将 Linux Qt6 的逐行完整证据从 11 项增加到 59 项，但没有关闭
`CAP-GAP-007`。

## 限制与下一步

- 只覆盖 Linux amd64、Qt 6.4.2 和当前安全语料，不代表其他 Qt 6 minor 或平台。
- Qt 6 global HostApi 首轮 harness 已完成；format QObject 全矩阵和更多转换边界
  仍未覆盖，见
  [`global-host-api-runtime-differential.md`](global-host-api-runtime-differential.md)。
- 四行 warning 的精确 Qt 调用点和 enabled heuristic 路径仍待最小表达式实验。
- 普通输出、scan、special、基础 path 和首轮 nested gate 矩阵已完成；
  path 的 filesystem/locale/TOCTOU/large-directory 边界、database
  layer/cache 及其余 dispatch/nested engine harness 仍未完成；
  已完成四入口、device/subdevice、filter、cancel 和 sort 的
  engine-contract harness、三层数据库/priority/init/type/mode gate 的规则编排
  差分、五组 result-model harness 和 private signature-path harness。
- Windows、macOS 固定 oracle 仍缺失。
