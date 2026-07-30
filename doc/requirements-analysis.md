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
