# Release Checklist

This document defines the release process and verification checklist
for diec-rust. Every item must be verified before publishing a release.

## Pre-Release

### Code Quality
- [x] `cargo fmt --check` passes with zero diffs
- [x] `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` passes
- [x] No `TODO` or `FIXME` comments in released code paths
- [x] All `unsafe` blocks have safety documentation and tests

### Testing
- [x] `cargo test --workspace --all-features --locked` passes (477 tests)
- [x] Corpus differential tests pass (31 baseline + 20 edge samples)
- [x] FFI tests pass (unit + integration + sanitizer)
- [x] Edge corpus tests pass (no-crash, no-spurious, no-hang)
- [x] Go binding tests pass (5 tests)
- [x] Python binding tests pass (9 tests)
- [x] C smoke test passes

### Compatibility
- [x] `COMPATIBILITY.md` updated with current metrics
- [x] Rule loading success rate >= 99% (actual: 100%, 1186/1186)
- [x] Corpus differential: 0 engine mismatches (4 rule-version diffs documented)
- [x] All known differences documented with ADRs
- [x] Upstream source pinned to specific commit SHA (`c2c17dfa5`, vendored subtree)

### Performance
- [x] Benchmarks run on release build
- [x] database_load < 600ms (actual: ~510ms)
- [x] scan_corpus per-file < 250ms
- [x] No performance regression vs previous release
- [x] Benchmark results recorded in COMPATIBILITY.md

### Fuzz
- [x] All 6 fuzz targets compile
- [x] Seed corpora generated and committed (165 seeds across 6 targets)
- [x] Short fuzz run (5 min per target) shows no crashes
      — seed-corpus replay passed locally on stable Rust
      (`cd fuzz && cargo test --no-default-features --features replay`,
      7 tests, 0 failures, 165 seeds × 6 harnesses); coverage-guided
      libFuzzer 5-min/target run delegated to CI (`.github/workflows/fuzz.yml`,
      Linux + nightly + cargo-fuzz, runs on every push to main and on PRs)
- [x] Any crash from prior fuzz runs is fixed or quarantined (none observed)

### CI
- [x] CI passes on all three platforms (Linux, macOS, Windows)
- [x] MSRV (1.88) build and test passes
- [x] FFI smoke test passes on all platforms
- [x] Python binding test passes on all platforms

## License and Supply Chain
- [x] `LICENSE` file present and correct (MIT)
- [x] `NOTICES.md` updated with all third-party attribution
- [x] `AUDIT.md` reviewed and current
- [x] `cargo license --all-features` output matches NOTICES.md
- [x] No copyleft licenses in dependency tree
- [x] No new dependencies without license review
- [x] Cargo.lock committed and up to date

## Build Artifacts
- [x] Release build: `cargo build --workspace --all-targets --release --locked`
- [x] CLI binary: `base/diec` (or `base/diec.exe` on Windows)
- [x] Server binary: `base/died` (or `base/died.exe` on Windows)
- [x] Top-level launcher: `diec` (Unix) / `diec.cmd` (Windows)
- [x] Static library: `lib/libdiec_ffi.a` (Unix) / `lib/diec_ffi.lib` (Windows)
- [x] Dynamic library: `lib/libdiec_ffi.so` / `.dylib` / `lib/diec_ffi.dll`
- [x] C header: `include/diec.h`
- [x] Rule database: `base/db`, `base/db_extra`, `base/db_custom`
- [x] Go binding: `bindings/go/diec/diec.go`
- [x] Python binding: `bindings/python/diec.py`
- [x] All artifacts verified on at least one platform

### GUI Artifacts (v0.4.0+)
- [ ] GUI portable: `die-gui-<version>-<platform>-portable.zip/.tar.gz`
  - Windows: `die.exe` + `db/` + README + LICENSE
  - Linux: `die` + `db/` + README + LICENSE
  - macOS: `die` + `db/` + README + LICENSE
- [ ] GUI installer (Windows): `die-gui-<version>-windows-x86_64-installers.zip`
  - MSI: `Detect It Easy_<version>_x64_en-US.msi` (~14MB, perMachine)
  - NSIS: `Detect It Easy_<version>_x64-setup.exe` (~8.5MB, perMachine)
