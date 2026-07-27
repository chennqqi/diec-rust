# Phase 0 风险清单

Status: Draft

Last updated: 2026-07-27

## 1. 用途与依据

本文集中跟踪会阻止 diec-rust 达到能力兼容、安全、静态链接或跨平台目标的风险。
调研文档保存事实，架构/API/测试文档保存设计；本清单只保存风险状态、触发条件、
应对、验证和关闭证据。

依据：

- [`architecture.md`](architecture.md)
- [`api.md`](api.md)
- [`c-abi.md`](c-abi.md)
- [`testing.md`](testing.md)
- [`rule-compatibility.md`](../research/rule-compatibility.md)
- [`rule-runtime-spike.md`](../research/rule-runtime-spike.md)
- [`rquickjs-rule-runtime-spike.md`](../research/rquickjs-rule-runtime-spike.md)
- [`binary-rule-lifecycle.md`](../research/binary-rule-lifecycle.md)
- [`nested-scan-behavior.md`](../research/nested-scan-behavior.md)
- [`cli-dependency-and-license.md`](../research/cli-dependency-and-license.md)
- [`yara-license-closure.md`](../research/yara-license-closure.md)
- [`upstream-build-baseline.md`](../research/upstream-build-baseline.md)

## 2. 评级与状态

影响：

- `Critical`：可能导致内存安全、代码执行、ABI UB、规则整体不可用或错误兼容声明。
- `High`：阻塞主要能力、目标平台、发布或造成大范围错误结果。
- `Medium`：可局部降级，但影响性能、维护或部分能力。
- `Low`：影响有限且有明确 workaround。

可能性：`Likely`、`Possible`、`Unlikely`。优先级由影响和可能性共同评审，不用一个
不可解释的乘积分数掩盖 Critical 风险。

状态：

- `Open`：风险存在，缓解/证据尚不足。
- `Mitigating`：已执行缓解，但关闭门禁未满足。
- `Accepted`：经 ADR 明确接受 residual risk；不能只在此表改状态。
- `Closed`：触发面已消除或关闭证据全部通过。

风险 owner 是职责角色，不假设具体个人。每次影响设计、runtime、依赖、规则或
baseline 的变更都要检查本表。

## 3. 风险总览

| ID | 风险 | 影响 | 可能性 | Owner | 状态 | 最晚关闭 |
| --- | --- | --- | --- | --- | --- | --- |
| R-001 | JavaScript runtime 无法 1:1 执行完整规则 | Critical | Likely | Rules | Open | Phase 3 start |
| R-002 | 规则/组件许可证或归属阻止原样分发 | Critical | Possible | Release | Open | runtime/rules decision |
| R-003 | 能力矩阵和物化组件不完整导致漏实现 | High | Likely | Compatibility | Open | Phase 0 exit |
| R-004 | 畸形二进制触发 panic、越界或无界分配 | Critical | Possible | Core/Formats | Open | each format merge |
| R-005 | archive/resource/overlay 导致解压炸弹或无界嵌套 | Critical | Likely | Engine | Open | nested implementation |
| R-006 | native runtime/解压依赖破坏可移植性与 static link | High | Possible | Build | Mitigating | dependency ADR |
| R-007 | C ABI ownership、allocator、线程或 panic 产生 UB | Critical | Possible | FFI | Mitigating | Phase 5 exit |
| R-008 | 结果 schema/顺序错误使 CLI、FFI 与差分不一致 | High | Possible | API/Output | Open | schema freeze |
| R-009 | Windows/macOS oracle 缺失却声称跨平台兼容 | High | Likely | Compatibility | Open | Phase 4 exit |
| R-010 | 语料覆盖或许可证不足，兼容证据失真 | High | Likely | Test Data | Open | Phase 6 exit |
| R-011 | 并行/runtime 状态造成非确定性或数据竞争 | Critical | Possible | Engine/Rules | Open | parallel enablement |
| R-012 | Rust 重写未改善或恶化延迟、内存和产物大小 | High | Possible | Performance | Open | Phase 6 exit |
| R-013 | upstream subtree/rules 更新产生未审计漂移 | High | Possible | Upstream Sync | Mitigating | every sync |
| R-014 | 依赖供应链、MSRV 或 feature 漂移破坏构建 | High | Possible | Build/Release | Open | Phase 1/release |
| R-015 | runtime 无可靠 interrupt，取消/timeout 失效 | Critical | Likely | Rules | Open | runtime decision |
| R-016 | upstream oracle 自身不可重建或产生漂移 | High | Possible | Compatibility | Mitigating | Phase 0 exit |
| R-017 | GUI/plugin 等未来范围反向污染核心 | Medium | Possible | Architecture | Mitigating | continuous |
| R-018 | `.a` 消费方式被误解，Go/Python 集成不可交付 | High | Possible | FFI | Mitigating | Phase 5 exit |
| R-019 | 目录枚举、symlink/junction 和路径编码不安全 | Critical | Possible | CLI | Open | Phase 4 start |
| R-020 | 规范化/waiver 隐藏真实兼容回归 | Critical | Possible | Compatibility | Mitigating | Phase 1/release |

