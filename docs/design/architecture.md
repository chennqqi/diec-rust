# diec-rust 分层架构

Status: Draft

Last updated: 2026-07-26

## 1. 状态与证据

本文是 Phase 0 的架构草案，不表示设计门禁已经通过，也不授权开始正式功能实现。
它冻结优先级最高的边界：workspace 职责、依赖方向、扫描数据流、资源预算和第三方
runtime 隔离。公共 Rust API、CLI 契约和完整结果字段仍由后续 `api.md` 定义。

设计依据如下：

- [`source-analysis.md`](../research/source-analysis.md)：上游模块、扫描入口和依赖关系；
- [`behavior-baseline.md`](../research/behavior-baseline.md)：可观察输出及兼容基线；
- [`rule-compatibility.md`](../research/rule-compatibility.md)：规则生命周期、宿主 API 和未知语法；
- [`nested-scan-behavior.md`](../research/nested-scan-behavior.md)：overlay、resource、
  archive 和递归行为；
- [`rule-runtime-spike.md`](../research/rule-runtime-spike.md) 与
  [`rquickjs-rule-runtime-spike.md`](../research/rquickjs-rule-runtime-spike.md)：
  runtime 候选的能力与风险；
- [`c-static-link-spike.md`](../research/c-static-link-spike.md)：静态链接、panic 和 allocator
  验证；
- [`c-abi.md`](c-abi.md)：C ABI 的所有权和线程模型。

所有兼容性结论继续固定到仓库记录的确切上游 commit。本文中的 crate 名称可以在
实现前评审时调整，但任何会反转依赖方向或绕开统一扫描服务的调整必须新增 ADR。

## 2. 目标

- 用一个无 GUI、可移植的 Rust 核心承载所有检测语义。
- CLI、C ABI、Go 和 Python 看到同一份结构化扫描结果。
- 上游规则字节原样保存，规则行为可与固定上游 oracle 差分。
- 把所有二进制输入视为不可信数据，统一控制偏移、分配、递归、时间和脚本资源。
- 使格式解析、规则 runtime 和扫描编排能够分别测试与替换。
- 默认产生确定性结果；并行执行不能改变有语义的顺序。
- 将 native 依赖和必要的 `unsafe` 限制在可审计的最小边界。

## 3. 非目标

- Phase 0 不实现正式检测功能，只允许可丢弃的技术 spike 和测试基础设施。
- 当前 workspace 不包含 `diec-gui`，也不依赖 Qt 或其他 GUI 框架。
- 不设计稳定的 Rust ABI、动态插件 ABI 或进程内第三方插件系统。
- 不承诺复刻上游内部类层次、全局状态或线程模型；只兼容可观察行为。
- 不将派生规则缓存格式、调试内部对象或第三方 runtime 类型作为稳定 API。
- 不以无限制递归、无限制解压或崩溃来复刻上游；安全硬上限优先，必要偏差用 ADR
  和回归测试记录。

## 4. 架构原则

1. 依赖只向内：适配层依赖业务层，业务层不认识 CLI、FFI 或 GUI。
2. 解析与策略分离：格式 crate 提供事实，engine 决定探测顺序和扫描策略。
3. 规则与格式解耦：规则通过宿主 port 查询数据，不直接依赖具体格式模块。
4. 一份结果模型：检测逻辑只写一次，所有输出端只做表示转换。
5. 显式上下文：数据库、预算、取消和诊断随请求传递，不使用可变全局单例。
6. 有界工作：嵌套扫描使用显式 work queue，不依赖调用栈递归。
7. 失败可见：未知规则语法、数据库错误、预算耗尽和部分扫描均产生结构化诊断。

该决定由
[`ADR 0002`](decisions/0002-layered-workspace.md) 记录。

## 5. Workspace 布局

初始 workspace 规划如下：

| crate | 类型 | 职责 | 允许的 workspace 依赖 |
| --- | --- | --- | --- |
| `diec-core` | library | checked input、公共值模型、错误、选项、预算、取消、结果 arena | 无 |
| `diec-formats` | library | 格式探测与安全解析，返回格式事实 | `diec-core` |
| `diec-rules` | library | 规则数据库、语法诊断、runtime/host ports 和 backend 隔离 | `diec-core` |
| `diec-engine` | library | 扫描编排、候选选择、嵌套队列、结果聚合 | `diec-core`, `diec-formats`, `diec-rules` |
| `diec-output` | library | canonical JSON 和人类可读渲染 | `diec-core` |
| `diec-cli` | binary | 参数、文件输入、退出码和终端输出 | `diec-engine`, `diec-output` |
| `diec-ffi` | `staticlib`/library | C ABI、panic containment 和句柄生命周期 | `diec-engine`, `diec-output` |
| `xtask` | tooling binary | 上游同步、清单、oracle、语料和发布检查 | 不进入 runtime graph |

