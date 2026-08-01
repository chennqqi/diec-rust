# Supply Chain Audit

This document records the supply chain security audit for diec-rust.

Last updated: 2026-08-01

## Dependency Policy

1. **License compatibility**: All dependencies must use permissive licenses
   (MIT, Apache-2.0, BSD, Zlib, Unicode-3.0, BSL-1.0). No GPL/AGPL/copyleft.
2. **Minimum release age**: New dependencies must be published at least 7
   days before adoption. Newly published versions are not vetted.
3. **No floating ranges**: Dependencies use pinned versions in Cargo.lock.
   No `latest`, `*`, or unbounded `>=` ranges.
4. **Audit trail**: All dependencies are listed in `NOTICES.md` with
   license and purpose.

## Audit Checklist

- [x] `cargo license` output reviewed — all permissive licenses
- [x] No GPL/AGPL/copyleft licenses in dependency tree
- [x] All direct dependencies identified with purpose
- [x] QuickJS (via rquickjs-sys) is MIT licensed
- [x] Upstream DIE-engine is MIT licensed
- [x] Corpus is project-generated (no third-party bytes)
- [x] No secrets, API keys, or credentials in repository
- [x] CI uses pinned action versions (SHA-pinned)
- [x] `Cargo.lock` is committed and verified with `--locked`

## CI Security

- GitHub Actions are pinned to specific commit SHAs (not tags)
- `persist-credentials: false` on all checkout steps
- `permissions: contents: read` (minimal scope)
- Concurrency group prevents redundant CI runs

## Submodule Security

- `upstream/Detect-It-Easy` is a git submodule pointing to the fixed
  upstream DIE-engine repository
- The submodule is pinned to a specific commit SHA
- Rules are loaded verbatim; no modifications to upstream files

## Known Risks

1. **rquickjs-sys builds QuickJS from source**: The QuickJS C source is
   bundled in the crate and compiled via `cc`. This is inherent to the
   rule execution approach. Risk is mitigated by:
   - Using the published `rquickjs` crate (not vendored QuickJS)
   - QuickJS is MIT licensed and widely used
   - The build is reproducible with `--locked`

2. **JavaScript runtime in scan path**: Rule execution involves a JS VM.
   Risk is mitigated by:
   - All inputs are untrusted and validated before reaching the VM
   - The VM has fuel/timeout limits (see scan options)
   - Panic containment at the FFI boundary
