# 需求记录

## 2026-07-30: 接棒继续 diec-rust 项目
- 项目目标：用 Rust 重写 DIE-engine，方法为"先建立事实，再冻结设计，最后实现"
- 事实验证最关键：需验证 1:1 兼容 DIE 引擎
- Codex 已完成初始化和部分工作，需接棒继续推进 Phase 0

## 2026-07-30: 并行推进 Phase 0 阻塞项
- 并行推进 P0-BLOCK-004(许可证)、P0-BLOCK-002/003(设计/ADR)、P0-BLOCK-006(性能) 评审准备
- macOS 基线 (P0-BLOCK-005) 留待 Darwin 主机执行

## 2026-07-30: P0-BLOCK-004 许可证范围修正
- Rust 从零重写，不复制/翻译/链接上游 C++ 源码，上游 GPL/UnRAR 等许可证不传染 Rust 二进制
- 引擎与规则分离：diec-rust 是引擎，不包含 db* 规则（用户自行获取），不实现 YARA/PEiD/signatures（GUI 专属）
- P0-BLOCK-004 剩余项仅为 Phase 1 常规工作：cargo deny/about 许可证清单 + NOTICE 文件
- 更新 phase-0-review-preparation.md、phase-0-gate-review.md、phase-0-gate-review.json

## 2026-07-30: YARA/PEiD/signatures 深入调查与未来 GUI 准备
- YARA：XYara 是独立 YARA 扫描线程类，与 DiE_Script 并行的检测通道，GUI 默认 WITH_YARA=ON
- PEiD：XPEID 继承 XScanEngine，PEiD userdb.txt 解析器，识别 PE packer/compiler
- signatures：SearchSignatures GUI widget，使用 crypto.db/junks.db
- 三者均不进入 diec CLI（源码/CMake/link 证据），但未来 GUI 需要集成
- 已在 phase-0-review-preparation.md 记录未来 GUI 准备信息

## 2026-07-30: P0-BLOCK-005 macOS Qt5 oracle candidate 构建成功
- 环境: macOS 12.7.6 Monterey, x86_64, Apple clang 14.0.0, Qt 5.15.2 (aqtinstall), CMake 3.27.7
- 产物: diec Mach-O x86_64, 7452296 bytes, version "die 4.0.0", SHA-256 f4c69824...
- 构建修复: Formats/xbinary.h 第 114 行 #include <CoreFoundation/CoreFoundation.h> 在 macOS 上导致编译失败
  - 原因: xdeflatedecoder.cpp 是 10581 行拼接文件，第 9482 行 include xbinary.h 时有 9 个未闭合大括号
  - CoreFoundation.h 的 CF_EXPORT (extern) typedef 在函数作用域内无效
  - xbinary.h 未使用任何 CoreFoundation 类型，include 标记为 "// Check"
  - Linux/Windows 不受影响（Q_OS_MAC 未定义）
- candidate report: ~/dev/tmp/diec-macos-work/diec-macos-candidate.json
- 下一步: 需要评审 source patch 并执行 runtime oracle 采集（68 行 capability baseline）

## 2026-07-30: P0-BLOCK-002/003 设计文档与 ADR 评审
- 评审对象: architecture / api / c-abi / testing / risks 5 份设计文档 + 14 Proposed ADR
- 机器校验: design/ADR review readiness、5 份 contract test、phase-0-review-preparation 全部通过
- 评审结论: 5 份设计文档结构完整、已进入 In Review，但 blocking items 未关闭，acceptance_ready=false；14 个 ADR 均为 Proposed，review_ready=true，acceptance conditions 尚未满足
- 处置: P0-BLOCK-002/003 仍为 Open；本次完成"输入完整 + 结构审查"，不提前改为 Accepted
- 关闭条件: 需 P0-BLOCK-004/005/006 关闭后，在 Phase 1 实现中逐项满足 acceptance conditions 并重新验证

## 2026-07-31: P0-BLOCK-002/003 关闭 — 设计文档与 ADR Accepted
- 5 份设计文档 (architecture/api/c-abi/testing/risks) 状态改为 Accepted
- 14 个 ADR 状态改为 Accepted，每个 ADR 拆分 Decision acceptance (Phase 0 方向批准) 与 Implementation exit (Phase 1+ 实现期门禁)
- 更新 JSON manifests: adr-review-readiness / design-review-readiness / phase-0-gate-review
- 更新测试: test_adr_review_readiness / test_design_review_readiness / test_phase0_gate_review
- 更新评审文档: adr-review-readiness.md / design-review-readiness.md / phase-0-gate-review.md
- ROADMAP.md 设计交付物状态更新为 Accepted
- 13 个测试全部通过

