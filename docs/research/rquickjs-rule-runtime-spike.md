# rquickjs/QuickJS-NG 规则运行时技术验证

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Candidate: `rquickjs@0.12.1` / vendored QuickJS-NG 0.15.1

Last updated: 2026-07-30

## 结论

rquickjs 0.12.1 在 Windows MSVC 上可以直接使用预生成绑定构建，并把
QuickJS-NG C 源码编译成静态 archive。它能够：

- 执行 603,640 字节的真实 `Binary/audio.1.sg`；
- 原样执行 `_runtime_helpers`；
- 注册和调用 Rust native function；
- 通过 interrupt handler 中断无限循环；
- 由另一个线程通过原子取消令牌中断无限循环，并在同一 context 中恢复执行；
- Rust native HostApi 长循环通过显式检查同一类 token 合作退出；
- QuickJS VM 与 Rust native HostApi 均可检查 monotonic wall-clock deadline；
- Rust `U24`/`read_uint24` 与 `shru64` 聚焦数值 fixture 匹配固定 Qt 5/Qt 6
  上游 oracle；
- 通过 runtime memory limit 拒绝超限分配，并在同一 context 恢复执行；
- 通过包裹 pinned `RustAllocator` 的 custom allocator 拒绝超限 live heap、
  记录 eval 内瞬时 high-water，并在 runtime 释放后归零；
- 通过 128 KiB runtime stack limit 拒绝无界 JavaScript 递归，并在同一 context
  恢复执行；
- Rust native callback panic 由固定 rquickjs trampoline 在 C ABI 内捕获，在
  Rust eval 边界恢复原 sentinel payload，调用方捕获后同一 context 仍可执行。

但它不能原样作为 DIE 兼容运行时。显式使用 sloppy-script 模式并为语法覆盖提供
受控宿主 proxy 后，2235 个固定规则文件中仍有 1 个执行失败：

```text
db/Binary/format_bin.Nintendo-certified-file.1.sg
Error: invalid redefinition of a variable
```

这是 Boa 0.21.1 拒绝的同一条规则。Qt Script 接受函数内 `var tp` 与后续
`const ..., tp` 的 legacy 行为，而两个现代 ECMAScript runtime 都拒绝。
不能修改上游规则字节来规避它。

rquickjs 的资源控制、较小依赖闭包和较小二进制优于本轮 Boa spike，但引入
vendored C、MSVC/clang/gcc 构建链及 native 安全边界。后续 staticlib spike
已在 Windows `/MD`、Windows `/MT` 和 Linux GNU 三条真实 C 链路中通过，并完成
18-package 许可证初审；详见
[`rquickjs-static-link.md`](rquickjs-static-link.md)。ADR 0006 因此提议把它
作为首个私有 backend，但完整规则/HostApi、macOS 和 sanitizer acceptance
conditions 未完成前仍不冻结为 Accepted。

后续最小实验确认：对唯一失败规则应用 source-identity 约束、等长且不落盘的
compatibility overlay 后，QuickJS 接受该规则；同一 overlay 在 2235 个文件中
恰好命中一次，isolated eval 错误由 1 降为 0。该结果只证明受控兼容层可行，
随后使用 Rust 最小 Byte HostApi，在每个 scan context 中按真实顺序执行 global
`_init`、Binary `_init` 及四个 include，再用 14 个项目生成样本执行
`detect()`；目标 Nintendo detection 与 Qt 5 baseline 14/14 匹配。进一步按固定
Linux Qt5 oracle 顺序在一个 context 中求值 292 条 Binary 顶层代码：原始规则
出现 3 个 legacy lexical 差异，三个精确、等长 overlay 后为 0。per-rule
lexical wrapper 进一步让 292/292 规则仅用 Nintendo overlay 即可求值。

selected lifecycle probe 随后在同一固定全库加载环境中依次调用
`archive_DEFLATE`、`audio_EXA` 和 Nintendo `detect`。它发现前者通过隐式全局
`bad` 为 EA-XA 建立动态前置状态；补齐该调用及目标所需 Byte HostApi 后，PS3 和
PS Vita 的目标完整有序结果与 Qt 5 baseline 14/14 匹配，三个目标调用均未使用
fallback HostApi。全 Binary diagnostic probe 随后逐条尝试了 292 个 `detect`，
首轮有 253 条规则使用缺失 HostApi 代理。按固定上游实现补入基础整数、字符串、
字节数组、size 与 `Util.div64` 后，仍有 233 条规则触发 19 类 fallback；再以
Qt 5/Qt 6 oracle 闭合 `U24`/`read_uint24` 与 `shru64` 后，调用从 387 降至
365、路径从 19 降至 17，但触发规则仍为 233。另有 32 条规则调用 317 种当前
简化 `X.c` 不支持的签名模式。该结果只用于形成缺口清单，不能作为兼容率；
完整宿主方法和跨平台 oracle 仍未覆盖；该事实限制 ADR 0006 的 acceptance，
不能由 static-link 成功替代。

随后 diagnostic HostApi 直接复用隔离的纯 Rust signature spike，实现
`Binary.c`/`compare` 与 `X.c`/`compare`。固定 89-case Qt 5 oracle 中 compare wrapper
路径 7/7 一致，包含严格 `<`、invalid suffix 和负 offset 经
`QString::mid` clamp 到 header 起点的行为。在同一 292-rule probe 中，799 次
compare 均返回或产生已记录 quirk：776 次 header fast path、23 次 generic、
5 次未闭合引号 quirk、0 adapter error；292/292 个 `detect` 无异常完成。
fallback 降到 16 条规则、58 次调用、18 条路径。代理仍可制造真假分支，因此
10 条 detection 仍不是兼容证据。

同一 oracle 又以 4/4 个 wrapper 向量固定 `findSignature`、`fSig` 和
`isSignaturePresent` 的范围裁剪、`size == -1`、别名及布尔投影。接入共享
pure-Rust search adapter 后，固定样本实际执行 11 次搜索（`fSig` 5、
`isSignaturePresent` 6、`findSignature` 0），1 个已记录 quirk、0 adapter
error。真实 `false/-1` 替换 truthy fallback proxy 后改变了后续分支：
compare 增至 1179 次，291/292 条 `detect` 无异常，fallback 为 14 条规则、
39 次、15 条路径。唯一异常 `data_overlays.6.sg` 来自随后抵达的
`isOverlay/getOverlayOffset/getOverlaySize` 缺口，不是签名搜索错误；5 条
detection 仍不构成兼容证据。

固定 oracle 的 3/3 个 overlay HostApi 向量进一步证明 file-part 与 nested
overlay 是两组独立状态。`BinaryHostContext` 接入 `isOverlay`、
`getOverlayOffset/Size` 和 `isOverlayPresent` 后，当前 top-level header 只执行
2 次 `isOverlay`，均为 false，另外三个方法因规则短路未调用。结果恢复为
292/292 无异常；fallback 为 12 条规则、34 次、11 条路径，未记录 fallback
规则为 280。短路又使 compare 从 1179 变为 1109；4 条 detection 仍不构成
兼容证据。该输入不证明 PE/ELF 等格式 context 或实际 overlay subdevice 的构造。

固定 oracle 再扩展 15 个字符串 context 向量并全部匹配；接入后缀、header、
plain/UTF-8 API 后，292/292 仍无异常，fallback 降为 3 条规则、4 次、4 条路径，
未记录 fallback 规则为 289。上游未初始化的 Unicode-text 布尔值未被伪装成
确定性 Rust 事实。最后 3 个 scan ID/resource/debugdata context 与 4 个
构造前 storage prefill 向量固定剩余源码行为；Rust 按 ADR 0005 显式初始化文本
facts，并接入 `getScanID`、`isResource`、`isDebugData`、`isFilePart`、
`isUnicodeText` 和 `isText`。固定 292-rule trace 达到 292/292、0 异常、
0 fallback，仍只产生同一条 Nintendo detection；这只闭合该样本的实际调用路径，
不等于全规则兼容。随后固定 Qt5 harness 与 Rust 又对三条原样上游规则执行
8/8 个 resource/debugdata/text context 差分，三条正例的完整 detection 四元组
和五条 gate 反例全部一致。

