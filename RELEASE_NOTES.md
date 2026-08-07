# Release Notes

## diec-rust v0.4.5

Patch release fixing the last libFuzzer CI job (fuzz_scan_ffi)
that failed due to dead code elimination removing diec-ffi's
#[no_mangle] symbols from the rlib.

### Fixes

- **Force-link diec-ffi symbols**: fuzz_scan_ffi.rs uses `extern "C"`
  to declare diec-ffi's C ABI functions, but the Rust linker removes
  unreferenced `#[no_mangle]` symbols during dead code elimination.
  Added a `const _: ()` block that references `diec_ffi::scan::`
  functions to force the linker to retain them, allowing the
  `extern "C"` declarations to resolve at link time.

### CI Status (v0.4.4 → v0.4.5)

| Job | v0.4.4 | v0.4.5 (expected) |
| --- | --- | --- |
| seed replay (all 3 platforms) | ✅ | ✅ |
| libFuzzer (5 other targets) | ✅ | ✅ |
| libFuzzer (fuzz_scan_ffi) | ❌ undefined symbol | ✅ (fixed) |

### Verification (Docker CI simulation)

- ubuntu:24.04 + nightly Rust + cargo-fuzz v0.13.2
- `cargo +nightly fuzz build fuzz_scan_ffi`: compiles successfully
- Seed replay: 7/7 pass (165 seeds)

### No Functional Code Changes

Only fuzz_scan_ffi.rs linker fix + version bump.
All features identical to v0.4.0.

## diec-rust v0.4.4

Patch release fixing the last libFuzzer CI job (fuzz_scan_ffi)
that failed due to diec-ffi not being linked as a regular dependency.

### Fixes

- **diec-ffi linking**: Moved `diec-ffi` from `[dev-dependencies]` to
  `[dependencies]` in fuzz/Cargo.toml. The `fuzz_scan_ffi` target uses
  `extern "C"` declarations referencing diec-ffi symbols, but
  dev-dependencies are not linked into binary targets during
  cargo-fuzz builds, causing "undefined symbol" linker errors.

### CI Status (v0.4.3 → v0.4.4)

| Job | v0.4.3 | v0.4.4 (expected) |
| --- | --- | --- |
| seed replay (ubuntu) | ✅ | ✅ |
| seed replay (windows) | ✅ | ✅ |
| seed replay (macos) | ✅ | ✅ |
| libFuzzer (fuzz_byte_source) | ✅ | ✅ |
| libFuzzer (fuzz_byte_view_subview) | ✅ | ✅ |
| libFuzzer (fuzz_format_probe) | ✅ | ✅ |
| libFuzzer (fuzz_output_render) | ✅ | ✅ |
| libFuzzer (fuzz_scan_engine) | ✅ | ✅ |
| libFuzzer (fuzz_scan_ffi) | ❌ undefined symbol | ✅ (fixed) |

### No Functional Code Changes

Only fuzz/Cargo.toml dependency placement + version bump.
All features identical to v0.4.0.

## diec-rust v0.4.3

Patch release fixing libFuzzer CI jobs that had been failing since
v0.3.0 due to missing cargo-fuzz metadata.

### Fixes

- **cargo-fuzz metadata**: Added `[package.metadata] cargo-fuzz = true`
  to fuzz/Cargo.toml. Without this, cargo-fuzz searched for
  `fuzz/fuzz/Cargo.toml` (double nesting) and failed with
  "No such file or directory".
- **fuzz.yml path fix**: Run cargo-fuzz from repo root instead of
  `cd fuzz` first, since cargo-fuzz auto-discovers the fuzz/ directory
  via the metadata marker.
- **Independent workspace**: Added `[workspace] members = ["."]` to
  fuzz/Cargo.toml for proper independent workspace declaration.

### Verification (Docker CI simulation)

