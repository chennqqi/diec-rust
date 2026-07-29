# Windows Qt5 ZIP 规则数据库行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 范围与结论

本文把 Linux Qt5 已固定的 17 个 ZIP 规则数据库 case 原样移植到原生
Windows x86_64 Qt5 oracle。机器报告为
[`data/windows-qt5-cli-database-archive.json`](data/windows-qt5-cli-database-archive.json)，
SHA-256 为
`53c673620cc4388f0da7ffe36af7a325a099bceb0e29912c1f733119f942d748`。

17 个 case 每个连续执行两次，共 34 次进程执行：

- 34/34 双轮 raw summary 完全稳定；
- 17/17 exit code 与 Linux Qt5 相同；
- 17/17 stderr 与 Linux Qt5 相同，均为空；
- 10 个 scan JSON case 的 validity 与 Linux Qt5 相同；
- 仅替换实际 path argument 并把 CRLF 改为 LF 后，17/17 stdout
  SHA-256 与 Linux Qt5 原始 stdout 相同。

因此，在本矩阵范围内，完整/空/多种截断 ZIP、重复 entry、`..` entry 和额外
根前缀的加载、规则执行、错误 framing 与 Linux Qt5 没有语义差异。这个结论只
覆盖发布 CLI 的 ZIP database 分支。CLI 不可达的首轮 engine cache/DACL
行为已由
[`windows-database-cache-behavior.md`](windows-database-cache-behavior.md)
单独固定；两份报告的 reachability 和构建边界不同，不能合并。

## 2. 固定身份

采集器在执行前重新验证：

| 输入 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Detect-It-Easy rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| Recursive submodules | 58，全部 clean |
| Qt | 5.15.2，`win32-msvc` |
| `diec.exe` | `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e` |
| Fixture manifest | `90b6ce18e5656fa30c2dfd55573df4612825a74e77cb9e2f4fc1baa81fd7223c` |
| Linux Qt5 reference | `fca0dc355c5e12bfd955317534c369a123587df3f475615865225caced9be0ac` |

采集器还绑定自身、Windows database helper、Linux archive case 定义和固定
Linux 报告的 SHA-256。case 直接复用
[`probe_database_archives.py`](../../tools/upstream/probe_database_archives.py)
的 `ARCHIVE_CASES`，没有复制或维护第二套参数清单。

## 3. 可重复采集

先用固定生成器 materialize
[`database-fixture.json`](data/database-fixture.json)，再运行：

```text
python tools\upstream\collect_windows_cli_database_archives.py `
  --binary <source>\build\release\diec.exe `
  --source-dir <source> `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --fixture-dir <database-fixture> `
  --expected-binary-sha256 `
    e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e `
  --output `
    docs\research\data\windows-qt5-cli-database-archive.json
```

报告不保存本机绝对路径，也不保存未受控的临时文件。每次 Windows observation
保存 exit code、stdout/stderr 长度和 SHA-256；同 case 的两轮结果先进行原始
确定性比较。

跨平台比较只执行两项命名变换：

1. 把每个实际 Windows path argument 替换为该 case 的原始 `/dbfx/...`
   argument；
2. 把 CRLF 替换为 LF。

比较不解析或重排 JSON，不改写 ZIP entry name，不删除 diagnostic，不排序
record，也不进行其他空白规范化。Windows raw stream hash 仍是权威 observation。

## 4. 行为投影

Windows 与 Linux Qt5 精确一致的关键行为包括：

- 完整 ZIP、无 EOCD ZIP、仅 local header+payload ZIP 和 payload 少一个末尾
  换行的 ZIP 都加载 `Fixture`；
- EOCD-only 空 ZIP、29-byte local-header 截断和带额外根前缀的 ZIP 产生
  `Unknown`；
- 结构截断的规则先产生 `Unknown` JSON，再在 stdout 追加
  `SyntaxError: Parse error`，使整个 stdout 不是合法 JSON，但仍 exit 0；
- 两个同名 entry 按 archive record 顺序执行，得到
  `DuplicateFirst`、`DuplicateSecond`；
- `Binary/../traversal.1.sg` 不被拒绝或重写，执行得到
  `TraversalName`；
- 七个 `--showdatabase` case 的规则计数、exit code 与输出 framing 均与
  Linux Qt5 相同。

这些事实意味着 Rust legacy 兼容 profile 不能依赖宿主路径语义去清理 ZIP
逻辑名称，也不能用通用 ZIP library 的严格“必须存在 central directory”
判断替代上游枚举行为。

## 5. 剩余边界

- Windows domain/group 复杂 DACL、UNC/network share、EFS/integrity level；
- Windows changed-during-read、不同内容 writer 和恶意 cache resource 边界；
- macOS ZIP database 与 cache/path 行为；
- deflate/其他 method、encrypted ZIP、CRC mismatch、data descriptor、ZIP64；
- 超大 entry count、声明长度、压缩比和总解压预算。

Linux engine cache 的 stale/corrupt/cancel/permission 事实和 Rust 安全约束见
[`database-archive-cache.md`](database-archive-cache.md)。
