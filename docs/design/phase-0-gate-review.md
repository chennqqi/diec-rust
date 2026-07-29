# Phase 0 设计门禁审计

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 结论

Phase 0 当前为 **not ready**，`ROADMAP.md` 必须继续保持 `IN PROGRESS`。这不是
因为调研数量不足：三项技术验证已经有可重复证据，风险清单和后续阶段门禁也已
形成。稳定 capability traceability 已在本轮闭合；其余阻塞点是现有证据还没有
闭合为可评审的 Phase 0 决策。

机器可读结论保存在
[`data/phase-0-gate-review.json`](data/phase-0-gate-review.json)。该清单只判断
Phase 0 设计门禁，不把 Phase 2—6 的实现期风险误当成当前必须关闭的功能。

## Roadmap 退出条件

| ID | 退出条件 | 当前判断 | 证据或缺口 |
| --- | --- | --- | --- |
| `P0-EXIT-001` | 能力矩阵每项有源码或可重复实验 | Ready for review | 68 个稳定 `CAP-*` 均绑定固定源码或可重复实验，并已投影到 272 个平台 cell；source-only/platform-missing 作为 EXIT-002 缺口保留 |
| `P0-EXIT-002` | 基线覆盖主要格式和代表规则语法 | Not ready | 基础安全格式样本、七类专用规则差分、CLI 专用模式临界值、七种非 JPEG/PNG Image 分派、规则 priority、取消及 device/subdevice 边界已存在；Linux Qt5/Qt6 与 Windows Qt5 的 68 项均为 runtime-observed，source-only 与 corpus-gap 均为 0，但 macOS 完整基线仍缺 |
| `P0-EXIT-003` | 三项技术验证完成或记录替代 | Ready for review | rquickjs runtime、C static link 和固定 Linux upstream oracle 均有可重复证据及边界 |
| `P0-EXIT-004` | 架构、规则 runtime、ABI、测试方案完成评审 | Not ready | 五份必需设计已进入 In Review、但未获得评审结论；十四个有效 ADR 均为 Proposed |
| `P0-EXIT-005` | 风险清单完整 | Ready for review | 20 项风险均含触发、缓解、验证和关闭条件，但文档仍需评审 |
| `P0-EXIT-006` | 后续阶段有可测完成条件 | Ready for review | `ROADMAP.md` 与 `testing.md` 已给出 Phase 1—6 的量化门禁 |
| `P0-EXIT-007` | 性能基线与资源目标得到回答 | Not ready | 固定 Linux Qt5 warm baseline、单 vCPU 三次 session、2,283-file access union、候选页 residency/fadvise 后验、runner schema v2 的五 case × 10 组 warm/file-content ABBA 配对、Linux/Windows cache-state 边界和 macOS hash-bound candidate plan、cgroup/noise 及 ELF+动态依赖+规则 size 已有证据；Rust 成对/dedicated system-cold/macOS candidate runtime/长期 session/跨平台发行包、阈值和默认限制仍未冻结 |

`Ready for review` 不等于 `Accepted`，也不允许把 Roadmap 状态改为 `DONE`。

## 必需交付物

Roadmap 点名的五份调研正文和五份设计正文均已存在。调研正文仍为 Draft；设计中
只有 subtree 同步方案已经 Accepted，以下五份门禁正文已进入 In Review：

- [`architecture.md`](architecture.md)
- [`api.md`](api.md)
- [`c-abi.md`](c-abi.md)
- [`testing.md`](testing.md)
- [`risks.md`](risks.md)

这表示正文已具备评审输入，不表示 Accepted，证据见
[`design-review-readiness.md`](design-review-readiness.md)。当前有效决策中，
ADR 0001—0006 与 0008—0015 共十四份仍为 Proposed；ADR 0007 已被 0011
Superseded，不计作待接受决策。不能仅因对应 spike 通过就自动把 ADR 改为
Accepted。

## 三项技术验证

1. 规则 runtime：固定规则、生命周期、语法/HostApi inventory、资源限制和七类
   专用规则差分已有证据；ADR 0006 的全量 HostApi、跨平台 static archive、
   许可证和正式 backend 门禁尚未满足。
2. C static link：Windows/Linux x64 的首轮 `.lib`/`.a`、C 调用、所有权、
   panic containment 和依赖证据已存在；它不是最终 C ABI 或三平台发布证明。
3. upstream oracle：固定 SHA 的 Linux Qt5 qmake/CMake、Linux Qt6 与
   Windows Qt5 oracle、生成语料和原始输出哈希可重复；macOS oracle 尚未固定。

因此这三项可进入评审，但其受限范围必须原样保留。

