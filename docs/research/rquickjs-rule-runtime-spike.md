# rquickjs/QuickJS-NG 规则运行时技术验证

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Candidate: `rquickjs@0.12.1` / vendored QuickJS-NG 0.15.1

Last updated: 2026-07-25

## 结论

rquickjs 0.12.1 在 Windows MSVC 上可以直接使用预生成绑定构建，并把
QuickJS-NG C 源码编译成静态 archive。它能够：

- 执行 603,640 字节的真实 `Binary/audio.1.sg`；
- 原样执行 `_runtime_helpers`；
- 注册和调用 Rust native function；
- 通过 interrupt handler 中断无限循环；
- 通过 runtime memory limit 拒绝超限分配。

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
vendored C、MSVC/clang/gcc 构建链及 native 安全边界。当前仍不冻结规则
runtime；需要先验证按真实上游生命周期执行、legacy compatibility patch/
受控转换的可维护性，以及 Linux/macOS/Windows 静态链接和 fuzz 行为。

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

## 构建与依赖

| 项目 | 值 |
| --- | --- |
| Host OS/target | Windows amd64 / `x86_64-pc-windows-msvc` |
| Default Rust | 1.86.0，候选明确拒绝 |
| Spike Rust | 1.88.0 |
| rquickjs | 0.12.1，`default-features = false`，仅 `std` |
| rquickjs-sys | 0.12.1，crate checksum 固定于 `Cargo.lock` |
| Vendored engine | QuickJS-NG 0.15.1 |
| Lockfile packages | 23 |
| 当前 target packages | 18 |
| Clean release build | 13,258 ms，本机已缓存下载、空 target |
| Release executable | 1,392,128 bytes |

`cargo +1.86.0 check --locked` 明确报告
`rquickjs@0.12.1 requires rustc 1.87`。本实验继续复用已安装的 1.88 工具链。

`rquickjs-sys` 的 `build.rs` 编译 `libregexp.c`、`libunicode.c`、`quickjs.c`
和 `dtoa.c` 为 `libquickjs.a`；Windows MSVC 不需要运行时 QuickJS DLL，但
构建不再是纯 Rust。crate 内含 QuickJS-NG 的 MIT `LICENSE` 和 MSVC patch。

当前 Windows target 的 18 个 package 都有许可证表达式，涉及 MIT、
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
- 两次 eval 同名 `const` 时第二次失败；
- 17 次 handler callback 后无限循环返回 `Error: interrupted`；
- 4 MiB runtime limit 拒绝 16 MiB `ArrayBuffer`，返回 `out of memory`。

内存限制使用 rquickjs 默认 libc allocator。官方 API 说明使用 `rust-alloc` 或
自定义 allocator 时 `set_memory_limit` 是 no-op，因此未来不能在未验证的情况
下同时启用这两个选项。

## 与 Boa 首轮结果对比

| 维度 | Boa 0.21.1 | rquickjs 0.12.1 |
| --- | ---: | ---: |
| 固定语料独立错误 | 1（parse） | 1（带 shim 的 eval） |
| Nintendo legacy 规则 | 拒绝 | 拒绝 |
| 复杂 audio 规则 | 接受 | sloppy 模式接受 |
| 外部 interrupt | 未发现公开接口 | 支持 |
| Heap limit | 未发现公开接口 | 支持默认 allocator |
| Windows target packages | 126 | 18 |
| Release spike | 11,784,192 bytes | 1,392,128 bytes |
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

cargo +1.88.0 run --release --locked -- eval-shared \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra
```

`fixture` 预期退出 0；两个全库命令因已记录差异预期退出 1，但仍向 stdout 输出
完整 JSON。`elapsed_ms` 只用于本机观察，不做跨机器精确断言。

## 对设计的约束

- runtime adapter 必须显式设置 sloppy/global script 语义。
- 原始规则字节、执行前兼容转换和 runtime patch 必须分层，任何转换都要保留
  原始哈希、源码位置和 Qt oracle 回归。
- 选择 rquickjs 意味着引入 native build、安全审计和 C toolchain CI，不能将
  “静态链接”误写为“纯 Rust”。
- context 生命周期必须从上游加载顺序推导，不能从 shared-path 实验猜测。
- interrupt、memory、stack 和 wall-clock deadline 应进入统一资源预算模型。
- 若使用自定义 allocator，必须重新实现或验证 heap limit。

## 尚未完成

- 按上游 file type、priority、database、init/include 顺序执行全库。
- 338 个直接宿主方法及继承方法的行为 fixture。
- Nintendo legacy 语义的最小 runtime patch 或受控转换验证。
- Qt 5/Qt 6 与 QuickJS 的整数、字符串、数组、异常和 RegExp 差分。
- Linux/macOS/Windows GNU/MSVC 静态链接、ASan/UBSan 和 fuzz。
- 并行 runtime/context 的吞吐、峰值内存和取消延迟。

## 外部候选资料

- [rquickjs 0.12.1 API](https://docs.rs/rquickjs/0.12.1/rquickjs/)
- [rquickjs `Runtime` limits](https://docs.rs/rquickjs/0.12.1/rquickjs/runtime/struct.Runtime.html)
- [rquickjs `Ctx` eval API](https://docs.rs/rquickjs/0.12.1/rquickjs/struct.Ctx.html)