初期不为每个文件格式建立 crate。格式以 `diec-formats` 内部模块隔离；只有出现独立
依赖、编译时间或复用证据后才拆分，避免大量几乎为空的 crate。

`diec-core` 也不得成为杂物箱。它只容纳所有内层消费者都需要、且不依赖具体格式或
runtime 的概念。若某个模型只服务 engine，就保留在 `diec-engine`。

## 6. 依赖 DAG 与禁止边

```text
                         diec-cli
                        /        \
                 diec-engine   diec-output
                /      |   \        |
       diec-formats     |  diec-rules
                \      |       /
                    diec-core

                         diec-ffi
                        /        \
                 diec-engine   diec-output

       xtask/tools/tests ──> 构建与测试产物，不是 runtime 依赖
```

箭头表示“上层依赖下层”。强制禁止：

- `diec-core -> diec-formats|diec-rules|diec-engine|diec-output|diec-cli|diec-ffi`；
- `diec-formats -> diec-rules|diec-engine|diec-output|diec-cli|diec-ffi`；
- `diec-rules -> diec-formats|diec-engine|diec-output|diec-cli|diec-ffi`；
- `diec-engine -> diec-cli|diec-ffi|diec-output`；
- `diec-output -> diec-engine|diec-formats|diec-rules|diec-cli|diec-ffi`；
- CLI 与 FFI 相互依赖，或任一层依赖未来 GUI；
- runtime graph 依赖 `xtask`、oracle、测试语料生成器或上游源码树。

后续用 `cargo metadata` 检查或依赖策略工具在 CI 中执行这些规则。第三方 crate 的
类型不得出现在 `diec-core` 的公共类型和 C ABI 中。

## 7. Checked input 模型

`diec-core` 定义只读的 `ByteSource`/`ByteView` 抽象。实现可以是借用内存、owned
bytes、文件或 mmap，但解析器不直接打开路径，也不自行 seek 全局文件句柄。

- offset、length 和文件大小在内部统一使用 `u64`。
- `subview(offset, length)` 必须用 checked arithmetic 验证终点。
- 所有整数读取先验证边界；不得通过切片 panic 表示解析错误。
- 转换到 `usize`、创建容器或分配缓冲区之前先检查平台上限和请求预算。
- parser 返回带位置和类别的错误，不把短读、溢出或 unsupported 混为一类。
- mmap 和平台文件 API 若需要 `unsafe`，放在单独 adapter 模块并记录安全不变量。

嵌套对象要么引用已验证的父 view，要么拥有受预算约束的解压缓冲区。每个对象保存
来源、父节点、file-part、原始 offset/size 和变换信息，保证结果可以追溯。

## 8. 格式探测与解析

`diec-formats` 提供面向事实的接口，例如 `FormatProbe`、轻量 header probe 和按需
parser。它不决定是否扫描 overlay、是否启用 aggressive mode 或先运行哪条规则。

格式候选由显式、有版本控制的有序表驱动。probe 返回：

- 是否匹配及匹配强度；
- 已验证的格式种类和基础元数据；
- 需要延迟解析的能力；
- 格式错误或 unsupported 诊断。

解析器只通过 checked input 访问字节。昂贵的字符串、哈希、熵、反汇编和解压均按需
计算并计入预算。格式模块不得直接写最终 detection，也不得读取规则数据库。

## 9. 规则数据库与 runtime port

`diec-rules` 保存三类边界：

1. 原样规则资产和来源 manifest；
2. 规则元数据、加载诊断及可丢弃的派生缓存；
3. `RuleRuntime` 与 `HostApi` ports。

规则源文件不得格式化或手工修正。加载清单记录上游路径、commit、文件哈希和同步
时间。派生索引或 bytecode cache 是内部、带版本且可重建的数据，不属于 ABI。
unknown syntax、include 失败和数据库冲突必须成为明确错误或兼容性失败，不能跳过。

