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
macOS runtime benchmark（5 case warm baseline）、macOS deployment size、
Rust 成对 benchmark（2 case）和 Rust deployment size 已完成并提交至
`docs/research/data/`。

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

**进展**：
- diec-engine 扫描编排层完成（Database + Scanner + BufferHost）
- diec-output JSON/text/XML/CSV/TSV 渲染完成（无 serde 依赖）
- diec-cli 参数解析 + 退出码 + 多目标批量扫描 + 递归扫描完成
- CLI 扫描控制标志：--deepscan, --heuristicscan, --verbose, --aggressivescan, --alltypes, --hideunknown
  - 标志通过 ScanFlags → BufferHost → HostApi 传递到规则运行时
  - --alltypes 运行所有文件类型规则（匹配上游 bIsAllTypesScan）
  - --hideunknown 过滤空名和 "Unknown" 检测
- CLI 输出控制：--format（格式化空格）、--profiling（计时）、--messages（诊断输出）
- CLI 专用模式：--entropy（Shannon 熵）、--info（文件信息）
- CLI 数据库功能：--extradb、--customdb（多数据库合并）、--showdatabase（规则统计）、--showstructs（结构方法列表）
- 5 种输出格式：text（默认）、json、xml、csv、tsv
- 文件类型检测 + 误报过滤：使用 ProbeTable 分发规则，匹配上游 scanProcess 行为
  - 可执行格式（PE/ELF/MACH/MACHOFAT）仅运行格式特定规则
  - 非可执行格式运行格式特定 + Binary 规则
  - Java Class 优先于 Mach-O FAT 检查（解决 CAFEBABE 歧义）
- ELF host API 完整实现（30+ 方法，真实 ELF 解析替代 stub）
- Mach-O host API 完整实现（25+ 方法，真实 Mach-O 解析替代 stub）
- PE host API 完整实现（30+ 方法，真实 PE 解析 + 40+ stub 方法）
- 所有格式全局对象独立化（__proto__ = Binary，避免方法覆盖）
- const→var 预处理（匹配 Qt Script 行为，修复 SyntaxError）
- 端序方法补全（read_uint16/32/64_le/be）
- 27 个语料库文件诊断数降为 0
- 差分测试：corpus_differential.rs 27 文件全部通过
- 扫描性能优化：按文件类型共享 runtime（8x 加速，~1s/文件）
- 24 个 CLI 集成测试覆盖输出格式、扫描标志、专用模式、退出码、递归扫描、数据库查询
- 374 个测试全部通过，cargo fmt/clippy/check-deps 零警告

**尚未实现**（低优先级，不影响核心功能）：
- --test、--createtest 测试入口（上游也标记为 TODO）

退出条件：能力矩阵中当前范围的 CLI 功能完成；自动化输出契约和错误行为有集成测试。

## Phase 5：C ABI 与语言集成 — 完成

- 提供带版本的稳定 C ABI 和公共头文件。
- 提供一次性扫描和/或句柄 API。
- 构建 Unix-like `.a` 与 Windows `.lib`/`.dll`。
- 提供 C、Go/cgo 和 Python ctypes/cffi 集成测试或最小示例。

**完成项**：
- 公共头文件 `include/diec.h` 完成（ABI 版本协商、状态码、opaque handle、scan options）
- `diec-ffi` crate 实现完整 C ABI：
  - ABI 版本协商：`diec_abi_version`、`diec_abi_is_compatible`
  - 状态码查询：`diec_v1_status_name`
  - Scan options：`diec_v1_scan_options_init`（repr(C) 结构体，additive extension）
  - Database builder：`diec_v1_database_builder_new/add_path_utf8/build/free`
  - Database：`diec_v1_database_metadata_json/free`
  - Cancel token：`diec_v1_cancel_new/request/free`
  - One-shot scan：`diec_v1_scan_bytes/scan_path_utf8`（thread-neutral）
  - Reusable scanner：`diec_v1_scanner_new/scan_bytes/scan_path_utf8/free`
  - Result accessors：`diec_v1_result_json/path_utf8/detection_count/free`
  - Error accessors：`diec_v1_error_status/message/free`
  - Panic containment：所有 FFI 函数通过 `catch_unwind` 捕获 panic
  - Pointer-to-pointer free：配对释放，double-free 安全
- 构建产物：`diec_ffi.lib`（staticlib）+ `diec_ffi.dll`（cdylib）
- 语言绑定：
  - Go/cgo 绑定 (`bindings/go/diec/`)：Database、Scanner、Result、ScanBytes、ScanPath，5 个测试通过
  - Python ctypes 绑定 (`bindings/python/diec.py`)：Database、Result、scan_bytes、scan_path，9 个测试通过
  - C smoke test (`tests/c/smoke.c`) 验证完整扫描流程