## 4. 详细风险

### R-001：规则 runtime 语义不兼容

- **触发**：任一固定规则无法 parse/load；sloppy JS、global/type init、include、
  host object、exception 或函数抽取与上游不同。
- **当前证据**：Boa 与原始 QuickJS 都拒绝 Nintendo 规则；QuickJS 的单点、等长、
  manifest-pinned overlay 已让 2235 文件 isolated eval 达到 0 错误；最小 Rust
  Byte HostApi 的 Nintendo target detection 在 Qt 5 baseline 上 14/14 匹配。
  固定源码已确认一次 scan 共享一个 script engine；QuickJS probe 已按真实顺序
  执行 global/Binary init、30 次 include 和 292 条 Binary 顶层程序。原始规则有
  3 个 lexical 差异，三个精确等长 overlay 后为 0；专用 7 规则 fixture 已确认
  Qt 5 的跨 `evaluate()` lexical 环境与 QuickJS 单一 global context 不等价，
  后者仅得到 4/7 detection。per-rule lexical wrapper 已达到 fixture 7/7，并让
  292/292 Binary 规则以仅一个 Nintendo 单脚本 overlay 解析出 `detect`；
  但状态 fixture 证明 wrapper 会丢失 Qt 持久化的顶层 var/function（5/7）。
  固定 Binary AST 审计的 wrapper-loss candidate 为 0，但静态零候选不能视为
  动态等价。选定生命周期 probe 已在全 292 条规则加载环境中依次调用
  archive_DEFLATE、EA-XA 和 Nintendo `detect`，目标调用
  未使用 fallback HostApi，PS3/Vita 完整目标结果与 Qt 5 baseline 14/14 匹配；
  同时发现 archive_DEFLATE 动态初始化隐式全局 `bad` 是 EA-XA 的前置依赖。
  selected lifecycle 中非目标规则尚未调用 `detect`，顶层加载仍有三次来自
  `shell-script` include 的可追踪 HostApi fallback。后续 diagnostic 已逐条尝试
  全部 292 个 `detect`。补入固定上游契约的基础读取方法后为 285 条无异常、
  7 条异常；固定 Qt 5/Qt 6 oracle 闭合 `U24`/`read_uint24` 与 `shru64` 后，
  仍有 233 条规则共调用 365 次 fallback、涉及 17 条动态路径；
  32 条规则还调用 317 种未支持 signature pattern。代理制造 153 条无效
  detection；只有 59 条未记录 fallback，且仍无逐条 Qt oracle。该结果是缺口
  inventory，不是 285/292 兼容率。随后接入 pure-Rust `c`/`compare` adapter：
  799 次 compare 为 776 fast、23 generic、5 个显式 quirk、0 error；292/292
  个 `detect` 无异常，fallback 降为 16 条规则、58 次和 18 条路径。但剩余代理
  仍影响控制流，10 条 detection 及 276 条“未记录 fallback”都不是逐条兼容
  证据。继续接入 `fSig`/find/presence 后，11 次搜索为 1 quirk、0 error；
  真实 `false/-1` 改变控制流，1179 次 compare 后为 291/292 条无异常、
  14 条规则 39 次 fallback 和 15 条路径，唯一异常暴露 overlay HostApi 缺口。
  独立 overlay context 接入后为 1109 次 compare、292/292 条无异常、
  12 条规则 34 次 fallback 和 11 条路径；当前 4 条 detection 与 280 条
  “未记录 fallback”仍不是兼容证据。字符串 context 15/15 oracle 接入后为
  3 条规则 4 次 fallback 和 4 条路径；当前 1 条 detection 与 289 条
  “未记录 fallback”同样不是兼容证据。最后接入 scan/file-part 和确定性 text
  HostApi 后，固定 trace 为 292/292、
  0 异常、0 fallback、1105 次 compare 和 1 条 detection；零 fallback 只说明
  单输入实际分支已闭合，不能替代逐规则 Qt oracle。纯 Rust
  signature spike 已在显式兼容模式
  解析动态 317/317，并对 6 个上游宽松点返回 quirk。固定 XBinary oracle 的
  89 个向量已确认 compare/find 在 `%&`、DEL、leading `+` 和 invalid suffix
  上存在不同语义；Rust context-free compare 当前差分 16/16，六类合成
  memory-map 分支差分 7/7，PE32/64、ELF32/64、Mach-O32/64、COM、MS-DOS、
  AmigaHunk 真实 parser map 差分 9/9；独立 find 三分支聚焦差分 19/19。
  `Binary_Script::compare` header fast path 端到端差分 7/7，确认字符/字节混合
  size、严格 `<` 和 Qt 5 负 offset clamp 会改变结果；EP/overlay 各 5/5 又确认
  256-byte cache 被当作 512-byte 范围、原始 pattern 长度参与分支，能改变合法
  literal 结果；search/presence wrapper 4/4 固定范围裁剪、`size == -1`、别名
  和布尔投影；overlay HostApi 3/3 证明 file-part 与 nested overlay 独立；
  文件后缀/header text context 15/15 固定确定性字符串语义；execution context
  3/3 固定 scan ID 和 resource/debugdata file-part；storage prefill 4/4 证明
  非 Unicode 的 `m_bIsUnicodeText/isText` 依赖未初始化状态。ADR 0005 采用
  显式确定性 facts，接入后固定 trace 为 292/292、0 异常、0 fallback、1105 次
  compare 和 1 条 detection；仍不能把单输入零 fallback 当作兼容率。三条原样
  context-sensitive 规则的 Qt5/Rust 差分随后为 8/8，但只验证已给定 context
  后的规则行为，未验证 scanner 的 subdevice 枚举、scan ID 和调度。
  固定 signature AST inventory 随后解析 `db`/`db_extra`
  2175/2175，保存 5968 个具名 signature API 调用点和 5628 个静态 pattern，
  覆盖动态 317/317；四个保守动态参数中的 `byteCode` 又已闭合为 97 个唯一
  pattern，其余 3 个是输入相关 Number→QString 调用。完整规则语法清单按 runtime
  spike 的 2235 文件口径达到 2235/2235，记录 55 种 AST 类型、28,372 个调用和
  29 个宿主 receiver 上的 429 个第一层 receiver/method、464 个 arity 形状，
  动态 computed 第一层宿主方法名为 0。固定 XScanEngine 30 个类实际有 337 个
  C++ slot；与 13 个规则脚本扩展静态覆盖 460/464 个 arity 形状。共享 Qt 5/
  Qt 6 QObject 探针已闭合四个静态缺口：三个额外实参形状在两侧保持相同语义
  返回，但 Qt 6 发出 stderr warning；未定义 `PE.getEPSignature` 在两侧抛出
  runtime-specific `TypeError`。代表性转换还证明 Qt 5 把 `qint64` 的
  null/undefined 转成 0，而 Qt 6 拒绝。其余类型转换、畸形 map、find 的畸形/
  穷举边界、无效/短小 wrapper 上下文、异常上层传播和其余 HostApi 行为仍未
  验证。Qt 6.4.2 初始 CLI 差分已确认两个可达未定义 global 的 detection 相同而
  `ReferenceError` 文本不同；最小 PE 另有四行 Qt 6-only stderr，已二分到单条
  GenericHeuristicAnalysis 规则但未定位精确表达式。四类整数返回桥接两侧相同，
  不能外推其余转换。非格式面已固定 16 个 native global slot；Qt 5 只注册其中 15 个，
  固定规则实际调用 7 个共 253 次。71 个 undeclared direct-call 名已全部分类，
  暴露两个不应静默修复的规则拼写错误；32/40 字节安全输入已证明二者在固定
  Qt 5 qmake/CMake 中可达，并产生相同 `Unknown`、trailing `ReferenceError`、
  空 stderr 和 exit 0。跨文件函数 include 可达性和 native global 的完整行为
  仍未验证。共享 Qt 5/Qt 6 global harness 已确认 Qt 5 缺参 `"undefined"`
  转换与 Qt 6 `Insufficient arguments` 严格错误不同；null 字符串化和
  `_encodingList` 也不同，而重复结果、单项删除/block、数组字符串化、双 stop
  状态和重复 include 相同。受限 Qt5 CLI fixture 又证明 self/two-node include
  cycle 依赖 VM 栈上限，产生 28 条 signal 和一条 init error 后继续规则；
  ADR 0010 提议静态图与 active stack 提前拒绝该循环。固定 QuickJS-NG fixture
  已用 128 KiB stack limit 使无界 JavaScript 递归产生明确异常，并在同一
  context 恢复 `"42"`；这只证明末级 VM hard limit 接线，不等于 Qt include-cycle
  错误传播兼容。固定 native `Function` callback panic 也已由 rquickjs 在 C ABI
  trampoline 内捕获、在 Rust eval 边界恢复原 payload；调用方捕获后同一 context
  继续返回 `"42"`。4 MiB heap limit 拒绝 16 MiB 分配后同一 context 也已恢复
  `"42"`。这些结果不覆盖正式 HostApi adapter 或 native crash/abort。完整
  format HostApi 矩阵、更多参数/转换边界和逐规则 execution 仍是开放风险。