- ubuntu:24.04 + nightly Rust + cargo-fuzz v0.13.2
- `cargo fuzz list` correctly shows all 6 targets:
  fuzz_byte_source, fuzz_byte_view_subview, fuzz_format_probe,
  fuzz_output_render, fuzz_scan_engine, fuzz_scan_ffi
- Seed replay: 7/7 pass (165 seeds)

### No Functional Code Changes

Only fuzz/Cargo.toml metadata + fuzz.yml CI config + version bump.
All features identical to v0.4.0.

## diec-rust v0.4.2

Patch release fixing fuzz CI failure caused by .gitignore excluding
.pyc seed files from the repository.

### Fixes

- **Track .pyc fuzz seed files**: The `.gitignore` rule `*.py[cod]`
  was matching `fuzz/corpus/*/minimal.pyc` seed files, causing them
  to be excluded from git. CI fresh checkout got only 162 seeds
  instead of 165, failing `replay_seed_count_matches_release`.
  Added negation rule `!fuzz/corpus/**/*.pyc` and committed the 3
  missing .pyc files (format_probe, scan_engine, scan_ffi).

### Verification (Docker CI simulation)

- ubuntu:24.04 + stable Rust + clean git archive checkout
- Seed count: 165 (was 162 in v0.4.0/v0.4.1 CI)
- `cargo test --no-default-features --features replay`: 7/7 pass
- `replay_seed_count_matches_release`: ok

### No Functional Code Changes

Only .gitignore fix + 3 seed files + version bump.
All features identical to v0.4.0.

## diec-rust v0.4.1

Patch release fixing fuzz/Cargo.lock version mismatch that caused
CI fuzz workflow to fail on v0.4.0 tag.

### Fixes

- **fuzz/Cargo.lock updated to 0.4.1**: The fuzz workspace Cargo.lock
  was not updated when the workspace version was bumped, causing all
  9 fuzz CI jobs (3 replay + 6 libFuzzer) to fail with exit code 101.
  All 6 diec-* entries updated to match the workspace version.

### No Code Changes

No functional code changes — only version numbers and lock files.
All features and artifacts are identical to v0.4.0.

## diec-rust v0.4.0

Minor release adding the **die-gui** desktop application (Tauri v2 + React 18)
with full feature parity to the upstream DIE GUI, plus native installer
packages and CLI auto-loading of extra rule databases.

### New Features

- **die-gui desktop application** (ADR 0018):
  - Tauri v2 + React 18 + TypeScript GUI with dark/light theme
  - Full feature parity to upstream `die` GUI:
    - 7A core: file/dir scan, drag-drop, stop, settings persistence,
      recent files, fullscreen, keyboard shortcuts
    - 7B advanced: hex viewer, disassembler (Intel/GAS/NASM),
      C++/Rust demangle, signature browser with source view/edit/run/debug
    - 7C extensions: YARA scanner, PEID scanner, online lookup,
      archive viewer, data converter, file info panel (hashes/entropy/
      sections/symbols), memory map viewer
  - Internationalization (i18n): English, Chinese (Simplified), Russian,
    German, French — all UI strings externalized via react-i18next
  - Windows Explorer context menu integration: one-click add/remove
    "Scan with DIE" from Settings panel (HKCU registry, no admin needed)
  - Single-instance support: launching from context menu focuses existing
    window and auto-loads the right-clicked file

- **Native installer packages** (MSI/NSIS/DEB/RPM/DMG):
  - Windows: MSI (WiX, perMachine, ~14MB) + NSIS (~9.3MB)
  - Linux: DEB + RPM + AppImage
  - macOS: DMG + .app bundle
  - All installers bundle the complete rule database (7 data directories)
  - Portable archives (zip/tar.gz) also provided for each platform

- **CLI auto-loading of db_extra/db_custom**:
  - CLI now auto-discovers `db_extra/` and `db_custom/` alongside the
    main `db/` directory, matching upstream DIE-engine behavior
  - Rule count: 2037 → 2175 (+138 from db_extra)
  - Users can still override with `--extradb`/`--customdb`

