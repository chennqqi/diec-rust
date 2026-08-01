# diec-rust

A Rust rewrite of [Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE).

[中文文档](README.zh-CN.md)

## Why

diec-rust is a from-scratch Rust reimplementation of DIE. It maintains
**1:1 compatibility** with upstream — same detection capabilities, same
rule semantics, same I/O behavior — while delivering measurable
improvements in robustness, safety, and performance.

## Key Points

- **1:1 DIE compatibility**: loads 1184/1186 upstream rules verbatim
  (99.83%), produces identical detection results and output formats
  (JSON, XML, CSV, TSV, text)
- **Rust safety**: zero `unsafe` in core, memory-safe by construction,
  panic containment at FFI boundary — no crashes on malformed input
- **Performance**: parallel database loading (~400ms vs ~1.2s
  upstream), sub-microsecond format probing
- **Multi-language bindings**: C ABI + Go/cgo + Python ctypes out of
  the box

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