- **缓解**：保持 `RuleRuntime`/`HostApi` port；建立全规则 inventory、最小失败
  fixture、host call trace；基于证据选 runtime，禁止静默转换规则。
- **验证**：固定规则 100% discovered/parsed/loaded，zero silent unsupported；
  lifecycle/host API conformance 和代表语料 differential 通过。
- **关闭**：runtime ADR Accepted，所有门禁有 CI 证据，剩余差异仅有精确 waiver。

### R-002：许可证与归属不允许分发

- **触发**：规则、bundled code、runtime、archive backend 或样本缺失许可证、条款
  冲突或要求无法随 static library 履行。
- **当前证据**：固定 source image 已对 58/58 直接组件校验 commit 与根 LICENSE，
  全部首行为 MIT、共有 12 个文本 hash，且无嵌套 `.gitmodules`；103 个按名称
  发现的 license files 中 45 个位于 bundled/build-tool 路径。该结果关闭直接
  component root/submodule inventory，不覆盖 XArchive/XYara 文件头、规则数据或
  候选 Rust 依赖组合。固定 Linux CLI 又证明 XArchive 有 106 个实际编译单元和
  217 个依赖文件；其中 Brotli/Zstandard 聚合源进入链接闭包但没有文件内
  license marker。内容追溯已固定到 Brotli 1.2.0 MIT 和 Zstandard
  1.6.0-dev BSD/GPLv2（后者官方 token 精确一致），但 XArchive 未携带相应
  license/attribution，仍是明确未关闭的发布缺口。XYara 的 Linux YARA target
  又固定了 51 个编译单元/109 个依赖文件：YARA 主体映射官方 v4.5.2，
  6 个 Bison 生成文件含 GPL-3.0-or-later + special exception，6 个 TLSH 文件
  精确追溯到 `avast/tlshc` 的 Apache-2.0 OR BSD-3-Clause 与 Trend Micro
  NOTICE；但 bundled tree 没有携带 YARA `COPYING` 或 tlshc
  `LICENSE`/`NOTICE.txt`。10 个 Avast MIT Authenticode 文件在当前无 OpenSSL
  target 中未进入闭包，其他平台/feature 仍待审。五组 YARA/PEiD/signature
  数据资产又已固定逐文件 path/hash/history：三个 YARA 文件明确 GPLv2，三个
  DosX 文件只有归属保留请求，`peid.yar` 聚合多项外部 database URL，而
  PEiD/signature 数据没有文件级许可声明。固定 `diec` CLI 不加载这些资产，
  但上游打包脚本仍会复制 component YARA、PEiD 和根 `crypto.db`，因此不能以
  “CLI 不可达”免除发布物许可审计。