- **Complete data directory bundling**:
  - All 7 upstream data directories packaged: `db/`, `db_extra/`,
    `db_custom/`, `dbs_min/`, `dbs_special/`, `peid_rules/`, `yara_rules/`
  - GUI auto-loads db + db_extra + db_custom for scanning
  - PEID scanner auto-loads `peid_rules/PE/userdb.txt`
  - YARA scanner provides dropdown to load built-in `yara_rules/*.yar`

- **GUI vs CLI differential tests**:
  - `gui_cli_differential.rs`: 2 tests verifying GUI `scan_once` matches
    CLI `scan_bytes` on 32 corpus files + flag combination consistency

### Improvements

- Test count: 480 tests (up from 477, +3 GUI differential tests)
- Rule count: 2175 rules loaded (up from 2037, includes db_extra)
- New crate: `die-gui` (Tauri v2 GUI adapter, no core-layer dependency)
- Tri-platform GUI CI: Linux (webkit2gtk-4.1), macOS (arm64), Windows
- ADR 0018 (Tauri v2 GUI framework), ADR 0019 (auto-update deferred)

### Artifacts

**CLI** (4 platforms, unchanged from v0.3.0):
- `diec` / `diec.exe` — CLI binary
- `died` / `died.exe` — HTTP/JSON scan service
- `libdiec_ffi.*` — static and dynamic libraries
- `include/diec.h` — C header
- `db/` + `db_extra/` + `db_custom/` — rule databases
- `bindings/python/diec.py` + `bindings/go/diec/diec.go`

**GUI** (3 platforms, new in v0.4.0):
- Portable: `die-gui-<version>-<platform>-portable.zip/.tar.gz`
- Windows installers: MSI + NSIS exe
- Linux installers: DEB + RPM + AppImage
- macOS installers: DMG + .app bundle

### Documentation

- [docs/design/phase8-gui.md](docs/design/phase8-gui.md) — Phase 8 GUI design
- ADR 0018 (Tauri v2 framework selection) — Accepted
- ADR 0019 (auto-update deferred) — Accepted
- NOTICES.md updated with die-gui dependencies (tauri, iced-x86,
  cpp_demangle, yara-x, winreg, react, etc.)

### Testing

480 tests, 6 fuzz targets, 0 failures. Tri-platform GUI CI.

### License

MIT — see [LICENSE](LICENSE) and [NOTICES.md](NOTICES.md)

## diec-rust v0.3.0

Minor release adding the died (die daemon) HTTP/JSON scan service and
runtime reuse optimization for batch scanning.

### New Features

- **died (die daemon) HTTP/JSON service** (ADR 0017):
  - `GET /health` — service status and version info
  - `POST /scan/path` — scan local file by path
  - `POST /scan/bytes` — scan uploaded file content
  - Security: `--allow-root` path restriction, `--max-file-size`,
    `--max-request-size`, `--scan-timeout`
  - Windows service support: `died install` / `died uninstall` via `sc.exe`
  - Linux systemd unit template generation
  - Packaging: DEB (cargo-deb), RPM (spec), MSI (cargo-wix)
  - API documentation with curl/PowerShell/Python/Go client examples
    ([docs/died-api.md](docs/died-api.md))

- **Scanner runtime reuse** (ADR 0016):
  - `diec_engine::Scanner` — stateful scanner that reuses QuickJS
    runtimes across files of the same file type
  - `RquickjsRuntime::reinit()` — clears results and re-runs type init
    scripts to update host aliases for a new file
  - Differential verification: reuse vs no-reuse 0 mismatches
  - BudgetExceeded error evicts the runtime for fresh creation

- **Database::version()** (ADR 0017):
  - Loads commit/synced_at from `rule-source-manifest.json`
  - Fallback to `DatabaseVersion::unknown(rule_count)` when manifest
    is not available