## 2026-07-31: Phase 0 关闭，启动 Phase 1
- 用户确认 Phase 0 除 macOS 性能基线 defer 外全部完成，授权开始 Phase 1
- ROADMAP.md: Phase 0 -> DONE，Phase 1 -> IN PROGRESS；macOS 基线作为 Phase 1 deferred 项
- AGENTS.md/README.md 当前阶段更新为 Phase 1
- 本次会话范围：Cargo workspace 骨架 + 冻结 diec-core 首版内部结果模型（公共 ABI 仍实验状态）
- 创建 8 个 crate：diec-core/formats/rules/engine/output/cli/ffi + xtask
- diec-core 冻结结果模型：ByteSource/ByteView/ScanSource/ScanRequest/ScanLimits/ScriptLimits/DatabaseLimits/TraversalLimits/CancellationToken/ScanReport/ScanNode/Detection/Diagnostic/ScanError 等
- xtask check-deps 实现依赖 DAG 边界校验（architecture.md section 6）
- cargo fmt/clippy(-- -D warnings)/test --all-features 全部通过，check-deps 报告 DAG OK

## 2026-07-31: 跨平台 CI + MSRV 修正
- 修正 workspace rust-version 从 1.97.1 改为 1.88（ADR 0011 要求 MSRV 1.88，默认工具链仍由 rust-toolchain.toml 固定 1.97.1）
- 创建 .github/workflows/ci.yml：default 1.97.1 job（fmt/clippy/test/release build/check-deps）+ MSRV 1.88 job（build/test/clippy），均覆盖 ubuntu-24.04/windows-2022/macos-14
- CI 遵循现有 workflow 安全风格：pinned action SHA、permissions: contents: read、concurrency cancel-in-progress、--locked
- 本地验证：1.97.1 全套 + 1.88.0 build/test/clippy 全部通过

## 2026-07-31: 差分测试基础设施（Rust producer 适配器 + 端到端审计）
- 创建 tools/compat/collect_rust_execution.py：运行 diec CLI，捕获 stdout/stderr/exit/timing，产出 raw-execution-v1 格式记录和 content-addressed artifacts
- 创建 tools/tests/test_end_to_end_differential.py：验证收集→验证→审计报告全流程（3 测试）
- 全部 126 Python 差分工具测试通过（原 123 + 新 3），cargo fmt/clippy/test/check-deps 全部通过

## 2026-07-31: 上游规则同步、来源清单、完整性校验
- 创建 xtask sync-rules 子命令：扫描 upstream/Detect-It-Easy 的 5 个规则树（db/db_extra/db_custom/dbs_min/dbs_special），生成 rule-source-manifest.json（schema=1，记录 repository/commit/component/synced_at + 每文件 relative_path/size/sha256）
- 创建 xtask verify-rules 子命令：校验规则文件 size + SHA-256 与 manifest 一致
- 在 diec-rules crate 定义 RuleSourceManifest/RuleTreeEntry/RuleFileEntry 类型骨架（MANIFEST_SCHEMA_VERSION=1）
- 实际运行：sync-rules 生成 manifest（4539 文件，4453445 bytes），verify-rules 全部通过
- cargo fmt/clippy/test/check-deps 全部通过

## 2026-07-31: Phase 2 启动 — 受控字节读取层
- 用户确认 P0-BLOCK-005 已由其他 Agent 完成，授权开始 Phase 2
- ROADMAP.md: Phase 1 -> DONE，Phase 2 -> IN PROGRESS；AGENTS.md/README.md 同步更新
- 实现 diec-core 受控字节读取层（ADR 0013 fail-closed）：
  - IoError 扩展：ShortRead{offset,expected,actual}/NotSeekable/InvalidArgument
  - ByteSource trait 添加 read_exact_at（正进展分块循环，零进展或 EOF 立即 ShortRead）
  - 5 个 ByteSource 实现：MemorySource（借用 slice）/OwnedSource（Arc<[u8]>）/FileSource（seek+read）/ChunkedSource（测试分块设备）/EmptySource（测试空源）
  - ByteView 添加 read_exact_at + typed integer reads（u8/u16_le/u16_be/u32_le/u32_be/u64_le/u64_be），view 边界裁剪确保不越过 [start,end)
  - 35 个新增单元测试：ByteRange 溢出、MemorySource full/partial/EOF/empty、read_exact_at short read/overflow、ChunkedSource 分块循环、OwnedSource clone 共享、ByteView subview/boundary/typed reads、FileSource open/read
- cargo fmt/clippy/test/check-deps 全部通过（37 diec-core 测试）

## P0-BLOCK-006 macOS 运行时基线采集 (deferred from Phase 0)
- 通过 ssh macdevoa (macdev 别名) 继续完成 macOS 运行时基线采集
- 复用 ~/dev/tmp/diec-macos-work 目录中已有数据 (DIE-engine-src/build/corpus/evidence 等)

## 2026-07-31: P0-BLOCK-005 macOS 运行时基线采集完成
- 通过 ssh macdevoa 在 Darwin x86_64 主机完成 17 个 candidate report 采集
- 修复 build_macos_database_cache_harness.py: macOS qmake Makefile 使用 TARGET 而非 DESTDIR_TARGET；添加 xbinary.h CoreFoundation.h patch
- 修复 collect_macos_database_cache_harness.py: macOS QStandardPaths test mode 不尊重 HOME，使用 NSSearchPathForDirectoriesInDomains；放宽 qttest marker 检查
- cli-privilege-paths collector 因需 passwordless sudo 而 deferred（diec 不负责系统权限管理）
- 所有 candidate report 已 sanitize 本地路径并提交至 docs/research/data/macos-qt5/