- **缓解**：每次导入/同步前生成 source/license inventory；保留原始 LICENSE、
  commit、path、hash 和 attribution；选型前由发布责任人复核组合。
- **验证**：规则 bundle、source closure、binary dependency、samples 和 release
  artifacts 均进入 SBOM/license report。
- **关闭**：目标发布组合完成书面许可评审；未知/不兼容组件为零。

### R-003：能力范围漏项

- **触发**：能力只有源码推断无实验；关键 gitlink 未物化；Formats 中存在能力但
  scan dispatch/rules/corpus 未交叉验证。
- **缓解**：稳定 `CAP-*` ID 和 traceability；优先物化关键组件；Source only 不
  升级为 Supported。
- **验证**：Phase 0 capability matrix 每项有源码或可重复实验；各 Phase 范围
  100% traceable。
- **关闭**：Phase 0 评审确认矩阵范围，无未分类 CLI/engine/rule/format 能力。

### R-004：不可信输入破坏内存/资源安全

- **触发**：panic、越界、integer wrap、超大 reserve、OOM abort、hang 或 native
  sanitizer failure。
- **当前证据**：固定 YARA v4.5.2 `-O3` build 对 `atoms.c` 四个写入位置产生
  12 条 `-Wstringop-overflow=` warning，诊断涉及 4-byte atom 的 offsets
  4/5/6。尚无 sanitizer 或可达输入证明，不能直接定性为漏洞或 false positive；
  Rust atom extraction 必须独立使用受控长度并覆盖差分边界。固定
  XScanEngine cache loader 又对文件 `readAll()`，直接按不可信 record count
  `reserve()`，没有 cache byte/record/script 上限；ZIP database 使用
  `getRecords(-1)` 并逐项解压。发布 CLI 不启用 cache，但 ZIP 可达，Rust
  database loader 必须统一纳入输入和分配预算。固定 Qt5 engine harness 已确认
  弱 freshness 会命中同 count/size/mtime 的旧内容；截断 cache 会在 fallback
  前泄漏部分反序列化 record；预取消 miss 会返回成功并持久化空 cache，下一次
  未取消加载继续复用并静默得到 `Unknown`。机器证据见
  [`database-cache-engine-qt5.json`](../research/data/database-cache-engine-qt5.json)。
