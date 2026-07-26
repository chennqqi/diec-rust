# 上游引擎过滤、排序、取消与扫描入口行为

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-27

## 范围

本实验补充 CLI 无法覆盖的 `XScanEngine`/`DiE_Script` 契约：

- `sSignatureName` 精确规则过滤；
- `bIsSort` 最终 record 排序；
- scan callback、规则 `_breakScan()` 和预先停止的 `PDSTRUCT`；
- `scanFile`、`scanMemory`、`scanDevice`、`scanSubdevice`；
- 源码中存在但公共扫描入口不可达的 `sSignatureFilePath`。

固定 Linux amd64、Qt 5.15.13 CMake oracle。harness 替换上游 console main 后链接
同一组已构建对象；输入和规则均由项目生成，不包含外部样本。机器报告为
[`data/engine-contract-linux-qt5.json`](data/engine-contract-linux-qt5.json)。

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
- 规则内 `_breakScan()` 同样保留调用前已追加的当前 record，再停止后续规则；
- 两种运行中停止均令 `pd_stopped=true`、`pd_not_canceled=false`、
  `pd_success=false`，但 API 仍返回包含部分 detection 的 `SCAN_RESULT`；
- 调用前已停止时不执行规则，但普通 Unknown 收尾仍增加唯一 `Unknown`。

因此上游“停止”不是事务性错误返回，也不会丢弃部分结果。Rust modern API 若选择
返回类型化 `Cancelled` 且不暴露部分 detection，属于有意差异，必须由 ADR 和
legacy/modern 两套回归测试约束。

### 扫描入口

对同一 35-byte 输入及同一精确规则过滤，四个入口的完整 record 数组一致：
path、相同 memory bytes、`QBuffer` device，以及带前后哨兵的 `QBuffer`
subdevice 精确切片。该结论仅证明本 Binary fixture，不外推 I/O 错误、设备位置、
无效范围、并发设备或其他文件类型。

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
hash、fixture 全集/hash、16 个 case 关系和源码可达性；raw streams 保存在未跟踪
目录，提交报告只保存长度和 SHA-256。

## 尚未覆盖

- callback 在中间规则停止及 callback 自身异常；
- scan 运行期间由其他线程设置 `PDSTRUCT` 的精确竞态窗口；
- device short-read/error、无效 subdevice 范围和非 seekable device；
- 相同契约的 Qt 6、Windows 和 macOS 行为。