在此基础上，`verify-binary-corpus` 已对 14 个项目生成 Nintendo 样本分别创建
完整 scan context，并逐样本调用全部 292 个 Binary `detect`：合计 4088/4088
次无异常、0 fallback，产生的 21 条结果按固定
`XScanEngine::typeToPrio()`/`sortRecords()` 语义排序后，type/name/version 与
双 Linux Qt5 CLI baseline 14/14 一致；14 条 Nintendo `info` 均为 `fSELF`。
Vita 的实际规则执行顺序是 audio→format，而上游输出顺序是 format→audio，
因此本轮也替换了此前仅对两种目标类型硬编码的投影。多结果样本的优先级均互异；
上游 `std::sort` 对同优先级没有稳定顺序契约，该边界仍明确拒绝外推。

同一命令在 Windows x86_64 MSVC release profile 连续运行三轮；每轮 14 个
runtime 的稳定计量投影逐字节等价，SHA-256 均为
`286e778c3891dd3b289446526f2910601f9e25932feec25489ee74adbcc5c326`。
每轮正常生命周期共触发 28 次 QuickJS-NG interrupt callback，其中 9 次发生在
`detect` 内、19 次发生在 init/include/诊断辅助边界，每规则最大 1 次。Binary
签名 HostApi 同时按“每次 compare/search 入口一次，之后每扫描 4096 个候选位置
一次”记录原生协作检查点；每轮固定 16,439 次，其中 compare 16,285 次、search
154 次。因为本语料的搜索区间都未达到第二个检查点，三项恰好等于 HostApi
调用数；独立边界测试另证明第 4096 个候选位置触发第二次回调，且该回调能在
单次 native search 尚未返回时产生显式 `Interrupted`。每轮
4,130 个 `Runtime::memory_usage()` checkpoint 的最大 `malloc_size` 为
654,562 bytes，最大 `memory_used_size` 为 623,012 bytes，均出现在
`ps3-type-1-elf.self`。checkpoint 在 runtime 创建、init、每条规则返回后和最终
报告边界采集，不能观察 eval 内部瞬时 allocator high-water。

为闭合这个观测缺口，`verify-binary-corpus-tracked-heap` 使用包裹 pinned
`RustAllocator` 的 `TrackingLimitAllocator` 重跑完全相同的 14 个样本与
4088 次 `detect`。每个样本 runtime 独立设置 32 MiB live allocation
`Layout`-byte 硬上限；
三轮仍为 14/14 oracle 匹配、4088/4088 无异常、0 fallback、0 allocation
rejection，且全部 42 个 runtime 在 drop 后 live bytes 归零。三轮稳定投影
SHA-256 均为
`c455f6932322ff8161a4f6c9288710b5ed792ff5486b4459e11ef27e794e45c4`，
并由独立 canonical JSON 实现重算一致。最大瞬时 high-water 为
4,478,992 bytes，仍出现在 `ps3-type-1-elf.self`。

该数字统计 `RustAllocator` 实际 `Layout` bytes：8-byte 对齐后的 payload 加
`max(sizeof(usize), 8)` internal header；QuickJS 所需的 `usable_size()` 仍只
返回 payload。它不等于进程 RSS。该计费避免每个 live allocation 漏掉 header，
并证明 Windows x86_64 MSVC 上这个候选 custom allocator 能在完整 Binary 语料
路径中同时执行硬限制与瞬时观测；不证明默认 libc allocator 的 high-water，也
不替代 Linux/macOS、sanitizer 或更广规则/格式语料验证。

另一个独立实验 `eval-isolated-compat-tracked-heap` 将固定 `db` 与 `db_extra`
中的全部 2,235 个程序文件（2,902,881 source bytes）在同一个 custom-allocator
runtime 内逐个建立隔离 realm、执行顶层 parse/eval，并应用已锁定的一处
Nintendo overlay。Windows x86_64 MSVC release 连续三轮均为 2,235/2,235
接受、0 allocation rejection，runtime drop 后 live bytes 归零；三轮稳定投影
及独立 JSON 哈希都等于
`582d5af0995925fa9c2188a38d999e0bcb3373b91fe22510798786828cbc5f58`。
瞬时 high-water 为 3,486,384 bytes，drop 前仅保留 171,272 live bytes。
这闭合“全规则源码 parse/eval 没有瞬时 heap 观测”的缺口，但没有调用
`detect`，也没有复刻各 file type 的上游顺序、include 生命周期或真实 HostApi，
所以不能替代 Binary oracle 或七类代表性差分。

为避免只观察 Binary 全规则生命周期，本轮又复用已通过 Qt5 差分的 PE、ELF、
Mach-O、DEX、APK、Archive 和 PDF 七条原样上游规则。七类代表性格式规则共
25 个 case，每个 case 使用独立 runtime，并在 runtime 创建、HostApi/结果 shim
初始化后、规则返回后采集三个 memory snapshot。Windows x86_64 MSVC release
连续三轮均为 25/25 oracle 匹配、每 case 恰好 1 次正常 QuickJS-NG interrupt
callback，因此每轮合计 25 次 callback 和 75 个 memory checkpoint；七份完整
canonical JSON 报告各自三轮相同。全矩阵最大 `malloc_size` 为 124,485 bytes，
最大 `memory_used_size` 为 113,926 bytes，均出现在 Archive
`verbose_stored_zip` 的 `after_rule` 阶段。

七个 `-tracked-heap` 变体又在完全相同的 25 个 case 上执行 32 MiB custom
allocator hard limit。三轮均为 25/25 oracle 匹配、0 allocation rejection，
共 75/75 runtime drop 后 live bytes 归零；每类完整 canonical 报告在三轮间
分别相同。全矩阵最大瞬时 high-water 为 134,792 bytes，出现在 Mach-O
`rust_macho64_x86_64_entry_point_match`。各类最大值为 PE 129,176、ELF
129,392、Mach-O 134,792、DEX 129,136、APK 129,160、Archive 130,560、
PDF 131,704 bytes；逐类 stable report SHA-256 记录在机器证据中。

该矩阵证明同一探针在七类既有格式差分上的确定性和代表性量级，不是所有格式或
全部固定规则的 runtime scaling。每个 case 只执行一条短规则，观察到的“一次
poll”不能转换为 VM instruction 数。tracked 结果补齐了这些代表性 case 的
瞬时 allocator high-water，但不能替代全部格式/规则的 full lifecycle、
production backend、sanitizer 或跨平台测量。

## 实验边界

