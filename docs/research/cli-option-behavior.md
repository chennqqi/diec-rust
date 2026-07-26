# 上游 CLI verbose、messages、profiling 与测试入口行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 范围

本文补齐能力矩阵中此前只有源码证据的五个 CLI 入口：

- `--verbose`；
- `--messages`；
- `--profiling`；
- `--test <directory>`；
- `--createtest <filename>`。

确定性选项探针同时运行固定 Linux Qt5 qmake 与 CMake oracle。两个镜像的 revision
均为 `74eaf505...`，共同的 `/usr/bin/true` SHA-256 为
`4b5a5694e3c0e8b1d58fc52ac6ef076e55e72c2f53195243ac86d5ff517cc2f6`。
9 个 case 的退出码、stdout 和 stderr 在两个构建间逐字节相同。

机器报告为
[`cli-option-behavior-linux.json`](data/cli-option-behavior-linux.json)，生成器为
[`probe_cli_option_behavior.py`](../../tools/upstream/probe_cli_option_behavior.py)。
报告保存 canonical 原始 UTF-8 文本、长度和 SHA-256；每个 oracle/case 的原始
stdout/stderr 还保存到 `--raw-dir` 指定的非版本化目录。

## `--test` 是加载数据库后的无操作分支

固定
[`main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp#L382-L392)
在 `--test` 分支先调用 `loadDatabase()`，随后只有 `// TODO`。选项值
`sTestDirectory` 不再被读取。

实验分别传入存在的 `/tmp` 与不存在的 `/does-not-exist`：

| 输入 | Exit | stdout | stderr |
| --- | ---: | --- | --- |
| `--test /tmp` + 固定数据库 | 0 | empty | empty |
| `--test /does-not-exist` + 固定数据库 | 0 | empty | empty |

因此固定版本没有执行规则测试，也不校验 directory。这里的 exit 0 依赖 main
database 成功；如果数据库加载失败，入口末尾的 `bIsDbUsed && !bDbLoaded` 仍会
改写为数据库错误码 3。

## `--createtest` 只打印文案

固定
[`main_console.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp#L393-L410)
同样先加载数据库。完整参数要求 option value 之外还有两个 positional argument，
依次解释为 detect string 和 directory：

```text
--createtest /usr/bin/true ... "Detect String" /tmp
```

结果 exit 0，只向 stdout 打印：

```text
Adding test for file '/usr/bin/true' with detect string 'Detect String' in directory '/tmp'
```

打印后仍只有 `// TODO`，没有创建或修改测试文件。缺少 positional arguments 时
exit 4，stdout 为：

```text
Error: --addtest requires <filename> <detect_string> <directory>
```

错误文案使用未注册的旧名称 `--addtest`，而实际注册的 long option 是
`--createtest`。两种路径的 stderr 都为空。

## `--verbose` 改变结构化检测语义

CLI 将该选项写入 `SCAN_OPTIONS::bIsVerbose`。固定
[`XScanEngine::scanFileFormatInfo()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L1817-L1850)
仅在 verbose 下把 `FILEFORMATINFO` 的 OS 信息追加为普通 `SCANSTRUCT`。

默认 `/usr/bin/true` JSON 只有 GLIBC library value。verbose 保留该 value，并在
前面精确增加：

```json
{
  "type": "operation system",
  "name": "Linux",
  "version": "ABI: 3.2.0",
  "info": "AMD64, 64-bit"
}
```

所以 verbose 不是纯表示层的“多打印一些日志”，而是改变统一扫描结果中的 records
集合及顺序。Rust 兼容比较必须把新增 record 作为语义字段处理。

## `--messages` 把 signals 写入 stdout

固定 CLI 只在 `--messages` 时把 `DiE_Script` 的 error、warning 和 info signals
连接到 `ConsoleOutput`。三个 slot 都用 `printf("%s\n", ...)` 写 stdout；不会写
stderr，也没有结构化 framing。

在 main database 不存在时：

- 不带 messages：exit 3，只打印三条 database path；
- 带 messages：exit 仍为 3，在相同 path 输出之前增加
  `Cannot load database: /does-not-exist`；
- 两种路径的 stderr 都为空。

因此 messages 不改变该错误码，但会污染 stdout。若与 `--json` 一起使用且扫描
期间产生 signal，完整 stdout 可能不再是有效 JSON；这不是 stderr channel。

源码证据：

- [`main_console.cpp` signal wiring](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/main_console.cpp#L334-L340)；
- [`consoleoutput.cpp`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/consoleoutput.cpp)。

## `--profiling` 需要 messages 才可观察

CLI 将 profiling 写入 `bLogProfiling`。固定
[`DiE_Script::_executeSignature()`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp#L264-L332)
在每条 signature 前 emit 规则名，并在执行后 emit
`<signature>: [<elapsed> ms]`；signature/search helpers 还可产生其他 timing
message。

本轮确定性对照表明：

- `--profiling --json` 但不带 `--messages` 时，退出码和原始 stdout/stderr 与默认
  JSON 逐字节相同；
- 这不表示 profiling 没有执行，而是 signals 没有连接到 console；
- 带 `--messages` 后，profiling lines 位于 JSON 之前，elapsed 毫秒数非确定，
  完整 stdout 不再是 JSON 文档。

固定 Binary 语料的真实 profiling+messages 探针已从两个 oracle 各提取 292 条
规则且顺序一致；canonical 顺序和原始 artifact 哈希见
[`binary-rule-lifecycle.md`](binary-rule-lifecycle.md#linux-qt5-实测顺序) 与
[`binary-rule-order-linux-qt5.json`](data/binary-rule-order-linux-qt5.json)。
规范化只去除非确定 elapsed 值，不能忽略规则顺序、缺失、重复或附加 diagnostics。

## 复现

两个固定镜像必须已由上游构建基线生成：

```powershell
python tools\upstream\probe_cli_option_behavior.py `
  --raw-dir I:\tmp\diec-cli-option-behavior-raw `
  --output docs\research\data\cli-option-behavior-linux.json
```

探针对 Docker 容器使用 `--network=none`，校验 image revision、image ID、样本
SHA-256、两个 oracle 的逐字节一致性以及上述全部关系。任何关系变化都会拒绝生成
报告，而不是只更新 hash。

## 兼容边界

这些事实不等于本项目应在 canonical CLI 宣传未完成的 test/create 功能：

- 若提供上游兼容入口，其 no-op、stdout、错误码和旧 `--addtest` 文案都是可观察
  基线；
- 若 canonical CLI 不暴露无功能选项，则这是相对上游的明确范围/契约差异，不能
  把 `--test` 或 `--createtest` 标成已实现能力；
- verbose 必须进入核心扫描选项，因为它改变 record 集合；
- messages/profiling 必须与 canonical 结构化输出 channel 分离，否则无法同时
  保证上游 framing 和有效 JSON。

最终产品策略属于设计决策；本文只固定上游事实。
