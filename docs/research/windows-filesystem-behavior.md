# Windows Junction 与扩展路径行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

本实验固定原生 Windows x86_64、Qt 5.15.2 qmake CLI oracle 对目录 Junction、
两跳 Junction 链和 Win32 `\\?\` 扩展命名空间的首轮行为。8 个 case 各连续
运行两次，共 16 次执行：

- 所有退出码均为 `0`，stderr 为空，双轮原始流无漂移；
- 显式经过 Junction 指定 PDF、直接指定 Junction 目录和两跳 Junction 目录，
  均产生与固定 `minimal.pdf` 完全相同的 detection tree；
- 枚举同时包含 `tree/alias` Junction 和 `tree/real` 时，上游按
  `alias -> real` 扫描同一底层 PDF 两次，没有按目标身份去重；
- 普通长度的 `\\?\` 文件和 Junction 目录参数均被接受，其 stdout 与对应普通
  Win32 路径逐字节相同。

这些事实只描述固定上游 legacy 行为。Rust 的安全默认策略仍可不跟随枚举发现的
reparse point，但 legacy compatibility 模式若选择偏离，必须由 ADR 和差分测试
明确记录。

## 固定输入

夹具由
[`generate_windows_filesystem_fixture.py`](../../tools/corpus/generate_windows_filesystem_fixture.py)
从 baseline corpus 的 331-byte `minimal.pdf` 构造；payload SHA-256 为
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。
版本化清单为
[`windows-filesystem-fixture.json`](data/windows-filesystem-fixture.json)，
SHA-256 为
`7e9f1a05df2d165c4c2177c35cde26a916ba6141eb3f79d6d8bffdca519b5c51`。

目录图是有限且无环的：

```text
direct-alias  -> direct-target/child.pdf
chain-entry   -> chain-hop -> chain-target/child.pdf
tree/alias    -> tree/real/child.pdf
```

Junction 使用普通用户可创建的目录重解析点。生成器要求输出目录不存在或为空，
创建后校验 `FILE_ATTRIBUTE_REPARSE_POINT`、目标可读性、文件长度和哈希。

## 采集与身份绑定

采集命令：

```powershell
python tools\upstream\collect_windows_cli_filesystem.py `
  --binary <source>\build\release\diec.exe `
  --source-dir <source> `
  --qt-dir <qt-root>\5.15.2\msvc2019_64 `
  --fixture-dir <generated-fixture> `
  --expected-binary-sha256 e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e `
  --output docs\research\data\windows-qt5-cli-filesystem.json
```

采集器在运行前重新校验上游 commit、规则 commit、58 个递归 submodule、
Qt 关键文件、CLI 哈希、fixture 清单和既有 Windows `minimal.pdf` detection
reference。报告仅保存 argv 占位符、流长度/哈希及结构化投影，不保存本机绝对
路径或原始流。

机器报告为
[`windows-qt5-cli-filesystem.json`](data/windows-qt5-cli-filesystem.json)，
SHA-256 为
`bab9ce41f5bc82e56cba42a2d577669e8d8a6a372da030b0957fcb8b888fa02f`。
报告同时绑定：

- CLI SHA-256：
  `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e`；
- Qt 5.15.2 `qmake.exe`、`Qt5Core.dll` 和 `Qt5Script.dll` 哈希；
- fixture generator 与 collector 自身 SHA-256；
- Windows 默认 baseline 报告 SHA-256。

## 可观察边界

单目标和只有一个 PDF 的目录均输出 756 bytes JSON，stdout SHA-256 为
`50eac08de24510fecccfb962f5e85eacf3f658d0712061e5de115daa3c6d7590`。
`tree` case 扫描 alias 和 real 两项，输出两个 filename-prefixed JSON document，
共 1,643 bytes，SHA-256 为
`784b77024b3fad0c460dbc6daffaf875e7531678109d70d404cee610dabccbf0`。
这延续了上游多目标结构化输出不是单一 JSON document 的既有契约。

普通用户环境不能创建文件或目录 symbolic link，系统返回需要相应权限的错误；
因此本报告没有把 Junction 结论泛化为所有 reparse tag。以下缺口保持显式：

- 文件/目录 symbolic link、dangling reparse point；
- junction/reparse cycle 及其超时、深度和访问预算；
- 超过 `MAX_PATH` 的真实长路径（当前 `\\?\` case 是普通长度）；
- ACL denial、UNC share、alternate data stream 和大小写敏感目录。

这些缺口分别需要受控权限主体、网络 share 或带硬超时/资源预算的隔离 harness，
不能从本轮成功路径推断。