`RuleRuntime` 的生命周期必须表达上游所需的 init、include、单规则求值、函数抽取、
取消和预算；不能为了同时容纳多个候选 backend 而退化成最低公分母。`HostApi` 由
`diec-rules` 定义，由 `diec-engine` 的 adapter 实现，因而规则层无需依赖
`diec-formats`。

Boa 尚未通过全库求值；QuickJS 的 per-rule lexical wrapper 已让固定 292 条
Binary 规则解析出 `detect`，但完整 HostApi 下逐条调用、其他 file type 和跨平台
门禁仍未通过；wrapper 还会隔离 Qt 本应跨规则保留的顶层 var/function，当前
固定 Binary 的静态审计未发现显式依赖。selected lifecycle 又发现前一
`detect` 动态创建的隐式全局 `bad` 是后一 EA-XA 规则的前置状态，说明 runtime
抽象必须保留跨规则动态状态，不能把静态零候选当作隔离依据。因此本文不选择 runtime。
全 292 条 fallback-tolerant 调用首轮显示 253 条规则会触及 34 类未实现 HostApi；
补入基础读取方法后仍有 233 条规则触及 19 类 fallback，32 条规则还调用 317 种
未支持 signature pattern。所以“脚本无异常返回”也不得成为 backend 验收指标，
signature parser 也不得把未知语法静默折叠为 false。固定文法与纯 Rust spike 见
[`signature-language.md`](../research/signature-language.md)：parser 与
context-free matcher 可以保持纯 Rust，但 relative/address 操作必须通过显式
memory-map port 获得上下文，不能回读 runtime 或 CLI 状态。`compare_at` 与
`find_signature` 是两个独立兼容 operation；后者的 control-record、SigByte 和
plain-hex 分支不得由前者循环模拟。
后续 ADR 必须基于固定规则集、宿主 API、资源中断、static link、许可证和跨平台
实验选型。
native runtime、FFI glue、runtime-specific handles 只存在于 `diec-rules`
backend 私有模块。

数据库完成校验后形成 immutable snapshot。scanner/session 引用 snapshot，不在扫描
期间修改规则。main、extra、custom 数据库的合并顺序是请求契约的一部分。

## 10. Engine 扫描流水线

`diec-engine` 是唯一的扫描编排层。一次请求按以下阶段执行：

1. 校验选项、输入元数据和所有 hard limits。
2. 固定 immutable database snapshot。
3. 创建 scan context：取消、deadline、预算、诊断和稳定序号分配器。
4. 按有序 probe table 收集格式候选，选择 preferred type 或 all-types 集合。
5. 为候选建立 host adapter，执行全局/type init 和排序后的规则。
6. 聚合 detections、script diagnostics、handlers 和待扫描 child work。
7. 用显式有界 work queue 处理 resource、overlay、archive entry 等 file-part。
8. 以稳定顺序 finalize result arena；渲染发生在 engine 返回之后。

CLI、FFI 和 output crate 不得复制上述任一检测分支。一次性 API 与可复用 scanner
调用同一个 scan service，仅数据库/runtime session 生命周期不同。

## 11. 嵌套扫描 work queue

嵌套扫描不直接递归调用主入口。queue item 至少包含：

- 稳定的父 `NodeId`、child ordinal 和 file-part；
- depth、source/view、provenance；
- 继承后的兼容选项和剩余全局预算；
- 必要的 ancestry/cycle fingerprint。

队列默认按父序号和 child ordinal 确定性消费。即使 worker 并行执行，merge 也按
预分配 ordinal，而不是完成时间。整个 scan 共享以下 hard budget：

- 根输入、累计读取/映射和累计解压字节；
- archive entry、结果 node 和诊断条数；
- 最大嵌套 depth、队列长度和单对象输出；
- runtime heap、stack、instruction/fuel 和 wall-clock deadline。

能够识别的 ancestry cycle 应提前终止，但 cycle detection 不能替代 hard cap。
预算耗尽返回结构化 `limit reached`，保留允许的部分结果及原始位置。若固定上游存在
off-by-one 深度行为，兼容模式也只能在安全硬上限内模拟，并须单独 ADR。

## 12. 结果模型与确定性

核心结果采用 arena：`Vec<Node>` 加稳定、仅在本结果内有效的 `NodeId` 和 parent
link，避免递归 owned graph、随机 UUID 和 FFI 自引用生命周期。

每个 node 至少能表达：

- 输入/子对象 provenance、offset、size、file-part 和初始格式；
- 有序格式候选和 detections；
- 规则/脚本错误、解析诊断及是否因预算而不完整；
- debug、profiling、handler、资源使用和有序 child ids。

