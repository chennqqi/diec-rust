# Release Notes

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
