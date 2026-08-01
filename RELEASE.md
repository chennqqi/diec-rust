# Release Checklist

This document defines the release process and verification checklist
for diec-rust. Every item must be verified before publishing a release.

## Pre-Release

### Code Quality
- [ ] `cargo fmt --check` passes with zero diffs
- [ ] `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` passes
- [ ] No `TODO` or `FIXME` comments in released code paths
- [ ] All `unsafe` blocks have safety documentation and tests

### Testing
- [ ] `cargo test --workspace --all-features --locked` passes (414+ tests)
- [ ] Corpus differential tests pass (27 baseline + 20 edge samples)
- [ ] FFI tests pass (unit + integration + sanitizer)
- [ ] Edge corpus tests pass (no-crash, no-spurious, no-hang)
- [ ] Go binding tests pass (5 tests)
- [ ] Python binding tests pass (9 tests)
- [ ] C smoke test passes

### Compatibility
- [ ] `COMPATIBILITY.md` updated with current metrics
- [ ] Rule loading success rate >= 99%
- [ ] Corpus differential: 0 mismatches
- [ ] All known differences documented with ADRs
- [ ] Upstream submodule pinned to specific commit SHA

### Performance
- [ ] Benchmarks run on release build
- [ ] database_load < 500ms (was ~1.2s, now ~400ms)
- [ ] scan_corpus per-file < 250ms
- [ ] No performance regression vs previous release
- [ ] Benchmark results recorded in COMPATIBILITY.md

### Fuzz
- [ ] All 6 fuzz targets compile
- [ ] Seed corpora generated and committed
- [ ] Short fuzz run (5 min per target) shows no crashes
- [ ] Any crash from prior fuzz runs is fixed or quarantined

### CI
- [ ] CI passes on all three platforms (Linux, macOS, Windows)
- [ ] MSRV (1.88) build and test passes
- [ ] FFI smoke test passes on all platforms
- [ ] Python binding test passes on all platforms

## License and Supply Chain
- [ ] `LICENSE` file present and correct (MIT)
- [ ] `NOTICES.md` updated with all third-party attribution
- [ ] `AUDIT.md` reviewed and current
- [ ] `cargo license --all-features` output matches NOTICES.md
- [ ] No copyleft licenses in dependency tree
- [ ] No new dependencies without license review
- [ ] Cargo.lock committed and up to date

## Build Artifacts
- [ ] Release build: `cargo build --workspace --all-targets --release --locked`
- [ ] CLI binary: `target/release/diec` (or .exe on Windows)
- [ ] Static library: `target/release/libdiec_ffi.a` (Unix) / `diec_ffi.lib` (Windows)
- [ ] Dynamic library: `target/release/libdiec_ffi.so` / `.dylib` / `diec_ffi.dll`
- [ ] C header: `include/diec.h`
- [ ] Go binding: `bindings/go/diec/diec.go`
- [ ] Python binding: `bindings/python/diec.py`
- [ ] All artifacts verified on at least one platform

## Documentation
- [ ] `ROADMAP.md` updated with release status
- [ ] `COMPATIBILITY.md` updated with final metrics
- [ ] `README.md` reflects current state
- [ ] `docs/design/` documents are current
- [ ] `AGENTS.md` reflects current phase
- [ ] Changelog / release notes drafted

## Version and Tag
- [ ] Version bumped in `Cargo.toml` (workspace.package.version)
- [ ] Git tag created: `vX.Y.Z`
- [ ] Tag is signed or annotated
- [ ] Tag message includes release summary

## Post-Release
- [ ] Release notes published
- [ ] Artifacts uploaded to release page
- [ ] Compatibility report published
- [ ] Next milestone planned in ROADMAP.md
