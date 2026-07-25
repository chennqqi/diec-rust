# C 静态链接与 ABI 边界技术验证

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-26

## 结论

Phase 0 的 C 静态链接路径已在三个真实 C11 可执行文件中验证：

- Windows x64 MSVC，Rust 默认动态 CRT + C `/MD`；
- Windows x64 MSVC，Rust `+crt-static` + C `/MT`；
- Linux x86_64 GNU，Rust `staticlib` `.a` + GCC。

三条路径都成功从 C 调用 Rust、读取结构化 JSON 字节、覆盖错误码、连续执行
1000 次分配/释放、把句柄置空并安全重复释放同一变量，还验证了内部 Rust panic
被转换为状态码且进程可以继续调用 ABI。

实验同时证明“提供 `.a`/`.lib`”不等于“最终程序没有动态依赖”：

- Windows 默认路径仍依赖 `VCRUNTIME140.dll` 和 Universal CRT；
- Windows static-CRT 路径不依赖 VC runtime DLL，但仍依赖 Windows 系统 DLL；
- Linux GNU 可执行文件仍依赖 glibc loader、`libc.so.6` 和 `libgcc_s.so.1`。

因此发布设计必须分别声明 Rust staticlib、C runtime 链接模式、系统库清单和最终
产物依赖，不能笼统写成“全静态”。

这个 spike 只验证 ABI 机制。它返回由输入长度和字节和生成的确定性 JSON，不是
DIE 扫描器实现、正式结果 schema 或已接受的公共 ABI。

## 实验位置与固定输入

验证程序位于
[`spikes/c-static-link/`](../../spikes/c-static-link/)，机器可读摘要位于
[`data/c-static-link.json`](data/c-static-link.json)。

| 文件 | 作用 |
| --- | --- |
| `src/lib.rs` | Rust `staticlib` 与受控 `unsafe` FFI 边界 |
| `include/diec_spike.h` | C11 头文件和所有权契约 |
| `c/smoke.c` | 真实 C 调用方及生命周期/错误/panic fixture |
| `run-windows-msvc.cmd` | `/MD` 与 `--static-crt` 两种 Windows 构建 |
| `run-linux-gnu.sh` | Linux GNU `.a` 构建、链接与运行 |

所有执行输入的 SHA-256 固定在机器基线中。Cargo crate 没有第三方依赖，lockfile
只有 spike 自身。

## ABI fixture

头文件只暴露：

- `uint32_t` ABI 版本和状态码；
- `uint64_t` 输入/输出长度；
- `uint8_t` 字节视图；
- 前置声明的 `diec_spike_result` 不透明句柄。

没有 Rust enum、`String`、`Vec`、trait object、panic payload 或 Rust 布局结构
穿过边界。稳定导出符号共 6 个：

```text
diec_spike_abi_version
diec_spike_scan
diec_spike_result_json
diec_spike_result_free
diec_spike_status_message
diec_spike_force_panic
```

`dumpbin /linkermember:1` 和 Linux `nm -g --defined-only` 都确认这 6 个符号进入
静态库。

### 所有权

`diec_spike_scan` 借用输入，只为调用期间读取；成功时返回唯一 Rust-owned
opaque result。`diec_spike_result_json` 返回非 NUL 结尾的借用字节视图，生命周期
不超过 owning result。

调用方不能使用 `free()`、`delete` 或自己的 allocator 释放 Rust 内存。唯一释放
入口接收 `diec_spike_result **`，先把调用方变量写成 null，再回收 Rust allocation。
因此：

- 用同一个已置空变量再次调用 free 是幂等的；
- 保存另一份旧指针并再次释放仍是非法 stale-pointer/double-free；
- 读取可以并发，但调用方必须保证没有线程同时释放句柄。

这个模型比向 C 暴露 `Vec` 的 length/capacity 更难误用，也是正式 C ABI 的优先
候选；是否还需要一次性 caller-buffer API 留待 `docs/design/c-abi.md` 决定。

