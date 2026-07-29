# 上游 ZIP 规则数据库与 cache 行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Components:
`horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`,
`horsicq/XArchive@0fcd4e8d3e9933baac3b12246d82ac026557ffd0`

Last updated: 2026-07-29

## 1. 范围

本文补充 [`database-error-behavior.md`](database-error-behavior.md) 未覆盖的：

- 合法、空、截断、重复 entry、`..` 名称和额外根前缀 ZIP database；
- ZIP database 与目录 database 的规则选择和可观察结果；
- 发布 `diec` CLI 是否启用 XScanEngine database cache；
- engine cache 的路径、header、失效条件和不可信输入风险。

机器差分报告为
[`data/database-archive-linux-qt5.json`](data/database-archive-linux-qt5.json)，
原生 Windows Qt5 复验为
[`data/windows-qt5-cli-database-archive.json`](data/windows-qt5-cli-database-archive.json)，
Windows engine cache/DACL harness 为
[`data/database-cache-engine-windows-qt5.json`](data/database-cache-engine-windows-qt5.json)，
CLI cache 源码/容器探针摘要为
[`data/database-cache-cli.json`](data/database-cache-cli.json)，
engine `bUseCache=true` 专用 harness 报告为
[`data/database-cache-engine-qt5.json`](data/database-cache-engine-qt5.json)。

本轮证明 Linux Qt5 qmake/CMake 固定 CLI oracle、原生 Windows Qt5 qmake
CLI oracle，以及链接未修改上游 engine 的 Linux/Windows Qt5 专用 harness。
engine cache 结论不外推到 Qt6 或 macOS。

## 2. 固定身份

两套 oracle：

| Build | Image | Image ID |
| --- | --- | --- |
| Qt5 qmake reproducible | `diec-rust/upstream-oracle:74eaf505-repro` | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| Qt5 CMake | `diec-rust/upstream-oracle-cmake:74eaf505` | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| Qt5 CMake cache harness | `diec-rust/upstream-database-cache-harness:74eaf505` | `sha256:17f7bd0514e973df9da8ff06967cb73ddff906cb568d1d07d75f3b09c7146fc9` |

三个镜像 label 都固定到上游
`74eaf505c250ab47e709024e9dc41657cd8f2254`。关键源码 SHA-256：

| Path | SHA-256 |
| --- | --- |
| `src/console/main_console.cpp` | `ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f` |
| `XScanEngine/xscanengine.cpp` | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| `XScanEngine/xscanengine.h` | `ddef8387f72cd8a740052d47813018fb0e6f74ed3d3a911827ad1b7b3ce15fe8` |
| `XArchive/xzip.cpp` | `f20ab74f3f919bf8db666b7f7b9e6a0206c9d087a11b4ff60fb2a395162213b7` |
| `XArchive/xzip.h` | `dc9942c19e90b593de030bddeaf5994a47d6c59edc60c91e9be944bb42b41473` |

项目生成的
[`database-fixture.json`](data/database-fixture.json) 包含 15 个文件，
其中 10 个是 ZIP 边界。fixture 不包含上游规则或第三方样本字节。

## 3. ZIP database 源码语义

`XScanEngine::loadDatabase(path, type, useCache, ...)` 先判断 path 是 file
还是 directory。file 一律交给 `XZip`，且 ZIP 分支完全不使用
`useCache`。

ZIP 有效时调用 `getRecords(-1)`，再按固定类型前缀逐次选择 entry：

- 名称不含 `/` 的根 entry 作为 `FT_UNKNOWN`；
- 名称第一段等于 `Binary`、`PE`、`ELF` 等固定类型名，且第二段非空时，
  作为对应 file type；
- 额外根前缀如 `database/Binary/a.sg` 不匹配；
- 选择逻辑不拒绝第二段或后续段为 `..`；
- 相同名称的多个 records 不去重；
- archive loader 不调用目录 loader 使用的 `isSignatureFileValid()`；
- 每个匹配 record 都被解压为 `SIGNATURE_RECORD.sText`，并标记
  `bReadOnly = true`。

这不是文件系统解包：`Binary/../a.sg` 没有写到宿主路径。但该逻辑会把含
`..` 的 archive 逻辑名称作为规则路径加载和执行，Rust loader 不能在
normalization 时静默改变这一兼容事实。

## 4. 可重复 ZIP 差分

生成 fixture：

```text
python tools/corpus/generate_database_fixture.py <fixture-dir>
```

运行两套固定 oracle：

```text
python tools/upstream/probe_database_archives.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --database-fixture-dir <fixture-dir> \
  --output docs/research/data/database-archive-linux-qt5.json
```

