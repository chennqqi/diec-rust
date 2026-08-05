# diec-rust

A Rust rewrite of [Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE).

[中文文档](README.zh-CN.md)

> **⚠️ Work in Progress — Not Production Ready**
>
> This project is under active development. Detection coverage, API
> stability, and output formats may change between commits. Some PE
> protector/packer rules that rely on disassembly (Capstone) are not
> yet supported. Do not use in production environments.

## Why

Aim for compatibility with upstream DIE — same detection capabilities,
same rule semantics, same output formats — with Rust's memory safety and
multi-language bindings.

## Key Points

- **DIE compatibility**: loads upstream rules verbatim via the rquickjs
  runtime; PE/ELF/MACH host API bridge implements most commonly used
  methods
- **Rust safety**: zero `unsafe` in core, panic containment at FFI
  boundary, no crashes on malformed input
- **Performance**: parallel database loading (3x faster than sequential),
  sub-microsecond format probing
- **Multi-language bindings**: C ABI + Go/cgo + Python ctypes

## Known Limitations

- `getDisasmString` returns empty string (Capstone not integrated);
  protector rules relying on disassembly (PELock, Arxan, VMProtect,
  GenericHeuristicAnalysis) will miss detections
- Some detection names/versions differ from upstream due to rule
  version differences (submodule rules vs upstream 3.21 bundled rules)
- `format` type detections may produce duplicate entries in some cases

## Benchmark

Database load: **160ms** (parallel) vs **480ms** (sequential before
optimization) — **300% improvement**. Format probing: **60-407ns** per file.

Test method and raw data: [tools/benchmark/](tools/benchmark/) ·
[benchmark_results.json](tools/benchmark/results/benchmark_results.json)

Reproduce:
```sh
python tools/benchmark/run_benchmarks.py --quick
```

## Compatibility

**477 tests pass**, upstream rules loaded, 28 baseline + 20 edge-case
corpus files verified — no crashes, no spurious detections, no hangs.

Differential testing against upstream DIE 3.21:
- diec.exe self-detection: **5/5 match** (linker, compiler, tool,
  debug data, C/C++ runtime)
- 6 large system DLLs (0.5-61MB): **6/6 match**
- 28-file corpus: 17/28 match (remaining differences are rule version
  differences and format-type deduplication behavior)

Test method and raw data: [tools/benchmark/](tools/benchmark/) ·
[compatibility_results.json](tools/benchmark/results/compatibility_results.json)

Reproduce:
```sh
python tools/benchmark/run_compatibility.py
python tools/compat/compare_upstream.py
```

## Quick Start

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust && cargo build --workspace --release
./target/release/diec --alltypes file.exe
```

Python / Go / C bindings: see [README.zh-CN.md](README.zh-CN.md) or
[bindings/](bindings/).

## died (Scan Service)

died (die daemon) is an HTTP/JSON scan service for batch file
identification. It loads the rule database once and reuses it across
requests, avoiding the 160ms per-process database load overhead.

```sh
# Build and start the server
cargo build --release --package diec-server
./target/release/died --db upstream/Detect-It-Easy/db --bind 127.0.0.1:18080
```

Client examples (curl, PowerShell, Python, Go) and full API reference:
[docs/died-api.md](docs/died-api.md).

Windows service installation, Linux systemd setup, and DEB/RPM/MSI
packaging: [crates/diec-server/packaging/README.md](crates/diec-server/packaging/README.md).

## License

MIT — same as upstream. See [NOTICES.md](NOTICES.md).