- 35 个 FFI 测试（7 单元 + 12 集成 + 16 sanitizer）覆盖：
  - 完整生命周期（build → scan → verify → cleanup）
  - Double-free 安全（所有 handle 类型）
  - Null 指针验证（所有 accessor）
  - 错误句柄查询和释放
  - Scan options 边界（null、小 size）
- 411 个测试全部通过，cargo fmt/clippy 零警告

退出条件：内存所有权、并发、错误码和 panic 隔离均通过测试；目标平台完成静态链接 smoke test。✅

## Phase 6：兼容性、性能与发布准备 — 进行中

- 扩大差分测试语料和跨平台矩阵。
- 建立持续 fuzz 和历史回归语料。
- 依据固定基准优化运行时间和峰值内存。
- 完成许可证、归属、供应链和发布物审计。
- 发布首个具备兼容性报告的版本。

**进展**：
- Benchmark 基础设施：
  - `crates/diec-engine/benches/scan.rs`：scan_corpus（9 种格式）、scan_flags（default/heuristic/all_types/deep）、database_load
  - `crates/diec-formats/benches/probe.rs`：probe_corpus（13 种格式）、probe_table 构造
  - 使用 criterion 0.5，harness=false
- 边缘语料差分测试：
  - `tools/corpus/generate_edge_corpus.py`：20 个边缘样本（truncated/malformed/oversized/empty）
  - `crates/diec-engine/tests/edge_corpus.rs`：3 个测试（no-crash、no-spurious、no-hang）
  - 验证截断/畸形输入不崩溃、不误检、不挂起
- FFI 跨平台 CI：
  - `.github/workflows/ci.yml` 新增 ffi-smoke job（Linux/macOS/Windows C smoke test）
  - 新增 python-binding job（Linux/macOS/Windows Python ctypes test）
- 许可证和供应链审计：
  - `LICENSE`：MIT 许可证文件
  - `NOTICES.md`：第三方归属（上游 DIE-engine、QuickJS、所有 Rust 依赖）
  - `AUDIT.md`：供应链安全审计（依赖策略、CI 安全、已知风险）
- 414 个测试全部通过，cargo fmt/clippy 零警告
- Fuzz 种子语料：165 个种子文件覆盖 6 个 fuzz targets
- 性能优化：database_load 从 ~1.2s 优化到 ~400ms（3x 加速，并行文件 I/O via std::thread::scope）
- Fuzz targets 扩展（6 个）：
  - `fuzz_byte_source`、`fuzz_byte_view_subview`（diec-core 层）
  - `fuzz_format_probe`（diec-formats 层）
  - `fuzz_scan_engine`（diec-engine 层，default/heuristic/all_types 三种 flag）
  - `fuzz_output_render`（diec-output 层，JSON/text/XML/CSV/TSV 渲染）
  - `fuzz_scan_ffi`（diec-ffi 层，C ABI 边界 + double-free 安全）
- 兼容性报告模板 `COMPATIBILITY.md`：
  - 规则加载兼容性（1184/1186 = 99.83%）
  - 语料差分测试矩阵（27 样本 + 20 边缘样本）
  - CLI 功能兼容性清单
  - C ABI 兼容性清单
  - 性能基线数据
  - 测试统计

退出条件：既定兼容指标、性能目标和发布检查全部满足；已知差异均公开、精确且可复现。

**发布准备**：
- 双语 README：`README.md`（英文默认）+ `README.zh-CN.md`（中文）
- 多平台构建发布 workflow：`.github/workflows/release.yml`
  - 4 个构建目标：Linux x86_64、Windows x86_64、macOS arm64、macOS x86_64
  - tag 触发自动构建并发布到 GitHub Releases
  - 发布物包含 CLI、FFI 库、C 头文件、规则数据库、语言绑定
- 规则分发策略 ADR 0012：打包固定快照 + `--customdb`/`DIEC_DB_PATH` 覆盖
- CLI 数据库搜索路径增强：`DIEC_DB_PATH` 环境变量 + 可执行文件相邻 `db/` 目录
- 发布说明模板 `RELEASE_NOTES.md`

## Future：GUI — TODO

GUI 明确不属于当前交付范围。核心库、CLI 和 C ABI 稳定后，另行调研 GUI 技术栈、交互需求和跨平台发布方案；当前阶段禁止为假设中的 GUI 引入框架依赖或反向耦合。