- **缓解**：checked `u64` range、allocation cap、`try_reserve`、无 panic parser；
  cache key 绑定完整内容 manifest；decode/build/publish 事务化；失败或取消不提交
  cache；unsafe 最小化；unit/property/fuzz/sanitizer/Miri。
- **验证**：每个 parser 的合法/截断/畸形/边界/fuzz target 通过，历史 crash 全部
  晋升 regression；cache 每字段截断、伪造 count/length、取消时序、写失败和并发
  writer 证明无部分发布或 poisoned cache。
- **关闭**：这是持续风险；单个格式只有在对应证据通过后可关闭其子风险。

### R-005：嵌套和解压资源耗尽

- **触发**：深链、循环、极高 entry count、声明长度欺骗、高压缩比或累计输出超限。
- **缓解**：显式 work queue；全 scan depth/node/entry/read/decompressed/time
  hard budgets；cycle hint；不复刻无界调用栈。
- **验证**：每种 limit 的 `-1/exact/+1`、zip-bomb synthetic case、取消和 peak
  memory；安全偏差有 ADR/waiver。
- **关闭**：所有 extractor 共享预算且 sanitizer/fuzz/资源测试通过。

### R-006：native/static-link 可移植性失败

- **触发**：backend 引入不可静态链接系统库、C++ runtime、动态加载、平台缺失、
  许可证问题或大量 unsafe。
- **当前证据**：ADR 0006 提议的 rquickjs/QuickJS-NG backend 已在
  Windows MSVC `/MD`、`+crt-static`/`/MT` 和 Linux GNU 三条真实 C 链路中
  创建 runtime/context 并求值，最终程序无 QuickJS 动态依赖；rustc system
  library、最终 DLL/SO、产物大小和 18-package 许可证闭包已记录。macOS、
  musl、arm64 和 sanitizer 仍未验证。
- **缓解**：纯 Rust 优先；大型/native 依赖必须 ADR；backend 私有隔离；构建
  target matrix 早验证。
- **验证**：Windows `.lib`、Unix `.a` 的真实 C link/run 和 system library 清单；
  cross-platform CI。
- **关闭**：选定依赖在全部承诺平台通过链接、运行、许可证与安全评审。

### R-007：C ABI 未定义行为

- **触发**：跨 allocator free、wrong-thread runtime access、panic 穿越 ABI、
  layout 不匹配、borrow-after-free 或重复释放。
- **当前缓解**：ADR 0001、opaque handles、paired free、static-link spike。
- **验证**：header/Rust layout、symbol/status、lifecycle、wrong-thread、panic、
  allocation failure、ASan/Verifier、C/Go/Python matrix。
- **关闭**：`c-abi.md` Accepted 且 Phase 5 全矩阵通过。

