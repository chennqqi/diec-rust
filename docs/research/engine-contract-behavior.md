# 上游引擎过滤、排序、取消与扫描入口行为

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  

Components:
`XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`,
`Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`

Last updated: 2026-07-28

## 范围

本实验补充 CLI 无法覆盖的 `XScanEngine`/`DiE_Script` 契约：

- `sSignatureName` 精确规则过滤；
- `bIsSort` 最终 record 排序；
- scan callback 在首条/中间/末条停止、同步跨线程停止、规则 `_breakScan()`、
  预先停止及取消后恢复；
- `scanFile`、`scanMemory`、`scanDevice`、`scanSubdevice`；
- device 分块读取、提前 EOF、read/seek error、sequential 与初始 position；
- subdevice 合法/非法范围、父设备短读/error 和 slice 边界；
- 源码中存在但公共扫描入口不可达的 `sSignatureFilePath`。

同一 37-case harness 的固定 Windows Qt5 结果见
[`windows-engine-contract-behavior.md`](windows-engine-contract-behavior.md)。

固定 Linux amd64、Qt 5.15.13 CMake oracle。harness 替换上游 console main 后链接
同一组已构建对象；输入和规则均由项目生成，不包含外部样本。机器报告为
[`data/engine-contract-linux-qt5.json`](data/engine-contract-linux-qt5.json)。
派生镜像 ID 为
`sha256:2a3ce9d5...4462a`，harness binary SHA-256 为
`22d0219a...c0cdb2`；报告同时绑定 harness、Dockerfile、fixture 和七个上游
源码文件的完整 hash。

## 观察结果

### 规则名过滤

`sSignatureName` 使用区分大小写的完整文件名匹配。指定
`a_extra.0.sg` 时只有 extra 层该规则执行；缺失名称或仅大小写不同均不执行规则，
随后按普通 `bAddUnknown` 路径产生唯一 `Unknown`。精确指定 `DS.deep.2.sg` 也不
绕过 deep gate：关闭 deep 得到 `Unknown`，开启后才执行该规则。

`sSignatureFilePath` 不是 `SCAN_OPTIONS` 字段。它只存在于
`DiE_Script::processDetect()` 私有参数及 `_shouldExecuteSignature()` 内部路径；
受保护的 `_processDetect()` 在本 commit 唯一真实调用中固定传 `""`。因此当前
公共扫描 API 无法请求文件路径过滤。报告保存三个相关源码文件的 SHA-256，并要求
调用点形态改变时探针失败。

### record 排序

同一规则按 `packer(100)`、`format(12)`、`compiler(30)` 插入三条 record：

- `bIsSort=false` 保持插入顺序；
- `bIsSort=true` 得到 `format(12)`、`compiler(30)`、`packer(100)`。

这是检测 record 的最终排序，与数据库加载阶段的 signature 排序不同。

### 停止语义

- callback 在每条规则执行前收到规则文件名、规则总数和零基 current index；
- callback 对第一条返回 false 后，第一条规则仍执行并保留结果，后续规则停止；
- callback 对第二条返回 false 时保留前两条 record；对最后一条返回 false 时
  三条 record 全部存在，但 `PDSTRUCT` 仍为 stopped/not-success；
- 独立线程在第二次 callback 内设置 stop、并在线程 `join` 后再返回 callback，
  同样保留前两条 record。报告证明 setter 确实由不同线程执行一次；
- 规则内 `_breakScan()` 同样保留调用前已追加的当前 record，再停止后续规则；
- 两种运行中停止均令 `pd_stopped=true`、`pd_not_canceled=false`、
  `pd_success=false`，但 API 仍返回包含部分 detection 的 `SCAN_RESULT`；
- 调用前已停止时不执行规则，但普通 Unknown 收尾仍增加唯一 `Unknown`。
- 同一个 `DiE_Script` 实例在一次第二条取消后，换用新的 `PDSTRUCT` 再扫描会执行
  全部三条规则并恢复 success；取消状态属于传入的 progress state，而不是永久
  污染 engine。

因此上游“停止”不是事务性错误返回，也不会丢弃部分结果。Rust modern API 若选择
返回类型化 `Cancelled` 且不暴露部分 detection，属于有意差异，必须由 ADR 和
legacy/modern 两套回归测试约束。

固定源码还限定了“异步”的含义：`PDSTRUCT::bIsStop` 是普通 `bool`，
`setPdStructStopped()` 是普通赋值，`isPdStructNotCanceled()` 是普通读取，没有
atomic 或 mutex。未同步地由一个线程写、扫描线程同时读属于 C++ 数据竞争和未定义
行为，不能生成可移植 compatibility golden。本实验只保存由 callback 与 `join`
建立 happens-before 的跨线程请求；Rust modern API 则必须使用 thread-safe atomic
cancel token。首/中/末 checkpoint、同步外部请求、预停止、规则内停止和 fresh-state
恢复共同闭合 Linux Qt5 的 `CAP-GAP-011`。