ZIP database 矩阵为 17 case、34 次 oracle 执行。两套构建的 exit、stdout
和 stderr 全部逐字节相同，报告 `failures = []`。每个 case 同时保存两侧原始 stream 的
Base64、长度和 SHA-256；不是只保存规范化结果。

### 4.1 有效、空与截断

| ZIP 状态 | `--showdatabase` | 扫描结果 | JSON |
| --- | --- | --- | --- |
| 完整，单条 Binary rule | exit 0，`Binary: 1` | `Fixture` | valid |
| 空 EOCD-only ZIP | exit 0，无规则 | `Unknown` | valid |
| 删除 22-byte EOCD | exit 0，`Binary: 1` | `Fixture` | valid |
| 只保留 local header + 完整 payload | exit 0，`Binary: 1` | `Fixture` | valid |
| payload 末尾缺 1-byte newline | exit 0，`Binary: 1` | `Fixture` | valid |
| payload 缺 closing brace + newline | exit 0，`Binary: 1` | `Unknown` 后追加 parse error | invalid |
| local header 在 29 bytes 截断 | exit 0，无规则 | `Unknown` | valid |

因此，上游 `XZip` 的“有效 database”不要求 central directory 或 EOCD；
它能从 local header 枚举 record。声明 payload 比实际剩余数据更长也没有让
database load 失败。若缺失字节仍不改变 JavaScript 语法，结果与完整 ZIP
逐字节相同；若破坏语法，错误延迟到规则执行：

```text
fixture.1.sg: Binary/fixture.1.sg: 4: SyntaxError: Parse error
```

CLI 仍退出 0，错误追加 stdout 并破坏 JSON。29-byte local header 也被静默
接受为空 database。与既有 19-byte 非 ZIP 文本的 `--showdatabase` exit 3
不同，不能用通用 ZIP library 的 `BadZipFile` 分类替代上游 oracle。

### 4.2 重复名称、`..` 与根前缀

- 两个同名 `Binary/duplicate.1.sg` 都被执行，按 archive record 顺序得到
  `DuplicateFirst`、`DuplicateSecond`；
- `Binary/../traversal.1.sg` 被作为 Binary rule 执行，得到
  `TraversalName`；
- `database/Binary/prefixed.1.sg` 不匹配固定第一段，结果为 `Unknown`；
- 三者 exit 0、stderr 为空且 JSON 有效。

差分规范化不得按名称去重、把 `..` entry 静默拒绝，或自动剥离任意公共根目录，
否则会隐藏真实兼容差异。现代安全 profile 可以拒绝危险名称，但必须形成明确
diagnostic/SafetyDeviation，而不是改变 legacy profile 后仍声称等价。

### 4.3 原生 Windows Qt5 复验

[`collect_windows_cli_database_archives.py`](../../tools/upstream/collect_windows_cli_database_archives.py)
直接复用上述 17 个 case，在固定 Windows Qt5 oracle 上每项连续运行两次，共
34 次。全部双轮稳定；17/17 exit code、stderr 和受限规范化后的 stdout
SHA-256 与 Linux Qt5 相同，10 个 scan case 的 JSON validity 也逐项相同。

跨平台规范化只把实际 Windows path argument 替换成对应 `/dbfx/...` argument，
并把 CRLF 改为 LF；不解析 JSON、不改写 ZIP entry、不删除 diagnostic 或排序
record。完整身份、复现命令和逐项结论见
[`windows-database-archive-behavior.md`](windows-database-archive-behavior.md)。

## 5. 发布 CLI 的 cache 可达性

`main_console.cpp` 使用：

```text
XScanEngine::SCAN_OPTIONS scanOptions = {};
```

随后设置数据库层、formatter 和 scan flags，但没有设置 `bUseCache`，也没有
注册 cache CLI option。因此固定发布 CLI 调用 `loadDatabase()` 时
`bUseCache == false`。

目录分支仍先调用 `_getDatabaseCachePath()`。它会创建：

```text
QStandardPaths::AppDataLocation/db_cache/
    <MD5(database path UTF-8)>.cache
```

接着，cache disabled 分支若发现同名文件便调用 `QFile::remove()`。在两套
一次性 oracle 中设置 `XDG_DATA_HOME=/tmp/xdg`，先放置 13-byte
`corrupt-cache`，再让 CLI 加载 `/dbfx/valid-main`：

| Oracle | Cache name | Before | After |
| --- | --- | ---: | --- |
| qmake | `2a513e7f3b4e0f02c53e6da3c4b0d866.cache` | 13 bytes | removed |
| CMake | `2a513e7f3b4e0f02c53e6da3c4b0d866.cache` | 13 bytes | removed |

两次 probe 均 exit 0。故 cache hit/stale/corrupt cache 不属于当前发布 CLI 的
可观察扫描路径；CLI 的实际副作用是创建 app-data/cache 目录并删除对应旧文件。

