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
