# Windows 超过 MAX_PATH 的路径行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 范围与结论

本实验固定原生 Windows x86_64、Qt 5.15.2 qmake CLI oracle 对真实超过
`MAX_PATH` 的文件与目录行为。7 个 case 各连续运行两次，共 14 次执行：

- 324-code-unit 显式文件通过普通 Win32 path 和 `\\?\` path 均扫描成功；
- 指向该文件的深目录通过普通 path 和 `\\?\` path 均扫描成功；
- 从短 `discovery-root` 开始递归，能够发现相对路径为 325 code units 的叶子；
- 给短 discovery root 添加 `\\?\` 前缀也得到相同行为；
- 全部执行退出 `0`、stderr 为空、JSON 有效，detection tree 与固定
  `minimal.pdf` 相同；
- 7 个 case 的 756-byte stdout 全部逐字节等于短路径 control。

因此，固定上游 CLI 在当前 Windows/Qt5 环境中不受传统 260-character 边界
阻断；它既能接收显式超长路径，也能在目录递归中形成并打开超长叶子。该结论
不等价于已验证 Win32/NT 命名空间精确最大值。

## 确定性夹具

[`generate_windows_long_path_fixture.py`](../../tools/corpus/generate_windows_long_path_fixture.py)
从固定 331-byte `minimal.pdf` 生成短 control 和两个长路径副本。每个长路径
包含 6 个 49-code-unit ASCII 目录组件；最长组件远低于单组件 255 限制，而
完整相对路径独立超过 260：

| ID | 相对路径长度 | 用途 |
| --- | ---: | --- |
| `control` | 18 | 短路径输出 reference |
| `explicit` | 324 | 显式文件和深目录 argv |
| `discovery` | 325 | 从短根目录递归发现长叶子 |

因为相对路径本身已经超过 `MAX_PATH`，无论 fixture 根目录位于哪个绝对位置，
物化后的绝对路径都必然更长。payload SHA-256 为
`47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92`。

版本化清单
[`windows-long-path-fixture.json`](data/windows-long-path-fixture.json) SHA-256
为 `ef9bfe473ed4bd36df3c21500f7961080e1b3043ac2cf952f135939dabe2ccad`。
生成器只用 `\\?\` 命名空间物化和校验长 fixture，避免生成工具自身成为被测
Win32 普通路径能力的一部分。

## Oracle 与证据绑定

采集命令：

```powershell
python tools\upstream\collect_windows_cli_long_paths.py `
  --binary <source>\build\release\diec.exe `
  --source-dir <source> `
  --qt-dir <qt-root>\5.15.2\msvc2019_64 `
  --fixture-dir <generated-fixture> `
  --expected-binary-sha256 e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e `
  --output docs\research\data\windows-qt5-cli-long-paths.json
```

采集器重新校验上游/rules commit、58 个递归 submodule、Qt 关键文件、CLI、
fixture manifest 和 Windows 默认 `minimal.pdf` reference。机器报告
[`windows-qt5-cli-long-paths.json`](data/windows-qt5-cli-long-paths.json)
SHA-256 为
`54084feff726a1da17e8b4b7ff40eed46733bd6eb2f5f900e4f02ec43bfb6cf5`。
报告只保存流长度/哈希、去本机路径的 argv 和 detection projection。

## 尚未覆盖

- 接近 Win32 `32,767` namespace 上限的精确成功/失败边界；
- Unicode supplementary character 的 UTF-16 code-unit 计数边界；
- UNC 长路径及 `\\?\UNC\`；
- symbolic link、dangling/cyclic reparse point、ACL denial、alternate data
  stream 和大小写敏感目录。

这些边界不能由 324/325-code-unit ASCII 正例外推；后续应使用独立、带硬资源
上限的 fixture，而不修改本报告的固定输入。