### Improvements

- Rule count: 2037 rules loaded (up from 1186 — includes db_extra)
- Test count: 477 tests (up from 459)
- New crate: `diec-server` (thin adapter over `diec-engine`, no core
  layer dependency on CLI or FFI)

### Artifacts

Each platform archive now also includes:
- `bin/died` — HTTP/JSON scan service daemon
- `bin/died.exe` (Windows) — with Windows service support

### Documentation

- [docs/died-api.md](docs/died-api.md) — full API reference with client
  examples in curl, PowerShell, Python, and Go
- [crates/diec-server/packaging/README.md](crates/diec-server/packaging/README.md)
  — DEB/RPM/MSI packaging guide
- ADR 0016 (runtime reuse) and ADR 0017 (scan service layer) — Accepted

### Testing

477 tests, 6 fuzz targets, 0 failures.

### License

MIT — see [LICENSE](LICENSE) and [NOTICES.md](NOTICES.md)

## diec-rust v0.2.2

Patch release that fixes the v0.2.1 release build failure.

### Bug Fixes

- **Cargo.lock sync**: The v0.2.1 release commit bumped
  `workspace.package.version` in `Cargo.toml` from 0.2.0 to 0.2.1 but
  forgot to regenerate and commit `Cargo.lock`. Because the release
  workflow builds with `--locked`, every build job failed with
  "cannot update the lock file because --locked was passed". The lock
  file is now regenerated and committed alongside the version bump.

### No Code Changes

No runtime, CLI, FFI, or rule changes versus v0.2.1 — this release
exists solely to produce working artifacts that v0.2.1 could not.

## diec-rust v0.2.0

First public release of diec-rust, a Rust reimplementation of Detect It Easy.

### Features

- **Format detection**: 20 format probes (PE, ELF, Mach-O, DEX, Java
  class, ZIP, tar, PDF, PNG, JPEG, BMP, WAV, ISO 9660, CFBF, and more)
- **Rule compatibility**: 1186/1186 upstream rules loaded (100%)
- **Native binary parsing**: pelite (PE) and goblin (ELF/Mach-O) replace
  hand-written JavaScript parsing for imports, exports, resources,
  manifest, version info, .NET CLR detection, and Authenticode
- **CLI**: full-featured with JSON/XML/CSV/TSV output, recursive scan,
  entropy analysis, profiling, custom databases
- **C ABI**: stable versioned C ABI with opaque handles
- **Language bindings**: Go/cgo and Python ctypes
- **Cross-platform**: Linux, macOS (arm64 + x86_64), Windows

### Performance

- Database load: ~510ms (parallel I/O)
- Format probe: sub-microsecond
- PE32 scan: ~89ms (native pelite + batch cache)
- ELF64 scan: ~15ms (native goblin)
- Mach-O 64 scan: ~14ms (native goblin)

### Artifacts

Each platform archive contains:
- `bin/diec` — CLI binary
- `lib/libdiec_ffi.*` — static and dynamic libraries
- `include/diec.h` — C header
- `db/` — pinned rule database (MIT licensed)
- `bindings/python/diec.py` — Python binding
- `bindings/go/diec/diec.go` — Go binding

### Rule Database

Rules are bundled from the upstream Detect-It-Easy repository at a
fixed commit (c2c17dfa). To use a different or updated database:

```sh
diec --customdb /path/to/rules/ file.exe
```

Or set the `DIEC_DB_PATH` environment variable.

### Compatibility

- Rule loading: 1186/1186 (100%)
- Corpus differential: 31 baseline + 20 edge samples, 0 mismatches
- Known differences: 4 rule version diffs (archive:Zip vs format:ZIP),
  all documented in [COMPATIBILITY.md](COMPATIBILITY.md)

### Testing

459 tests, 6 fuzz targets, 0 failures.

### License

MIT — see [LICENSE](LICENSE) and [NOTICES.md](NOTICES.md)