验证程序位于
[`spikes/rquickjs-rule-runtime/`](../../spikes/rquickjs-rule-runtime/)，是
Phase 0 隔离 spike，不属于未来 Cargo workspace 或正式 API。机器可读摘要位于
[`data/rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json)。

rquickjs 的安全高层 `EvalOptions` 没有 compile-only 选项；底层
`JS_EVAL_FLAG_COMPILE_ONLY` 只由 raw FFI 暴露，直接使用会引入 `unsafe`。
因此本实验执行脚本而不是只解析 AST。为了把缺失 30 个格式宿主对象与语法错误
分开，实验显式安装：

- `meta` 和 `includeScript`；
- 30 个固定格式名的无副作用 callable proxy；
- 上游无扩展规则依赖的初始 `bBorlandC = 0`。

proxy 只用于语法/顶层执行覆盖，不代表宿主 API 兼容，也不能证明检测结果正确。
每文件设置 1,000,000 次 interrupt-handler callback 上限，避免未来规则变更
导致无界执行。

custom allocator 需要实现 rquickjs 的 `unsafe Allocator` trait。spike 将
`unsafe` 限制在 `tracking_allocator.rs`：所有 pointer 创建、realloc、释放和
layout metadata 仍委托给 pinned `RustAllocator`；wrapper 只在 allocation
存活期读取 `usable_size`，再加上 pinned source 定义的 header，检查投影 live
`Layout` bytes 并更新原子计数。超限 realloc 在委托前返回 null，保留原
allocation 所有权；calloc 乘法、alignment rounding 和 allocator header 加法
均先检查溢出。单元测试固定“精确 limit 成功、limit−1 拒绝、最大 payload+1
因对齐越界而拒绝”，并验证 denied realloc 不改变原 allocation/accounting。
该模块仍是候选实现，需要 sanitizer 与跨平台验证后才能进入正式 backend。

## 构建与依赖

| 项目 | 值 |
| --- | --- |
| Host OS/target | Windows amd64 / `x86_64-pc-windows-msvc` |
| Default Rust | 1.86.0，候选明确拒绝 |
| Spike Rust | 1.88.0 |
| rquickjs | 0.12.1，`default-features = false`，仅 `std` |
| rquickjs-sys | 0.12.1，crate checksum 固定于 `Cargo.lock` |
| sha2 | 0.10.9，仅用于 spike 输入/基线 identity 验证 |
| Vendored engine | QuickJS-NG 0.15.1 |
| Lockfile packages | 34 |
| 当前 target packages | 28（`cargo metadata --filter-platform x86_64-pc-windows-msvc`） |
| Clean release build | 13,258 ms（adapter 前记录，本机已缓存下载、空 target） |
| Release executable | 2,515,968 bytes（Rust 1.97.1）；2,536,960 bytes（Rust 1.88.0） |

`cargo +1.86.0 check --locked` 明确报告
`rquickjs@0.12.1 requires rustc 1.87`。本实验继续复用已安装的 1.88 工具链。

`rquickjs-sys` 的 `build.rs` 编译 `libregexp.c`、`libunicode.c`、`quickjs.c`
和 `dtoa.c` 为 `libquickjs.a`；Windows MSVC 不需要运行时 QuickJS DLL，但
构建不再是纯 Rust。crate 内含 QuickJS-NG 的 MIT `LICENSE` 和 MSVC patch。

当前 Windows target 的 28 个 package 都有许可证表达式，涉及 MIT、
Apache-2.0、BSL-1.0、Unlicense 和 Zlib 组合。这是 metadata 初筛，不替代
发布前的源码、patch、NOTICE 和二进制归属审计。

## Sloppy-script 要求

rquickjs 0.12.1 的 `EvalOptions::default()` 会强制 strict mode。直接使用
`Ctx::eval()` 时，真实 `audio.1.sg` 在以下语句失败：

```javascript
msg = decEncoding(msg_,'CP437'); delete msg_;
```

显式设置 `EvalOptions.strict = false` 后规则正常加载，fixture 得到：

```text
audio||chunkparsers,soundchips,bytecodeparsers|function
```

因此未来 adapter 不得依赖 rquickjs 默认 eval 选项；sloppy/global script
语义必须成为有回归测试的显式配置。

## 全库 isolated eval

选择口径与 Boa spike 完全一致：递归读取 `db` 和 `db_extra` 中 `.sg` 及无
扩展名文件。

| 指标 | 值 |
| --- | ---: |
| Files | 2235 |
| Bytes | 2,902,881 |
| Eval errors | 1 |
| Observed elapsed | 约 1.38 秒 |

唯一错误是 Nintendo 规则的 `var`/`const` 重定义。未安装格式 proxy 时共有
39 个错误，其中 38 个是预期的宿主对象或跨规则状态缺失，1 个才是语法错误；
这也是为什么报告必须明确区分“原始规则兼容”和“host shim 完整度”。

## Shared realm 信号

把同一批文件按规范化路径顺序放入一个 QuickJS context，得到 3 个错误：

- Nintendo `invalid redefinition of a variable`；
- `Binary/__MiniExtensionsHeuristic_By_DosX.7.sg` 的 `detect` 重声明；
- `db/bytecodeparsers` 的 `debug` 重声明。

shared realm 结果明显不同于 Boa 的 parse-only 2021 个错误，但这个数字同样不是
真实兼容率。上游会按格式、优先级、include 和扫描阶段管理脚本；本实验的全路径
排序会把本不应共享同一规则槽位的脚本放在一起。该结果只证明 QuickJS 的 global
lexical 状态必须按真实生命周期验证，不能据此选择“每规则 context”或“全库单
context”。

## Runtime fixture

稳定断言包括：

- `hostAdd(20, 22)` 返回 `"42"`；
- `_runtime_helpers` 返回 `a, b/c|007`；
- `Binary/audio.1.sg` sloppy eval 成功；
- Nintendo 规则 eval 失败；
- Nintendo 原始文件保持 SHA-256
  `1f7485b8b0c9c211932fdcc31529ea37588c176e46a1ff06230fc376df5ad0f5`，
  compatibility overlay 后 eval 成功且 evaluated length 不变；
- 两次 eval 同名 `const` 时第二次失败；
- 17 次 handler callback 后无限循环返回 `Error: interrupted`；
- 外部线程在 handler 首次被调用后设置原子取消标志，无限循环返回
  `Error: interrupted`，百万次 handler 硬停止兜底未触发；
- 重置取消标志后，同一 runtime/context 求值 `String(40 + 2)` 返回 `"42"`；
- `cooperativeHostLoop()` 在外部 token 请求后正常返回，未达到 1,000,000 次
  native 检查点硬上限；
- QuickJS VM 与 native HostApi 的 25ms deadline 均到期、未触发各自硬上限，
  清理后各自 context 都返回 `"42"`；
- 4 MiB runtime limit 拒绝 16 MiB `ArrayBuffer`，返回 `out of memory`，随后
  同一 context 求值 `String(6 * 7)` 返回 `"42"`；
- 128 KiB runtime stack limit 使无终止递归返回
  `Maximum call stack size exceeded`，随后同一 context 求值
  `String(6 * 7)` 返回 `"42"`；
- `panicHost()` 的固定 Rust panic payload 在 eval 调用方被 `catch_unwind`
  捕获，payload 未改变，随后同一 context 求值 `String(6 * 7)` 返回 `"42"`。

原有 4 MiB fault fixture 使用 rquickjs 默认 libc allocator。官方 API 说明
使用 `rust-alloc` 或自定义 allocator 时 `set_memory_limit` 是 no-op，因此
tracked-heap 实验不调用它，而由 wrapper 自身执行 4 MiB/32 MiB hard limit。
4 MiB custom-allocator fixture 拒绝一次 16 MiB `ArrayBuffer`，报告明确
`out of memory`，同一 context 随后返回 `"42"`，runtime drop 后 live bytes
为 0。

pinned `rquickjs-core 0.12.1/src/runtime/base.rs` 还记录默认 VM stack 为
`256 * 1024` bytes，并公开 `memory_usage()`/`JS_ComputeMemoryUsage`。当前机器
报告已在三轮真实 Binary corpus 生命周期汇总正常 interrupt poll，并保存 4,130 个
post-operation memory checkpoint；但 handler callback 不是 JS instruction，
默认 allocator checkpoint 仍不是 eval 内瞬时 heap high-water。custom
allocator 已在本机完整 Binary 语料中测得 4,478,992-byte high-water，但它仍是
单平台、单候选 backend 的观测值；4 MiB fault/128 KiB stack/25 ms deadline
只证明故障注入与恢复接线，不能直接充当 production heap、stack、fuel 或
deadline 候选的最终预算。

stack fixture 使用显式递归函数而不是 include graph，因此只证明 QuickJS-NG
`set_max_stack_size` 对脚本调用栈生效且 exception 后 context 可恢复。它不替代
固定 Qt include-cycle 的深度、signal 数或错误传播差分；正式 runtime 仍按
ADR 0010 在进入 VM 前拒绝 active include cycle，并将 VM stack limit 作为末级
资源防线。

### Native callback panic 边界

固定 `rquickjs-core 0.12.1` 的普通 callback trampoline 通过
`Ctx::handle_panic_inner` 在 Rust→C→Rust 回调入口捕获 unwind，把 payload 保存到
runtime opaque 并向 QuickJS 返回 exception tag；`Ctx::handle_exception` 在控制流
回到 Rust eval 边界后取回 payload 并 `resume_unwind`。fixture 在 eval 调用方用
`catch_unwind` 捕获固定 sentinel，并临时替换/恢复 panic hook，避免已捕获的预期
panic 污染命令 stderr。

因此观察到的 panic 没有跨越 C ABI，也没有被伪装成普通 JavaScript exception。
这只证明 pinned rquickjs 的普通 `Function` callback 路径；正式 backend 仍必须
在自己的 HostApi adapter 与最外层 scanner/FFI 边界分别测试 panic 分类、状态清理
和恢复，native crash/abort 不能由 Rust unwind 防护捕获。

### 外部取消与恢复

fixture 不用固定 sleep 猜测脚本是否已经开始。外部 worker 先等待 QuickJS
interrupt handler 至少执行一次，再以 `Release` 写入共享 `AtomicBool`；handler
以 `Acquire` 读取并返回取消状态。handler 还保留 1,000,000 次回调的独立硬停止，
使取消同步发生回归时实验仍有上界。worker 只写原子状态，不访问 runtime/context；
QuickJS 仍只在创建它的线程中执行。

首次运行在 5 次 handler callback 后观察取消。随后同一 release binary 重复运行
10 次，全部满足 requested=true、hard-stop=false、recovery=`"42"`；回调次数为
6..12。该次数受 OS 调度影响，不进入稳定兼容断言。机器基线只固定：

- 外部取消确实被请求并产生 interrupted error；
- 百万次硬停止不是本次退出原因；
- 清除取消标志后同一 context 可继续执行。

复现单次稳定断言：

```sh
cargo +1.88.0 run --release --locked -- fixture \
  ../../upstream/Detect-It-Easy/db
```

这证明 rquickjs interrupt handler 可以桥接线程安全的外部取消 token，并证明
JavaScript exception 不必污染后续同 context 求值。它不证明 wall-clock deadline
精度，也不能自行中断一个长期阻塞且不返回 QuickJS VM 的 Rust/native HostApi
调用。

### Native HostApi 合作取消

第二个 fixture 把 Rust `cooperativeHostLoop()` 注册到独立 QuickJS context。
函数先以 `Release` 标记已经进入 native 调用，然后在循环中：

1. 增加本地迭代计数；
2. 以 `Acquire` 检查外部取消 token；
3. 未取消时 `yield_now()`，并在 1,000,000 次检查点强制退出。

worker 只在 native 函数已进入后请求取消；若 JavaScript 在调用前失败，独立
finished 标志会使 worker 正常退出。首次运行在 1,285 次检查点返回。随后同一
release binary 重复 10 次全部满足 requested=true、returned=true、
hard-stop=false，迭代数为 200..1,511。迭代数由调度决定，不进入稳定机器断言。

该实验关闭“Rust HostApi 可否共享 scan cancel token 并有界合作退出”的可行性
问题，但不允许把所有 native 调用视为天然可取消。正式 HostApi 必须把
token/deadline 传入可能长时间运行的 signature、字符串搜索、解压和遍历循环；
一次不可分割的阻塞系统/native 调用仍不能由 QuickJS interrupt 抢占。

### 真实 Binary signature HostApi 检查点

相邻 pure-Rust signature spike 为 Binary compare/search wrapper 增加显式
checkpoint callback。callback 在 HostApi 入口执行一次；所有由不可信输入搜索
范围放大的 exact、SigByte 和 control fallback 候选循环共享同一计数器，并在
第 4096、8192……个候选比较前再次执行。callback 返回 false 时以
`MatchError::Interrupted` 退出，不把取消伪装成 mismatch。原有无 callback API
仍使用恒为 true 的适配器，因此 oracle 行为不变。

边界回归固定三件事：短 compare 只有一个入口 checkpoint；4095 个候选的无匹配
搜索只有一个 checkpoint，4096 个候选精确触发两个；在第二个 callback 返回
false 时，同一 native search 在完成前返回 `Interrupted`。随后 14-sample
full Binary corpus 三轮均记录 16,439 次，compare/search 分区均为
16,285/154，且兼容结果和 runtime 稳定投影三轮相同。这证明 Binary signature
路径的确定性检查点接线与正常工作量计量，不证明其他字符串、解压、遍历或格式
HostApi 已覆盖，也不能由这些短搜索样本推导跨格式 fuel。

### Monotonic wall-clock deadline

VM fixture 不从 runtime/context 创建时开始计时，而是在 interrupt handler 首次
真正被调用时记录 `Instant`，25ms 后返回 interrupt。这样初始化开销不会制造
“进入脚本前已超时”的假阳性。handler 仍有 1,000,000 次回调硬停止；deadline
退出后移除 handler，同一 context 求值返回 `"42"`。

native fixture 在调用前配置绝对 `Instant`，`deadlineHostLoop()` 每个检查点比较
`Instant::now()`，同时保留 10,000,000 次迭代硬上限。到期返回后，同一 context
也能继续求值。首次 VM/native 分别观察到 1,453 次 handler callback 和 238,867
次 native checkpoint。随后重复 10 次：

| 路径 | deadline | 观察范围 | deadline 到期 | 硬上限触发 | 恢复 |
| --- | ---: | ---: | --- | --- | --- |
| QuickJS VM | 25ms | 969..1,449 callbacks | 10/10 | 0/10 | 10/10 |
| Rust native HostApi | 25ms | 135,108..253,895 checkpoints | 10/10 | 0/10 | 10/10 |

callback/checkpoint 数量取决于 CPU 和调度，不进入稳定机器契约。稳定断言只固定
deadline duration、确实到期、预期 interrupt/return、硬上限未触发和 context
恢复。该实验证明 monotonic deadline 接线可行，不冻结 25ms 为产品默认值，也不
证明任意平台的最大取消延迟；真实方法的 checkpoint 密度仍需逐项 benchmark。

## Nintendo compatibility overlay 实验

唯一失败规则长 1994 bytes，原始 SHA-256 如上。问题声明是：

```javascript
var tp, e;
// ...
const attr = X.U16(8, e), tp = X.U16(0xA, e), /* ... */;
```

静态检查确认第一个 `tp` 在 lexical `const tp` 之前没有读取。spike 新增
`nintendo-unused-var-tp-v1`，只在 normalized path、1994-byte 长度和唯一精确
declaration 同时匹配时，把传给 runtime 的等长副本改为：

```javascript
var     e;
```

上游文件不写入、不格式化；测试从固定 subtree 重新计算原始 SHA-256。命令自身还
检查 path、size 和唯一 declaration，任何漂移都拒绝 overlay。正式实现若采用类似
方案，必须在加载 manifest 时先做 cryptographic hash check，不能只依赖字符串
匹配。

结果：

| 模式 | Files | Bytes | Overlay 命中 | Errors |
| --- | ---: | ---: | ---: | ---: |
| 原始 isolated eval | 2235 | 2,902,881 | 0 | 1 |
| isolated + overlay | 2235 | 2,902,881 | 1 | 0 |

这个 overlay 删除未使用的 function-scoped `var tp`，没有改 lexical `const tp`
及后续引用。它仍只是语法/顶层 eval 证据。关闭兼容门禁还需要：

- 使用已建立的
  [`Nintendo Certified File 行为基线`](nintendo-certified-rule.md)
  覆盖各 `switch(tp)` 分支；
- 在固定 Qt 5/Qt 6 oracle 和 QuickJS host adapter 中比较 detect/result；
- 证明 source location/diagnostic mapping 在等长 overlay 后保持准确；
- 验证真实规则加载生命周期中 overlay 只应用一次；
- 用 ADR 决定 runtime patch、source overlay 或其他方案。

### Rust Byte HostApi detect 对照

spike 的 `detect-nintendo` 命令为每个样本创建独立 QuickJS runtime/context，
用 Rust 注册：

```text
X.c U16 U32 U64 Sz isHeuristicScan isVerbose
_setResult
```

随后在同一 context 中原样 eval root `_init`，由真实 `includeScript()` registry
依次求值 `_debug`、`_runtime_helpers`、`language`；再 eval Binary `_init` 并
include `read`。最后 eval overlay 后的 Nintendo 规则并调用 `detect()`。它从
[`nintendo-certified-baseline.json`](data/nintendo-certified-baseline.json)
读取 Qt 期望的第一条 detection，并额外固定 `info = fSELF`。

14 个样本的 type/name/version/info 全部匹配，包括：

- big/little endian；
- type 1 ELF/headerless；
- type 2–6；
- U+014D 名称；
- PS3/PSVita version。

专项 runtime 只支持规则实际请求的四种 `X.c` pattern，未知 pattern 明确返回
false；init 和 helper 都是上游原始 JavaScript。该结果证明了 init/include
生命周期的最小可行路径，但没有执行完整 Binary signature sequence。下一节的
selected lifecycle probe 单独覆盖 EA-XA 邻接结果。

### 固定全库加载下的 selected lifecycle

`detect-nintendo-lifecycle` 为每个样本创建独立 context，执行 global/Binary
init，按固定 Linux Qt 5 清单用 per-rule lexical wrapper 加载 292 条规则，并
完成 30 次真实 include。它只调用三条经过选择的规则：

```text
archive_DEFLATE.1.sg
audio_EXA.1.sg
format_bin.Nintendo-certified-file.1.sg
```

最初只调用 EA-XA 与 Nintendo 时，Vita 样本以 `bad is not defined` 失败。源码
和动态 trace 显示 `archive_DEFLATE.detect()` 会无条件创建隐式全局 `bad`，
`audio_EXA.detect()` 随后读取并更新它。因此 probe 按固定执行顺序加入该前置
调用。这是顶层持久状态 AST 审计没有覆盖的跨 `detect` 动态依赖。

为加载非目标规则顶层代码，probe 安装可追踪、链式 HostApi fallback；实际调用
仅来自 `shell-script` include 的：

```text
Binary.getString
Binary.getString.replace
Binary.getString.replace.match
```

每个选定 `detect` 前后都比较 fallback call count，任何新增调用立即使实验失败。
三条目标规则的 fallback 增量均为零。目标 Byte HostApi 在原 Nintendo 集合上
补充 `U8`、`SA`、默认 little-endian 的可选 endian 参数、`isDeepScan`、
`Util.shlu64` 和 EA-XA 所需的 `'SC'` signature pattern。`SA` 的 NUL 截断和越界
行为有本地单元测试，但本轮没有用独立 Qt fixture 隔离证明其完整语义。

14 个样本全部匹配 Qt 5 machine baseline。PS3 只产生 Nintendo `format`；Vita
按规则调用时间产生 `audio`、`format`，按当前目标输出投影得到 `format`、
`audio`，与 Qt 输出一致。该投影只覆盖这两种目标结果，不能外推为完整上游结果
排序模型。所有 Nintendo `info` 仍为 `fSELF`，每个样本的 overlay 命中数为 1。

本实验加载了全 292 条规则，但只执行三个 `detect`；它不等同于“完整 Binary
signature sequence 通过”。

### 全 Binary detect 缺口诊断

`trace-binary-detects` 在同样的固定 Linux Qt 5 顺序、共享 host/global context
和 per-rule lexical wrapper 下逐条调用全部 292 个 `detect`。输入固定为项目
生成的 128-byte `ps3-type-2-revoke-list.self`：

```text
SHA-256 499c269ca6a0be20f48480b1ed766e5d8f448c5a4a8facdff9335b7c1b0a994e
```

诊断代理会记录缺失 `Binary`/`Util` 方法的实际调用路径，每条规则最多保存 256
条路径，同时单独累计总调用数；本次没有规则触发截断。每条规则还独立记录异常、
interrupt handler 调用、返回值和新增 detection，异常后继续下一条。

基础方法的别名、宽度、符号与 endian 行为来自固定
[`binary_script.cpp`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.cpp)
和
[`binary_script.h`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.h)；
`Util.div64` 的零除数 `-1` 行为来自固定
[`util_script.cpp`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/util_script.cpp)。
本轮实现 `Sz/getSize`，8/16/32/64-bit 有/无符号读取、unsigned 24-bit 读取及
其上游别名，
`SA/getString/read_ansiString`、`BA/readBytes`、`Util.div64` 和聚焦范围的
`Util.shru64`。越界字符串和字节数组按可用输入截短；负 offset/size 安全返回
空值或零。

首次执行暴露了 Rust 绑定自身的边界错误：`format_bin.COL.1.sg` 在 `p == 0` 时
按规则设计调用 `X.U8(p - 1)`，原来的 `usize` 参数在进入 HostApi 前产生
Underflow。将字节读取偏移改为有符号输入，并让负值安全返回越界默认值后，该规则
不再异常；这也是“不可信 offset 必须在宿主内部验证，不能依赖 Rust 参数转换”的
直接证据。

基础方法及 numeric oracle 增量前后的摘要：

| 指标 | 补入前 | 基础读取后 | `U24`/`shru64` 后 | `c`/`compare` 后 | search/presence 后 | overlay context 后 | string context 后 | execution context 后 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Attempted `detect` | 292 | 292 | 292 | 292 | 292 | 292 | 292 | 292 |
| 无异常返回 | 281 | 285 | 285 | 292 | 291 | 292 | 292 | 292 |
| 异常 | 11 | 7 | 7 | 0 | 1 | 0 | 0 | 0 |
| 调用 fallback 的规则 | 253 | 233 | 233 | 16 | 14 | 12 | 3 | 0 |
| Fallback 调用 | 496 | 387 | 365 | 58 | 39 | 34 | 4 | 0 |
| 唯一 fallback 路径 | 34 | 19 | 17 | 18 | 15 | 11 | 4 | 0 |
| 未记录 fallback 的规则 | 39 | 59 | 59 | 276 | 278 | 280 | 289 | 292 |
| 未记录 fallback 且异常 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 代理影响下产生的 detections | 122 | 153 | 153 | 10 | 5 | 4 | 1 | 1 |

`U24`/`shru64` 后的 7 个异常仍是诊断代理值或非字符串值进入结果边界；接入
compare 后这些分支不再触发异常；search/presence 的真实假值又让 overlay
分支暴露一个后续缺口；显式 overlay context 随后闭合该异常。完整历史快照和
该阶段剩余的 11 条路径保存在
[`rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json)。