### 参数与资源边界

- `length == 0` 时允许 `data == NULL`；
- 非零长度要求可读 input pointer；
- output pointer 无效时返回 `INVALID_ARGUMENT`；
- 所有可写输出在后续失败前先清为 null/0；
- spike 把输入限制为 16 MiB，并在构造 Rust slice 前检查；
- 未知状态码返回明确错误，不返回悬空 message。

裸指针导出函数在 Rust 类型层标为 `unsafe extern "C"`，每个函数有 `# Safety`
契约；实际解引用限制在带 SAFETY 注释的最小 `unsafe` block。

## Panic 边界

除只返回编译期常量的 `diec_spike_abi_version` 外，其余导出函数都经过：

```text
catch_unwind(AssertUnwindSafe(...))
```

`diec_spike_force_panic` 产生真实 Rust panic，C fixture 得到 `STATUS_PANIC`，随后
再次读取 ABI version 成功，证明 unwind 没有越过 `extern "C"` 边界。

这个结果有严格限制：

- Cargo release profile 必须是 `panic = "unwind"`；源码在其他策略下
  `compile_error!`；
- `catch_unwind` 不捕获 `panic=abort`、OOM abort、进程终止、部分 stack overflow
  或 native fault；
- 默认 Rust panic hook 会在 panic 已被捕获时仍写 stderr，本实验实际观察到该
  输出；
- 若宿主安装的全局 panic hook 自身 panic 或终止进程，边界不能保证恢复；
- library 不应临时替换进程全局 panic hook，因为会与宿主及并发调用冲突。

正式实现仍应把“不得 panic”作为第一层保证，把 catch 仅作为最后边界，并设计
不会修改宿主全局状态的诊断回调或错误采集机制。

## Windows MSVC

环境：

| 项目 | 值 |
| --- | --- |
| Rust | `rustc 1.88.0 (6b00bc388 2025-06-23)` |
| Visual Studio | 2022 Community |
| `cl.exe` | 19.44.35207.1 |
| `link.exe` / `dumpbin` | 14.44.35207.1 |
| Target | `x86_64-pc-windows-msvc` |

runner 通过 `vswhere.exe` 定位 Visual Studio，并调用 `VsDevCmd.bat` 初始化 x64
环境；不依赖调用者预先打开 Developer Command Prompt。

### 默认动态 CRT

rustc 报告：

```text
kernel32.lib ntdll.lib userenv.lib ws2_32.lib dbghelp.lib
/defaultlib:msvcrt
```

C 使用 `/MD`。产物：

| 产物 | 大小 |
| --- | ---: |
| Rust `.lib` | 14,552,206 bytes |
| C smoke `.exe` | 125,952 bytes |

最终 executable 的导入包含：

```text
VCRUNTIME140.dll
api-ms-win-crt-stdio-l1-1-0.dll
api-ms-win-crt-string-l1-1-0.dll
api-ms-win-crt-runtime-l1-1-0.dll
api-ms-win-crt-math-l1-1-0.dll
api-ms-win-crt-locale-l1-1-0.dll
api-ms-win-crt-heap-l1-1-0.dll
api-ms-win-core-synch-l1-2-0.dll
KERNEL32.dll
ntdll.dll
```

### 静态 CRT

Rust 使用 `-C target-feature=+crt-static`，rustc 将 CRT 建议改为
`/defaultlib:libcmt`；C 同时使用 `/MT`。产物：

| 产物 | 大小 |
| --- | ---: |
| Rust `.lib` | 14,552,206 bytes |
| C smoke `.exe` | 257,024 bytes |

`dumpbin /dependents` 只剩：

```text
api-ms-win-core-synch-l1-2-0.dll
KERNEL32.dll
ntdll.dll
```

Rust 和 C 的 CRT 模式必须成对设置。混合 `/MD`、`/MT` 或与依赖库使用不同 CRT
可能产生重复 runtime、allocator 不匹配或链接冲突，必须成为 CI matrix 的显式
维度。

