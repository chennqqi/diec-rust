# Windows 普通输出格式全 baseline 样本扩展

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

首轮 Windows output matrix 只覆盖 5 个代表样本。本实验对 baseline corpus
剩余 21 个样本执行 colored text、plain text、JSON、XML、CSV、TSV 和同时传入
全部输出开关 7 个 case，每项连续运行两次，共 147 case、294 次执行。

结果为：

- 294 次进程执行均退出 `0`、stderr 为空，双轮原始流无漂移；
- 21/21 JSON 的 raw summary 与 detection tree 都等于固定 Windows 默认
  baseline；
- 21/21 `all_output_flags` 与单独 CSV 逐字节相同，再次固定普通扫描优先级
  `CSV > JSON > TSV > XML > plain text > colored text`；
- JSON 21/21 可解析；XML 17/21 可解析；
- `minimal-fat.macho`、`Minimal.class`、`minimal.pyc` 和 `minimal.iso` 的 XML
  稳定但不是 well-formed document；
- text/plaintext/CSV/TSV 及 all-flags 结果均为非空 UTF-8。

与既有 5-sample 报告合并后，Windows 普通输出格式现覆盖全部 26 个 baseline
样本。entropy/info/struct 专用模式的独立 26-sample 扩展见
[`windows-special-matrix-extension.md`](windows-special-matrix-extension.md)，
不能从本报告本身外推。

## 四个 invalid XML 边界

四个失败样本的 detection filetype 分别为 `Mach-O FAT`、`Java Class`、
`Python Bytecode` 和 `ISO 9660`，都包含空格。固定源码的 `_toXML()` 路径把
动态 filetype 文本直接作为 XML element name；这与既有
[`cli-output-boundaries.md`](cli-output-boundaries.md) 已固定的动态元素名问题
一致。解析失败是上游可观察行为，不是采集器丢失或平台路径差异。

Rust legacy XML 若追求可观察兼容，必须保留该失败边界；modern canonical XML
应使用固定合法元素名并把 filetype 放在 attribute/text 中。两者不能共用一个
未经标记的输出契约。

## 身份与采集

采集器
[`collect_windows_cli_output_remaining.py`](../../tools/upstream/collect_windows_cli_output_remaining.py)
直接复用固定
[`compare_cli_oracles.py`](../../tools/upstream/compare_cli_oracles.py) 的
`OUTPUT_MATRIX`，并绑定首轮 Windows matrix collector 和报告，防止 case 定义
或已覆盖 5-sample 分区漂移。

采集命令：

```powershell
python tools\upstream\collect_windows_cli_output_remaining.py `
  --binary <source>\build\release\diec.exe `
  --source-dir <source> `
  --qt-dir <qt-root>\5.15.2\msvc2019_64 `
  --corpus-dir <generated-baseline-corpus> `
  --expected-binary-sha256 e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e `
  --output docs\research\data\windows-qt5-cli-output-remaining.json
```

机器报告
[`windows-qt5-cli-output-remaining.json`](data/windows-qt5-cli-output-remaining.json)
SHA-256 为
`672370ebb6f689366098af2e2262be60569a37f7f80c781a1b49b044c4887376`。
报告同时绑定：

- 固定 upstream/rules、58 个递归 submodule、Qt 关键文件和 CLI identity；
- 26-sample corpus manifest；
- Windows 默认 baseline；
- 首轮 5-sample Windows output matrix；
- matrix definitions 和两个 collector 的 SHA-256。

报告只保存去本机路径 argv、原始流长度/哈希、文档有效性与 JSON detection
projection，不保存 raw stream 或本机绝对路径。

## 尚未覆盖

- 这 21 个样本的 Linux/macOS 同 case output，用于跨平台 raw/semantic 差分；
- 新增格式 corpus 的普通 output/special 扩展；
- formatter 注入字符边界之外的系统化 XML element-name 字符集合。
