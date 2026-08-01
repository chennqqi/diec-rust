# diec-rust

A Rust reimplementation of [horsicq/DIE-engine](https://github.com/horsicq/DIE-engine)
— Detect It Easy.

[中文文档](README.zh-CN.md)

## Overview

diec-rust is a from-scratch Rust implementation of the Detect It Easy
file identification engine. It maintains detection capability and rule
semantics compatibility with a fixed upstream version while improving
architecture, code quality, performance, dependency footprint, and
portability.

"Rust rewrite" does not mean line-by-line translation from C++.
What is compatible: capabilities, rule semantics, I/O behavior, and
boundary conditions. What is new: clean, safe, testable Rust architecture.

## Features

- **Format detection**: 20 format probes (PE, ELF, Mach-O, DEX, Java
  class, ZIP, tar, PDF, PNG, JPEG, BMP, WAV, ISO 9660, CFBF, and more)
- **Rule compatibility**: loads 1184/1186 upstream rules verbatim (99.83%)
- **CLI**: full-featured command-line tool with JSON/XML/CSV/TSV output
- **C ABI**: stable versioned C ABI with opaque handles for FFI
- **Language bindings**: Go/cgo and Python ctypes
- **Cross-platform**: Linux, macOS, Windows (MSRV 1.88)
- **Safe**: no `unsafe` in core, panic containment at FFI boundary
- **Fast**: parallel database loading (~400ms), sub-microsecond format
  probing

## Quick Start

### Build

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust
cargo build --workspace --release
```

### CLI Usage

```sh
# Scan a single file
./target/release/diec file.exe

# JSON output
./target/release/diec --output json file.exe

# Recursive directory scan
./target/release/diec --recursive /path/to/dir/

# Use custom database
./target/release/diec --customdb /path/to/rules/ file.exe
```

### Database

The rule database is bundled in release artifacts. The CLI searches
for it in this order:

1. `--db <path>` flag
2. `DIEC_DB_PATH` environment variable
3. `db/` directory adjacent to the executable
4. System paths (`/usr/share/diec/db`, `/opt/diec/db`)
5. Development paths (`upstream/Detect-It-Easy/db`)

To use updated rules, download a newer release or use `--customdb`.

### C ABI

```c
#include "diec.h"

DiecDatabaseHandle db;
diec_v1_database_builder_new(&builder, &error);
diec_v1_database_builder_add_path_utf8(builder, 0, db_path, len, 0, &error);
diec_v1_database_builder_build(builder, &db, &error);

DiecResultHandle result;
diec_v1_scan_bytes(db, data, size, NULL, NULL, &result, &error);
```

### Python

```python
from diec import Database, scan_bytes

db = Database("/path/to/db")
result = scan_bytes(db, b"file data")
print(result.detections)
```

### Go

```go
db, err := diec.NewDatabase("/path/to/db")
result, err := diec.ScanBytes(db, []byte("file data"))
```

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | Done | Design gate |
| 1 | Done | Engineering scaffold & test infrastructure |
| 2 | Done | Core data model & format detection |
| 3 | Done | Rule compatibility runtime |
| 4 | Done | CLI feature parity |
| 5 | Done | C ABI & language integration |
| 6 | In progress | Compatibility, performance & release prep |

See [ROADMAP.md](ROADMAP.md) for detailed progress.

## Documentation

- [ROADMAP.md](ROADMAP.md) — Phase plan, deliverables, and milestones
- [AGENTS.md](AGENTS.md) — Engineering constraints for development
- [COMPATIBILITY.md](COMPATIBILITY.md) — Compatibility report
- [RELEASE.md](RELEASE.md) — Release checklist
- [NOTICES.md](NOTICES.md) — Third-party attribution
- [AUDIT.md](AUDIT.md) — Supply chain audit
- `docs/design/` — Architecture, API, ABI, and testing design
- `docs/research/` — Upstream analysis and experiment results

## Testing

```sh
# Run all tests
cargo test --workspace --all-features

# Run benchmarks
cargo bench -p diec-engine
cargo bench -p diec-formats

# Run clippy
cargo clippy --workspace --all-targets --all-features -- -D warnings
```

414 tests, 6 fuzz targets, 0 failures.

## Upstream & License

- Upstream: <https://github.com/horsicq/DIE-engine>
- License: MIT (same as upstream)
- Rules: MIT licensed, bundled from upstream at a fixed commit

See [NOTICES.md](NOTICES.md) for full attribution and [AUDIT.md](AUDIT.md)
for supply chain details.