## 6. Engine cache 格式与风险

engine caller 将 `bUseCache` 设为 true 时，目录 database 使用 version 5
Qt `QDataStream` cache：

1. magic `0x44494543`（`DIEC`）；
2. version `5`；
3. engine name；
4. recursive file count、total size、newest mtime；
5. record count；
6. 每条 record 的 file type、name、path、database type、完整 script text、
   parsed type/version/info、EP flag 和 line。

cache 文件名只绑定 database path 的 MD5；有效性只比较 file count、total
size 和 newest mtime，不包含逐文件 path/content hash。源码还能观察到：

- `_loadDatabaseCache()` 对 cache 使用 `readAll()`；
- `nRecordCount` 直接用于 `reserve()` 和循环；
- 没有 cache byte、record count 或 script text 上限；
- stream status 在反序列化循环结束后才检查；
- 目录统计递归包含全部文件，而规则 loader 只读取根和固定类型一级目录。

这些是 Rust 设计的安全输入，不是应照搬的格式。Rust 实现不得把上游 cache
当作可信二进制，也不得用无界 read/reserve。若未来需要 cache，应使用带 schema、
完整内容身份、checked length 和预算的项目格式；legacy CLI 兼容只需复现当前
cache-disabled 行为。

### 6.1 固定 engine harness

专用 harness 只替换上游 console `main`，链接固定 CMake Qt5 镜像中的未修改
engine objects。它以非特权 UID/GID `65534:65534` 运行，复制项目生成的单条
Binary 规则，固定文件 mtime 为 `1700000000.123` 秒，设置
`bUseCache=true`，并在网络禁用、2 CPU、1 GiB 内存和 256 PIDs 的容器中
连续执行十九个状态：

```text
docker build --network none \
  --build-arg BASE_IMAGE=diec-rust/upstream-oracle-cmake:74eaf505 \
  -f tools/upstream/Dockerfile.database-cache-harness-qt5 \
  -t diec-rust/upstream-database-cache-harness:74eaf505 \
  tools/upstream

python tools/upstream/probe_database_cache_harness.py \
  --image diec-rust/upstream-database-cache-harness:74eaf505 \
  --binary /opt/die-build/src/console/diec-database-cache-harness \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --database-fixture-dir <fixture-dir> \
  --repetitions 2 \
  --output docs/research/data/database-cache-engine-qt5.json
```

报告保存两次完整 stdout/stderr 的 Base64、长度和 SHA-256；两次输出逐字节相同，
`passed=true` 且 `failures=[]`。十九个 case 的可观察结果如下：

| Case | Binary records | Scan | Cache |
| --- | ---: | --- | --- |
| `initial_miss` | 1 | `Fixture` | 创建 399-byte cache |
| `unchanged_hit` | 1 | `Fixture` | 相同 SHA-256 |
| `same_stats_stale_hit` | 1 | `Fixture` | 内容已改成 `Changed`，仍命中旧 cache |
| `stats_changed_rebuild` | 1 | `Changed` | mtime 改变后重建 |
| `bad_magic_fallback` | 1 | `Changed` | 回退目录并重写有效 cache |
| `bad_version_fallback` | 1 | `Changed` | 回退目录并重写有效 cache |
| `empty_cache_fallback` | 1 | `Changed` | 空文件回退并重写 |
| `magic_only_fallback` | 1 | `Changed` | 仅 magic 回退并重写 |
| `magic_version_only_fallback` | 1 | `Changed` | 仅 magic/version 回退并重写 |
| `truncated_record_fallback` | 2 | `Changed` | 半截 record 污染内部列表后回退 |
| `record_tail_truncated_fallback` | 2 | `Changed`, `Changed` | 尾部少 1 byte，完整检测重复 |
| `cache_write_denied` | 1 | `Changed` | 成功且无诊断，不产生 cache |
| `cache_write_recovery` | 1 | `Changed` | 权限恢复后创建 399-byte cache |
| `concurrent_identical_writers` | 1 | `Changed` | 8 writer 均成功，最终 cache 有效 |
| `database_directory_permission_denied` | 0 | `Unknown` | 返回成功并保存 42-byte 空 cache |
| `database_file_permission_denied` | 0 | `Unknown` | 返回失败，无诊断和 cache |
| `canceled_cache_hit` | 0 | `Unknown` | 返回成功，原 cache 不变 |
| `canceled_cache_miss` | 0 | `Unknown` | 返回成功并写出 42-byte 空 cache |
| `poisoned_empty_cache_hit` | 0 | `Unknown` | 未取消的后续加载命中空 cache |

所有 case 的 `loadDatabase()` 都返回 true，`scan_errors` 都为空。具体含义是：

