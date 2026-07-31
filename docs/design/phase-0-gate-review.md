# Phase 0 设计门禁审计

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-31

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
| `P0-EXIT-004` | 架构、规则 runtime、ABI 和测试方案完成评审 | Ready for review | 五份必需设计已 Accepted、十四个有效 ADR 已 Accepted；P0-BLOCK-004 许可证审计已 closed |
| `P0-EXIT-005` | 风险清单完整 | Ready for review | 20 项风险均含触发、缓解、验证和关闭条件，但文档仍需评审 |
| `P0-EXIT-006` | 后续阶段有可测完成条件 | Ready for review | `ROADMAP.md` 与 `testing.md` 已给出 Phase 1—6 的量化门禁 |
| `P0-EXIT-007` | 性能基线与资源目标得到回答 | Ready for review | 固定 Linux Qt5 warm baseline、三次 session 汇总、file-access 闭包、page-cache 证明、file-content ABBA 配对、cache-environment 边界、Windows/macOS cache 策略、deployment size 和 resource limit 候选（0 unresolved）均已冻结为 Phase 0 评审候选；Rust 成对 benchmark、dedicated system-cold、macOS runtime 和 release size 为 Phase 1 实现期门禁 |

`Ready for review` 不等于 `Accepted`，也不允许把 Roadmap 状态改为 `DONE`。

## 必需交付物

Roadmap 点名的五份调研正文和五份设计正文均已存在。调研正文仍为 Draft；设计中
只有 subtree 同步方案已经 Accepted，以下五份门禁正文均已 Accepted：

- [`architecture.md`](architecture.md) — Accepted
- [`api.md`](api.md) — Accepted
- [`c-abi.md`](c-abi.md) — Accepted
- [`testing.md`](testing.md) — Accepted
- [`risks.md`](risks.md) — Accepted

十四个有效 ADR 全部 Accepted，每个 ADR 拆分了 Decision acceptance（方向批准）
和 Implementation exit（实现期门禁）。ADR 0007 已被 0011 Superseded，不计作
待接受决策。

## 三项技术验证

1. 规则 runtime：固定规则、生命周期、语法/HostApi inventory、Qt5/Qt6 native
   global query conversion raw 差分、资源限制和七类专用规则差分已有证据；
   ADR 0006 的全量 HostApi、跨平台 static archive、许可证和正式 backend 门禁
   尚未满足。
2. C static link：Windows/Linux x64 的首轮 `.lib`/`.a`、C 调用、所有权、
   panic containment 和依赖证据已存在；它不是最终 C ABI 或三平台发布证明。
3. upstream oracle：固定 SHA 的 Linux Qt5 qmake/CMake、Linux Qt6 与
   Windows Qt5 oracle、生成语料和原始输出哈希可重复；macOS oracle 尚未固定。

因此这三项可进入评审，但其受限范围必须原样保留。

## 阻塞项与关闭证据