### 扫描入口

对同一 35-byte 输入及同一精确规则过滤，四个入口的完整 record 数组一致：
path、相同 memory bytes、`QBuffer` device，以及带前后哨兵的 `QBuffer`
subdevice 精确切片。

### 分块读取与设备位置

所有新增 case 强制 `FT_BINARY` 并精确选择不读取输入内容的
`z_priority.1.sg`，从而隔离扫描入口的 I/O 行为，不让未初始化尾部影响检测分支。

- direct device 每次底层最多返回 3 bytes 时，`safeReadData()` 共调用 12 次，
  返回序列为 11 个 `3` 和一个 `2`，最终补齐 35 bytes；
- 带前后哨兵的 35-byte subdevice 同样调用 12 次，但父 `QIODevice` 每次底层
  返回 `3`，合计读取 36 bytes；逻辑 subdevice 结果仍为 35 bytes，证明 Qt
  buffering 触碰了 slice 末端后一字节；
- direct device 初始位置设为 7 后，扫描依次 seek `7 → 0`，最终位置为 35。
  上游不会保留调用前 cursor。

### 提前 EOF、read error 与不可 seek

direct 和合法 subdevice 各覆盖四种不完整输入：

| Behavior | 底层返回 | Scan result |
| --- | --- | --- |
| early EOF | `5, 0`，只取得 5/35 bytes | Binary / `Priority one` |
| read error | `-1`，取得 0/35 bytes | Binary / `Priority one` |
| seek error | seek 失败，read 未调用 | Binary / `Priority one` |
| sequential | seek 失败，read 未调用 | Binary / `Priority one` |

八个 case 都是 `pd_success=true`、`pd_finished=true`、空 `result.listErrors` 和空
`PDSTRUCT::sErrorString`。只有注入 read-error device 自己的 `errorString()` 为
`injected read error`；scanner 没有传播它。

源码解释了该结果：`scanProcess()` 对不超过 16 MiB 的输入分配
`new char[nSize]`，忽略 `read_array_process()` 返回值，再以完整声明长度构造
`QBuffer`；`safeReadData()` 对 `read <= 0` 仅 break。未读尾部因此是未初始化
字节。Rust 不复制这一行为；安全决策见
[`ADR 0013`](../design/decisions/0013-fail-closed-incomplete-input.md)。

### Subdevice 范围

父设备固定 42 bytes。五个非法范围为：

- offset `-1`, size `1`；
- offset `0`, size `0`；
- offset `0`, size `-1`；
- offset `42`, size `1`；
- offset `41`, size `2`。

它们都在 `isOffsetAndSizeValid()` gate 返回 false：结果 size 为 0、filetype 为
Unknown、records/errors 为空、seek/read 均为 0，PDSTRUCT 未 finished/success。
offset `41`, size `1` 精确最后一字节则有效，读取 1 byte 并产生正常 Binary
结果。注意 `SubDevice` 构造器本身支持 `size=-1` 的“到末尾”语义，但公共
`scanSubdevice()` 的前置 gate 使该分支不可达。

以上运行证据与源码审计闭合 Linux Qt5 的 `CAP-GAP-009`。Rust 对 silent
short-read success、slice 外读取和非法范围空成功的有意偏离由 ADR 0013 与未来
SafetyDeviation regression 管理。

## 复现

```powershell
python tools\corpus\generate_rule_orchestration_fixture.py `
  I:\tmp\diec-rule-orchestration-fixture

docker build --network=none `
  -f tools\upstream\Dockerfile.engine-contract-harness-qt5 `
  -t diec-rust/engine-contract-harness-qt5:74eaf505 `
  tools\upstream

python tools\upstream\probe_engine_contract.py `
  --fixture-dir I:\tmp\diec-rule-orchestration-fixture `
  --raw-dir I:\tmp\diec-engine-contract-raw `
  --output docs\research\data\engine-contract-linux-qt5.json
```

Docker 全程 `--network=none`，fixture 只读挂载。探针验证 image revision、binary
hash、fixture 全集/hash、37 个 case 关系和源码可达性；raw streams 保存在未跟踪
目录，提交报告只保存长度和 SHA-256。

## 尚未覆盖

- callback 抛出 C++ exception 的 unwind 行为未执行；公共 callback 契约没有
  类型化异常通道；
- 未同步跨线程 stop 的真正数据竞争不执行，也不属于可移植兼容契约；
- unknown/negative-size device、未打开或 null device、并发修改和超大
  `nOffset + nSize` 的 C++ signed-overflow 路径未执行；
- 本轮强制 Binary 规则不读取输入内容，因此未把未初始化尾部的偶然字节保存为
  兼容 golden；该路径只作为源码证明的安全缺陷；
- 相同契约的 macOS 行为。
