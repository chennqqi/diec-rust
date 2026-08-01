# Release Notes

## diec-rust v0.1.0

First release of diec-rust, a Rust reimplementation of Detect It Easy.

### Features

- **Format detection**: 20 format probes (PE, ELF, Mach-O, DEX, Java
  class, ZIP, tar, PDF, PNG, JPEG, BMP, WAV, ISO 9660, CFBF, and more)
- **Rule compatibility**: 1184/1186 upstream rules loaded (99.83%)
- **CLI**: full-featured with JSON/XML/CSV/TSV output, recursive scan,
  entropy analysis, profiling, custom databases
- **C ABI**: stable versioned C ABI with opaque handles
- **Language bindings**: Go/cgo and Python ctypes
- **Cross-platform**: Linux, macOS, Windows

### Performance

- Database load: ~400ms (parallel I/O)
- Format probe: sub-microsecond
- Scan (default): ~190ms per file

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
fixed commit. To use a different or updated database:

```sh
diec --customdb /path/to/rules/ file.exe
```

Or set the `DIEC_DB_PATH` environment variable.

### Compatibility

See [COMPATIBILITY.md](COMPATIBILITY.md) for the full compatibility
report.

### Testing

414 tests, 6 fuzz targets, 0 failures.

### License

MIT — see [LICENSE](LICENSE) and [NOTICES.md](NOTICES.md)