固定源码与扩展到 89-case 的 Qt5 wrapper oracle 随后闭合文件名/文本上下文：
`BinaryStringContext` 按上游不同采样上限计算 plain、UTF-8 和 UTF-16 facts，
保留无 BOM UTF-8 仍跳过 3 bytes、无 BOM UTF-16 端序反向等可观察行为；路径
后缀按 Qt 最后点号语义且保留大小写。接入 `getFileSuffix`、
`getHeaderString`、`isPlainText` 和 `isUTF8Text` 后，固定样本分别调用
9、5、2、0 次，292/292 无异常；fallback 降至 3 条规则/4 次，只剩
`getScanID`、`isDebugData`、`isResource` 和 `isText`。后者依赖上游构造器未
初始化的 `m_bIsUnicodeText`。真实字符串返回值改变控制流后只产生 1 条
Nintendo detection。

新增 3/3 个 execution context 用例固定 `getScanID`、resource/debugdata
file-part 和 `isFilePart`；4/4 个 prefill 用例证明非 Unicode 的
`isUnicodeText/isText` 随构造前 storage 改变，而 UTF-16 分支稳定覆盖字段。
Rust 按 [`ADR 0005`](../design/decisions/0005-deterministic-text-classification.md)
使用显式确定性 facts，不复制未初始化读取。接入六个 native HostApi 后，
`debug_data_debugData.1.sg` 调用 `isDebugData` 1 次，`win_resources.1.sg`
调用 `isResource` 1 次，`format_DESKTOP.1.sg` 调用 `isText` 1 次；三个值均为
false，短路使 `getScanID`、`isFilePart` 和 `isUnicodeText` 在此样本上为 0 次。
292/292 无异常且 fallback 为 0；compare 因 `isText=false` 的短路从 1109 降为
1105，search 保持 11，检测仍为同一条 Nintendo result。它仍是单样本缺口诊断，
不是全规则兼容证据。

