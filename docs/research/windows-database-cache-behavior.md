# Windows Qt5 engine database cache 与 DACL 行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Component: `horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-29

## 1. 范围与结论

本文在原生 Windows x86_64、Qt 5.15.2、非提升 token 下复验 Linux
[`database-archive-cache.md`](database-archive-cache.md) 已固定的 19 个
engine `bUseCache=true` 状态。机器报告为
[`data/database-cache-engine-windows-qt5.json`](data/database-cache-engine-windows-qt5.json)，
SHA-256 为
`d1cbcbe741e4cf3999f54f4696f6eee59472b59bd3aaf9d98f94bb337b1e16da`。

两轮 harness 进程执行的 raw stdout/stderr 逐字节稳定；38 个 case
observations 的结构化结果稳定。与 Linux Qt5 比较：

- 19/19 case 的 load result、cancellation、Binary record count、scan names、
  scan errors 和 cache existence 投影相同；
- 去掉 POSIX UID/GID 条件后，18/18 命名行为关系全部成立；
- 有 record 的有效 cache 在 Windows 为 403 bytes，在 Linux 为 399 bytes；
- canceled miss、poisoned empty hit 和 permission-denied directory 的空 cache
  两侧均为 42 bytes；
- cache SHA-256 是平台/path 表示相关事实，不做跨平台等价声明。

因此，stale hit、corrupt fallback 的部分 record 污染、silent write failure、
同输入并发 writer、权限拒绝、取消后空 cache poisoning 等低层行为在本范围内
不是 Linux 特例。Rust 安全实现仍不得复制这些缺陷；legacy compatibility
profile 如需表达差异，必须与默认事务化 cache 隔离。

## 2. 固定构建身份

Windows harness 不修改上游 source tree，也不重编 engine objects。构建器
[`build_windows_database_cache_harness.ps1`](../../tools/upstream/build_windows_database_cache_harness.ps1)
验证固定 source/rules/58 个递归 submodule、Qt 二进制和既有 CLI 后：

1. 读取固定 qmake Release `Makefile.Release`；
2. 只把 `release/main_console.obj` 替换为项目生成的 Windows adapter object；
3. 继续链接同一批未修改上游 engine/format/archive objects；
4. 为研究 DACL 操作额外链接 Windows 系统库 `Advapi32.lib`。

| 项目 | SHA-256 / 值 |
| --- | --- |
| 固定 `diec.exe` | `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e` |
| 原始 Release Makefile | `5250c5d08d120c914351b858ff115442baebfdf31efb799d1a70fad4890a0293` |
| 原始 `main_console.obj` | `47180c01c4fb12359a8621ecc829afd899f5ee8b6262c6caafb320b50a928abf` |
| Harness executable | `f7a9aed9c6eedb323dfbed8be01020df3b4c759c20668d79dcf75b7421aa1bf7` |
| Harness size | 3,107,840 bytes |
| Host | Windows `10.0.26100`, AMD64 |
| Token | non-elevated |

构建 manifest、builder、共享 harness、adapter 和 compatibility header 的哈希
均嵌入机器报告。MSVC/PE bit-for-bit 可重复性仍未由本次单次最终构建证明；
运行时行为由连续两轮 raw stream hash 固定。

## 3. Windows 适配边界

共享 19-case 主体仍是
[`database_cache_harness_main.cpp`](../../tools/upstream/database_cache_harness_main.cpp)。
Windows adapter 只提供三类平台设施：

- `utimensat` 映射为 `QFile::setFileTime(FileModificationTime)`；
- `chmod(0555/0000/restore)` 映射为当前用户 SID 的 DACL deny/restore；
- POSIX effective UID/GID 输出使用 `-1` sentinel，不参与跨平台关系。

cache directory 的 deny ACE 只拒绝 add/write/delete-child。数据库目录的 deny
ACE 使用 `SUB_CONTAINERS_AND_OBJECTS_INHERIT` 传播到既有 `Binary` 子目录和
规则文件；仅拒绝根目录不足以模拟 POSIX mode `0000`，因为普通 Windows token
通常具有 `SeChangeNotifyPrivilege`，可绕过已知子路径的 traverse 检查。
ZIP database 文件则直接拒绝当前用户的 read data。

