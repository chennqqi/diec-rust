# Windows NTFS Alternate Data Stream 行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

本实验固定原生 Windows x86_64、Qt 5.15.2 qmake CLI oracle 对 NTFS named
`$DATA` stream 的输入与枚举行为。5 个 case 各连续运行两次，共 10 次执行：

- `carrier.bin` 默认流包含固定 `plain.txt`，显式扫描得到 Binary /
  `Plain text`；
- `carrier.bin:payload.pdf` 命名流包含固定 `minimal.pdf`，普通 Win32 path
  和 `\\?\` path 均得到 PDF detection；
- 两种命名流扫描的 756-byte stdout 都与独立 `minimal.pdf` control 逐字节
  相同；
- 扫描 `ads` 目录只处理 `carrier.bin` 默认流，500-byte stdout 与显式默认流
  逐字节相同；命名流不会作为独立目录项被枚举；
- 全部执行退出 `0`、stderr 为空、JSON 有效且双轮无漂移。

因此，上游把显式 ADS path 当作普通可打开文件目标，并按命名流实际内容检测；
目录递归不会主动发现同一文件的 named stream。Rust legacy compatibility 必须
把“显式打开”和“枚举发现”视为两个不同路径。

## 固定夹具

[`generate_windows_ads_fixture.py`](../../tools/corpus/generate_windows_ads_fixture.py)
物化一个普通文件及一个命名流：

```text
ads/carrier.bin                 default stream: plain.txt, 31 bytes
ads/carrier.bin:payload.pdf     named stream: minimal.pdf, 331 bytes
```

默认流 SHA-256 为
`22b217bfba5795d402092bf48bfb28146c0ee4dd0036fd4d0c93e25bbe65e998`；
命名流 SHA-256 为
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。
生成器在提交清单前重新读取两条 stream，并确认普通目录枚举只出现 carrier。

版本化清单
[`windows-ads-fixture.json`](data/windows-ads-fixture.json) SHA-256 为
`9f3dfe34e5f728abd0ee8642a516e82cf1daba08343582315d9b78dbfbf1ab10`。
若目标 filesystem 不支持 named stream，生成器明确失败，不将 sidecar 文件
冒充 ADS。

## Oracle 与证据绑定

采集命令：

```powershell
python tools\upstream\collect_windows_cli_ads.py `
  --binary <source>\build\release\diec.exe `
  --source-dir <source> `
  --qt-dir <qt-root>\5.15.2\msvc2019_64 `
  --fixture-dir <generated-fixture> `
  --corpus-dir <generated-baseline-corpus> `
  --expected-binary-sha256 e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e `
  --output docs\research\data\windows-qt5-cli-ads.json
```

采集器重新校验上游/rules commit、58 个递归 submodule、Qt 关键文件、CLI、
fixture manifest、`minimal.pdf`/`plain.txt` corpus identity 和既有 Windows
detection references。机器报告
[`windows-qt5-cli-ads.json`](data/windows-qt5-cli-ads.json) SHA-256 为
`bfdec0a8a516dd5d86721a9331d1d914c7e66f29df0fe0d6115c6dcca079224e`。
报告只保存流长度/哈希、去本机路径 argv 和 detection projection。

## 尚未覆盖

- 目录自身的 named stream、多个 stream 的显式 argv 顺序；
- 非 `$DATA` stream type 和 native backup API 的 stream enumeration；
- ADS 名称 Unicode、大小写、空名、非法名及路径长度组合边界；
- UNC、ACL denial、symbolic link、dangling/cyclic reparse point、大小写敏感
  目录和精确 path namespace 上限。

这些边界需要独立 fixture；本报告只冻结一个普通文件上的单个 named
`$DATA` stream。