### 全 292 条规则的固定语料 oracle

`verify-binary-corpus` 复用上述同一全规则 trace，但不再把检测结果作为代理影响下
的诊断输出。它先按
[`nintendo-certified-corpus.json`](data/nintendo-certified-corpus.json)
逐项验证 14 个生成输入的 size/SHA-256，再为每个样本重新创建 runtime/context，
依次执行 global/Binary init、30 次 include 和固定 Linux Qt5 顺序的 292 个
`detect`。任一样本出现规则异常、HostApi fallback、overlay 数量漂移、include
数量漂移、signature compare/search adapter error 或输入哈希漂移都会使命令
失败。corpus manifest 与 baseline 文件本身也绑定固定 SHA-256；292 个顺序名称
重新按 UTF-8/LF canonical 形式计算 hash，不只信任 JSON 中自报的字段。输入在
校验后以同一字节缓冲进入 HostApi，避免“校验一次、执行时再读一次”的 TOCTOU
窗口。

结果为：

| 指标 | 值 |
| --- | ---: |
| 样本 | 14 |
| `detect` 尝试/成功 | 4088 / 4088 |
| `detect` 异常 | 0 |
| HostApi fallback | 0 |
| 结果记录 | 21 |
| Signature compare/search | 16,285 / 154 |
| Baseline 匹配 | 14 / 14 |
| 正常 interrupt callback（每轮） | 28 |
| `detect` 内 callback（每轮） | 9 |
| Memory checkpoints（每轮） | 4,130 |
| 最大 observed `malloc_size` | 654,562 bytes |
| 最大 observed `memory_used_size` | 623,012 bytes |

