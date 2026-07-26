# 固定规则未定义 global 的可达性与错误传播

Status: Draft
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254` / `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
Last updated: 2026-07-26

## 1. 目的与结论

全规则静态清单发现两个没有定义来源的直接 global call。本文用 project-generated
最小输入证明两个分支在固定 Linux Qt 5 CLI 中都可达，并冻结它们的错误传播。

固定 qmake 和 CMake oracle 对两个输入的行为逐字节相同：

- 返回一个 `Binary` / `Unknown` detection；
- 把带规则路径、行号和变量名的 `ReferenceError` 写在 JSON 文档之后的 stdout；
- stderr 为空，进程退出码为 0；
- qmake/CMake 的完整 stdout SHA-256 相同。

因此 Rust 兼容层不得静默修正拼写，也不能只依据退出码或已解析 JSON 判断规则是否
成功。机器基线见
[`global-typo-errors-qt5.json`](data/global-typo-errors-qt5.json)。

## 2. 固定源码证据

| 规则 | SHA-256 | 可达调用 |
| --- | --- | --- |
| `db/Binary/debug_data_debugData.1.sg` | `381b6259b239f2633b92fbd84fd0d99b972751e20cab12b6e09139a260f1f47d` | 第 58 行 `get_DWRAF_vi(...)` |
| `db/Binary/audio_WEM.1.sg` | `3ea818a39cf03337249883771a55cd1acacdecd3097f79edb85bce6b9bd85d94` | 第 55 行 `xma2_pase_xma2_chunk(...)` |
| `db/vgmcodingutils` | `ef43f8258558b6dbfc212d5505a9d2b803b27e76a8fd8be5821ad60ea2d815e7` | 第 14 行定义 `xma2_parse_xma2_chunk(...)` |

第一条规则在大小超过 16、末尾 16 字节以 little-endian `0x00534954` 开始、随后
两个 dword 为零且 `size - debugSize >= 0` 时调用未定义名字。第二条规则在
RIFF/RIFX WAVE/XWMA chunk walk 同时找到非零 `XMA2` 和 `data` payload offset 后
调用拼错的 helper。固定规则集中没有 `get_DWRAF_vi` 或
`xma2_pase_xma2_chunk` 的定义。

这两个名字是上游规则字节的一部分。兼容实现不得把它们改写为推测的
`get_DWARF_vi` 或已存在的 `xma2_parse_xma2_chunk`。

## 3. 安全且可重复的输入

生成器 [`generate_global_typo_corpus.py`](../../tools/corpus/generate_global_typo_corpus.py)
只构造 32/40 字节的确定性数据，不包含第三方样本或规则字节。固定 manifest 见
[`global-typo-corpus.json`](data/global-typo-corpus.json)。

| 输入 | 字节布局摘要 | Size | SHA-256 |
| --- | --- | ---: | --- |
| `debug-dwarf-typo.bin` | offset 16: `0x00534954`; offset 20..27: zero; offset 28: debug size 16 | 32 | `fc3a9a165b74ff75047cca723f5145c14604e2e696d21fafc52e68ccb827ee47` |
| `audio-xma2-typo.wem` | `RIFF`/`WAVE`; `XMA2` size 4; `data` size 8 | 40 | `7b4eb91e7492744667c53143312c020316aaa0ebeec9dd9d46314cfedf79dd01` |

复现：

```powershell
python tools/corpus/generate_global_typo_corpus.py `
  <external-work-dir>/global-typo-corpus

python tools/upstream/probe_global_typo_errors.py `
  --fixture-dir <external-work-dir>/global-typo-corpus `
  --raw-dir <external-work-dir>/global-typo-raw `
  --output docs/research/data/global-typo-errors-qt5.json
```

probe 在执行前验证 fixture inventory、文件哈希、规则 commit 和三份规则源码哈希；
Docker 禁用网络，并设置 512 MiB memory、1 CPU 和 128 PID 上限。原始 stdout/
stderr 写入调用方指定的仓库外目录，版本库只保存哈希和结构化观察。