- freshness 三元组无法发现保持 file count、total size、newest mtime 不变的内容替换；
- bad magic、bad version 以及 0/4/8-byte header 截断会干净回退并重写；
  截断发生在 record 中时，stream status 在 append 之后才检查，已反序列化的
  record 没有回滚；半截 record 令状态计数为 2 但只产生一个有效检测，尾部少
  1 byte 则把同一条规则执行两次；
- cache directory 不可写时，规则仍从源目录加载且 `loadDatabase()` 返回 true，
  写失败没有 signal/返回值；权限恢复后的下一次 load 会正常创建 cache；
- 同一路径、相同输入的 8 个同步并发 miss/writer 在两次独立运行中全部成功，
  最终 cache 与串行输出逐字节相同；源码仍是无锁的直接 `QFile(WriteOnly)`
  truncate/write，没有临时文件、原子 rename 或跨进程锁，因此此结果不能证明
  changed-during-read 或不同内容 writer 安全；
- 不可搜索的 database 目录被当作空目录成功加载并持久化空 cache；存在但
  不可读的 database ZIP file 则静默返回 false。两者都不产生 scan error；
- 预取消的 cache hit 和 miss 都被报告为成功且不产生诊断；
- 更严重的是，预取消的 miss 会持久化零 record cache；下一次未取消加载会复用它，
  稳定地产生 `Unknown`，而不是重新读取仍有效的规则源。

这些行为属于固定低层 oracle 的事实，但不是 Rust 默认实现应复制的安全缺陷。
Rust cache decode 必须事务化：完整校验成功后才能发布 records；取消或失败不得提交
cache，也不得把部分/空状态暴露给后续扫描。若 legacy engine profile 确需模拟这些
差异，必须以类型化兼容选项和差分测试隔离，不能污染默认安全路径。

### 6.2 原生 Windows Qt5 engine harness

Windows adapter 复用同一 19-case harness，仅将 POSIX file-time/permission
设施映射为 Qt file time 与当前用户 SID 的 DACL deny/restore，并只替换固定
qmake Release 构建中的 `main_console.obj`。两轮原生进程执行 raw stream
逐字节稳定；19/19 load/cancel/count/scan/cache-existence 投影与 Linux Qt5
相同，18/18 非身份行为关系全部成立。

有 record 的 cache 在 Windows 为 403 bytes、Linux 为 399 bytes；42-byte
空 cache 两侧相同。报告保留这一平台字节差异。Windows 权限 case 使用继承
DACL 拒绝整棵 database tree；只拒绝根目录不能替代 POSIX mode `0000`，
因为 Windows token 的 traverse bypass 允许访问已知子路径。入口启用 Qt
test mode，将 cache 隔离到 `qttest` app-data 命名空间。完整构建身份、DACL
模型和复现命令见
[`windows-database-cache-behavior.md`](windows-database-cache-behavior.md)。

## 7. 对 Rust 实现的约束

- ZIP database loader 必须把 archive 结构状态与规则 parse/runtime 状态分开；
- legacy profile 保留 record 顺序、重复项、固定第一段类型选择和原始规则路径；
- unknown/unsupported ZIP compression 或损坏 payload 必须明确诊断，不能当作
  空 database 静默通过；
- archive entry count、compressed/uncompressed bytes、单规则文本和总规则文本
  必须有 checked budgets；
- 现代 profile 可以拒绝 `..` 和重复 entry，但差异必须类型化并可审计；
- 默认 Rust CLI 不需要复用上游 Qt cache；若产生自己的 cache，不得污染或删除
  上游 app-data；
- cache freshness 绑定规则 bundle 的完整内容身份；decode、database build 与
  cache publish 均为事务，失败或取消时不发布部分 records、不写 cache；
- cache publish 使用同目录临时文件、flush/close 校验与原子替换，并按 cache
  identity 串行化 writer；permission/write failure 必须形成类型化诊断；
- cache bytes、record count、单 script 和总 script bytes 使用 checked budgets，
  cache miss/fallback 不能绕过同一预算；
- 差分保留 raw stdout/stderr，特别是 JSON 后追加规则错误的 framing。

## 8. 仍未覆盖

- bad engine、超大 record count 和声明 script 长度；
- changed-during-read 与不同内容 writer 的竞争结果；固定源码已证明没有锁和
  原子 publish，本项目不把未定义调度结果作为 golden output；
- deflate/其他 method、encrypted ZIP、CRC mismatch、data descriptor、ZIP64；
- 超大 entry count、声明长度欺骗、压缩比和总解压预算；
- Windows domain/group DACL、UNC/network share/EFS/integrity level，
  macOS path/QStandardPaths，以及 archive filename encoding。