结果排序不再使用 `format, audio` 特例。固定
`XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83` 的
`typeToPrio()` 给每条结果赋 `nPrio`，`sortRecords()` 调用 `std::sort`，比较器
`_sortItems()` 只比较数值优先级。Rust probe 复制该优先级映射，并仅在一个样本的
所有结果优先级互异时把有序结果作为证据；否则明确判失败，因为上游同优先级的
`std::sort` 次序没有稳定契约。本语料中 PS3 每例一条 `format`，Vita 每例一条
`format`（优先级 12）和一条未知类别 `audio`（优先级 1000），所以 14 个样本的
排序证据均无 tie。

比较范围是双 upstream CLI baseline 保存的完整有序 type/name/version，以及
Nintendo 规则已固定的 `info == "fSELF"` 不变量。EA-XA 的空 info 被保留在 Rust
原始四元组诊断中，但现有 upstream baseline 没有保存该字段，因此不把它写成已
完成的上游 info 差分。该实验覆盖 14 个短 Binary header，不覆盖其他格式、
file-part、扫描选项或 292 条规则各自的正例；14/14 不能改写为“全规则兼容率”。

### Resource、debugdata 与 text 真实规则差分

静态规则清单确认：

- `Binary.getScanID/isResource` 只由
  `win_resources.1.sg` 调用；
- `Binary.isDebugData` 只由 `debug_data_debugData.1.sg` 调用；
- `Binary.isText` 只由 `format_DESKTOP.1.sg` 调用；
- `X.isFilePart` 只存在于 profiling helper 的延迟方法体，本轮三条规则不调用。

项目生成的
[`context_rule_harness_main.cpp`](../../tools/upstream/context_rule_harness_main.cpp)
在固定 Qt Script 5.15.13 中注册未修改的 `Binary_Script`，加载上述三条规则前
逐一验证原始 bytes 的 SHA-256，不加载改写版本。它使用内存 `QBuffer` 构造
8 个上下文：

| 类别 | 正例 | 反例 |
| --- | --- | --- |
| Resource | `FILEPART_RESOURCE` + scan ID `24` → `format / Manifest / "" / Resources` | 未知 ID；相同 ID 但 header file-part |
| Debug data | `FILEPART_DEBUGDATA` + `RSDS` → `debug data / PDB file link / 7.0 / ""` | 相同 bytes 但 header file-part |
| Desktop text | ASCII `[Desktop Entry]\n` → `format / Desktop Entry (.desktop) / "" / ""` | plain text 缺 marker；binary bytes |

Qt5 原始输出保存在
[`context-rule-qt5.json`](data/context-rule-qt5.json)，SHA-256 为
`8ccb15372bf6272f1c90356664208b12e096c9cb9430b63cd1573a99b6972c03`。
probe 对 case inventory、detect 布尔值、完整 detection 四元组、规则错误和
`Binary_Script` diagnostic 做强断言。Rust 使用同一规则 bytes、相同 context
facts 和同一 baseline 端到端执行，8/8 一致；没有为测试重写规则。

该差分证明显式 Rust context 足以重现三条规则在已给定 subdevice/text facts 后的
行为，但不证明上游 scanner 如何从 PE 等父对象枚举 resource/debugdata、如何
生成 scan ID、如何排序子扫描，或何时调度这些规则。这些仍属于扫描编排与嵌套
语料差分范围。

复现：

```sh
docker --context=default buildx build \
  --load \
  --provenance=false \
  --file tools/upstream/Dockerfile.context-rule-harness-qt5 \
  --tag diec-rust/upstream-context-rule-harness:74eaf505 \
  tools/upstream

python tools/upstream/probe_context_rule_harness.py \
  --docker-context default \
  --image diec-rust/upstream-context-rule-harness:74eaf505 \
  --binary /opt/die-build/src/console/diec-context-rule-harness \
  --baseline docs/research/data/context-rule-qt5.json \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254

cargo +1.88.0 test --locked \
  --manifest-path spikes/rquickjs-rule-runtime/Cargo.toml \
  fixed_context_rules_match_pinned_qt5_oracle_end_to_end
```

### `U24` 与 `shru64` Qt oracle

共享上游 harness 直接注册未修改的 `Binary_Script` 与 `Util_script`。固定
Qt Script 5.15.13 和 QJSEngine 6.4.2 都确认：

- bytes `12 34 56` 的 little-endian `U24` 为 `0x563412`，big-endian `U24` 与
  `read_uint24` 都为 `0x123456`；
- `shru64(0xFFFFFFFF, 0/4/32)` 分别为
  `0xFFFFFFFF`、`0x0FFFFFFF`、`0`；
- 额外实参不改变值；Qt 5 静默，Qt 6 每个调用发出两行 warning。

Rust fixture 对同一六值序列逐项匹配，并在 292 条 diagnostic `detect` 中让两个
fallback 路径消失。`shru64` spike 只接受非负 safe integer 与 shift < 64，
其他输入明确抛错；这不是完整 Qt `quint64` conversion profile。固定 C++ 对
shift >= 64 直接使用 `>>`，本实验不把未定义范围冻结成兼容行为。完整 oracle
身份、stderr 和未覆盖边界见
[`format-host-api-runtime-differential.md`](format-host-api-runtime-differential.md)。

此前简化的 `X.c` 只识别 Nintendo spike 使用的 5 个固定 pattern，并对其他
pattern 静默返回 false。这不符合“不支持语法必须显式诊断”的兼容门禁。本轮在
该方法外增加诊断包装，固定样本上有 32 条规则、331 次调用、317 个唯一 pattern
未被实现，且未发生记录截断。上游
[`xbinary.h`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.h)
还定义通配、ASCII、相对跳转等组合语法，因此不能用若干字符串特判近似
`compare`/`fSig`；固定语法审计、317-pattern inventory 与纯 Rust parser spike
见 [`signature-language.md`](signature-language.md)。compatibility parser 已
覆盖该动态清单，固定 XBinary oracle 又确认 `compare` 与 `fSig/find_signature`
存在 class 和 search 分支差异。独立 Rust find 已覆盖 control-record、SigByte、
plain-hex 三分支的 19 个聚焦差分并全部一致。`Binary_Script::compare` 的
wrapper-level header fast path 又以 7/7 端到端向量确认：不能把 `X.c` 无条件
映射到 record matcher；EP 与 overlay wrapper 各 5/5 又确认 cache 长度单位和
原始 pattern 长度都会改变结果。合成 memory-map matcher 已覆盖六类 file type，
并与固定 oracle 7/7 一致；PE32/ELF64/Mach-O64 parser-derived map 又达到
3/3，COM/MS-DOS/AmigaHunk 及 PE64/ELF32/Mach-O32 再达到 6/6。畸形 map、
find 的畸形/穷举边界、无效/短小 wrapper 上下文和全调用点差分尚未完成。

当前 diagnostic runtime 已用这个 pure-Rust parser/matcher 替换五-pattern
特判，并单独记录 compare 与 search 的 call/fast/generic/quirk/error。接入
search 前固定样本得到 799 次 compare、0 error；接入后因真实搜索假值改变控制流，
得到 1179 次 compare（1115 fast、64 generic、5 quirk、0 error）和 11 次
search（0 match、1 quirk、0 error）。overlay context 再次改变分支，得到
1109 次 compare（1047 fast、62 generic、5 quirk、0 error），search 计数不变；
string context 接入后仍为 1109/11。execution context 的确定性 `isText=false`
再次短路，最终为 1105 次 compare（1043 fast、62 generic、5 quirk、0 error）
和 11 次 search。
header fast path 对未知字符仍按上游
string matcher 返回 false；generic parser/search 才产生显式诊断。此处的全库
diagnostic trace 只覆盖 generic Binary identity memory map；后续规则级差分已
分别闭合真实 PE32、ELF32/ELF64 与 Mach-O64 x86_64/arm64 format map
分支，但仍不能外推到其他格式或 HostApi。

