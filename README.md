# diec-rust

A Rust rewrite of [Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE).

[中文文档](README.zh-CN.md)

## Why

1:1 compatible with upstream DIE — same detection capabilities, same
rule semantics, same output formats — with Rust's memory safety and
multi-language bindings.

## Key Points

- **1:1 DIE compatibility**: loads 2037 upstream rules verbatim, identical
  detection results and output (JSON/XML/CSV/TSV/text)
- **Rust safety**: zero `unsafe` in core, panic containment at FFI boundary,
  no crashes on malformed input
- **Performance**: parallel database loading (3x faster than sequential),
  sub-microsecond format probing
- **Multi-language bindings**: C ABI + Go/cgo + Python ctypes

## Benchmark

Database load: **160ms** (parallel) vs **480ms** (sequential before
optimization) — **3x improvement**. Format probing: **60-407ns** per file.

Test method and raw data: [tools/benchmark/](tools/benchmark/) ·
[benchmark_results.json](tools/benchmark/results/benchmark_results.json)

Reproduce:
```sh
python tools/benchmark/run_benchmarks.py --quick
```

## Compatibility

**414 tests pass**, 2037 rules loaded, 27 baseline + 20 edge-case corpus
files verified — no crashes, no spurious detections, no hangs.

Test method and raw data: [tools/benchmark/](tools/benchmark/) ·
[compatibility_results.json](tools/benchmark/results/compatibility_results.json)

Reproduce:
```sh
python tools/benchmark/run_compatibility.py
```

## Quick Start

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust && cargo build --workspace --release
./target/release/diec --alltypes file.exe
```

Python / Go / C bindings: see [README.zh-CN.md](README.zh-CN.md) or
[bindings/](bindings/).

## License

MIT — same as upstream. See [NOTICES.md](NOTICES.md).
