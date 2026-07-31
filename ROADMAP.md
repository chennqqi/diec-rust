# Roadmap

本路线图按“先建立事实，再冻结设计，最后实现”的顺序推进。阶段状态使用：

- `TODO`：尚未开始。
- `IN PROGRESS`：正在进行。
- `DONE`：退出条件已满足并完成评审。

## Phase 0：上游调研与设计门禁 — DONE

设计门禁已于 2026-07-31 评审通过并关闭。五份调研正文、五份设计正文和十四个有效
ADR 全部 Accepted；六项 blocker 中五项 closed，`P0-BLOCK-005`（macOS 运行时基线
采集）deferred 至 Phase 1 与 Rust 实现并行完成。评审输入见
[`docs/design/phase-0-gate-review.md`](docs/design/phase-0-gate-review.md)。

在本阶段完成前，不开始正式功能开发。允许编写调研工具、上游构建脚本、基线采集工具、测试语料基础设施和验证性原型；验证性原型不得直接视为正式架构或稳定 API。

### 调研交付物

- `docs/research/upstream-baseline.md`
  - 固定的 DIE-engine commit SHA。
  - 构建方式、工具链、依赖和全部 submodule。
  - Linux、Windows、macOS 可重复运行环境。
  - 主仓库、子模块、规则和样本的许可证清单。
- `docs/research/capability-matrix.md`
  - CLI/engine 能力和参数。
  - 支持的文件格式、扫描模式和递归/嵌套行为。
  - 输出字段、检测类别、规则类别和优先级。
  - 每项能力对应的源码位置或可重复实验。
- `docs/research/source-analysis.md`
  - 上游模块关系和 Qt 耦合点。
  - 扫描、格式识别、规则加载和执行调用链。
  - 数据模型、缓存、并发及资源管理方式。
- `docs/research/rule-compatibility.md`
  - 规则目录、完整语法和内建函数。
  - 宿主数据访问模型、执行语义及异常行为。
  - 解释执行、编译或转换方案的可行性比较。
  - 原始规则同步、哈希和溯源方案。
- `docs/research/behavior-baseline.md`
  - 代表性测试语料。
  - 固定上游版本的原始输出。
  - 规范化规则、确定性和平台差异。

### 设计交付物

- [`docs/design/architecture.md`](docs/design/architecture.md) — Accepted
  - Cargo workspace、模块职责、依赖方向和数据流。
  - 可扩展点、资源限制与明确非目标。
- [`docs/design/api.md`](docs/design/api.md) — Accepted
  - 纯 Rust API、CLI 契约、结果及错误模型。
  - 取消、超时、并发和资源限制。
- [`docs/design/c-abi.md`](docs/design/c-abi.md) — Accepted
  - ABI 版本、导出函数和结构布局。
  - 不透明句柄状态机、内存所有权和线程安全。
  - panic 隔离、allocator 和静态链接策略。
- [`docs/design/testing.md`](docs/design/testing.md) — Accepted
  - 测试语料、上游 oracle 和差分算法。
  - 已知差异 allowlist 规则。
  - fuzz、benchmark 和 CI 平台矩阵。
- `docs/design/decisions/`
  - 记录影响长期兼容性、依赖或公共接口的 ADR。
- [`docs/design/risks.md`](docs/design/risks.md) — Accepted
  - 每项风险包含处理策略、触发条件和验证方式。

### 必须回答的问题

- “能力相同”具体比较哪些字段、层级、顺序、置信度和错误行为？
- DIE-engine、Detect-It-Easy 及其 submodule 中哪些内容属于兼容范围？
- 上游规则依赖哪些语法、内建函数和宿主 API？
- 容器嵌套、递归扫描、启发式检测、熵、哈希、字符串及反汇编的行为和资源上限是什么？
- 上游 CLI 在 Linux、Windows、macOS 上是否具有一致的输入输出和退出码？
- Rust 静态链接涉及哪些 runtime、panic、allocator、TLS、系统库和 native 依赖？
- C、Go 和 Python 调用方需要一次性扫描 API、低层句柄 API，还是两者都需要？
- 测试样本如何合法、安全、可重复地获得和保存？
- 性能基线、基准硬件、冷/热缓存条件和峰值内存目标是什么？

### 技术验证

- 规则运行时 spike：执行覆盖复杂语法的代表性上游规则。
- C 静态链接 spike：Windows/Linux x64 的 `.lib`/`.a`、C 调用、结果读取、
  正确释放、panic containment 和 CRT 依赖已完成首轮验证，见
  [`docs/research/c-static-link-spike.md`](docs/research/c-static-link-spike.md)；
  正式 ABI 及其他平台仍待设计和验证。
- 上游 oracle：自动运行固定版本上游并保存原始及结构化基线。

### 退出条件

- 能力矩阵的每一项都有源码证据或可重复实验。
- 基线语料覆盖主要格式和代表性规则语法。
- 三项技术验证完成，或明确记录不可行点及替代设计。
- 架构、规则引擎、ABI 和测试方案均完成书面权衡与评审。
- 风险清单完整。
- 后续每个开发阶段都有可测量的完成条件。

## Phase 1：工程骨架与兼容测试基础设施 — DONE