## Linux GNU

实验使用固定镜像：

```text
rust:1.88.0-slim-bookworm
sha256:38bc5a86d998772d4aec2348656ed21438d20fcdce2795b56ca434cf21430d89
```

环境为 Rust 1.88.0 与 GCC 12.2.0。rustc 报告 native libraries：

```text
-lgcc_s -lutil -lrt -lpthread -lm -ldl -lc
```

产物：

| 产物 | 大小 |
| --- | ---: |
| Rust `.a` | 20,339,232 bytes |
| C smoke ELF | 4,570,200 bytes |

`ldd` 显示最终 ELF 依赖 `libgcc_s.so.1`、`libc.so.6` 和动态 loader。当前未验证
musl fully-static、macOS archive、Windows GNU、arm64 或 32 位 ABI。

## C fixture 覆盖

真实 C11 程序使用 `/W4 /WX` 或 `-Wall -Wextra -Werror` 编译，并断言：

- ABI version 为 1；
- `{1,2,3,4}` 返回精确 JSON
  `{"schema_version":1,"size":4,"sum":10}`；
- 借用 JSON 在 result 存活期间可读；
- free 后句柄为 null，再次 free 同一变量成功；
- 1000 次 scan/free 循环均成功；
- null input、null output、超 16 MiB 输入得到精确状态码；
- 零长度 null input 成功；
- 失败路径将输出清零；
- static status message 不要求释放；
- 真实 panic 返回状态 3，之后 ABI 仍可调用。

Rust 侧另有 3 个单元测试覆盖 JSON、所有权、输出清理和静态消息。

## 复现

Windows：

```cmd
cd spikes\c-static-link
run-windows-msvc.cmd
run-windows-msvc.cmd --static-crt

cargo +1.88.0 rustc --release --locked -- --print native-static-libs
```

Linux：

```sh
cd spikes/c-static-link
./run-linux-gnu.sh

cargo +1.88.0 rustc --release --locked \
  --target-dir target/linux-gnu -- \
  --print native-static-libs
```

本轮 Linux 复现容器：

```text
docker run --rm \
  --mount type=bind,source=<repository>,target=/work \
  --workdir /work/spikes/c-static-link \
  rust:1.88.0-slim-bookworm \
  sh ./run-linux-gnu.sh
```

panic probe 预期在 stderr 出现 hook 输出，但两个 runner 必须打印
`PASS c-static-link-smoke` 并退出 0。

## 对正式设计的约束

- ABI 必须单独版本化，且 runtime/规则版本不能与 ABI version 混为一谈。
- 导出层只接受固定宽度 C 类型、字节 view 和 opaque handle。
- Rust-owned 内存只由配对 Rust free API 回收，释放函数优先使用 pointer-to-pointer。
- 所有返回 view 必须声明 NUL、编码、借用期限和线程安全。
- 每个失败路径必须初始化 output，禁止调用方看到旧指针。
- panic containment 依赖 unwind，不得宣传能捕获 abort/OOM/native crash。
- 发布物必须附带每目标 `native-static-libs` 和最终 binary dependency audit。
- Windows 必须分别测试 `/MD` 与 `/MT`；Linux GNU 与 future musl 不能混称。
- header 应通过 C、C++、cgo、ctypes/cffi 的编译与布局测试后才能冻结。

## 尚未完成

- 正式一次性扫描 API 与低层 scanner/database handle 的取舍。
- 结构化结果、错误对象、取消 token、allocator policy 和日志回调。
- ABI symbol visibility、版本脚本、SONAME/dylib 与名称前缀策略。
- C++ header、Go/cgo、Python ctypes/cffi 的消费者测试。
- macOS、Windows GNU、Linux musl、arm64 和 32 位布局验证。
- sanitizer、Miri 可覆盖的内部层、fuzz、并发 read/free misuse 测试。
- 真正扫描结果通过相同所有权模型返回后的端到端差分。