最终字段由 `api.md` 冻结。确定性规则现在即生效：

- 不允许按 `HashMap` 的迭代顺序输出；
- 规则、候选、diagnostic 和 child 都有显式排序键或发现 ordinal；
- 并行结果按输入 ordinal 合并；
- canonical JSON 明确 key/order/number/UTF-8 规则；
- wall-clock timing、地址和随机 id 不进入 canonical 比较，profiling 字段必须标为
  非稳定并在差分规范化中显式处理。

规范化只能去掉文档明确声明的非语义字段，不能隐藏 detection、顺序、层级或错误。

## 13. 资源、取消与失败语义

预算是 scan context 中的单调计数器，不由每个 parser 自行解释。子任务只能消耗
父请求剩余预算，不能重新获得完整额度。所有乘法、加法和预分配都先检查。

取消 token 与 monotonic deadline 在 probe、解析循环、解压、queue 调度和规则执行
之间检查。runtime backend 必须提供 interrupt/fuel/heap 机制；不能中断的 backend
不得通过规则 runtime 门禁。

rquickjs spike 已证明外部线程可通过原子 token 触发 QuickJS interrupt，并在清除
token 后继续复用同一 context；独立 native fixture 也证明 Rust HostApi 可在受控
循环中检查同类 token 并在硬上限前合作退出。native HostApi 不会因 VM interrupt
自动停止，因此 signature/search/decompression 等循环必须接收同一
token/deadline。handler 回调和 native checkpoint 次数依赖调度，只能断言
bounded termination 和恢复，不能作为 ABI 或性能常量。

库代码以 typed `Result` 和结构化诊断报告预期失败。畸形输入、unsupported 格式、
脚本异常和预算耗尽不得 panic。系统性错误与 per-node 诊断分层，partial result
必须明确标记，不能伪装为完整成功。

库中不使用隐式 global logger。调用方可以接收结构化 diagnostics；可选 tracing
adapter 不得改变扫描行为或结果顺序。

## 14. 并发与线程模型

- database snapshot 在完成校验后 immutable，可跨 worker 共享。
- scanner 持有可变 runtime session，初始契约保守地 thread-affine、不可重入。
- 并行首先放在独立文件/job 边界，使用有界 worker pool。
- 同一 scan context 不被多个调用方并发使用；内部并行必须通过受控调度器。
- 不按文件、entry 或规则无界创建线程。
- one-shot API 可创建局部 session；复用 API 由调用方建立 scanner pool。

如果 backend 证明 session 可安全迁移或并行，也只放宽内部实现，不立即扩大 ABI
承诺。C ABI 的具体约束见 [`c-abi.md`](c-abi.md)。

## 15. Output、CLI 与 FFI adapters

`diec-output` 只消费 immutable result model，生成 canonical JSON 或人类可读文本。
它不能回读输入、执行规则或补充 detection。

`diec-cli` 负责参数、路径/stdin、批处理、终端和退出码。路径行为、特殊模式及平台
差异以固定上游 baseline 为 oracle。CLI 不构造独立结果类型。

`diec-ffi` 负责 C 类型转换、不透明句柄、panic boundary 和 allocator ownership。
它调用与 CLI 相同的 engine，并复用 `diec-output` 的 canonical JSON。静态 `.a`/
`.lib`、C/Go/Python 的限制由 [`c-abi.md`](c-abi.md) 定义。

未来 GUI 只能作为另一个 adapter 依赖 engine/output；核心层永远不反向依赖 GUI。

## 16. `unsafe`、native 与依赖隔离

workspace 默认禁止 `unsafe`。例外只允许在小型、命名清晰的 adapter/backend 模块：

- mmap/OS handle 边界；
- 经 ADR 选择的 native rule runtime；
- C ABI pointer 校验和 unwind containment。

每个 `unsafe` block 记录调用前置条件、安全不变量、所有权和线程假设，并覆盖空指针、
边界长度、重复释放、并发误用和 panic 测试。禁止让 native pointer 或 runtime handle
越过所属 crate 的安全 wrapper。

核心优先纯 Rust、跨平台、可关闭 default features 的依赖。大型依赖、系统库、C/C++
编译、动态加载或许可证敏感依赖必须有 ADR。release 构建和运行时不访问网络；规则
在发布前同步、验证并打包。

