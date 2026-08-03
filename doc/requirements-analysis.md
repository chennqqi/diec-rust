# 需求分析摘要

## 2026-07-30: 接棒继续 diec-rust 项目

### 现状评估
- 项目处于 Roadmap Phase 0 (IN PROGRESS)
- 上游基线已固定: DIE-engine@74eaf505, Detect-It-Easy@c2c17df
- 58 个 submodule SHA 已锁定在 components.lock.toml
- 大量调研文档已产出 (docs/research/ 100+ 文件)
- 5 份设计文档已进入 In Review 状态
- 15 个 ADR (14 Proposed + 1 Superseded)
- 3 项技术验证已有证据: rquickjs runtime, C static link, upstream oracle

### Phase 0 阻塞项
- P0-BLOCK-001: Closed (能力矩阵)
- P0-BLOCK-002: Open (设计文档需评审结论)
- P0-BLOCK-003: Open (ADR 需接受)
- P0-BLOCK-004: Open (许可证/闭包审计未完成)
- P0-BLOCK-005: Open (macOS 基线缺失)
- P0-BLOCK-006: Open (性能基线/资源限制未冻结)

### 环境约束
- 当前环境为 Windows, 无法执行 macOS 基线采集
- macOS 基线需要 Darwin 主机执行

### 2026-07-30: 修复与评审准备

#### 修复
- 修复 global_host_api_harness_main.cpp 源码 identity 漂移（上次提交添加了新 case 但未更新 JSON 报告中的 bytes/sha256）
- 级联更新: qt5/qt6 报告 -> 合并报告 -> result-model -> closure plan -> coverage -> source-only closure
- 全部 1547 测试通过

#### 评审准备
- 创建 `docs/design/phase-0-review-preparation.md` 汇总三个阻塞项的当前证据和缺口
- P0-BLOCK-004 许可证: 14 份技术证据文档已完成，6 个剩余缺口，可提交书面评审
- P0-BLOCK-002/003 设计/ADR: 5 份设计文档 + 14 ADR 评审输入完整，需人工评审结论
- P0-BLOCK-006 性能: 上游 baseline 方法已验证，limit 候选需评审冻结，Rust 侧需实现后执行

### 2026-07-30: 研究文档状态提升与 Windows 缓存验证

#### 文档提升
- upstream-baseline.md、source-analysis.md、rule-compatibility.md 从 Draft 提升到 In Review
- 依据：核心证据完整，已知缺口（macOS）由 P0-BLOCK-005 跟踪
- capability-matrix.md 和 behavior-baseline.md 保持 Draft（gate_status=evidence_incomplete，macOS 缺失）

#### Windows 缓存环境验证
- 重新运行 probe_windows_benchmark_cache_environment.py，输出与提交报告逐字节相同
- SHA-256: bc58d9de0ee32e7aa55dd8f2bea7436ee8fdb6e2626eda83e9c41c2fc01abce7

#### 测试状态
- 全部 1554 测试通过，1 skipped，5078 subtests passed

### 2026-07-30: P0-BLOCK-004 许可证范围修正

#### 背景
用户确认：(1) 引擎与规则分离，db* 规则由用户自行获取，引擎项目不包含规则；(2) YARA/PEiD/signatures 不进入 diec CLI（源码证据）；(3)(4) NOTICE/SBOM 按 Rust 标准做法（cargo deny/about），Phase 1 常规工作。

#### 修正内容
- 引擎不包含/不分发 db* 规则、YARA/PEiD/signatures 资产
- 上游 C++ 许可证（GPL/UnRAR/Brotli/Zstandard）不传染 Rust 二进制
- P0-BLOCK-004 剩余项仅为 Phase 1 常规工作：cargo deny/about + NOTICE
- 建议将 P0-BLOCK-004 从 Open 降为 Review Ready

### 2026-07-30: YARA/PEiD/signatures 深入调查

#### 背景
用户指出需要深入调查 YARA/PEiD/signatures 的作用，且未来要实现 GUI。

#### 调查结果
- XYara：独立 YARA 扫描线程类（XThreadObject），与 DiE_Script 并行的检测通道，GUI 默认 WITH_YARA=ON
- XPEID：继承 XScanEngine，PEiD userdb.txt 解析器，识别 PE packer/compiler
- SearchSignatures：GUI widget，使用 crypto.db/junks.db
- 三者均不进入 diec CLI（main_console.cpp/CMakeLists.txt/link.txt 证据）
- XScanEngine 是独立开源仓库（MIT），不是私有代码
- 已在 phase-0-review-preparation.md 记录未来 GUI 集成准备信息