后续静态 AST inventory 已把范围从单一样本扩大到固定 `db`/`db_extra`：
2175/2175 文件解析成功，5968 个具名 signature API 调用点中有 5855 个 literal、
109 个可枚举静态表达式和 4 个动态表达式；5628 个静态 pattern 包含本动态 probe
的 317/317。后续固定源码受限求值已把其中 `byteCode` 的 33 个调用点闭合为
97 个唯一 pattern；其余 3 个仍是输入相关 Number→QString 值域，因此仍不能据此
替换 HostApi。

历史快照的 285 条“无异常”及 153 条 detection、compare 增量的 292/10、
search 增量的 291/5、overlay 增量的 292/4、string 增量的 292/1，以及当前
execution context 增量的 292/1，
都不能作为兼容证据：
代理返回的 callable
object 在 JavaScript 条件中可能为 truthy，已明显制造大量 false positive。即使
当前 292 条规则没有记录 fallback 调用，本轮也没有逐条 Qt oracle 结果，且“零
fallback”只覆盖这个输入抵达的实际 function application，不能把“未记录”扩大
解释为 HostApi 完整。该 probe
的有效产物是可重复的缺口优先级和失败隔离机制。

## Binary 顶层生命周期实验

`eval-binary-lifecycle-raw` 读取固定
[`binary-rule-order-linux-qt5.json`](data/binary-rule-order-linux-qt5.json)，
在一个 QuickJS context 中依次执行 global `_init`、Binary `_init` 和 292 条
Binary 规则。init 与规则共触发 30 次真实 include。规则总字节数为 1,122,477。

原始规则产生 3 个错误：

| Index | Rule | QuickJS 差异 |
| ---: | --- | --- |
| 212 | `format_bin.Nintendo-certified-file.1.sg` | function 内 `var tp` 与 `const tp` 重定义 |
| 288 | `__MiniExtensionsHeuristic_By_DosX.7.sg` | `const detect` 与前序 global function 冲突 |
| 291 | `archive_archives.ancient.sg` | 给 `audio.1.sg` 留下的 global `const debug` 赋值 |

固定 Qt5 qmake/CMake profiling 均执行到这三条规则并继续完成，未输出对应 error。
后两个差异只有在真实共享 context 和固定顺序下才出现，isolated eval 无法发现。

Phase 0 feasibility probe 增加三个内存 overlay：

| ID | Fixed rule | Equal-length change |
| --- | --- | --- |
| `audio-global-const-debug-v1` | `audio.1.sg` | `const debug` → `var   debug` |
| `nintendo-unused-var-tp-v1` | Nintendo rule | 删除未使用的 function-scoped `tp` |
| `extensions-global-const-detect-v1` | MiniExtensions rule | `const detect` → `var   detect` |

三者都绑定 path、size、唯一声明和源 SHA-256，不写回规则；替换前后字节数相同。
应用后 292/292 顶层 eval 通过，overlay 恰好命中 3 次。这仍不是 production
转换方案。

专用 7 规则 fixture 随后确认 Qt 5 qmake/CMake 都允许前一 `evaluate()` 的顶层
`const` 名称在后一 `evaluate()` 中赋值，也允许 `function detect`、
`const detect`、`function detect` 连续出现；每次求值后的本次 `detect` 均可被
宿主调用。相同顺序的 QuickJS 产生 3 个错误，只得到 4/7 detection。完整证据与
边界解释见
[`script-scope-semantics.md`](script-scope-semantics.md)。

per-rule non-strict function lexical wrapper 随后在相同 fixture 上达到 0 error、
7/7 detection，并与 Qt 5 结构化结果完全一致。固定 292 条 Binary 顺序下，
wrapper 也让 292/292 规则成功求值并解析出 function 类型的 `detect`；只需保留
Nintendo 的单脚本语法 overlay，`audio` 和 MiniExtensions 的跨规则 overlay
均不再需要。

后续 persistent-state fixture 同时证明了 wrapper 的边界：Qt 会让顶层 `var` 和
普通函数跨规则持久化；raw QuickJS 7/7 匹配，wrapper 因隔离这两类 binding 只有
5/7。固定 Binary AST 审计在 302 个 persistent 声明中未发现后序规则依赖前序
显式 var/function 的候选，因此当前规则集仍可继续验证 wrapper，但不能把它当作
通用 Qt 等价模型。详见
[`script-state-semantics.md`](script-state-semantics.md)。

## 与 Boa 首轮结果对比

| 维度 | Boa 0.21.1 | rquickjs 0.12.1 |
| --- | ---: | ---: |
| 固定语料独立错误 | 1（parse） | 1（带 shim 的 eval） |
| Nintendo legacy 规则 | 拒绝 | 拒绝 |
| 复杂 audio 规则 | 接受 | sloppy 模式接受 |
| 外部 interrupt | 未发现公开接口 | 跨线程 token 已中断并同 context 恢复 |
| Heap limit | 未发现公开接口 | 支持默认 allocator |
| Windows target packages | 126 | 28 |
| Release spike | 11,784,192 bytes | 2,515,968 bytes（Rust 1.97.1） |
| 实现语言 | 纯 Rust | Rust wrapper + vendored C |
| 本轮工具链 | Rust 1.88 | 最低 1.87，本轮 1.88 |

两者都没有满足“固定规则原样、零差异”的选型门禁。QuickJS-NG 当前更适合作为
资源控制和体积基线，Boa 仍提供纯 Rust 路径；最终决策不能只依据这两个微型
spike 的大小或速度。

## 复现

```sh
cd spikes/rquickjs-rule-runtime

cargo +1.88.0 build --release --locked
cargo +1.88.0 fmt -- --check
cargo +1.88.0 clippy --locked --all-targets -- -D warnings
cargo +1.88.0 test --locked

cargo +1.88.0 run --release --locked -- fixture \
  ../../upstream/Detect-It-Easy/db

cargo +1.88.0 run --release --locked -- eval-isolated \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra

cargo +1.88.0 run --release --locked -- eval-isolated-compat \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra

cargo +1.88.0 run --release --locked -- eval-isolated-compat-tracked-heap \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra

cargo +1.88.0 run --release --locked -- eval-shared \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra

cargo +1.88.0 run --release --locked -- eval-binary-lifecycle-raw \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- eval-binary-lifecycle \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- eval-scope-fixture \
  /tmp/diec-rust-script-scope-fixture \
  ../../docs/research/data/script-scope-fixture.json \
  ../../docs/research/data/script-scope-qt5.json

cargo +1.88.0 run --release --locked -- eval-scope-fixture-lexical \
  /tmp/diec-rust-script-scope-fixture \
  ../../docs/research/data/script-scope-fixture.json \
  ../../docs/research/data/script-scope-qt5.json

cargo +1.88.0 run --release --locked -- eval-binary-lifecycle-lexical \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

# Use the generated script-state fixture and its fixed Qt5 baseline.
cargo +1.88.0 run --release --locked -- eval-scope-fixture \
  /tmp/diec-rust-script-state-fixture \
  ../../docs/research/data/script-state-fixture.json \
  ../../docs/research/data/script-state-qt5.json

cargo +1.88.0 run --release --locked -- eval-scope-fixture-lexical \
  /tmp/diec-rust-script-state-fixture \
  ../../docs/research/data/script-state-fixture.json \
  ../../docs/research/data/script-state-qt5.json

cargo +1.88.0 run --release --locked -- detect-nintendo \
  ../../upstream/Detect-It-Easy/db \
  /tmp/diec-nintendo-certified-corpus \
  ../../docs/research/data/nintendo-certified-baseline.json

cargo +1.88.0 run --release --locked -- detect-nintendo-lifecycle \
  ../../upstream/Detect-It-Easy/db \
  /tmp/diec-nintendo-certified-corpus \
  ../../docs/research/data/nintendo-certified-baseline.json \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- trace-binary-detects \
  ../../upstream/Detect-It-Easy/db \
  /tmp/diec-nintendo-certified-corpus/ps3-type-2-revoke-list.self \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- verify-binary-corpus \
  ../../upstream/Detect-It-Easy/db \
  /tmp/diec-nintendo-certified-corpus \
  ../../docs/research/data/nintendo-certified-corpus.json \
  ../../docs/research/data/nintendo-certified-baseline.json \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- verify-binary-corpus-tracked-heap \
  ../../upstream/Detect-It-Easy/db \
  /tmp/diec-nintendo-certified-corpus \
  ../../docs/research/data/nintendo-certified-corpus.json \
  ../../docs/research/data/nintendo-certified-baseline.json \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- verify-pe-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/pe-rule-fixture.json \
  ../../docs/research/data/pe-rule-qt5.json

cargo +1.88.0 run --release --locked -- verify-elf-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/elf-rule-fixture.json \
  ../../docs/research/data/elf-rule-qt5.json

cargo +1.88.0 run --release --locked -- verify-macho-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/macho-rule-fixture.json \
  ../../docs/research/data/macho-rule-qt5.json

cargo +1.88.0 run --release --locked -- verify-dex-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/dex-rule-fixture.json \
  ../../docs/research/data/dex-rule-qt5.json

cargo +1.88.0 run --release --locked -- verify-apk-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/apk-rule-fixture.json \
  ../../docs/research/data/apk-rule-qt5.json

cargo +1.88.0 run --release --locked -- verify-archive-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/archive-rule-fixture.json \
  ../../docs/research/data/archive-rule-qt5.json

cargo +1.88.0 run --release --locked -- verify-pdf-rule \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/pdf-rule-fixture.json \
  ../../docs/research/data/pdf-rule-qt5.json
```

