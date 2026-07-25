# Boa 规则运行时技术验证

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Candidate: `boa_engine@0.21.1`

Last updated: 2026-07-25

## 结论

Boa 0.21.1 能解析绝大多数固定上游规则、执行 603,640 字节的真实复杂规则、
运行上游 prototype helpers、调用 Rust native function，并提供 loop、recursion
和 VM stack 限制。但它不能原样作为 DIE 兼容运行时：

- 2235 个 main+extra `.sg`/无扩展名文件中，有 1 个被 Boa 的独立
  `Script::parse()` 拒绝；
- 同一真实规则也被 `Context::eval()` 拒绝，而固定 Qt 5 oracle 正常执行该
  Binary 规则集且不报告脚本错误；
- Boa 的 shared realm 会拒绝后续 eval 中重复的 lexical declaration；DIE
  将许多独立规则依次放入同一个 Qt engine，必须进一步模拟真实顺序确认影响；
- `Script::parse()` 与 `Context::eval()` 的 early-error 行为本身并不完全一致，
  因而不能以单独 parse 结果替代全生命周期 conformance。

因此 Boa 保留为“需要上游修复或项目维护补丁后再评估”的候选，不进入设计决策。
规则文件仍必须保持原始字节，不能通过改写问题规则来掩盖差异。下一步应建立
QuickJS-NG 对照，并向 Boa 缩小/报告 parser-eval 一致性及 legacy Qt semantics
问题。

## 实验边界

验证程序位于
[`spikes/boa-rule-runtime/`](../../spikes/boa-rule-runtime/)。它是 Phase 0
隔离 spike，不属于未来 Cargo workspace、正式实现或稳定 API。
机器可读的稳定结果摘要及 Cargo/source 哈希位于
[`data/boa-rule-runtime.json`](data/boa-rule-runtime.json)；包含耗时的完整
临时报告不提交。

| 项目 | 值 |
| --- | --- |
| Host OS/target | Windows amd64 / `x86_64-pc-windows-msvc` |
| Default Rust | 1.86.0（不足以构建候选） |
| Spike Rust | 1.88.0，minimal toolchain |
| Boa | 0.21.1，`default-features = false` |
| serde_json | 1.0.145 |
| Lockfile packages | 133 |
| 当前 target metadata packages | 126 |
| Release executable | 11,784,192 bytes |
| 首次 release build | 约 89 秒（本机热下载缓存、冷编译） |

Boa 0.21.1 的声明 MSRV 是 Rust 1.88；当前项目默认 1.86 无法构建。首次
`rustup toolchain install` 已成功安装 1.88 核心组件，但安装后的 rustup
self-update 因 TLS handshake EOF 失败；这不影响隔离 toolchain 使用。

当前 Windows target 的 126 个 package 均有许可证表达式。主要为
MIT/Apache-2.0、Unicode-3.0、Unlicense、BSD 和 Zlib 的组合；这只是 Cargo
metadata 初筛，不替代发布前逐项许可证/NOTICE 审计。

## 全库独立解析

选择规则与现有调研口径一致：递归读取 `db` 和 `db_extra` 中所有 `.sg` 及
无扩展名文件，不读取 PNG/TXT/INI/JSON 等发布附属文件。

| 指标 | 值 |
| --- | ---: |
| Files | 2235 |
| Bytes | 2,902,881 |
| Isolated realm parse errors | 1 |
| Observed elapsed | 1921 ms |

唯一失败：

```text
db/Binary/format_bin.Nintendo-certified-file.1.sg
SyntaxError: lexical name declared in var names at line 10, col 9
```

该规则在 `detect()` 内先声明 `var tp, e`，随后在同一 block 使用
`const attr = ..., tp = ...`。按现代 ECMAScript early-error 规则这属于 lexical
冲突；Qt Script 接受它，上游固定 oracle 扫描 Binary 输入时没有产生对应错误。
兼容目标是上游可观察行为，不能因为 Boa 更接近现代规范就忽略此规则。

## Shared realm 信号

把同一批文件按规范化 path 顺序交给一个 Boa realm 的 `Script::parse()`：

| 指标 | 值 |
| --- | ---: |
| Files | 2235 |
| Parse errors | 2021 |
| Observed elapsed | 1798 ms |