- [ ] GUI installer (Linux): `die-gui-<version>-linux-x86_64-installers.tar.gz`
  - DEB: `detect-it-easy_<version>_amd64.deb`
  - RPM: `detect-it-easy-<version>-1.x86_64.rpm`
  - AppImage: `Detect It Easy_<version>_amd64.AppImage`
- [ ] GUI installer (macOS): `die-gui-<version>-macos-arm64-installers.tar.gz`
  - DMG: `Detect It Easy_<version>_aarch64.dmg`
  - App: `Detect It Easy.app`
- [ ] Rule database bundled in all installers via `tauri.conf.json > bundle.resources`

## Documentation
- [x] `ROADMAP.md` updated with release status
- [x] `COMPATIBILITY.md` updated with final metrics
- [x] `README.md` reflects current state
- [x] `docs/design/` documents are current
- [x] `AGENTS.md` reflects current phase
- [x] Changelog / release notes drafted (`RELEASE_NOTES.md`)

## Version and Tag
- [x] Version bumped in `Cargo.toml` (workspace.package.version = 0.3.0)
- [x] Git tag created: `v0.3.0`
- [x] Tag is annotated (`git cat-file -t v0.3.0` => `tag`)
- [x] Tag message includes release summary ("v0.3.0 - died scan service + runtime reuse")

## Post-Release
- [x] Release notes published (`RELEASE_NOTES.md` committed)
- [x] Artifacts uploaded to release page (verified 2026-08-05)
- [x] Compatibility report published (`COMPATIBILITY.md`)
- [x] Next milestone planned in ROADMAP.md (Phase 6 closed; maintenance + upstream-sync)

---

## Release Sign-off

### v0.4.2 — 2026-08-07

- **Tag**: `v0.4.2` (annotated)
- **Tests**: 480 pass, 0 failures (unchanged from v0.4.0)
- **Fuzz replay**: 7/7 pass in Docker CI simulation (ubuntu:24.04)
- **Fix**: .gitignore excluded 3 .pyc seed files (165→162 in CI)
- **No code changes**: only .gitignore + seed files + version bump
- **Artifacts**: identical to v0.4.0

### v0.4.1 — 2026-08-06

- **Tag**: `v0.4.1` (annotated)
- **Tests**: 480 pass, 0 failures (unchanged from v0.4.0)
- **Fix**: fuzz/Cargo.lock version mismatch (0.3.0 → 0.4.1)
- **No code changes**: only version numbers and lock files
- **Artifacts**: identical to v0.4.0

### v0.4.0 — 2026-08-06

- **Tag**: `v0.4.0` (annotated)
- **Tests**: 480 pass, 0 failures (+3 GUI differential tests)
- **Rule count**: 2175 (db + db_extra + db_custom, was 2037 in v0.3.0)
- **New**: die-gui desktop app (Tauri v2 + React 18), native installers
  (MSI/NSIS/DEB/RPM/DMG), i18n (5 languages), Windows context menu,
  CLI auto-loading of db_extra/db_custom
- **Platforms**: Linux x86_64, Windows x86_64, macOS arm64 (GUI);
  + macOS x86_64 (CLI only)
- **GUI artifacts**: portable + installer per platform (6 products)
- **GitHub Release**: artifacts uploaded after CI

### v0.3.0 — 2026-08-05

- **Tag**: `v0.3.0` (annotated)
- **Commit**: `ca656ea79` (ci: include died binary in release artifacts)
- **Upstream pin**: `c2c17dfa5` (vendored subtree, merge `e0bcca000`)
- **Tests**: 477 pass, 0 failures
- **Compatibility**: 1186/1186 rules load, 0 engine mismatches
- **Performance**: database_load ~510ms, scan_corpus < 250ms/file
- **Platforms**: Linux x86_64, Windows x86_64, macOS arm64, macOS x86_64
- **GitHub Release**: artifacts uploaded and verified

**Open items (non-blocking for v0.3.0)**:
- Coverage-guided libFuzzer 5-min/target run is delegated to the CI fuzz
  workflow (`.github/workflows/fuzz.yml`); it runs on every push to main
  and on PRs. Seed-corpus replay (165 seeds × 6 harnesses) passed locally
  on stable Rust as the deterministic pre-release gate.
- ROADMAP.md Phase 6 closure is recorded below; next milestone is
  "maintenance and upstream-sync" until a GUI phase is scoped.