### 2026-07-30: P0-BLOCK-005 macOS Qt5 oracle candidate 构建

#### 环境
- macOS 12.7.6 Monterey, x86_64, 8 core, 16GB RAM
- Apple clang 14.0.0 (CommandLineTools only, no full Xcode)
- Qt 5.15.2 clang_64 (aqtinstall), CMake 3.27.7
- 默认 SDK 13.1 (MacOSX.sdk -> MacOSX13.1.sdk)

#### 构建结果
- diec CLI 构建成功: Mach-O x86_64, 7.45MB, version "die 4.0.0"
- 依赖: QtConcurrent, QtScript, QtCore, DiskArbitration, IOKit, libc++, libSystem

#### 构建修复
- Formats/xbinary.h 第 114 行 `#include <CoreFoundation/CoreFoundation.h>` 在 macOS 上导致编译失败
- 根因: xdeflatedecoder.cpp (10581 行拼接文件) 在函数作用域内 include xbinary.h → CoreFoundation.h
- CFMessagePort.h 的 CF_EXPORT (extern) typedef 在函数内无效
- xbinary.h 未使用任何 CoreFoundation 类型，include 标记为 "// Check"
- Linux/Windows 不受影响（Q_OS_MAC 未定义）
- bootstrap 脚本的 tracked source 检查需要修改以允许此 patch

#### 下一步
- 评审并记录 source patch 为已知 macOS 构建修复
- 修改 bootstrap 脚本支持 macOS 构建修复
- 执行 runtime oracle 采集（68 行 capability baseline）
- 需要在 macOS 上运行项目生成的安全语料和 CLI 矩阵

### 2026-07-31: P0-BLOCK-002/003 关闭分析
- 拆分策略: 每个 ADR 的 Acceptance conditions 拆为 Decision acceptance (Phase 0 方向批准) + Implementation exit (Phase 1+ 实现期门禁)
- 设计文档: 5 份均改为 Accepted，blocking_items 清空，review_disposition 记录
- JSON manifests: 3 个清单全部更新，summary 反映 accepted_count=14, acceptance_ready=true
- 测试: 3 个测试文件更新断言，从 Proposed/In Review 改为 Accepted，13 passed
- Phase 0 仍为 not_ready: P0-BLOCK-004/005/006 仍 open

## 2026-07-31: P0-BLOCK-005 关闭分析
- macOS 基线采集范围: 18 个 candidate report (workflow plan 定义)
- 已完成 17 个: oracle/cache-state/cli-baseline/cli-matrix/cli-remaining/cli-database/cli-database-archive/cli-path-nested/cli-special-path/cli-filesystem/cli-large-directory/cli-long-path/cli-toctou/special-path-fixture/long-path-fixture/database-cache-harness-build/database-cache-engine
- 缺失 1 个: cli-privilege-paths (需 passwordless sudo, deferred)
- 工具修复: build_macos_database_cache_harness.py (TARGET vs DESTDIR_TARGET, xbinary.h patch), collect_macos_database_cache_harness.py (macOS QStandardPaths behavior)
- Python 3.9 系统版本过旧, 使用 venv Python 3.14.6
- 所有 report 已 sanitize /Users/chenq 路径为 <macos-work>/<macos-home> 占位符

## 2026-07-31: 上游规则 bug 记录 — Nintendo-certified-file.1.sg const 重声明
- 文件: `db/Binary/format_bin.Nintendo-certified-file.1.sg`，上游 commit `4b675ffd`
- 第 10 行 `var tp, e;` 与第 15 行 `const tp` 在同一函数作用域重声明
- QtScript (上游 DIE 使用的 JS 引擎) 允许此行为，QuickJS/ECMAScript 规范禁止
- diec-rust 使用 QuickJS (rquickjs)，因此该规则加载失败
- 这是上游规则 bug，非 diec-rust 缺陷
- 建议修复: 第 10 行改为 `var e;`（`tp` 已在第 15 行用 `const` 正确声明）
- Bug 报告已写入 `docs/research/upstream-bug-const-redeclaration-nintendo-certified-file.md`

- [2026-08-01] macOS Phase 1 benchmark 门禁：需在 macdev 主机上运行三类 benchmark（runtime warm baseline、release deployment size、Rust 成对 benchmark），复用 Linux Qt5 现有 plan/runner 工具链并适配 macOS 路径与环境

## 2026-08-02: Host API 完善
- 分析：78 个 stub 方法，按差分收益排序
- 优先级：CFBF(+1) > JavaClass(+1) > PYC(+1) > Archive(架构) > PE验证/Resource/.NET/Manifest
- 当前差分：22/28 匹配，6 个差异全为规则版本差异
