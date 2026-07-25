# rquickjs/QuickJS-NG 规则运行时技术验证

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Candidate: `rquickjs@0.12.1` / vendored QuickJS-NG 0.15.1

Last updated: 2026-07-26

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

后续最小实验确认：对唯一失败规则应用 source-identity 约束、等长且不落盘的
compatibility overlay 后，QuickJS 接受该规则；同一 overlay 在 2235 个文件中
恰好命中一次，isolated eval 错误由 1 降为 0。该结果只证明受控兼容层可行，
随后使用 Rust 最小 Byte HostApi，在每个 scan context 中按真实顺序执行 global
`_init`、Binary `_init` 及四个 include，再用 14 个项目生成样本执行
`detect()`；目标 Nintendo detection 与 Qt 5 baseline 14/14 匹配。进一步按固定
Linux Qt5 oracle 顺序在一个 context 中求值 292 条 Binary 顶层代码：原始规则
出现 3 个 legacy lexical 差异，三个精确、等长 overlay 后为 0。实验仍未逐条
调用 `detect`、复现 EA-XA 邻接结果、覆盖 Qt 6 和其余 338 个宿主方法，因此候选
状态不变。

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
| Release executable | 1,602,560 bytes（加入固定顺序 Binary lifecycle probe 后） |

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
- Nintendo 原始文件保持 SHA-256
  `1f7485b8b0c9c211932fdcc31529ea37588c176e46a1ff06230fc376df5ad0f5`，
  compatibility overlay 后 eval 成功且 evaluated length 不变；
- 两次 eval 同名 `const` 时第二次失败；
- 17 次 handler callback 后无限循环返回 `Error: interrupted`；
- 4 MiB runtime limit 拒绝 16 MiB `ArrayBuffer`，返回 `out of memory`。

内存限制使用 rquickjs 默认 libc allocator。官方 API 说明使用 `rust-alloc` 或
自定义 allocator 时 `set_memory_limit` 是 no-op，因此未来不能在未验证的情况
下同时启用这两个选项。

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
生命周期的最小可行路径，但没有执行完整 Binary signature sequence，尤其没有
执行 `audio.1.sg` 和 `audio_EXA.1.sg`。因此不应与完整 Qt detection list 混淆：
PS Vita 的 EA-XA 第二条记录仍需全签名生命周期实验复现。

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
转换方案：Qt Script 对跨 evaluate lexical binding 的精确模型还需专用 fixture，
最终策略必须由 runtime ADR 决定。

## 与 Boa 首轮结果对比

| 维度 | Boa 0.21.1 | rquickjs 0.12.1 |
| --- | ---: | ---: |
| 固定语料独立错误 | 1（parse） | 1（带 shim 的 eval） |
| Nintendo legacy 规则 | 拒绝 | 拒绝 |
| 复杂 audio 规则 | 接受 | sloppy 模式接受 |
| 外部 interrupt | 未发现公开接口 | 支持 |
| Heap limit | 未发现公开接口 | 支持默认 allocator |
| Windows target packages | 126 | 18 |
| Release spike | 11,784,192 bytes | 1,602,560 bytes |
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

cargo +1.88.0 run --release --locked -- eval-shared \
  ../../upstream/Detect-It-Easy/db \
  ../../upstream/Detect-It-Easy/db_extra

cargo +1.88.0 run --release --locked -- eval-binary-lifecycle-raw \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- eval-binary-lifecycle \
  ../../upstream/Detect-It-Easy/db \
  ../../docs/research/data/binary-rule-order-linux-qt5.json

cargo +1.88.0 run --release --locked -- detect-nintendo \
  ../../upstream/Detect-It-Easy/db \
  /tmp/diec-nintendo-certified-corpus \
  ../../docs/research/data/nintendo-certified-baseline.json
```

`fixture`、`eval-isolated-compat` 和 `eval-binary-lifecycle` 预期退出 0；原始
isolated、shared 和 `eval-binary-lifecycle-raw` 因已记录差异预期退出 1，但仍向
stdout 输出完整 JSON。运行前先执行
`tools/verify_upstream.py` 和 Python 清单测试，确保 cryptographic source identity。
`elapsed_ms` 只用于本机观察，不做跨机器精确断言。

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
- interrupt、memory、stack 和 wall-clock deadline 应进入统一资源预算模型。
- 若使用自定义 allocator，必须重新实现或验证 heap limit。

## 尚未完成

- Binary 已按固定 Linux 顺序完成 292 条顶层 eval；尚未逐条调用 `detect`，也未
  完成其他 file type 和 Windows/macOS 顺序。
- 338 个直接宿主方法及继承方法的行为 fixture。
- Nintendo 已完成最小 HostApi 下 Qt 5 target detection 对照；仍缺 Qt 6 和完整
  Binary 规则列表（包括 PS Vita 的 EA-XA 邻接命中）。
- Qt 5/Qt 6 与 QuickJS 的整数、字符串、数组、异常和 RegExp 差分。
- Linux/macOS/Windows GNU/MSVC 静态链接、ASan/UBSan 和 fuzz。
- 并行 runtime/context 的吞吐、峰值内存和取消延迟。

## 外部候选资料

- [rquickjs 0.12.1 API](https://docs.rs/rquickjs/0.12.1/rquickjs/)
- [rquickjs `Runtime` limits](https://docs.rs/rquickjs/0.12.1/rquickjs/runtime/struct.Runtime.html)
- [rquickjs `Ctx` eval API](https://docs.rs/rquickjs/0.12.1/rquickjs/struct.Ctx.html)
