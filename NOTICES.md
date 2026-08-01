# Third-Party Notices

This file lists third-party software, licenses, and attribution used by
diec-rust. It is maintained manually and verified via `cargo license`.

## Upstream Project

- **DIE-engine** by horsicq: https://github.com/horsicq/DIE-engine
  - License: MIT
  - Used as: compatibility baseline, rule database source, submodule
  - Fixed commit SHA recorded in `upstream/Detect-It-Easy` submodule
  - Rules are loaded verbatim; no modifications

## Rust Dependencies

### Core Dependencies (runtime)

| Crate | License | Purpose |
|-------|---------|---------|
| rquickjs | MIT | JavaScript runtime for rule execution |
| rquickjs-core | MIT | QuickJS bindings core |
| rquickjs-sys | MIT | QuickJS FFI system bindings |
| serde | Apache-2.0 OR MIT | Serialization framework |
| serde_json | Apache-2.0 OR MIT | JSON serialization |
| sha2 | Apache-2.0 OR MIT | SHA-256 hashing |
| regex | Apache-2.0 OR MIT | Regular expressions |
| walkdir | MIT OR Unlicense | Directory traversal |
| memchr | MIT OR Unlicense | Fast byte search |
| aho-corasick | MIT OR Unlicense | Multi-pattern search |
| libc | Apache-2.0 OR MIT | C library bindings |
| slab | MIT | Slab allocator |

### Development Dependencies (build/test/bench only)

| Crate | License | Purpose |
|-------|---------|---------|
| criterion | Apache-2.0 OR MIT | Benchmarking |
| clap | Apache-2.0 OR MIT | CLI argument parsing |
| rayon | Apache-2.0 OR MIT | Parallelism |
| crossbeam | Apache-2.0 OR MIT | Concurrency primitives |
| plotters | MIT | Criterion plotting |
| oorandom | MIT | Simple PRNG for tests |
| ciborium | Apache-2.0 | CBOR encoding for fuzz |
| generic-array | MIT | Type-level array |

### Transitive Dependencies

All transitive dependencies use permissive licenses (MIT, Apache-2.0,
BSD-2-Clause, BSL-1.0, Zlib, Unicode-3.0). No GPL, AGPL, or copyleft
licenses are present in the dependency tree.

## QuickJS

- **QuickJS** by Bellard: https://bellard.org/quickjs/
  - License: MIT
  - Bundled via `rquickjs-sys` crate
  - Used as: JavaScript engine for rule script execution

## Corpus

All corpus samples in `corpus/` and `corpus/edge/` are project-generated.
No third-party sample bytes are included. See:
- `tools/corpus/generate_baseline_corpus.py`
- `tools/corpus/generate_edge_corpus.py`

## Verification

To verify the license inventory:

```sh
cargo install cargo-license
cargo license --all-features
```

The output should match the dependencies listed above. Any new dependency
must be checked for license compatibility before merging.
