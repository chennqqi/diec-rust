# Release Notes

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