runtime features 在选型后采用 compile-time mutually exclusive 检查，避免无意把
两个引擎都链接进产物。MSRV、锁文件、许可证清单、供应链审计和 target matrix 是
发布门禁。

## 17. 测试 seam

架构应允许以下测试替身，而不在 system test 中绕开真实兼容逻辑：

- in-memory/short-read/failing `ByteSource`；
- synthetic `FormatProbe` 和 parser；
- recording/failing/budgeted `RuleRuntime`；
- deterministic monotonic clock、cancel token 和 budget；
- synthetic nested extractor 与有序 scheduler。

测试分层：

- core：checked arithmetic、arena、预算和取消的单元/property test；
- formats：fixture、malformed corpus、parser fuzz 和资源上限；
- rules：固定上游规则的语法/host API/runtime conformance；
- engine：多阶段、嵌套、partial failure、顺序和并发集成测试；
- output：canonical JSON golden 和稳定性测试；
- CLI/FFI：端到端、链接、生命周期、panic 和语言调用测试；
- differential：固定 upstream executable、原始输出、规范化输出和差异分类。

oracle、corpus generator 和 benchmark 属于 `tools/` 或 `xtask`，不能成为生产依赖。

## 18. 数据与发布布局

发布产物中的规则 bundle 包含未经改写的源字节和 machine-readable manifest。
manifest 至少记录组件、上游路径、commit、SHA-256、同步时间和许可证来源。加载时
验证清单，不因缓存存在而跳过源版本检查。

运行时默认不写安装目录。可选 cache、profiling 和 debug 输出必须由调用方提供路径
或 writer，并且失败不会更改 detection 语义。测试样本遵守哈希清单、生成器或隔离
语料库策略。

## 19. 演进边界

以下变化可在保持依赖方向时内部演进：

- 将单个格式模块拆成独立 crate；
- 更换 `ByteSource` backend 或规则 runtime backend；
- 为结果添加内部字段或新的 output renderer；
- 在 engine 内引入确定性的有界并行。

以下变化需要 ADR 和兼容测试：

- 反转或跨越本文件禁止的依赖边；
- 选择 rule runtime 或新增 native/system dependency；
- 修改 canonical result ordering、错误分层或嵌套预算语义；
- 放宽 scanner 线程承诺；
- 添加动态 plugin ABI、callback allocator 或公开 typed C result graph。

## 20. Phase 映射

- Phase 0：验证 ports、runtime、静态链接、预算 queue 和差分 harness，完成设计评审。
- Phase 1：建立 core/formats/engine 的最小安全格式纵切片，不引入规则近似实现。
- Phase 2：接入已选 runtime，覆盖固定上游规则和 host API。
- Phase 3：补齐嵌套、archive、特殊模式及完整差分矩阵。
- Phase 4：冻结 CLI、C ABI、static library 和语言集成。
- 未来：GUI 作为 adapter，不改变核心依赖方向。

具体里程碑和门禁以 [`ROADMAP.md`](../../ROADMAP.md) 为准。

## 21. 风险与开放门禁

- 规则 runtime 尚未选型；两个 spike 均暴露完整规则兼容风险。
- 上游宿主 API 的精确生命周期和 side effects 尚需扩大 instrumentation。
- archive/decompression backend 可能引入 native 依赖和 zip-bomb 风险。
- 结果 model 的字段、排序和 partial success 仍需 `api.md` 与 baseline 共同冻结。
- 显式 queue 的并行策略和预算默认值尚需 corpus/benchmark spike。
- static linking 的完整平台系统库清单仍需 CI target matrix 验证。
- 上游许可证、规则许可证及第三方 runtime 组合必须在选型前完成复核。

这些门禁未关闭前，文档状态保持 Draft。

## 22. 架构验收条件

- workspace 建立后能由机器验证依赖 DAG 和禁止边，无循环依赖。
- checked input 对溢出、截断、极大长度和 allocation cap 有 property/fuzz coverage。
- 最小纵切片证明 CLI 与 FFI 调用同一 engine/result/output 路径。
- nested queue spike 证明深度、累计解压、节点数、取消和确定性 merge 均可控。
- rule runtime ADR 通过固定规则、host API、中断、许可证和 static-link 门禁。
- canonical result、错误和 partial semantics 在 `api.md` 中冻结并有 golden test。
- `testing.md` 定义差分、fuzz、性能、跨平台和发布矩阵。
- 设计评审明确接受 ADR 0002，Phase 0 退出条件全部满足。