主要错误为 `duplicate lexical declaration`。这个数字不是上游生命周期的最终
兼容率：实验没有按 file type/priority/database 精确排序，也没有执行后再解析
下一条规则。但独立 fixture 已确认，在同一 `Context` 中连续两次 eval
`const sharedName` 时第二次会失败。正式 spike 必须按上游真实 init/include/
signature 顺序执行全库，不能假设每条规则使用独立 realm，因为 include 和全局
helper 又要求共享状态。

## Runtime fixture

`fixture` 子命令验证：

- Rust native `hostAdd(20, 22)` 从 JavaScript 返回 `"42"`；
- 原样执行上游 `_runtime_helpers` 后，
  `String.append/appendS` 和 `Number.padStart` 得到 `a, b/c|007`；
- 使用最小 `meta/includeScript` host shim 原样 eval
  `Binary/audio.1.sg`，确认 603,640 字节规则定义 `detect` 并请求
  `chunkparsers,soundchips,bytecodeparsers`；
- 32 次 loop iteration limit 能中断 `for (;;) {}`，返回明确
  `RuntimeLimit`；
- 同一 context 的第二个同名 `const` 被拒绝；
- Nintendo 规则被实际 eval 拒绝。

Boa 的公开 `RuntimeLimits` 提供 loop iteration、recursion、stack size 和
backtrace 限制。当前公开接口未提供 heap 字节上限或基于外部 cancellation token
的指令级中断；时间限制、heap 隔离、panic/abort 行为和并发 context 策略仍需
单独验证。`Context` 也不是 `Send`/`Sync`，未来并行扫描若选择 Boa，需要每个
worker 拥有独立 context 或重新创建 context。

## 复现

```sh
cd spikes/boa-rule-runtime
rustup toolchain install 1.88.0 --profile minimal
rustup component add --toolchain 1.88.0 rustfmt clippy

cargo +1.88.0 build --release --locked
cargo +1.88.0 fmt -- --check
cargo +1.88.0 clippy --locked --all-targets -- -D warnings
cargo +1.88.0 test --locked

cargo +1.88.0 run --release --locked -- fixture \
  ../../upstream/Detect-It-Easy/db

cargo +1.88.0 run --release --locked -- parse-isolated \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra

cargo +1.88.0 run --release --locked -- parse-shared \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra
```

`fixture` 预期退出 0；两个 parse 命令因已确认的不兼容项预期退出 1，并仍将完整
JSON 报告写到 stdout。报告包含环境无关的计数和错误列表，也包含仅供性能观察的
`elapsed_ms`；后者不应作为跨机器精确断言。

## 对设计的约束

- runtime 选型 ADR 必须以全生命周期执行结果为门禁，不能只看语法覆盖率。
- 若维护 Boa patch，patch 必须修改 runtime/parser 行为而不是上游规则字节，
  并需要 Qt 5/Qt 6 conformance fixture。
- JavaScript context 不得进入格式解析层；host API 仍应由显式 trait/adapter
  提供，以保留切换 runtime 的能力。
- 资源限制模型至少需要补足 wall-clock/外部取消和 heap limit。
- MSRV、126 个 target 依赖及约 11.8 MB 的最小 spike 二进制是架构评审输入，
  不能把“纯 Rust”误等同于“小依赖”。

## 尚未完成

- 按上游 file type、priority、database、init/include 顺序做全库 eval。
- 338 个直接宿主方法及继承方法的参数/返回类型 fixture。
- Qt 5 与 Qt 6 的 64 位整数、字符串、数组、默认参数和异常 oracle。
- QuickJS-NG/rquickjs 同一语料对照。
- Boa heap、wall-clock cancellation、panic 隔离和多线程性能。
- PE/.NET、ELF、APK/DEX、PDF 等真实阳性/阴性检测。

## 外部候选资料

- [Boa engine 0.21.1 API](https://docs.rs/boa_engine/0.21.1/boa_engine/)
- [Boa `Context` host registration and limits](https://docs.rs/boa_engine/0.21.1/boa_engine/context/struct.Context.html)
- [Boa `RuntimeLimits`](https://docs.rs/boa_engine/0.21.1/boa_engine/vm/struct.RuntimeLimits.html)