### R-008：结果与输出契约漂移

- **触发**：CLI/FFI 各自检测/排序；HashMap 顺序；legacy 与 canonical schema
  混用；partial/limit 状态含糊。
- **缓解**：统一 arena/report；`diec-output` 单点序列化；ADR 0003 双输出；
  schema version 和 golden。
- **验证**：Rust/C/modern CLI canonical bytes 相同；legacy raw differential；
  repeated/parallel determinism。
- **关闭**：`api.md` schema 字段和排序 Accepted，跨平台 golden 全通过。

### R-009：跨平台兼容结论过度外推

- **触发**：用 Linux Qt5 结果代表 Windows/macOS；忽略 native path、locale、
  line ending、filesystem ordering 和 system dependencies。上游 Binary 固定
  文件名已使 `sort_signature_prio()` 产生非传递比较环，`std::sort` 结果不能
  外推到另一 STL/编译器。
- **当前证据**：固定 Linux Qt5 qmake/CMake oracle 的 292 条 Binary 执行序列
  逐项一致，重复运行 order hash 稳定；隔离 priority-only/init fixture 又证明
  `_init` 可直接形成比较环，并固定两个 Linux 构建偏离纯 priority 的相同顺序；
  Linux Qt6 初始矩阵已证明 runtime profile可改变异常文本和 stderr。尚无
  MSVC/libc++ 顺序证据。
- **缓解**：报告按 platform 分层；未固定 oracle 标记 missing；不允许跨平台
  blanket normalization。
- **验证**：Windows/macOS 固定 upstream oracle、path/encoding corpus 和 Rust
  differential。
- **关闭**：每个宣称支持的平台都有可重复 oracle 或经 ADR 限定为 semantic-only。

### R-010：语料不足或不可合法使用

- **触发**：主要格式/规则语法无样本；样本只覆盖 happy path；来源、许可证或客户
  数据不清。
- **缓解**：Tier A 生成优先；Tier B license inventory；Tier C 隔离；capability
  traceability 和 mutation/minimization。
- **验证**：每项能力 positive/negative/boundary；manifest hash；license review；
  fuzz regression growth。
- **关闭**：release 范围无 coverage gap，所有样本可追溯且处理策略合规。

### R-011：并发非确定性和数据竞争

- **触发**：共享 runtime/scanner、完成时间决定顺序、global cache/logger 或 cancel
  race 改变结果。
- **缓解**：database immutable；scanner `&mut`/thread-affine；scanner-per-worker；
  ordinal merge；无 mutable globals。
- **验证**：Loom/TSan/race detector（适用时）；同 case 串行/并行重复；cancel race。
- **关闭**：引入每一级并行前通过模型和 stress 证据；否则保持串行。

### R-012：性能目标无法证明

- **触发**：只报告最好值；混淆 database load/I/O/scan；在不同输入或 cache 条件
  比较；速度换取无界内存。
- **缓解**：固定 runner/corpus/options；分阶段 benchmark；median/p95/MAD 和 peak
  memory；profile before optimize。
- **验证**：noise calibration 后冻结回归阈值，持续 trend；upstream 同条件对比。
- **关闭**：Phase 6 目标及阈值通过。阈值未冻结前不得声称性能更优。

### R-013：上游同步漂移

- **触发**：subtree 与 metadata/lock 不一致；规则被格式化；gitlink/许可证变化未
  评审；基线就地覆盖。
- **当前缓解**：两个 sibling subtree、`components.lock.toml`、upstream verifier。
- **验证**：每次 sync 记录 old/new commit、tree/hash、gitlink/license/rule diff，
  old-vs-new oracle report。
- **关闭**：持续风险；每次 sync 独立关闭，verifier 必须 0 failure。

### R-014：供应链与构建漂移

- **触发**：依赖浮动、MSRV 意外提高、default feature 拉入 native/system 库、
  yanked/advisory 或 release 构建联网。
- **当前证据**：默认工具链已由 1.88.0 固定升级到 1.97.1，同时五个 spike
  继续声明 MSRV 1.88。五个 spike 在 1.97.1 下通过 fmt/Clippy/test；
  `signature-parser` 的新版 Clippy 修正又在 1.88 下通过相同 14-test suite。
  Windows MSVC `/MD`、`/MT` 和断网/只读/offline Linux GNU 共六条 C consumer
  均成功，native system library 集合未相对历史 1.88 报告增加。结果绑定到
  [`rust-toolchain-upgrade-1.97.1.json`](../research/data/rust-toolchain-upgrade-1.97.1.json)。
  Phase 1 双版本 CI、advisory/license CI、SBOM 和 clean release build 仍未建立。
