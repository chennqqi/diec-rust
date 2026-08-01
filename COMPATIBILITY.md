# Compatibility Report

This document tracks compatibility between diec-rust and the upstream
DIE-engine project. It is updated with each release.

Last updated: 2026-08-01

## Baseline

- **Upstream**: https://github.com/horsicq/DIE-engine
- **Fixed commit**: recorded in `upstream/Detect-It-Easy` submodule
- **Rule database**: loaded verbatim from upstream, no modifications

## Rule Loading Compatibility

| Metric | Result |
|--------|--------|
| Total rules in database | 1186 |
| Successfully loaded | 1184 |
| Failed to load | 2 |
| Load success rate | 99.83% |

### Known Load Failures

| Rule path | Error | Status |
|-----------|-------|--------|
| (record specific failures here) | | |

## Format Detection Compatibility

### Corpus Differential Test

| Category | Samples | Matched | Mismatched | Notes |
|----------|---------|---------|------------|-------|
| Executable (ELF) | 2 | 2 | 0 | |
| Executable (PE) | 2 | 2 | 0 | PE heuristic requires --heuristicscan |
| Executable (Mach-O) | 3 | 3 | 0 | FAT binary detected as lipo |
| Bytecode | 3 | 3 | 0 | Java class, DEX, PYC |
| Archive | 7 | 7 | 0 | Zip, tar, CFBF, APK, JAR, IPA |
| Document | 2 | 2 | 0 | PDF, ISO 9660 |
| Image | 3 | 3 | 0 | PNG, JPEG, BMP |
| Audio | 1 | 1 | 0 | WAV |
| Other | 4 | 4 | 0 | empty, text, RAR, GZIP |
| **Total** | **27** | **27** | **0** | |

### Edge-Case Robustness

| Category | Samples | No crash | No spurious | No hang |
|----------|---------|----------|-------------|---------|
| Truncated headers | 10 | 10 | N/A | 10 |
| Malformed structures | 2 | 2 | 2 | 2 |
| Oversized fields | 1 | 1 | 1 | 1 |
| Empty containers | 2 | 2 | N/A | 2 |
| No-match inputs | 5 | 5 | 5 | 5 |
| **Total** | **20** | **20** | **7** | **20** |

## CLI Compatibility

| Feature | Status | Notes |
|---------|--------|-------|
| Basic scan | ✅ | |
| --recursive | ✅ | |
| --deepscan | ✅ | |
| --heuristicscan | ✅ | |
| --verbose | ✅ | |
| --aggressivescan | ✅ | |
| --alltypes | ✅ | |
| --hideunknown | ✅ | |
| --output (json) | ✅ | |
| --output (xml) | ✅ | |
| --output (csv) | ✅ | |
| --output (tsv) | ✅ | |
| --format | ✅ | |
| --profiling | ✅ | |
| --messages | ✅ | |
| --entropy | ✅ | |
| --info | ✅ | |
| --extradatabase | ✅ | |
| --customdatabase | ✅ | |
| --showdatabase | ✅ | |
| --showstructs | ✅ | |

## C ABI Compatibility

| Feature | Status | Notes |
|---------|--------|-------|
| ABI version negotiation | ✅ | v1.0 |
| Opaque handles | ✅ | 6 handle types |
| Database builder | ✅ | |
| One-shot scan | ✅ | bytes + path |
| Reusable scanner | ✅ | bytes + path |
| Cancel token | ✅ | |
| Error handle | ✅ | |
| Panic containment | ✅ | catch_unwind |
| Double-free safety | ✅ | all handle types |
| Go/cgo binding | ✅ | 5 tests |
| Python ctypes binding | ✅ | 9 tests |
| C smoke test | ✅ | |

## Known Differences

| ID | Description | ADR | Impact |
|----|-------------|-----|--------|
| (none recorded) | | | |

## Performance Baseline

| Benchmark | Time (release) | Notes |
|-----------|----------------|-------|
| scan_corpus/ELF64 | ~19ms | minimal ELF |
| scan_corpus/PE32 | ~165ms | minimal PE |
| scan_corpus/Zip | ~190ms | payload.zip |
| scan_corpus/DEX | ~203ms | minimal DEX |
| scan_flags/default | ~190ms | payload.zip |
| scan_flags/heuristic | ~176ms | payload.zip |
| scan_flags/all_types | ~464ms | payload.zip |
| scan_flags/deep | ~178ms | payload.zip |
| database_load | ~400ms | full database (optimized from ~1.2s) |
| probe_corpus/ELF64 | ~345ns | format probe only |
| probe_corpus/Zip | ~950ns | format probe only |

## Test Summary

| Category | Count | Status |
|----------|-------|--------|
| Unit tests | 247 | ✅ all pass |
| Integration tests | 167 | ✅ all pass |
| FFI tests | 35 | ✅ all pass |
| Edge corpus tests | 3 | ✅ all pass |
| Fuzz targets | 6 | ✅ compile |
| **Total** | **414** | ✅ 0 failures |