入口在调用共享 harness 前启用
`QStandardPaths::setTestModeEnabled(true)`。Qt 5.15.2 Windows 将 app-data
隔离到用户 `qttest/NTInfo/die/db_cache` 命名空间，避免删除或覆盖普通
Detect It Easy 用户 cache。报告只保存 raw stream hash，并将已验证的 test-mode
根路径规范化为 `<qt-test-appdata>`；不提交用户名或本机绝对路径。

## 4. 可重复运行

构建：

```text
tools\upstream\build_windows_database_cache_harness.ps1 `
  -SourceDir <fixed-source> `
  -BuildDir <fixed-qmake-build> `
  -QtDir <qt-5.15.2-msvc2019_64> `
  -VsDevCmd <vs2019-vcvars64.bat> `
  -OutputBinary <output>\diec-database-cache-harness.exe `
  -OutputJson <output>\build.json
```

采集：

```text
python tools\upstream\collect_windows_database_cache_harness.py `
  --binary <output>\diec-database-cache-harness.exe `
  --source-dir <fixed-source> `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --fixture-dir <database-fixture> `
  --build-manifest <output>\build.json `
  --working-dir <drive-with-writable-tmp> `
  --output `
    docs\research\data\database-cache-engine-windows-qt5.json
```

采集器拒绝提升 token、错误 source/Qt/binary/build/fixture/Linux reference 身份、
少于两轮、case 缺失/重排、非零 exit、stderr、raw 非确定性和规范化 observation
非确定性。

## 5. 逐类事实

Windows 与 Linux Qt5 相同的行为关系为：

- initial miss 创建一条规则 cache；unchanged hit 复用同一 cache；
- 保持 size+mtime 的 `Fixture`→`Changed` 替换仍命中旧规则；
- mtime 改变后重建并执行 `Changed`；
- bad magic/version、0/4/8-byte header 截断回退并重写；
- record 中段/尾部截断在回退前注入部分 record，计数变为 2；尾部截断执行
  两次 `Changed`；
- cache directory DACL 拒绝写入时 load/scan 成功、无错误且不产生 cache；
  恢复 DACL 后下一次 load 创建有效 cache；
- 8 个同步相同 writer 均成功，最终 cache 可读；
- 整棵 database tree 被 DACL 拒绝后，load 返回 true、0 records、
  `Unknown`，并写 42-byte 空 cache；
- ZIP database file 被 DACL 拒绝后，load 返回 false、0 records、
  `Unknown`，且不写 cache；
- 预取消 cache hit 返回成功但 0 records；预取消 miss 写 42-byte 空 cache；
  后续未取消 load 复用 poisoned empty cache 并保持 `Unknown`；
- 所有 scan error lists 为空。

Windows 的 populated cache 比 Linux 多 4 bytes；本报告保留逐 case size delta
和各平台内部 cache hash 关系，不用重新序列化或删字段把两侧 cache bytes
伪装成等价。

## 6. Rust 约束与剩余边界

Rust 默认 cache 仍须满足
[`database-archive-cache.md`](database-archive-cache.md) 的事务化 decode/build/
publish、内容身份、预算和原子替换要求。Windows 额外要求：

- DACL/read/write failure 形成类型化 diagnostic，不依赖 POSIX mode 抽象；
- cache/app-data 根通过平台接口显式选择，并允许测试隔离；
- permission test 必须区分 root-only deny 与 inherited tree deny；
- 不把 Windows/Linux Qt `QDataStream` cache 大小或 hash 当作项目 cache ABI。

仍未覆盖：

- domain/group 复杂 DACL、UNC/network share、EFS 和 alternate integrity level；
- changed-during-read、不同内容 writer 与进程崩溃中断 publish；
- Windows cache 的恶意超大 record count/script length 资源表现；
- Qt6 和 macOS engine cache；
- 正式 Rust cache 设计的跨进程锁、恢复与故障注入验证。