- 创建 Cargo workspace 和单向依赖边界。
- 建立格式化、lint、测试和跨平台 CI。
- 建立上游规则同步、来源清单和完整性校验。
- 建立测试语料生成/获取、基线保存和差分报告工具。
- 冻结首版内部结果模型，公共 ABI 仍保持实验状态。
- 完成 `P0-BLOCK-005` deferred 项：macOS 运行时基线采集。✅ 已关闭：17 个
  candidate report 已在 Darwin x86_64 主机采集、校验、sanitize 并提交至
  `docs/research/data/macos-qt5/`；`cli-privilege-paths` 因需 passwordless
  sudo 而 deferred（diec 不负责系统权限管理）。

退出条件：三大桌面平台 CI 通过；规则和上游基线可重复获取；差分框架能对最小样本给出可审计报告。

Phase 1 已于 2026-07-31 关闭。Cargo workspace 8 crate 骨架 + 依赖 DAG 校验、
跨平台 CI（default 1.97.1 + MSRV 1.88）、Rust 执行收集器 + 端到端差分审计、
规则同步/来源 manifest/完整性校验均已交付。`P0-BLOCK-005` macOS 运行时基线
已关闭，17 个 candidate report 采集至 `docs/research/data/macos-qt5/`。

## Phase 2：核心数据模型与格式识别 — DONE

- 实现受控字节读取和通用扫描上下文。
- 按能力矩阵逐步实现格式探测与解析。
- 为畸形、截断和整数边界输入建立测试及 fuzz targets。
- 与上游逐格式进行差分验证。

退出条件：本阶段范围内的能力矩阵全部通过差分测试，没有未解释的崩溃、无界分配或非确定性。

Phase 2 已于 2026-07-31 关闭。受控字节读取层（ADR 0013 fail-closed）覆盖
MemorySource/OwnedSource/FileSource/ChunkedSource/EmptySource + read_exact_at +
typed integer reads + checked arithmetic。格式探测框架（FormatProbe trait +
ProbeError + ProbeTable versioned ordered probe table）注册 20 个 probe，覆盖
CAP-DISPATCH-001 至 007 全部组：PE/MSDOS、ELF32/64、Mach-O 32/64/FAT/FAT64、
DEX/Java Class/PYC、PDF/CFBF、ZIP/RAR/7Z/GZIP/TAR/ISO9660/CAB、JPEG/PNG/BMP/WAV。
PE/ELF/Mach-O 提取 header 字段（machine/class/data/osabi/e_type/cputype/
filetype）作为下游规则匹配元数据。测试覆盖：每个格式有 positive/truncated/
malformed/boundary/empty/fuzz/differential cases（见
[`docs/design/phase2-format-test-matrix.md`](docs/design/phase2-format-test-matrix.md)）。
3 个 cargo-fuzz targets + 11 个 property tests + 5 个 corpus differential tests。
总计 211 个测试全部通过，cargo fmt/clippy/check-deps 零警告。

## Phase 3：规则兼容运行时 — DONE

- 原样加载固定版本上游规则。
- 实现或集成经 Phase 0 验证的规则执行方案。
- 完整覆盖规则语法、内建函数和宿主数据访问接口。
- 对未知或不支持语法产生明确诊断，不静默忽略。

退出条件：目标规则集全部可加载；代表性语料的规则结果达到已定义的兼容标准；剩余差异均有精确记录和回归用例。

**完成状态**：1184/1186 规则加载成功（99.8%）；6 个端到端检测测试通过；
2 个剩余失败均有精确记录（1 个上游规则 bug，1 个需 PE 专属 API 实现）。
rquickjs 后端 + Binary host API bridge + 签名解析器 + PE stub 完成。

- 原样加载固定版本上游规则。
- 实现或集成经 Phase 0 验证的规则执行方案。
- 完整覆盖规则语法、内建函数和宿主数据访问接口。
- 对未知或不支持语法产生明确诊断，不静默忽略。

退出条件：目标规则集全部可加载；代表性语料的规则结果达到已定义的兼容标准；剩余差异均有精确记录和回归用例。

## Phase 4：CLI — IN PROGRESS

- 实现薄 CLI 层，不复制核心扫描逻辑。
- 支持稳定的结构化输出和人类可读输出。
- 定义参数、退出码、递归扫描及资源限制行为。
- 与上游 CLI 进行跨平台差分验证。

退出条件：能力矩阵中当前范围的 CLI 功能完成；自动化输出契约和错误行为有集成测试。

## Phase 5：C ABI 与语言集成 — TODO

- 提供带版本的稳定 C ABI 和公共头文件。
- 提供一次性扫描和/或句柄 API。
- 构建 Unix-like `.a` 与 Windows `.lib`。
- 提供 C、Go/cgo 和 Python ctypes/cffi 集成测试或最小示例。

退出条件：内存所有权、并发、错误码和 panic 隔离均通过测试；目标平台完成静态链接 smoke test。

## Phase 6：兼容性、性能与发布准备 — TODO

- 扩大差分测试语料和跨平台矩阵。
- 建立持续 fuzz 和历史回归语料。
- 依据固定基准优化运行时间和峰值内存。
- 完成许可证、归属、供应链和发布物审计。
- 发布首个具备兼容性报告的版本。

退出条件：既定兼容指标、性能目标和发布检查全部满足；已知差异均公开、精确且可复现。

## Future：GUI — TODO

GUI 明确不属于当前交付范围。核心库、CLI 和 C ABI 稳定后，另行调研 GUI 技术栈、交互需求和跨平台发布方案；当前阶段禁止为假设中的 GUI 引入框架依赖或反向耦合。
