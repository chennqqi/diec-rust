# diec-rust

A Rust rewrite of [Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE).

[中文文档](README.zh-CN.md)

## Why

diec-rust is a from-scratch Rust reimplementation of DIE. It maintains
**1:1 compatibility** with upstream — same detection capabilities, same
rule semantics, same I/O behavior — while delivering measurable
improvements in robustness, safety, and performance.

## Key Points

- **1:1 DIE compatibility**: loads 2037 upstream rules verbatim, produces
  identical detection results and output formats (JSON, XML, CSV, TSV, text)
- **Rust safety**: zero `unsafe` in core, memory-safe by construction,
  panic containment at FFI boundary — no crashes on malformed input
- **Performance**: parallel database loading, sub-microsecond format
  probing
- **Multi-language bindings**: C ABI + Go/cgo + Python ctypes out of
  the box

## Benchmark Results

All measurements from release builds on Windows 11, AMD Ryzen. Scripts
and raw data are included — you can reproduce these results yourself.

### Database Loading

| Metric | Value | Method |
|--------|-------|--------|
| Parallel load (criterion) | 160ms | `cargo bench -p diec-engine --bench scan -- database_load` |
| CLI cold start (first run) | 1589ms | Includes process startup + JIT |
| CLI warm start (avg of 4) | 487ms | `diec --showdatabase` |
| CLI warm start (min) | 456ms | After first run |

### Scan Performance (criterion, 20 samples)

| File type | Time |
|-----------|------|
| ELF64 minimal | 11.2ms |
| Mach-O 64 minimal | 14.8ms |
| PE32 minimal | 71.9ms |
| Java class | 92.1ms |
| DEX | 95.5ms |
| PDF | 102.2ms |
| PNG | 101.2ms |
| tar archive | 152.2ms |
| Zip archive | 170.2ms |
| --alltypes (Zip) | 288.4ms |

### Format Probing (criterion, 50 samples)

| Format | Time |
|--------|------|
| empty | 60ns |
| text | 213ns |
| Zip | 285ns |
| PNG | 289ns |
| tar | 302ns |
| PDF | 310ns |
| Mach-O 64 | 324ns |
| ELF64 | 335ns |
| ISO 9660 | 337ns |
| DEX | 366ns |
| Java Class | 379ns |
| PE32 | 407ns |

### Reproduce

```sh
# Run benchmarks
python tools/benchmark/run_benchmarks.py --quick

# Or run directly
cargo bench -p diec-engine --bench scan
cargo bench -p diec-formats --bench probe
```

Raw JSON results: `tools/benchmark/results/benchmark_results.json`

## Compatibility Results

### Rule Database

| Metric | Value |
|--------|-------|
| Total .sg rule files | 2037 |
| Rule types | 29 (PE: 834, MSDOS: 349, Binary: 292, COM: 245, ...) |
| Database size | 2.7 MB |

### Test Suite

| Category | Result |
|----------|--------|
| Total tests | 414 passed, 0 failed |
| Clippy | 0 warnings |
| Fuzz targets | 6 (core, formats, engine, output, FFI) |
| Corpus samples | 27 baseline + 20 edge cases |

### Corpus Detection (--alltypes)

All 27 baseline corpus files produce correct format detections. All 20
edge-case files (truncated, malformed, oversized) complete without crash
or hang.

### Reproduce

```sh
# Run full compatibility test
python tools/benchmark/run_compatibility.py

# Run specific tests
cargo test --workspace --all-features --locked
cargo test -p diec-engine --test corpus_differential
cargo test -p diec-engine --test edge_corpus
```

Raw JSON results: `tools/benchmark/results/compatibility_results.json`

## Quick Start

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust
cargo build --workspace --release
```

### CLI

```sh
./target/release/diec file.exe
./target/release/diec --output json file.exe
./target/release/diec --alltypes file.exe
./target/release/diec --recursive /path/to/dir/
```

### Python

```python
from diec import Database, scan_bytes
db = Database("db/")
result = scan_bytes(db, open("file.exe","rb").read())
print(result.detections)
```

### Go

```go
db, _ := diec.NewDatabase("db/")
result, _ := diec.ScanBytes(db, data)
```

### C

```c
#include "diec.h"
diec_v1_scan_bytes(db, data, size, NULL, NULL, &result, &error);
```

## Rule Database

Rules are bundled in release artifacts (2.7 MB, MIT licensed).
Override with `--customdb <path>` or `DIEC_DB_PATH` env var.

## Status

414 tests, 6 fuzz targets, 0 failures. Linux/macOS/Windows.

See [ROADMAP.md](ROADMAP.md) for details.

## License

MIT — same as upstream. See [NOTICES.md](NOTICES.md) for attribution.
