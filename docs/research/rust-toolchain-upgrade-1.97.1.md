# Rust 1.97.1 默认工具链升级验证

Status: Draft

Last updated: 2026-07-27

## 1. 目的与边界

本实验验证把仓库默认、开发和发布工具链从 Rust 1.88.0 升级到固定
Rust 1.97.1 后，现有 Phase 0 技术 spike 是否仍能构建、测试并被真实 C
consumer 静态链接。机器可读摘要位于
[`data/rust-toolchain-upgrade-1.97.1.json`](data/rust-toolchain-upgrade-1.97.1.json)。

本实验不提高 MSRV。五个 spike 的 `package.rust-version` 均保持 `1.88`；
Rust 1.88.0 只用于最低版本兼容性验证，不再用作默认或发布编译器。

本实验也不更新 Cargo dependency、feature 或 lockfile。历史
[`c-static-link-spike.md`](c-static-link-spike.md) 和
[`rquickjs-static-link.md`](rquickjs-static-link.md) 及其显式 1.88 runner
继续作为旧实验的可重复证据，不被本轮结果覆盖。

## 2. 升级触发因素

固定 1.88 不会自动得到 Cargo、rustc 或 LLVM 修复。升级依据是以下官方公告：

- [CVE-2026-33056](https://blog.rust-lang.org/2026/03/21/cve-2026-33056/)：
  Cargo 解包第三方 registry crate 的路径处理问题，Rust 1.94.1 更新相关依赖；
- [CVE-2026-5222](https://blog.rust-lang.org/2026/05/25/cve-2026-5222/)：
  Rust 1.68 至 1.96 所带 Cargo 的 sparse registry credential normalization
  问题；
- [CVE-2026-5223](https://blog.rust-lang.org/2026/05/25/cve-2026-5223/)：
  Rust 1.96 以前 Cargo 的第三方 registry symlink 解包问题；
- [Rust 1.97.1](https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/)：
  修复至少从 Rust 1.87 起存在的 LLVM optimization miscompilation。

这些公告不证明本项目或当前 lockfile 已被利用。前述 Cargo 问题需要特定第三方
registry 条件；但它们说明旧 Cargo 不适合作为日常依赖获取工具。LLVM
miscompilation 则直接削弱继续用 1.88 生成发布物的正确性假设。

## 3. 固定环境

### 3.1 默认与 MSRV

| 角色 | 固定版本 |
| --- | --- |
| default rustc | `rustc 1.97.1 (8bab26f4f 2026-07-14)` |
| default Cargo | `cargo 1.97.1 (c980f4866 2026-06-30)` |
| LLVM | `22.1.6` |
| rustfmt | `1.9.0-stable (8bab26f4f6 2026-07-14)` |
| Clippy | `0.1.97 (8bab26f4f6 2026-07-14)` |
| MSRV rustc | `rustc 1.88.0 (6b00bc388 2025-06-23)` |
| MSRV Cargo | `cargo 1.88.0 (873a06493 2025-05-10)` |

根 `rust-toolchain.toml` 使用 `minimal` profile，只附加 `clippy` 和
`rustfmt`。default 与 MSRV 是两个独立门禁。

### 3.2 Native consumer

Windows 使用：

- `x86_64-pc-windows-msvc`；
- MSVC C/C++ compiler `19.44.35207.1`；
- linker `14.44.35207.1`；
- `/MD` 与 Rust `+crt-static`、C `/MT` 两种 CRT 路径。

Linux 使用：

- `x86_64-unknown-linux-gnu`；
- `rust:1.97.1-slim-bookworm`；
- image ID
  `sha256:99e09cb2284e2ddbb73a995deee3e91783fd04d177602ccf6eab326d778ee777`；
- GCC `12.2.0`；
- `--network none`、2 CPU、2 GiB memory、只读源码、只读 host Cargo
  registry cache和 `cargo --offline`。

镜像 tag 仅用于说明来源；重跑时必须同时校验固定 digest。

## 4. Rust 门禁

每个 spike 在 1.97.1 下依次运行：

```text
cargo +1.97.1 fmt --manifest-path <manifest> --check
cargo +1.97.1 clippy --manifest-path <manifest> --all-targets --all-features -- -D warnings
cargo +1.97.1 test --manifest-path <manifest> --all-features
```

| Spike | rustfmt | Clippy | unit tests | doc tests |
| --- | --- | --- | ---: | ---: |
| `boa-rule-runtime` | pass | pass | 2 | 0 |
| `c-static-link` | pass | pass | 3 | 0 |
| `rquickjs-rule-runtime` | pass | pass | 30 | 0 |
| `rquickjs-static-link` | pass | pass | 2 | 0 |
| `signature-parser` | pass | pass | 15 | 0 |

1.97.1 Clippy 在 `signature-parser` 报告五处新 diagnostic：

- 三处 `collapsible_if`；
- 一处 `manual_saturating_arithmetic`；
- 一处 `manual_is_multiple_of`。

修正只替换等价控制流和标准整数操作，没有改变公开接口或预期结果。修改后的
source SHA-256 当时为
`fbfe13ea5135baff6c4ea0d24d0c837990536799a18133976c92bd16740c32f6`。
后续增加 `compareEP` cache/generic wrapper 与回归后，当前 source SHA-256 为
`e1ea895cfefd22a31aea05c89323008f95df44fec71480afb6da202b45cec958`；
同一源码在 1.88.0 和 1.97.1 下分别通过 rustfmt、`-D warnings` 和全部 15 项
测试，因此没有提高 MSRV。

后续 `rquickjs-rule-runtime` 增加 128 KiB VM stack-limit/recovery、native
callback panic-recovery fixture，以及带 SHA-256 输入 identity 的 292-rule
Nintendo 语料 oracle 后，更新源码 SHA-256 为
`141504df18200b89219e76a72687d86cf122d5a21943c451b4b21ec14fe98f3b`。
两套工具链 fixture 均捕获 stack overflow，并在 Rust eval 边界捕获 native
callback panic；4 MiB heap OOM 后同一 context 也恢复执行。语料 oracle 引入
固定纯 Rust `sha2@0.10.9`，因此 Cargo manifest、lockfile 和 spike 依赖闭包随之
更新；两套 release 构建的语料 oracle 都得到 4088/4088 次 `detect` 成功、
0 fallback 和 14/14 baseline 匹配。该变化不改变独立的 native static-link
consumer。随后依次增加真实 PE32/Cygwin32、ELF32/ELF64/Burneye、
Mach-O64 x86_64/arm64 Rust compiler、DEX035/QDBH、APK/ZIP QDBH、
Archive/ZIP metadata 和 PDF Tools object/string
规则差分；当前 source SHA-256 为
`4f9baf76a5e3960e569fdad778fcf861d07f7f61ffbc142040ef34589a63056a`。
两套工具链均通过 38 项测试，release 差分分别为 3/3、6/6、4/4、3/3、
3/3、3/3 和 3/3，且未新增 Cargo 依赖。

## 5. Native static-link 结果

下表记录观察到的产物，不承诺不同路径、链接时间或环境能够逐字节重现同一
artifact hash。可重复性门禁是固定输入和环境下的构建、链接、执行结果及依赖
集合；哈希用于标识本次观察到的具体产物。

### 5.1 Linux GNU

| Consumer | archive bytes / SHA-256 | executable bytes / SHA-256 | exit |
| --- | --- | --- | ---: |
| `c-static-link` | 21,989,188 / `2a036c365256b16ff9bb097f6ecd1a2231926c5cd5d7d26f4481425dd9b346a5` | 5,155,488 / `b2a6990a1834fee2d859d6338a11de8f39e553f4c9f9240fb47de4e19abbdefc` | 0 |
| `rquickjs-static-link` | 24,714,608 / `e1b01d0cb73be291063e10020bc75a0c0147a082ee6831de9e07e1c6584de4b4` | 6,651,064 / `91287d1c398e01a13bf5efb99eb519f3f3c43a7b1213c3996b24db7b741a2e6e` | 0 |

两者的 Rust native-static-libs 都是：

```text
-lgcc_s -lutil -lrt -lpthread -lm -ldl -lc
```

最终动态依赖：

- `c-static-link`：`libgcc_s.so.1`、`libc.so.6`、
  `ld-linux-x86-64.so.2`；
- `rquickjs-static-link`：在上述集合外增加 `libm.so.6`。

`c-static-link` 输出 `PASS c-static-link-smoke`；rquickjs C fixture 成功时
保持静默。两个 panic containment case 都观察到预期 panic hook stderr，随后
consumer 继续运行并以 0 退出。

### 5.2 Windows MSVC

| Consumer | CRT | staticlib bytes / SHA-256 | executable bytes / SHA-256 | exit |
| --- | --- | --- | --- | ---: |
| `c-static-link` | `/MD` | 12,030,768 / `980b16479ab1f0de820c6e2a69b8aa89fb83e3d142340c40a4e38aa4bb607156` | 119,296 / `2c71ae3d508fbd5babca31bde2bd67cea4034480cd012375c860d5ebe40e061d` | 0 |
| `c-static-link` | `/MT` | 12,030,768 / `167764bc569c00aa2865f94744f534732fe7db269c5042cbb0770679984bdad8` | 250,880 / `fbd14e6741c5972b2d62399ec317886476b5d20494d09c2c05022d65fd5eda19` | 0 |
| `rquickjs-static-link` | `/MD` | 15,735,194 / `e584768391854938c8fdf590774176361c7b9f0585a216854a6e097a5529bc0e` | 1,134,080 / `de7acb2fd7e27d54d375428830650cf260a357add4bf726262ef2f8cf4e171e3` | 0 |
| `rquickjs-static-link` | `/MT` | 15,772,692 / `6a58fd721bd2dc2b998cd0431d82b37ff01e52fcf79af650fc250a515930c661` | 1,376,768 / `da4ce375a2b9e3b3cafa28d1c899b5613580600adb299fb8a5026dd6790fc518` | 0 |

两者都声明
`kernel32.lib`、`ntdll.lib`、`userenv.lib`、`ws2_32.lib`、
`dbghelp.lib`，并按 CRT 路径声明 `/defaultlib:msvcrt` 或
`/defaultlib:libcmt`。

`/MT` 最终程序未动态依赖 Visual C runtime。`/MD` 程序按预期依赖
`VCRUNTIME140.dll` 和 Universal CRT API sets。rquickjs 程序还依赖
`bcryptprimitives.dll`。最终依赖中没有 QuickJS DLL。

## 6. 复现步骤

1. 校验根工具链与五个 spike 的输入哈希等于机器报告的 `input_hashes`。
2. 安装固定 `1.97.1` minimal toolchain、rustfmt 和 Clippy；另行保留
   `1.88.0` minimal toolchain用于 MSRV job。
3. 对五个 manifest 运行第 4 节三条命令。
4. 对 `signature-parser` 和补充 stack fixture 的 `rquickjs-rule-runtime` 使用
   `+1.88.0` 重跑相同门禁。
5. Linux 以固定 digest 启动容器，设置 `RUSTUP_TOOLCHAIN=1.97.1`，断网并只读
   挂载源码和 registry cache；分别 `cargo build --release --offline`，
   用 `gcc` 链接 C fixture，执行 fixture，并记录 `ldd` 与
   `cargo rustc -- --print native-static-libs`。
6. Windows 在 Visual Studio developer environment 中分别构建默认 `/MD`
   staticlib，以及使用
   `RUSTFLAGS=-C target-feature=+crt-static` 的 static CRT staticlib；用
   `cl /MD` 或 `cl /MT` 链接相应 C fixture，执行并记录 `dumpbin /DEPENDENTS`
   与 `native-static-libs`。

仓库历史 runner 显式固定 1.88.0，不能直接当作 1.97.1 runner 使用；本次复验
通过显式 `+1.97.1` 或 `RUSTUP_TOOLCHAIN=1.97.1` 覆盖，避免修改历史证据。

## 7. 结论与未覆盖项

现有五个 Phase 0 spike 与六条 Windows/Linux native C consumer 路径均兼容
Rust 1.97.1。已观察的 native system library 集合相对固定 1.88 报告没有增加，
而 `signature-parser` 与 `rquickjs-rule-runtime` 仍通过 Rust 1.88 MSRV 门禁。
因此，升级默认/发布工具链而保持 MSRV 1.88 有直接实验支持。

这不是 ADR 0011 的全部接受证据。仍未完成：

- Phase 1 的固定 default 1.97.1 与固定 MSRV 1.88 双 CI job；
- macOS x86_64/aarch64、Linux musl/aarch64、Windows GNU/aarch64；
- clean checkout 的 release provenance、SBOM 和 advisory CI；
- 对 artifact reproducibility 的多次 clean-build bit-for-bit 比较。

在这些门禁完成前，不应把本实验外推为所有目标平台或正式发布链已经完成。
