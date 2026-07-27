# 上游数据库与不可读输入错误行为

Status: Draft
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 范围

本文记录固定 Linux Qt5 qmake/CMake `diec` 对以下状态的退出码、stdout 和
stderr：

- main database 缺失、空目录、存在但不是有效 ZIP；
- 隔离 main database 中的 JavaScript 语法错误和运行时异常；
- project-generated 最小成功规则；
- main 有效但 extra/custom 缺失；
- 普通扫描、info 和 entropy 对存在但不可读文件的行为。

所有规则和输入 fixture 都由项目生成，不包含第三方样本字节。版本化清单为
[`database-fixture.json`](data/database-fixture.json)。

## 源码返回值与 CLI 状态

固定
[`XScanEngine::loadDatabase()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L1255)
先清空 signature list，再依次加载 main、extra、custom，但函数返回值只来自
main：

```text
result = load(main)
load(extra)   // return ignored
load(custom)  // return ignored
return result
```

目录存在即令该层 `loadDatabase()` 返回 true，即使目录为空或没有有效规则。
文件路径则被当作 ZIP；文件存在但 ZIP 无效时返回 false。只有“main 路径既不是
文件也不是目录”的分支 emit `Cannot load database: <path>`；无效 ZIP、
extra/custom 缺失都没有对应 signal。

固定
[`main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp#L346)
维护 `bIsDbUsed` 和 `bDbLoaded`：

- `--showdatabase`、`--test`、`--createtest` 在加载后把 `bIsDbUsed` 设为 true。
- positional target 分支调用 `loadDatabase()`，但没有把 `bIsDbUsed` 设为
  true。
- 最终只有 `bIsDbUsed && !bDbLoaded` 才返回
  `CR_CANNOTFINDDATABASE = 3`。

因此普通扫描、info 和 entropy 的 main database 加载失败不会触发最终数据库
退出码；之后 `ScanFiles()` 的结果覆盖 `nResult`。

`--messages` 只是把 error/warning/info signal 连接到
`ConsoleOutput`，三个 slot 都用 `printf()` 写 stdout。普通扫描完成后，
`scanResult.listErrors` 也无条件追加到 stdout，不依赖 `--messages`。

## 确定性 fixture

生成命令：

```sh
python3 tools/corpus/generate_database_fixture.py \
  /tmp/diec-database-fixture
```

fixture 包含：

```text
empty-main/
empty-extra/
empty-custom/
malformed-main/Binary/broken.1.sg
throwing-main/Binary/throw.1.sg
valid-main/Binary/fixture.1.sg
not-a-database.bin
input/plain.txt
```

- malformed rule 为确定性的 JavaScript parse error。
- throwing rule 在 `detect()` 中抛出 `Error("database fixture")`。
- valid rule 直接调用宿主 `_setResult()`，产生
  `Format: Fixture(1)`。
- invalid archive 是 19 字节固定文本，不是 ZIP。
- scan input 与基线 `plain.txt` 字节和 SHA-256 相同。

生成器记录所有文件的 purpose、size 和 SHA-256。测试要求两次生成逐字节
一致并匹配版本化 manifest。oracle 工具还拒绝路径逃逸、symlink、未声明
文件/目录及 hash/size 不匹配。

## 可重复实验

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --database-fixture-dir /tmp/diec-database-fixture
```

数据库矩阵包含 18 个 case、36 次 oracle 执行。不可读输入矩阵是工具的固定
通用基线，另含 4 个 case、8 次 oracle 执行。两个构建在所有 case 上的退出码、
原始 stdout 和原始 stderr 都逐字节相同；stderr 始终为空。

## Main database 加载状态

`--showdatabase`：

| Main 状态 | Exit | `--messages` 诊断 | 规则状态 |
| --- | ---: | --- | --- |
| missing path | 3 | 有：`Cannot load database: ...` | 无 |
| empty directory | 0 | 无 | 无 |
| invalid ZIP file | 3 | 无，即使启用 messages | 无 |
| directory with malformed rule | 0 | 无 | Binary: 1 |

即使 main 加载失败，`--showdatabase` 仍先后打印 main、extra、custom 路径。
没有 `--messages` 时 missing main 仅靠退出码 3 表示失败；invalid ZIP 即使有
messages 也没有文本诊断。malformed rule 在 load 阶段只作为文本记录计数，不
解析 JavaScript。

普通 JSON 扫描：

| Main 状态 | Exit | JSON 有效 | 结果/错误 |
| --- | ---: | --- | --- |
| missing，无 messages | 0 | yes | Binary `Unknown: Unknown` |
| missing，有 messages | 0 | no | load error 行在 JSON 之前 |
| empty directory | 0 | yes | 与 missing/no-messages 逐字节相同 |
| invalid ZIP | 0 | yes | 与 missing/no-messages 逐字节相同 |
| malformed rule | 0 | no | Unknown JSON 后追加 parse error |
| throwing rule | 0 | no | Unknown JSON 后追加 runtime error |
| valid rule | 0 | yes | `Format: Fixture(1)` |

missing/empty/invalid 的有效 Unknown JSON stdout SHA-256 均为
`83cbe006c9b24c93260312b75a213904e76b75b7fcdb17612c6640f37a20c78c`。
valid rule stdout SHA-256 为
`f4aba52e28e2dcc3bffc03eb016364485834d7501a0a0859fbfa4bee2593fa17`。

语法错误追加：

```text
broken.1.sg: Binary/broken.1.sg: 1: SyntaxError: Parse error
```

运行时异常追加：

```text
throw.1.sg: Binary/throw.1.sg: 2: Error: database fixture
```

两者都退出 0，错误写 stdout 且破坏 JSON。是否启用 `--messages` 不影响
`scanResult.listErrors` 的最终打印。

固定规则集中两个真实拼写错误也表现为相同 framing。project-generated 32/40
字节输入分别触发 `get_DWRAF_vi` 和 `xma2_pase_xma2_chunk` 的
`ReferenceError`；固定 qmake/CMake 都先输出 `Binary/Unknown` JSON，再追加一条
带规则路径和行号的 stdout 诊断，stderr 为空且 exit 0。该实验使用
`--messages`，尚未据此外推无该参数时的行为。详见
[`global-typo-error-behavior.md`](global-typo-error-behavior.md)。

## Extra/custom 失败

main 使用固定完整上游 db，而 extra/custom 指向不存在路径时：

- `loadDatabase(SCAN_OPTIONS*)` 返回 true；
- 即使启用 `--messages` 也没有 load error；
- `--showdatabase` 退出 0，并报告 main 的规则计数；
- plain text scan 的 JSON 与完整三层数据库基线逐字节相同。

最后一点只说明当前 plain text detection 不依赖 extra/custom，不能外推到其他
格式或规则。关键接口语义是 extra/custom 加载失败既不改变返回值，也不产生
诊断。

## Special mode 与数据库错误

target 分支无条件先加载数据库，即使 entropy/info 不使用 DIE rule。missing
main 且启用 messages 时：

- load error 先写 stdout；
- entropy/info 随后输出各自 JSON；
- 最终退出 0；
- 拼接结果不是有效 JSON。

entropy case stdout SHA-256 为
`5ad38aa824c0d700135846416dc631973a4ae2de3fdd9f2d49cb94be51d95326`，
info case 为
`c1a6dd12c3b3bb4fd0d202d851de621fa8fc1a11ccac785457ee9fb206ebbec1`。

## 不可读输入

为避免访问系统敏感文件，工具在每个临时容器内用
`install -m 000 /dev/null /tmp/unreadable-fixture` 创建空的非敏感 fixture，
再用 `runuser -u nobody` 启动 `diec`。结果：

| 路径 | Exit | JSON | stdout SHA-256 |
| --- | ---: | --- | --- |
| normal scan | 0 | 扁平 `Result` value object | `3813fcaab55579f111a39bca06243358aab53a6ba7925715b08cb4f30d821f0a` |
| normal + messages | 0 | 与 normal 逐字节相同，无诊断 | 同上 |
| info | 2 | `{"data": ""}` | `c0538adbaf9b1b80944941180f00fe139fb0457290e47944ef8e7c0c6cd67168` |
| entropy | 0 | total 0、空 status、空 records | `0a74d09f562d585bf7e8701dc7d1c3830bbb8f5493b55c52bb39ff145f85782d` |

normal scan 的 JSON 不是通常的 `{"detects": [...]}`，而是：

```json
{
  "info": "",
  "name": "",
  "string": "Result",
  "type": "",
  "version": ""
}
```

这三条路径的差异来自各自不同的 open-failure 检查：info 明确把
`XFileInfo::processFile()` false 映射为 `CR_CANNOTOPENFILE = 2`；entropy 不
检查 `processRegionsFile()` 是否打开成功；普通扫描也不把底层 open failure
映射到 CLI 返回码。

## Rust 兼容与错误模型约束

- 上游 CLI 的静默失败、stdout 诊断和无效 JSON 是兼容基线事实，不应被误解为
  推荐设计。
- 核心 Rust API 必须区分 database not found、invalid database archive、
  empty database、rule parse error、rule runtime error 和 input open error。
- 未知/不支持规则语法不得静默忽略；这也是本项目现有工程约束。兼容 CLI 若
  需要复现上游 exit/stdout，应在薄适配层显式转换，而不是让核心错误消失。
- extra/custom 是 optional layer 不等于其加载失败应不可见。Rust API 应返回
  每层 provenance/status；默认 CLI 策略和 strict/compatibility 行为需要 ADR。
- 自动化调用方不能只检查退出码，也不能假设 stderr 承载错误；差分测试必须
  同时保留原始 stdout、stderr、exit code 和 JSON validity。

## 尚未覆盖

- permission-denied database directory/file 已由非特权 engine harness 固定：
  不可搜索目录被静默当作空 database 成功加载并写出空 cache；不可读 ZIP
  静默返回 false。详见 [`database-archive-cache.md`](database-archive-cache.md)。
- 发布 CLI 的合法/空/截断 ZIP、重复 entry、`..` 名称和额外根前缀，以及
  cache-disabled 删除副作用已由
  [`database-archive-cache.md`](database-archive-cache.md) 覆盖。engine
  `bUseCache=true` 的 miss/hit、同统计 stale、bad magic、截断和预取消已由
  专用 harness 固定；扩展 harness 还覆盖 bad version、0/4/8-byte header、
  record 中部/尾部截断、cache 写失败与恢复，以及 8 个同输入并发 writer。
- encrypted/ZIP64/data descriptor/CRC mismatch、压缩比和超大 entry count。
- main/extra/custom 同名规则不覆盖、分层顺序和 load/runtime gate 已由
  [`database-layer-behavior.md`](database-layer-behavior.md) 固定；同层 ZIP
  duplicate 与跨层 directory/ZIP 混合仍待覆盖。
- 多个独立 script/include error 的最终 ordering；missing、parse error 和
  self/two-node include cycle 已由
  [`include-lifecycle-behavior.md`](include-lifecycle-behavior.md) 覆盖。
- Windows/macOS 文件权限及错误字符串。
