# ADR 0007：固定 Rust 1.88 作为当前工具链与 MSRV 基线

Status: Superseded

Last updated: 2026-07-27

Superseded by
[`0011-rust-1.97.1-default-toolchain.md`](0011-rust-1.97.1-default-toolchain.md).
Rust 1.88 remains the MSRV; only the default/development/release toolchain part
of this proposal is replaced.

## Context

仓库此前没有根 `rust-toolchain.toml`，因此裸 `cargo` 使用开发机默认工具链。
当前机器默认是 Rust/Cargo 1.86.0，而 Phase 0 的规则运行时、签名解析和静态链接
spike 已统一使用 Rust 1.88.0：

- `rquickjs@0.12.1` 声明最低 Rust 1.87，1.86 会在依赖解析后拒绝构建；
- `boa_engine@0.21.1` 声明最低 Rust 1.88；
- Windows MSVC 与 Linux GNU 静态链接证据固定到 Rust 1.88.0；
- 所有 spike 使用 edition 2024，项目尚未建立正式 workspace。

让开发者记住在每条命令中手工添加 `+1.88.0` 会造成验证路径分叉。另一方面，
直接跟随未固定的 `stable` 会让编译器、Cargo 行为、lint 和 native static
libraries 随时间漂移，不满足 Phase 0 的可重复性要求。

## Decision

在仓库根目录提交 `rust-toolchain.toml`，固定：

- channel `1.88.0`；
- minimal profile；
- `rustfmt` 与 `clippy` components。

所有当前 Rust spike 的 package metadata 显式声明 `rust-version = "1.88"`。因此：

- 在仓库内运行裸 `rustc`、`cargo`、`rustfmt` 和 `clippy` 使用同一固定工具链；
- Cargo 在不满足 MSRV 时给出显式诊断；
- 文档和重现脚本仍可保留 `+1.88.0`，用于强调外部环境中的精确版本；
- `Cargo.lock` 不因仅增加 package `rust-version` 而重写，除非 Cargo 证明 lockfile
  元数据确实需要变化。

此版本是当前 Phase 0/Phase 1 建库基线，不是无限期兼容承诺。正式 workspace
建立时在 `[workspace.package]` 继承 `rust-version = "1.88"`，并把 CI 分成：

- 固定 MSRV 1.88：证明最低版本契约；
- 经评审的当前 stable：尽早发现未来编译器和 lint 回归。

升级 MSRV 必须由依赖、安全、平台支持或语言能力的具体证据驱动，更新 CI、构建
镜像、静态链接基线和相关 ADR；不能只因本机 `rustup update` 而隐式升级。

## Alternatives considered

### 保持本机默认 1.86，spike 始终使用 `+1.88.0`

1.86 无法构建已选的 rquickjs，且不能构建 Boa 对照 spike。每条命令都依赖人工
选择工具链，容易让格式化、Clippy、测试和发布使用不同版本。

结论：拒绝。

### 固定最低可构建的 Rust 1.87

rquickjs 可以满足，但 Boa 0.21.1 对照 spike 仍要求 1.88；已有所有机器证据也都
来自 1.88。降低一个 minor 没有现成兼容收益，反而需要重新建立整套证据。

结论：拒绝当前阶段采用。

### 使用浮动 `stable`

可自动获得新编译器修复，但破坏可重复构建，并可能无审查地提高 MSRV、改变
Clippy 结果或静态库系统依赖。

结论：不作为默认工具链；只在 CI 的前瞻兼容任务中使用。

### 立即升级到比 1.88 更新的固定版本

可能获得编译器修复，但当前没有依赖或功能要求，也没有对应 Windows/Linux
静态链接与规则运行时基线。升级本身不能推进上游兼容。

结论：待出现证据后单独评审。

## Consequences

正面：

- 裸 Cargo 命令与已验证的 Phase 0 路径一致；
- MSRV 进入 package metadata，而不是只存在于调研文字；
- rustfmt、Clippy、编译器和 staticlib 证据使用同一版本；
- 后续 workspace 和 CI 有明确起点。

代价：

- 首次进入仓库的开发环境需要安装 1.88.0 及两个 components；
- 固定版本不会自动获得新编译器安全或正确性修复，需要主动升级评审；
- `rust-version = "1.88"` 对实际只需更低版本的独立 spike 是保守声明，但这些
  spike 是仓库验证资产，不是对外发布 crate。

## Evidence

- [`rule-runtime-spike.md`](../../research/rule-runtime-spike.md)
- [`rquickjs-rule-runtime-spike.md`](../../research/rquickjs-rule-runtime-spike.md)
- [`c-static-link-spike.md`](../../research/c-static-link-spike.md)
- [`rquickjs-static-link.md`](../../research/rquickjs-static-link.md)
- [`signature-language.md`](../../research/signature-language.md)
- 根目录 [`rust-toolchain.toml`](../../../rust-toolchain.toml)

## Acceptance conditions

本 ADR 从 Proposed 改为 Accepted 前必须满足：

- 裸 `rustc --version` 和 `cargo --version` 精确解析为 1.88.0；
- 所有当前 spike 的 `cargo fmt --check`、Clippy 和测试门禁在裸 Cargo 路径通过；
- Windows MSVC 和 Linux GNU staticlib C consumer 仍通过；
- Phase 1 workspace 从 `[workspace.package]` 继承 `rust-version`；
- CI 同时运行固定 MSRV 与经评审的 stable job，并对 stable failure 明确是否
  阻塞发布。