- **缓解**：lockfile、明确 features/MSRV、依赖/许可证/audit policy、离线 release
  build、SBOM。
- **验证**：clean locked build、minimal feature builds、dependency diff review、
  advisory/license CI。
- **关闭**：Phase 1 建立门禁；每次 release 重新验证。

### R-015：取消与 timeout 不可靠

- **触发**：runtime 无 interrupt；parser/decompressor 长循环无检查点；native call
  无法安全终止。
- **当前证据**：rquickjs 0.12.1/QuickJS-NG 0.15.1 的 Windows MSVC fixture
  已由外部线程在 handler 启动后设置原子 token，中断无限循环且未触发百万次
  handler 硬兜底；清除 token 后同一 context 返回 `"42"`。10 次重复均成功，
  handler 次数随调度为 6..12，故不作为固定延迟。Boa 0.21.1 仍未发现等价的
  外部取消/heap 公开接口。独立 Rust native HostApi fixture 又在进入函数后请求
  取消，10/10 正常返回且未触发百万次检查点硬上限；迭代数 200..1,511 同样只作
  调度观察。VM/native 的 25ms monotonic deadline 也分别 10/10 到期、0/10
  触发硬兜底并恢复同一 context；callback/checkpoint 范围不作跨机器延迟承诺。
  同一 fixture 的 128 KiB stack limit 也已捕获无界递归并恢复 context，但真实
  include graph 仍必须由 ADR 0010 的静态/active-stack budget 提前拒绝。
- **缓解**：runtime 选型硬门禁；fuel/deadline/heap；受控检查点；不可中断 backend
  不得采用。
- **验证**：每个 scan stage deterministic fake clock/cancel；恶意长循环在期限内
  清理并返回正确错误；下一次 scan 状态正常；真实 signature/search/
  decompression HostApi 长循环逐项验证合作取消，不能以 synthetic loop 或 VM
  interrupt 代替；跨平台 system test 冻结有依据的最大延迟和 typed timeout 映射。
- **关闭**：runtime 和全部长循环路径通过 bounded interruption tests。

### R-016：oracle 漂移或不可复现

- **触发**：APT 未 snapshot、base/toolchain 变化、binary hash 改变、oracle crash、
  qmake/CMake 分歧。
- **当前缓解**：image digest、Dockerfile/toolchain/binary hash、Qt 5
  qmake/CMake 双 oracle 和独立 Qt 6 CMake profile 比较。
- **缓解**：固定 package snapshot/OCI digest；identity mismatch 作为
  infrastructure failure；baseline namespace 不覆盖。
- **验证**：clean environment rebuild、行为 matrix、产物/依赖证据。
- **关闭**：Phase 0 至少行为可重复；bit-for-bit 若做发布声明须另有完整证据。

### R-017：未来范围污染核心

- **触发**：为 GUI/plugin 提前增加 Qt、callback ABI、反向依赖或展示逻辑。
- **当前缓解**：当前无 GUI crate；architecture 禁止反向边和动态 plugin ABI。
- **验证**：Cargo metadata dependency policy；public API review。
- **关闭**：持续架构风险；每次依赖变更检查。

### R-018：语言绑定交付方式错误

- **触发**：宣称 Python `ctypes` 直接加载 `.a`；Go goroutine 跨 OS thread 使用
  reusable scanner；Windows CRT 组合遗漏。
- **当前缓解**：C ABI 文档明确 CPython extension/static link、Go locked worker、
  one-shot 和 CRT matrix。
- **验证**：真实 C/Go/Python build+run，不只检查 symbol；发布 consumer examples。
- **关闭**：Phase 5 所有目标工具链通过并记录最终系统依赖。

### R-019：路径枚举和编码安全

- **触发**：symlink/junction cycle、路径逃逸、TOCTOU、权限错误、极深目录、非
  UTF-8/UTF-16 边界或 locale-dependent ordering。
- **缓解**：CLI `TargetExpander` 与 engine 分离；不默认跟随 directory link；
  depth/file/byte/time budgets；native path 保留无损 identity。
- **验证**：隔离 path corpus 覆盖循环、权限、重复、特殊字符和三平台排序。
- **关闭**：path policy ADR/API 冻结且三平台 system tests 通过。

