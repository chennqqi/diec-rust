# Phase 0 评审准备材料

Status: Draft

Last updated: 2026-07-30

## 用途

本文汇总 Phase 0 三个可在 Windows 环境推进的阻塞项的当前证据状态和剩余缺口，
为设计/ADR 评审、许可证书面评审和性能基线冻结提供结构化输入。macOS 基线
(P0-BLOCK-005) 需 Darwin 主机执行，不在本文范围。

## P0-BLOCK-004: 许可证审计

### 已完成的技术证据

| 证据 | 文档 | 状态 | 关键结论 |
| --- | --- | --- | --- |
| 58 组件根许可证清单 | `component-license-inventory.md` | Draft | 58/58 根 MIT；12 个不同 SHA-256；45 nested candidate |
| XArchive 编译闭包 | `xarchive-license-closure.md` | Draft | 106 编译源/217 依赖；MIT/PD/bzip2/zlib 标记 |
| XArchive 最终链接 | `xarchive-final-link-closure.md` | — | 85 source 最终贡献；仅 LzmaDec 进入 ELF |
| XCapstone 最终 ELF | `xcapstone-license-closure.md` | In Review | 11 source/71 依赖；MIT+BSD-3+LLVM/NCSA |
| XSIMD 最终 ELF | `xsimd-license-closure.md` | — | 3 member/6 依赖；全部 horsicq MIT |
| XYara 构建闭包 | `yara-license-closure.md` | Draft | 51-obj/109-file；YARA BSD+Bison GPL+TLSH Apache/BSD；build-only |
| XUCL 来源追溯 | `xucl-origin.md` | In Review | UCL 1.03 GPL-2.0-or-later；94.76% 12-token 覆盖 |
| Runtime 规则资产 | `runtime-rule-assets-license.md` | Draft | 2,268 文件；根 MIT；1 条显式 MIT；22 PNG |
| 规则资产来源 | `rule-asset-provenance.md` | — | YARA/PEiD/signatures 逐文件审计 |
| 产品源码闭包 | `product-source-closure.md` | — | 237 compile source/14 根 LICENSE |
| Linux install tree | `linux-cmake-install-tree.md` | — | 4,916 文件；仅 1 LICENSE candidate |
| Linux release trees | `linux-release-trees.md` | — | AppImage/portable 无 LICENSE |
| 嵌入压缩来源 | `embedded-compression-origins.md` | — | Brotli v1.2.0 MIT / Zstandard BSD+GPLv2 |
| RAR decoder 来源 | `rar-decoder-provenance.md` | — | UnRAR 7.13 94.21% 覆盖；无 notice |

### 剩余缺口（按优先级）

1. **XUCL MIT/GPL 组合书面评审**：`xucldecoder.cpp` 内嵌 UCL 1.03 GPL，
   外层 MIT。需发布/法律责任人书面判定。
2. **RAR decoder notice 缺失**：UnRAR 7.13 代码未保存 RARLAB notice。
3. **Brotli/Zstandard 声明剥离**：XArchive 剥离版权声明，未保存 LICENSE。
4. **db* 规则逐路径许可**：2,235 规则仅 1 条显式 MIT；22 PNG artwork 法律确认未完成。
5. **Windows/macOS/Qt6 闭包**：当前仅覆盖 Linux Qt5 CMake Release。
6. **Rust dependency SBOM**：候选 crate graph 未开始。

### 评审输入准备状态

技术证据充分，可提交书面评审。约束：技术可行性不替代许可证结论；评审前不得复制受约束代码。

## P0-BLOCK-002/003: 设计文档与 ADR 评审

### 设计文档状态

| 文档 | 状态 | 阻止 Accepted |
| --- | --- | --- |
| Architecture | In Review | ADR 0002/0006、canonical result、limits、许可证和平台门禁 |
| API | In Review | ADR 0003、modern schema、候选准入、thread/path policy |
| C ABI | In Review | ADR 0001、runtime thread model、三平台和 Go/Python 验证 |
| Testing | In Review | ADR 0004、Windows/macOS oracle、Rust benchmark、production limit 验证 |
| Risks | In Review | 设计/ADR 评审结论及 runtime/license/platform/performance blocker |

### ADR 状态

14 个 Proposed ADR，全部 review_ready=true，全部 acceptance_ready=false。
关键未满足 acceptance 见 `adr-review-readiness.md`。

### 评审约束

- 评审可接受决策方向，但 acceptance conditions 被机器证据满足前不得改 Accepted
- 若 acceptance conditions 是实现期门禁，应先修改 ADR 拆分 Decision acceptance 与 Implementation exit
- 不能将 spike/Linux-only 证据外推为完整兼容

### 评审输入准备状态

评审输入结构完整，可提交评审。主要阻塞：需人工评审结论 + runtime/license/platform/performance blocker 关闭。

## P0-BLOCK-006: 性能基线与资源限制

### 已完成的技术证据

| 证据 | 文档 | 状态 | 关键结论 |
| --- | --- | --- | --- |
| 缓存环境边界 | `upstream-benchmark-cache-environment.md` | In Review | WSL2 容器无独立 cache domain |
| Page cache | `upstream-benchmark-page-cache.md` | In Review | per-file mincore=0 可控；非 system-cold |
| 文件内容性能 | `upstream-benchmark-file-content-performance.md` | In Review | 100 child paired；ratio 1.33-8.76x |
| Windows 缓存 | `windows-benchmark-cache-state.md` | — | warm 可复用；system-cold 需 dedicated infra |
| macOS 缓存 | `macos-benchmark-cache-state.md` | — | XNU flag + MS_INVALIDATE 候选 |
| 资源限制候选 | `resource-limit-policy.md` | — | 完整但未准入；hash-bound 机器契约 |

### 剩余缺口

1. **Production budget 冻结**：limit 候选已有机器契约，未冻结为 production 阈值。
2. **Rust 成对 benchmark**：需 Rust 实现后与上游成对测量。
3. **Dedicated system-cold**：需独立基础设施，非容器内可完成。
4. **macOS runtime benchmark**：需 Darwin 主机。
5. **Release size benchmark**：需最终发布包。

### 评审输入准备状态

上游 baseline 测量方法和缓存控制策略已充分验证。Resource limit 候选完整但需评审冻结。
Rust 侧 benchmark 需实现后执行。当前可提交 limit 候选评审和 cache 策略评审。

## 下一步建议

1. **许可证**：将本文许可证部分提交给发布/法律责任人，启动书面评审流程。
2. **设计/ADR**：组织设计文档和 ADR 评审会议，先接受决策方向，拆分 Decision acceptance 与 Implementation exit。
3. **性能**：冻结 resource limit 候选为 production 阈值（需评审），确认 cache 策略三层模型。
4. **macOS**：准备 Darwin 主机环境，执行已固定的 bootstrap 和 baseline 采集计划。