| ID | 阻塞项 | 要求的关闭证据 |
| --- | --- | --- |
| `P0-BLOCK-001` | Closed | 68 个稳定 CAP ID、四级验证状态、证据路径和开放 gap 闭集已写入 manifest，并由测试与上游 lock 绑定 |
| `P0-BLOCK-002` | Closed | 五份设计文档全部 Accepted 2026-07-31；实现期门禁由对应 ADR Implementation exit 跟踪 |
| `P0-BLOCK-003` | Closed | 十四个有效 ADR 全部 Accepted 2026-07-31；每个 ADR 拆分 Decision acceptance 与 Implementation exit |
| `P0-BLOCK-004` | Closed | 引擎与规则分离已确认（diec CLI 不包含或分发 db*/YARA/PEiD/signatures 资产）；上游 C++ 许可证（XUCL GPL、UnRAR、Brotli、Zstandard）不传染 Rust 二进制；14 份技术证据文档绑定全部上游组件许可证；剩余 Rust crate 许可证清单（cargo deny/about）和 NOTICE 文件为 Phase 1 标准工作 |
| `P0-BLOCK-005` | Open | 68 行 × 4 平台 coverage report 已建立且无未分类 cell；Linux Qt5/Qt6 与 Windows Qt5 的 68 项均为 runtime-observed，source-only 与 corpus-gap 均为 0；Windows closure 绑定 23 份报告、2,438 次执行并以 path closure 关闭最后一行；CAP-GAP-008 的 Windows 部分 closed；macOS x86_64/Qt5 CLI-only bootstrap、oracle/cache candidate validator、64-exec 通用 CLI/corpus bundle、676-exec primary option/output/special matrix、1,092-exec remaining output/special matrix、36-exec release CLI database/error matrix、92-exec path/nested matrix、34-exec ZIP-database CLI matrix、46-exec special-path CLI matrix、16-exec filesystem-path CLI matrix、24-exec root/ACL/ownership privilege-path CLI matrix、10-exec large-directory CLI matrix、34-exec long-path CLI matrix、8-exec TOCTOU CLI matrix 和 2-exec/19-case database-cache engine harness collector/validator 已由同一 hash-bound workflow 固定；CLI 保留 2,132 次执行的 4,264 个 raw stream，engine cache 另保留 2 次执行的 4 个 raw stream，两份 build log 单列，runtime 合计 2,134 次执行和 4,268 个 raw stream；special-path fixture 动态记录 case/NFC-NFD alias、目录项字节名和非法 UTF-8 errno，CLI 矩阵再覆盖全部逻辑 UTF-8 拼写、目录枚举、显式顺序和 leading-dash；filesystem fixture/CLI 又固定 file/directory symlink、dangling link、self-cycle、非 root mode-000 权限和 64 层目录，self-cycle timeout 也作为观察保留；privilege-path collector 仅在全新 runner-temp fixture 上，以 passwordless-sudo probe、逐目标非递归 chown、Darwin `chmod +a/-N` 和清理证明固定 owner/root-owned 0644、root-owned 0600、mode-000、ACL deny-read/search 的 runner/root 双轮关系，且不预设 uid 0 是否绕过 deny ACE；large-directory fixture/CLI 再固定 0/1/256/4096 flat 与 16×256 nested 的全部 8,449 个空文件、完整 prefix 数和 name-order projection；long-path fixture/CLI 绑定固定 XNU `NAME_MAX=255`、`PATH_MAX=1024`、kernel-private `MAXLONGPATHLEN=8192` 与 runtime pathconf，通过 dir-fd relative 物化分离 filesystem create 能力和 CLI path-string 能力，并覆盖三个边界的 -1/exact/+1、explicit/discovery 及 errno；TOCTOU collector 复用固定四 case fixture，以关闭 `OPOST` 的 PTY、`SIGSTOP`/`waitpid(WUNTRACED)`、第二 prefix guard 和停止态 symlink mutation 替代不可移植的 GNU `stdbuf`，并保留前后 identity、entropy document 与 raw stream；database-cache builder 只替换固定 qmake console main object，保存原始/补丁 Makefile、共享 19-case harness、test-mode adapter、artifact identity 与 build log；engine collector 再以非 root runner 和隔离 HOME 双轮覆盖 cache miss/hit/stale/truncation/write denial/concurrency、directory/ZIP permission denial 与 cancellation poisoning，并逐 case 投影固定 Linux Qt5；普通 output/special 已覆盖全部 26 个生成样本，但所有候选均尚未在 Darwin 主机采集；root/ACL/ownership、TOCTOU 与 database-cache 都只有未运行 candidate，其余 engine-only 矩阵仍缺，因此仍有 68 个 platform-missing |
| `P0-BLOCK-006` | Closed | Resource limit 候选已冻结为 Phase 0 评审候选（0 unresolved budgets，ADRs 0006/0010/0012/0014/0015 已 Accepted）；Linux Qt5 warm baseline、三次 session 汇总、file-access 闭包、page-cache 证明、file-content ABBA 配对、cache-environment 边界、Windows/macOS cache 策略、deployment size 均有 hash-bound 证据；Rust 成对 benchmark、dedicated system-cold、macOS runtime benchmark 和 release size benchmark 为 Phase 1 实现期门禁 |

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
scan-owned capacity 单调累计提出 1 GiB/8 GiB；script runtime 又为
heap/JS stack/fuel/deadline 提出联合候选。必需字段现有 0 个 unresolved，
三轮 full Binary corpus 已固定每轮 28 次正常 VM poll 与 4,130 个 lifecycle
memory checkpoint，并固定每轮 16,439 次 Binary signature native checkpoint；
4095/4096 候选边界和单次 native search 中断已有回归。但瞬时 heap high-water、
其余 HostApi checkpoint、完整跨格式 scaling、三平台资源证据和 ADR 评审仍缺。
PE/ELF/Mach-O/DEX/APK/Archive/PDF 七类代表性规则的 25-case 矩阵已三轮稳定，
全部 2,235 个固定程序文件的隔离顶层 parse/eval 也已三轮固定 custom-allocator
high-water，逐规则独立 runtime 的分位数与最大规则也已固定；这些实验不调用
`detect`。30-scope init/顶层规则/include 动态闭包也已固定，但使用显式诊断序，
不替代平台规则顺序；七类矩阵又每类仅一条短规则，仍不能关闭上述完整性缺口。
该策略现为 `admitted=true`，候选已冻结为 Phase 0 评审候选。Production
limit-1/exact/+1 测试、跨平台 resource benchmark 和 Rust 成对测量为 Phase 1
实现期门禁。

## 下一步顺序

1. `P0-BLOCK-001` 已关闭；后续能力增删必须同时修改 matrix/manifest，validator
   会拒绝 ID、固定 commit、证据路径或汇总计数漂移。
2. `P0-BLOCK-002` 和 `P0-BLOCK-003` 已关闭；五份设计文档和十四个 ADR 全部
   Accepted，实现期门禁由 ADR Implementation exit 跟踪。
3. `P0-BLOCK-004` 已关闭；引擎与规则分离已确认，上游 C++ 许可证不传染 Rust
   二进制，Rust crate 许可证清单和 NOTICE 文件为 Phase 1 标准工作。
4. `P0-BLOCK-006` 已关闭；resource limit 候选已冻结为 Phase 0 评审候选，
   benchmark 策略和 cache 三层模型已确认，Rust 成对 benchmark 和 dedicated
   system-cold 为 Phase 1 实现期门禁。
5. Linux Qt5/Qt6 与 Windows Qt5 的 source-only、corpus-gap 与 platform gap
   已清零；下一步在 Darwin x86_64 执行已固定 bootstrap、冻结 toolchain
   lock，再建立 macOS 68 行完整 baseline。
6. `P0-BLOCK-005` 清零后更新 `ROADMAP.md` 并进入 Phase 1。

## 防误报约束

[`test_phase0_gate_review.py`](../../tools/tests/test_phase0_gate_review.py) 校验：

- Roadmap 仍为 Phase 0 `IN PROGRESS`；
- 清单中的每个文档和证据路径真实存在，且记录状态与 front matter 一致；
- 必需研究、设计、spike、退出条件和 blocker ID 完整且唯一；
- 存在 blocker 时结果只能是 `not_ready`；
- 本文列出的 blocker 状态和有效 Accepted ADR 数不发生静默漂移。

该测试不替代评审，也不会自动接受 ADR。