七个格式命令分别将命令名替换为
`verify-<format>-rule-tracked-heap`，即可复现同一 oracle 下的 32 MiB custom
allocator 报告。默认与 tracked 命令各连续运行三轮；完整 JSON canonicalize
后逐类 SHA-256 必须稳定，tracked 报告还必须逐 case 满足 0 denied allocation
和 drop 后 live bytes 为 0。

`fixture`、`eval-isolated-compat`、`eval-binary-lifecycle`、两个 lexical
fixture/lifecycle 命令预期退出 0；原始 isolated、shared 和
`eval-binary-lifecycle-raw` 因已记录差异预期退出 1，但仍向 stdout 输出完整
JSON。运行前先执行
`tools/verify_upstream.py` 和 Python 清单测试，确保 cryptographic source identity。
`elapsed_ms` 只用于本机观察，不做跨机器精确断言。
本轮在 Windows x86_64 MSVC release profile 将 `verify-binary-corpus` 重复三次，
原始 JSON 保存在临时目录且不提交；比较时排除 `elapsed_ms` 和路径，只保留兼容
计数、每样本 runtime measurement 与汇总 measurement，三份 canonical projection
得到相同 SHA-256。最终 spike 自身输出 `stable_projection_sha256`，并已与独立
Python canonical JSON/SHA-256 计算逐值核对。

## 对设计的约束

- runtime adapter 必须显式设置 sloppy/global script 语义。
- 原始规则字节、执行前兼容转换和 runtime patch 必须分层，任何转换都要保留
  原始哈希、源码位置和 Qt oracle 回归。
- compatibility overlay 必须绑定规则 commit/path/hash，拒绝未知 source；
  transformed bytes/hash 和 applied diagnostics 必须进入 scan/database metadata。
- 选择 rquickjs 意味着引入 native build、安全审计和 C toolchain CI，不能将
  “静态链接”误写为“纯 Rust”。
- 每个 scan 必须使用共享 context，按 global init、type init、signature 顺序
  执行；include 必须在该 context 立即求值。固定证据见
  [`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)。
- external cancel token、interrupt、memory、stack 和 wall-clock deadline 应进入
  统一资源预算模型；native HostApi 长循环必须合作检查 token/deadline。
- 若使用自定义 allocator，必须重新实现或验证 heap limit。

## 尚未完成

- Binary 已按固定 Linux 顺序完成 292 条顶层 eval、全 `detect` 缺口采集，并在
  14 个生成 header 样本上完成 4088 次零 fallback 调用和完整有序结果 oracle；
  全部 2,235 个程序文件的隔离顶层 parse/eval 又已有 custom-allocator
  high-water，但尚未为 292 条 Binary 规则分别提供正/反例 Qt oracle，也未完成
  其他 file type/file-part 的完整 lifecycle/detect 和 Windows/macOS 顺序。
- 首个格式专用分支已用真实 Rust PE32 context、native `PE.compareEP` 和原样
  Cygwin32 规则完成 positive/negative/truncated Qt5 差分 3/3；入口点、physical
  memory records、boolean 和完整 detection tuple 均一致。证据见
  [`pe-rule-runtime-differential.md`](pe-rule-runtime-differential.md)。
  第二个分支又用真实 Rust ELF32/ELF64 context、native `ELF.compareEP` 和原样
  Burneye 规则完成六例差分 6/6，并显式保存 XELF 截断时的负长度/virtual map
  记录及安全 matcher 投影，证据见
  [`elf-rule-runtime-differential.md`](elf-rule-runtime-differential.md)。
  第三个分支使用真实 Mach-O64 x86_64/arm64 context、native
  `MACH.compareEP` 和原样 Rust compiler 规则完成 4/4，精确核对 5/6/9 次
  wrapper 调用，证据见
  [`macho-rule-runtime-differential.md`](macho-rule-runtime-differential.md)。
  第四个分支使用真实 DEX035 string-table context、native
  `DEX.isDexStringPresent` 和原样 QDBH 规则完成 positive/negative/EOF 截断
  3/3；map、解析字符串、native boolean 和完整 tuple 均一致，证据见
  [`dex-rule-runtime-differential.md`](dex-rule-runtime-differential.md)。
  第五个分支使用真实 APK/ZIP central-directory context、native
  `APK.isArchiveRecordPresent` 和原样 QDBH 规则完成 3/3；大小写反例不命中，
  local records 全部缺失而 central names 保留时仍命中，证据见
  [`apk-rule-runtime-differential.md`](apk-rule-runtime-differential.md)。
  第六个分支使用真实 ZIP metadata context、native `Archive.isVerbose` 和三个
  format getter，以及原样 `_Archive.0.sg` 完成 verbose/quiet/
  central-directory-only 3/3；metadata、完整 tuple 和调用路径均一致，证据见
  [`archive-rule-runtime-differential.md`](archive-rule-runtime-differential.md)。
  第七个分支使用真实 PDF object/string context、native
  `PDF.getStringValuesByKey`/`getHeaderCommentAsHex` 和原样 Tools 规则完成
  literal-string、非 string 类型及缺 `endobj` 3/3；object token、去重数组、
  header comment、完整 tuple 和调用路径均一致，证据见
  [`pdf-rule-runtime-differential.md`](pdf-rule-runtime-differential.md)。
  七者仍不覆盖其余 PE/ELF/Mach-O/DEX/APK/Archive/PDF HostApi、PE32+、
  MUTF-8、decompression 或其他格式。
- 规则侧已清点 429 个第一层宿主 receiver/method 和 464 个 arity 形状；
  337 个 C++ slot 与 13 个脚本扩展静态覆盖 460 个形状。共享 Qt 5/Qt 6
  QObject 探针已闭合三个额外实参形状和缺失 `PE.getEPSignature` 的
  runtime-specific `TypeError`，并发现代表性 `qint64` 转换差异；仍缺其余
  参数/返回类型、默认参数和异常 fixture。
- 非格式 native global 的 Qt 5 探针已固定缺参字符串化、结果重复/删除/block、
  双 stop 状态和重复 include；QuickJS adapter 尚未逐项复刻并差分这些副作用。
- Nintendo 语料已在固定 292 条加载环境中逐样本调用全部 292 个 `detect`，
  Qt 5 完整有序 type/name/version 14/14 对照通过；仍缺 Qt 6 和其余规则各自能
  抵达有效分支的正/反例 HostApi/Qt oracle。
- Qt 5/Qt 6 与 QuickJS 的整数、字符串、数组、异常和 RegExp 差分。
- Linux/macOS/Windows GNU/MSVC 静态链接、ASan/UBSan 和 fuzz。
- 真实 signature/search/decompression HostApi 的 deadline/cancel checkpoint
  密度、不可分割阻塞调用、typed timeout 映射、跨平台最大延迟，以及并行
  runtime/context 的吞吐和峰值内存。

## 外部候选资料

- [rquickjs 0.12.1 API](https://docs.rs/rquickjs/0.12.1/rquickjs/)
- [rquickjs `Runtime` limits](https://docs.rs/rquickjs/0.12.1/rquickjs/runtime/struct.Runtime.html)
- [rquickjs `Ctx` eval API](https://docs.rs/rquickjs/0.12.1/rquickjs/struct.Ctx.html)