## 阻塞项与关闭证据

| ID | 阻塞项 | 要求的关闭证据 |
| --- | --- | --- |
| `P0-BLOCK-001` | Closed | 68 个稳定 CAP ID、四级验证状态、证据路径和开放 gap 闭集已写入 manifest，并由测试与上游 lock 绑定 |
| `P0-BLOCK-002` | Open | 五份设计已 review-ready/In Review；仍缺 architecture、API、C ABI、testing、risks 的明确评审结论 |
| `P0-BLOCK-003` | Open | 十四个 ADR 已 review-ready、但 acceptance-ready 均为 false；仍需 Accepted/Rejected/Superseded 评审结论 |
| `P0-BLOCK-004` | Open | 固定 Linux Qt5 CMake `diec` 已闭合为 223 direct + 14 archive = 237 个 compile source，绑定 13 组件、AUTOMOC、14 根 LICENSE 和 byte-identical GNU ld map；其中 XArchive 为 84 direct + 1/22 archive source，XCapstone 为 1 direct + 10/11 archive source，XSIMD 为 3/3。默认 CMake install staging 又固定为 4,916 个文件/60,881,050 bytes：同时安装 `die`/`diec`/`diel`、重复 `db`/`info`/YARA subtree，却只有一个根 LICENSE candidate；CLI-only build 会在部分复制后因缺少 GUI binary 失败。AppImage pre-linuxdeploy 与 portable post-build tree 也已复演：前者只有 GUI 却带完整 runtime/YARA/PEiD/signature，后者带三产品却漏 extra/custom 并额外带 YARA/signature，两者均无 LICENSE candidate；原始 tar 两次不同，规范化 post-build control 两次相同，但该错误内容 tree 不是获批 manifest。direct-link XUCL 已固定到官方 UCL 1.03：合并 12/64-token 覆盖 94.76%/89.08%，技术分类为 GPL-2.0-or-later，并恢复精确 `ACC_LICENSE` 证据。RAR decoder 也已固定到 RARLAB 官方自报 UnRAR 7.13 归档：150 个源码与镜像逐字节相同，159 个文件全部在换行规范化后相同，并绑定 license/acknowledgments；XArchive 仍缺对应 notice/归属。runtime `db*` 2,268 文件和 22 PNG 来源已有技术证据；仍需 XUCL MIT/GPL 组合及不同书面授权、RAR notice/第三方归属、artwork 授权、最终 linuxdeploy/获批 clean-build archive、其他平台 closure 和发布责任人书面评审 |
| `P0-BLOCK-005` | Open | 68 行 × 4 平台 coverage report 已建立且无未分类 cell；Linux Qt5/Qt6 与 Windows Qt5 的 68 项均为 runtime-observed，source-only 与 corpus-gap 均为 0；Windows closure 绑定 23 份报告、2,438 次执行并以 path closure 关闭最后一行；CAP-GAP-008 的 Windows 部分 closed；macOS x86_64/Qt5 CLI-only bootstrap、候选报告 validator 与 hash-bound 预执行计划已就绪，但尚未在 Darwin 主机采集，仍有 68 个 platform-missing |
| `P0-BLOCK-006` | Open | 固定 Linux Qt5 五层 warm baseline 已保留每 session 17 warmup/90 measured 的 latency/MAD/p95/RSS、cgroup 和确定性输出；[单 vCPU affinity 复验](../research/upstream-performance-affinity.md)证明 `cpuset.cpus.effective=0` 并保留短 control 的部分 RSS 边界，[三次 session 汇总](../research/upstream-performance-repeated-sessions.md)进一步绑定 51 warmup/270 measured，观察到 archive median 1.7704、PE median 1.3940 与 batch p95 1.6848 的跨 session max/min，明确单 session 不能冻结阈值；[成功文件访问闭包](../research/upstream-benchmark-file-access.md)通过每 case 两次 ptrace 固定 2,283 files/73,560,058 bytes，补齐 `PT_INTERP` 并区分 2,235 个成功打开的 `.sg` 与 33 个非脚本资产；[页 residency 与 advisory eviction](../research/upstream-benchmark-page-cache.md)再用无 `PT_INTERP`/`PT_DYNAMIC` 的静态 controller 对每 case 双次证明全部候选页 warm resident、fadvise 后逐文件 0 resident、post-run vector 及上游输出相同；[warm/file-content 成对测量](../research/upstream-benchmark-file-content-performance.md)继续以 runner plan/report schema v2 的 preflight/exec/finalize 链、同一静态 controller、clock 与 direct-child RSS 对五 case 各采集 10 组 ABBA，共 100 个 measured child，每个 run 均验证 plan/controller/manifest identity、before-run 页状态与未变输出，但只有一个 WSL2 session；[Linux 缓存环境边界](../research/upstream-benchmark-cache-environment.md)用双次只读观察固定 overlayfs、无 page-cache namespace、`/proc/sys` ro、无 `CAP_SYS_ADMIN` 与 `drop_caches=EROFS`，ADR 0015 因而分离 warm、file-content-nonresident-metadata-warm 与 dedicated system-cold，并禁止通用 cold；[Windows 缓存态边界](../research/windows-benchmark-cache-state.md)再用 native build 26100/NTFS 双次只读观察证明全局 flush 需要当前 token 不具备的 `SeIncreaseQuotaPrivilege`，且 NO_BUFFERING/FlushFileBuffers/EmptyWorkingSet 均不构成 Linux 第二层等价证据，因此 Windows 只复用 warm；[macOS 缓存态计划](../research/macos-benchmark-cache-state.md)固定 Apple XNU commit 和 `fcntl`/`mincore`/`msync`/`madvise` 契约，并提供只操作 unlink 后 16 MiB fixture 的双轮 `MS_INVALIDATE` + residency collector/validator；它保持 runtime missing 和 admission false；[体积基线](../research/upstream-deployment-size.md)已固定 ELF、16 个去重动态依赖与 2,268 个规则的两种口径，[默认 CMake staging](../research/linux-cmake-install-tree.md)另固定 4,916 文件/60,881,050 bytes；[发布树复演](../research/linux-release-trees.md)记录 AppImage 前置树 38,920,508 bytes、portable 未压缩树 52,751,519 bytes，原始 tar 因八个 mtime 不同而不可重复，规范化 post-build control 则产生两份相同的 17,463,573-byte tar.gz；linuxdeploy、兼容 Qt closure、获批 clean-build archive 和最终 compressed-size 仍未闭合；仍需 Rust 成对、dedicated system-cold、macOS candidate runtime/fixed-closure integration、physical-core/topology 与长期 session、跨平台最终发行包、评审阈值和默认资源限制 |

