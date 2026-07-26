# rquickjs/QuickJS-NG 静态链接与许可证验证

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `horsicq/Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Candidate: `rquickjs@0.12.1` / vendored QuickJS-NG

Last updated: 2026-07-27

## 结论

隔离 spike 证明 rquickjs/QuickJS-NG 可以进入 Rust `staticlib`，并被真实 C11
调用方在以下三个组合中链接和运行：

- Windows x64 MSVC，Rust/C 均使用动态 CRT；
- Windows x64 MSVC，Rust `+crt-static` 与 C `/MT`；
- Linux x86_64 GNU，Rust 1.88 与 GCC 12.2。

C 调用不只是引用空导出符号：每次调用都创建真实 `Runtime` 和完整 `Context`，
求值 `40 + 2`，读取结果 42，再销毁 context/runtime；三个 native smoke 均重复
16 次。null 输出被拒绝，真实 Rust panic 被转换为状态 3，未越过 C ABI。默认
panic hook 仍会写 stderr，与通用 C static-link spike 的边界相同。

最终 Windows PE 和 Linux ELF 均不依赖 QuickJS 动态库。QuickJS-NG C 对象由
`rquickjs-sys` vendored build 纳入 `.lib`/`.a`；这证明目标组合可静态消费，
不表示项目成为纯 Rust 或 fully-static executable。

## 实验边界

代码位于
[`spikes/rquickjs-static-link/`](../../spikes/rquickjs-static-link/)，只属于
Phase 0 feasibility spike，不是正式 ABI 或 runtime backend。机器摘要位于
[`data/rquickjs-static-link.json`](data/rquickjs-static-link.json)，并由
`test_rquickjs_static_link_spike.py` 校验所有输入哈希、lockfile 包集合、状态码、
导出符号及三条 smoke 记录。

固定版本：

| 项目 | 值 |
| --- | --- |
| Rust | `rustc 1.88.0 (6b00bc388 2025-06-23)` |
| rquickjs | `0.12.1`, `default-features = false`, feature `std` |
| rquickjs-core | `0.12.1` |
| rquickjs-sys | `0.12.1` |
| Native engine | vendored QuickJS-NG |
| Release panic | `unwind`，其他策略由 `compile_error!` 拒绝 |

## Windows MSVC

Visual Studio 2022 的 `cl.exe` 为 19.44.35207.1，`link.exe`/`dumpbin` 为
14.44.35207.1。rustc 对动态和静态 CRT 分别报告：

```text
kernel32.lib ntdll.lib userenv.lib ws2_32.lib dbghelp.lib
/defaultlib:msvcrt
```

```text
kernel32.lib ntdll.lib userenv.lib ws2_32.lib dbghelp.lib
/defaultlib:libcmt
```

产物：

| Variant | Rust `.lib` | C smoke `.exe` | Exit |
| --- | ---: | ---: | ---: |
| `/MD` | 18,322,760 bytes | 1,139,712 bytes | 0 |
| `+crt-static` + `/MT` | 18,360,456 bytes | 1,382,912 bytes | 0 |

`dumpbin /dependents` 的 `/MD` 结果包含 UCRT、`VCRUNTIME140.dll`、
`bcryptprimitives.dll`、`KERNEL32.dll` 和 `ntdll.dll`；`/MT` 只剩
`api-ms-win-core-synch-l1-2-0.dll`、`bcryptprimitives.dll`、`KERNEL32.dll`
和 `ntdll.dll`。静态 CRT 仍依赖 Windows 系统 DLL，不能描述为独立于操作系统。

## Linux GNU

固定镜像：

```text
rust:1.88.0-slim-bookworm
sha256:38bc5a86d998772d4aec2348656ed21438d20fcdce2795b56ca434cf21430d89
```

GCC 为 12.2.0。rustc 报告：

```text
-lgcc_s -lutil -lrt -lpthread -lm -ldl -lc
```

Rust archive 为 23,121,454 bytes，C smoke ELF 为 6,048,664 bytes，退出
0。`ldd` 显示 `libgcc_s.so.1`、`libm.so.6`、`libc.so.6` 和动态 loader。
因此当前 `.a` 是供最终消费者链接的静态 archive，不是 fully-static Linux
发布物；musl 仍需单独验证。

禁网复现使用只读 Cargo registry cache，避免实验隐式下载：

```sh
docker run --rm --network=none --memory=2g --cpus=2 \
  --mount type=bind,source="$PWD",target=/work \
  --mount type=bind,source="$CARGO_HOME/registry",\
target=/usr/local/cargo/registry,readonly \
  --workdir /work/spikes/rquickjs-static-link \
  rust:1.88.0-slim-bookworm sh ./run-linux-gnu.sh
```

## 许可证闭包

固定 lockfile 的保守第三方清单为 18 个包，其中当前 feature/target 实际 build
tree 为 10 个；清单有意保留未启用 optional dependency，避免许可证初审漏项，
不能把 18 写成运行时实际加载数量。每个 Cargo package 都有非空 SPDX 表达式，
组合只出现：

- MIT；
- Apache-2.0；
- Zlib；
- Unicode-3.0。

`rquickjs` 的 MIT `LICENSE` SHA-256 为
`976ad3d07927343ab99b31510625acba89eac8e0e517c712925620ddeda91b70`。
`rquickjs-sys-0.12.1/quickjs/LICENSE` 是 vendored QuickJS-NG 的 MIT
许可证，SHA-256 为
`96f73f9d2a16c21a36b418f06073be26e7d6d5e7c1bc99756b21a4f2c74ef171`，
保留 Fabrice Bellard、Charlie Gordon、Ben Noordhuis 和
Saúl Ibarra Corretgé 的归属。

这是固定候选闭包的工程初审，不替代发布责任人的法律审查、最终 SBOM、NOTICE
归集或 future feature 的重新审计。尤其不能用 `rquickjs-sys` 顶层 MIT
metadata 代替 vendored engine 的独立许可证保存。

## 对 runtime 选型的意义

本实验关闭了“rquickjs 必然无法导出 `.lib/.a`”这一可行性风险，并给出 native
系统库、CRT 和许可证代价。结合既有实验，rquickjs 相比 Boa 还具备：

- 可用的 VM interrupt、heap limit 和跨线程取消；
- VM 与合作式 native HostApi deadline；
- 更小的候选依赖/二进制基线；
- 已验证的固定 Binary lifecycle、精确 compatibility overlay 和零 fallback
  单输入 trace。

代价是 vendored C、C compiler CI、native sanitizer、安全审计和 runtime
backend 私有 `unsafe` 边界。static-link 成功不弥补规则语义差异，也不能替代
完整 HostApi、全 file type、Windows/macOS oracle 或逐规则 detection 差分。

## 尚未覆盖

- macOS `.a`、Windows GNU、Linux musl、arm64 和 32 位；
- ASan/UBSan/LSan、Windows Verifier 及 native fault 隔离；
- custom allocator 与 heap cap 在 staticlib/多 context 下的组合；
- 并发 C 调用、wrong-thread handle、长时间生命周期和 leak measurement；
- production FFI 的完整 opaque ownership、Go/Python consumer；
- 完整规则/HostApi conformance 和性能 benchmark。