## 4. 固定 oracle 与观察

| Oracle | Image ID | Binary |
| --- | --- | --- |
| Qt 5 qmake | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` | `/opt/die-source/build/release/diec` |
| Qt 5 CMake | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` | `/opt/die-build/src/console/diec` |
| Qt 6 CMake | `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b` | `/opt/die-build/src/console/diec` |

三个镜像的 OCI revision 都是固定 DIE-engine commit。调用参数为
`--messages --json`、固定 main/extra database 和单个输入。

| 输入 | Detection | 追加诊断 | stdout bytes / SHA-256 |
| --- | --- | --- | --- |
| debug | `Binary`, offset 0, size 32, `Unknown: Unknown` | `debug_data_debugData.1.sg: Binary/debug_data_debugData.1.sg: 58: ReferenceError: Can't find variable: get_DWRAF_vi` | 583 / `4eac19bbb4a4c994e746c2e53f623e9d7416496d049e0bc172fd3c8721d1f49c` |
| audio | `Binary`, offset 0, size 40, `Unknown: Unknown` | `audio_WEM.1.sg: Binary/audio_WEM.1.sg: 55: ReferenceError: Can't find variable: xma2_pase_xma2_chunk` | 569 / `a9b8d27dbfbb6dd7e72d02b38530e0f50d0a307770fb7381960ae572a236de68` |

每个组合的 exit code 都是 0；stderr 长度为 0，SHA-256 为标准空内容哈希
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

stdout 的 framing 是一个可独立 `raw_decode` 的 JSON document，随后空行和一条
诊断。把全部 stdout 交给要求 EOF 的 JSON parser 会失败；诊断也不在 detection
schema 内。probe 明确断言 JSON 后只能有预期的一条非空消息，避免 normalizer
吞掉新增、缺失或重排的错误。

同一命令第二次写到不同 raw/output 目录，报告 SHA-256 仍为
`cc251a16ba137644b0bb0924328c3c3a4dc1556bb8fe50785df316ab931f70be`。

Qt 6 的 detection、exit、stderr 和 framing 与 Qt 5 相同，但两条尾随诊断把
`Can't find variable: NAME` 写成 `NAME is not defined`。三 oracle 机器报告见
[`data/global-typo-errors-qt5-qt6.json`](data/global-typo-errors-qt5-qt6.json)，
完整构建身份和差分见
[`upstream-qt6-differential.md`](upstream-qt6-differential.md)。

## 5. 对 Rust 实现和测试的约束

- 规则加载必须保留原始拼写；未知 global 在运行到调用点时产生明确诊断。
- compatibility profile 至少比较 detection、错误文本、规则路径/行号、顺序、
  stdout/stderr framing 和 termination，不能只比较异常类型。
- 核心错误模型可以比上游 CLI 更结构化，但薄 CLI 的 legacy profile 必须显式决定
  如何复现“Unknown + stdout trailing diagnostic + exit 0”，不能让错误消失。
- oracle reader 必须保存 raw bytes，然后分别解析首个 JSON document 与 trailing
  records；EOF JSON parse failure 是可观察结果，不得规范化为空成功。
- 未来 runtime 测试需要证明抛错后剩余规则、后续 node 和下一次 scan 的状态行为。

## 6. 尚未覆盖

- Windows 和 macOS 的诊断文本与 framing；Qt 6 当前只覆盖 Linux 6.4.2。
- 不带 `--messages` 时这两条真实规则错误的 stdout。
- 一个扫描中多个 runtime error 的排序和上限。
- 错误规则之后的 signature 是否继续执行、已有 detection 是否全部保留。
- debug 规则意图对应的正确 helper 是否存在于其他未物化组件；这不影响固定快照中
  名字未定义和可达的事实。
