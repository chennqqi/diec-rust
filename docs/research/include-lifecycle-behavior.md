# 上游 include 循环与错误传播行为

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-27

## 范围

本实验验证 `includeScript()` 尚未覆盖的端到端失败路径：

- helper 直接 include 自身；
- 两个 helper 相互 include；
- included helper 存在 JavaScript parse error；
- include 名称不存在；
- init/include 失败后是否继续执行后续 Binary rule；
- messages signal、最终 `listErrors`、stdout/stderr 和进程终止。

fixture 和输入均由项目生成，不包含上游规则或外部样本。固定 qmake/CMake Qt5
oracle 各运行 4 个 case。机器报告为
[`data/include-lifecycle-linux-qt5.json`](data/include-lifecycle-linux-qt5.json)。

## 固定实现路径

`DiE_ScriptEngine::includeScriptSlot()` 在全部 root records 中按不区分大小写的名称
找到首项，然后直接在当前 engine 中 `evaluate()`。它没有 active include stack、
once cache、深度或 cycle guard。helper evaluation 返回 error 时发出
`includeScript <name>: ...` signal；缺失时发出 `Cannot find: <name>`。

global `_init` 本身由 `_executeInitSignature()`/`evaluateEx()` 求值，所以嵌套
evaluate 的异常还可能成为 `_init` 的最终错误。signal 与 `SCAN_RESULT.listErrors`
是不同通道。

## 观察结果

全部 8 次运行都：

- 在 10 秒探针上限内完成；
- exit code `0`；
- stderr 为空；
- 继续执行循环/错误之后的 `Binary/after.1.sg`；
- 返回该规则唯一的 `Format: After ...` detection；
- qmake/CMake 的完整 stdout 逐字节相同。

| Case | JSON 前 messages | JSON 后错误 | stdout bytes |
| --- | ---: | --- | ---: |
| self-cycle | 28 条 `includeScript self: ... RangeError` | 1 条 `_init ... RangeError` | 2485 |
| two-cycle | 28 条 cycle-a/cycle-b 交替 `RangeError` | 1 条 `_init ... RangeError` | 2567 |
| parse-error | 2 条相同 `includeScript broken-helper ... SyntaxError` | 1 条 `_init ... SyntaxError` | 650 |
| missing | 2 条相同 `Cannot find: not-present` | 无 | 544 |

两个循环都在 QtScript 内部栈上限处得到
`RangeError: Maximum call stack size exceeded.`，没有 native crash 或 timeout。
28 条 messages 是此固定 Qt5 build 的观察值，不是跨 runtime 的可移植深度契约。

included parse error 同时走 signal 和 `_init` 最终错误，因此 stdout 在 JSON 前后
都有诊断。missing include 只有 signal，不进入最终 `listErrors`；关闭
`--messages` 时该失败完全不可见，但后续规则照常运行。

所有 case 的结构化 JSON 都被前置或后置文本破坏 framing。仅检查 exit code、
stderr 或成功 detection 都会漏掉 include 失败。

## 安全与兼容含义

上游依靠 VM 栈上限结束循环，并在展开过程中重复发出诊断。本项目不能把不可信或
同步后可能损坏的规则转换成无界 Rust/native 递归。Rust 设计应在数据库阶段检测
静态 include cycle，并在 runtime 用 active stack、深度和执行预算覆盖动态路径。

这会有意改变诊断数量和错误类型，属于安全偏差，必须保留上游 raw baseline，并由
[`ADR 0010`](../design/decisions/0010-bounded-include-graph.md) 及精确 waiver
约束，不能用 normalizer 隐藏。

## Fixture 与复现

[`generate_include_fixture.py`](../../tools/corpus/generate_include_fixture.py)
生成 13 个文件和 17 个目录。版本化清单
[`data/include-fixture.json`](data/include-fixture.json) 固定每个路径、用途、
长度和 SHA-256。

```powershell
python tools\corpus\generate_include_fixture.py `
  I:\tmp\diec-include-fixture

python tools\upstream\probe_include_lifecycle.py `
  --fixture-dir I:\tmp\diec-include-fixture `
  --raw-dir I:\tmp\diec-include-raw `
  --output docs\research\data\include-lifecycle-linux-qt5.json
```

每次 Docker 运行固定 `--network=none`、只读 mount、`--memory=256m`、
`--pids-limit=64`，Python 另设每 case 10 秒 timeout。探针验证 manifest 全集、
image revision/binary hash、raw stream hash/length、诊断顺序、detection 和双
oracle 等价；timeout、非零退出或 stderr 都会失败。

## 尚未覆盖

- Qt 6、Windows 和 macOS 的 stack limit、error 文本及 signal 次数；
- 三层数据库同名 helper 与 cycle 的组合；
- 动态计算 include 名称；
- include 后 helper 留下的部分 global side effect；
- 单次 scan 中多个独立 include errors 的最终排序。