### R-020：差分工具隐藏回归

- **触发**：宽泛 normalizer/allowlist、只比较 parsed JSON、丢弃 JSON 前后
  stdout records、自动重录 golden、stale waiver 或 oracle failure 被算 pass。
- **当前缓解**：ADR 0004；raw bytes/hash；精确 fingerprint；默认失败；固定
  真实规则已证明 exit 0 的 stdout 可由 JSON document 加 trailing error 组成。
  Phase 0 v1 validator 已拒绝 wildcard/root、duplicate JSON key、identity drift、
  expired/stale/unmatched 和不可 waiver failure，并重新计算 fingerprint。
- **验证**：18 项 validator tests 覆盖差异扩大/缩小/消失、raw hash/平台/commit/
  schema 改变、过期/未执行 case、输入只读和 synthetic audit 重现；独立
  content-addressed raw artifact verifier 另覆盖固定派生路径、stream size/hash、
  预算、symlink/reparse、TOCTOU、输入只读和 golden 重现。raw artifact rehash
  已接入 lossless stdout framing，覆盖 prefix/invalid/trailing/multi-document
  byte ranges；固定 legacy CLI 的 normal/entropy/info/struct/open-error 已接入
  evidence-bound semantic result v1，unknown shape/document count/framing limit
  均显式失败，raw diagnostics/stderr/runtime log 以可逐行规范化且可精确重建的
  offset/size/hash/body/ending records 保留。单 case 双侧 comparator 已从两份 raw
  execution 重新投影、可选地双侧规范化，并严格比较 `semantic.comparison`；有序
  RFC 6901 差异携带 presence、双 raw-observation hash 和可复算 fingerprint。
  exact/semantic requirement、10,000 项完整差异上限、projection/limit blocked
  marker 防止失败或旧 report 进入 waiver；single-case auditor 已串联 exact
  waiver application 并复核中间产物；suite runner 已按 hash-bound expected
  matrix 运行并汇总 typed legacy case。engine-only/modern typed variants、
  真实跨平台矩阵和 release approval/signing 尚未完成。
- **关闭**：Phase 1 工具落地并通过测试；每次 release audit applied/stale waivers。

## 5. 风险变更流程

1. 新事实或失败先创建/更新风险，保留原始证据链接。
2. Critical/High 风险若影响架构、依赖、公共接口或兼容偏差，必须创建 ADR。
3. owner 选择 mitigation，并在 roadmap/issue 中安排可执行工作。
4. CI/test 输出只能证明列明的验证项，不能用相邻绿色测试推断关闭。
5. 关闭时填写确切 commit、test/report/artifact；只有设计意图不得关闭。
6. 风险重新触发时改回 Open，并保留历史关闭证据。

`Accepted` 不是“暂时不做”。它必须链接 Accepted ADR，写明 residual impact、用户
可见行为、监控和重新评审触发器。

## 6. Phase 0 风险门禁

Phase 0 不要求所有实现期风险 Closed，但必须满足：

- R-001/R-015 的 runtime 候选失败已被实验记录；ADR 0006 可保持 Proposed，
  acceptance conditions 未满足前不把选型写成已冻结或已兼容。
- R-002 的已知源码/规则/依赖闭包完成初审，无未经核对的导入。
- R-003 的能力矩阵缺口均显式，不把 Source only 写成已兼容。
- R-006/R-007/R-018 有 Windows/Linux static-link spike 和正式设计。
- R-013/R-016 的 commit、subtree、component lock 和 oracle identity 可验证。
- R-020 的默认失败与 waiver 规则完成设计。
- 每个 Critical/High 风险都有 owner、触发、缓解、验证和最晚关闭阶段。

Phase 0 评审可以让风险保持 Open，但不能接受缺少关闭路径或验证证据的风险。

## 7. 当前最高优先级

1. R-001 + R-015：完成 ADR 0006 的完整规则/HostApi、平台和 sanitizer
   acceptance evidence。
2. R-003：关闭 capability matrix 的 Source only/未物化关键证据缺口。
3. R-002：完成规则、关键 bundled code 和候选 runtime 的许可证组合复核。
4. R-016 + R-009：提高 oracle 可重复性并建立 Windows/macOS baseline。
5. R-005：实现前完成有界 nested queue/decompression spike。

优先级变化需要在本表记录原因，不能因为容易实现而绕过 Critical 风险。
