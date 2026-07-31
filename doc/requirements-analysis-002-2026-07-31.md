# 需求分析摘要 002 — 2026-07-31

## Phase 0 关闭与 Phase 1 启动

### 状态转换决策
- phase-0-gate-review.md 原写 ready_for_review，要求 ROADMAP 保持 IN PROGRESS 直到最终评审
- 用户明确授权开始 Phase 1，选择"Phase 0 标记 DONE"方案
- 处置：ROADMAP Phase 0 -> DONE，Phase 1 -> IN PROGRESS；macOS 基线 (P0-BLOCK-005) 作为 Phase 1 deferred 项保留；AGENTS/README 当前阶段同步更新

### 本次会话范围决策
- 用户选择"骨架 + 结果模型"：Cargo workspace 骨架 + 冻结 diec-core 首版内部结果模型
- CI（三大桌面平台 GitHub Actions）不在本次范围，属后续 Phase 1 交付物

### Workspace 骨架
- 8 crate 按 architecture.md section 5 落位：diec-core(无依赖)/formats(+core)/rules(+core)/engine(+core+formats+rules)/output(+core)/cli(+engine+output)/ffi(+engine+output, staticlib+rlib)/xtask(工具, 不在 runtime graph)
- 根 Cargo.toml 用 workspace.dependencies 集中内部版本；edition 2024, rust-version 1.97.1 (ADR 0011)
- 所有 crate #![forbid(unsafe_code)]，core/output/formats/rules/engine/ffi 加 #![warn(missing_docs)]

### 结果模型冻结 (diec-core)
- 按 api.md 落位类型骨架：input.rs(ByteSource+Debug bound/ByteView/ScanSource/ByteRange/IoError)、limits.rs(ScanLimits/ScriptLimits/DatabaseLimits/TraversalLimits/LimitKind/LimitReached，skeleton_default 用 ADR 0012 候选值并标注未 admit)、cancel.rs(Arc<AtomicBool> 共享取消)、request.rs、format.rs(FileType/FormatCandidate/FilePart)、node.rs(ScanNode/Detection/Provenance/RuleIdentity)、diagnostic.rs、report.rs(ScanReport/Completion/SchemaVersion SKELETON 0.1)、error.rs(ScanError 9 变体 + IoError From)
- 公共字段为设计骨架，构造器/不变量随实现补齐；公共 ABI 仍实验状态

### 依赖 DAG 校验
- xtask check-deps：cargo metadata --no-deps -> 解析 workspace 内 diec-*/xtask 依赖 -> 对照 allowed_deps() 检查禁止边
- 校验通过：check-deps: workspace dependency DAG OK

### 验证
- cargo fmt --check / clippy --workspace --all-targets --all-features -- -D warnings / test --workspace --all-features 全部通过
- 8 个单元测试通过（cancel 2 + formats/rules/engine/output/ffi 各 1 + cli/xtask 0）

### 后续 Phase 1 待办
- 跨平台 CI（fmt/clippy/test/build，三桌面平台）
- 上游规则同步、来源清单、完整性校验
- 测试语料生成/获取、基线保存、差分报告工具
- macOS 运行时基线采集 (P0-BLOCK-005 deferred)