`P0-BLOCK-006` 的默认资源限制现另有
[`resource-limit-policy.md`](resource-limit-policy.md) 和
[`data/resource-limit-policy-candidate.json`](data/resource-limit-policy-candidate.json)
作为 hash-bound 评审输入：ADR 0012/0014 的 scan/traversal 数值已统一，上游
21/2001/100000 临界值与 QuickJS spike-only 限额已分离；全库 include sizing
又提出 modern 16/256 与 legacy-high 64/4096；database load sizing 绑定完整
三层 2,268-entry bundle 和规范 stored ZIP，提出 10 个 modern/legacy-high
非零字段；traversal metadata/open 又以逐 adapter call reserve 的结构模型提出
524,288/8,388,608；diagnostics 以 typed fact/overflow completion 模型提出
4,096/131,072，并补齐 Legacy-high queue/node 字段；root input 又按稳定逻辑长度
提出 1 GiB/8 GiB，并与累计 I/O、allocation counter 分离；total allocation 又按
scan-owned capacity 单调累计提出 1 GiB/8 GiB。仍有 4 个尚无生产候选的
预算被显式列出。该策略仍为
`admitted=false`，因此 blocker 状态不变。

## 下一步顺序

1. `P0-BLOCK-001` 已关闭；后续能力增删必须同时修改 matrix/manifest，validator
   会拒绝 ID、固定 commit、证据路径或汇总计数漂移。
2. Linux Qt5/Qt6 与 Windows Qt5 的 source-only、corpus-gap 与 platform gap
   已清零；下一步在 Darwin x86_64 执行已固定 bootstrap、冻结 toolchain
   lock，再建立 macOS 68 行完整 baseline。
3. 并行准备许可证和 benchmark 评审材料；不得用技术可行性替代许可证结论，
   也不得在没有固定环境时声称性能改善。
4. 技术 blocker 清零后提交设计/ADR 评审；只有评审结论落盘后才能更新
   `ROADMAP.md` 并进入 Phase 1。

## 防误报约束

[`test_phase0_gate_review.py`](../../tools/tests/test_phase0_gate_review.py) 校验：

- Roadmap 仍为 Phase 0 `IN PROGRESS`；
- 清单中的每个文档和证据路径真实存在，且记录状态与 front matter 一致；
- 必需研究、设计、spike、退出条件和 blocker ID 完整且唯一；
- 存在 blocker 时结果只能是 `not_ready`；
- 本文列出的 blocker 状态和有效 Proposed ADR 数不发生静默漂移。

该测试不替代评审，也不会自动接受 ADR。
