# Compatibility Report

This document tracks compatibility between diec-rust and the upstream
DIE-engine project. It is updated with each release.

Last updated: 2026-08-02

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
| Bytecode | 3 | 3 | 0 | Java Class, DEX, PYC (PYC is rule version diff) |
| Archive | 7 | 4 | 3 | APK/JAR/ZIP: archive:Zip (rule version diff) |
| Document | 2 | 2 | 0 | PDF, CFBF (Microsoft Office) |
| Image | 3 | 3 | 0 | PNG, JPEG, BMP |
| Audio | 1 | 1 | 0 | WAV |
| Other | 5 | 5 | 0 | empty, text, RAR, GZIP, manifest |
| **Total** | **28** | **24** | **4** | All mismatches are rule version diffs |

### Mismatch Details (Rule Version Differences)

All 4 mismatches are due to differences between the submodule rule
database (newer version) and the upstream DIE 3.21 bundled rules.
These are NOT engine bugs:

| File | Our detection | Upstream 3.21 | Cause |
|------|---------------|---------------|-------|
| minimal.apk | archive:Zip:2.0 | (none) | New rule detects archive |
| minimal.jar | archive:Zip:2.0 | (none) | New rule detects archive |
| payload.zip | archive:Zip:2.0 | (none) | New rule detects archive |
| minimal.pyc | Python bytecode | (none) | New rule detects PYC |

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

## Host API Compatibility

| Feature | Status | Notes |
|---------|--------|-------|
| Binary (read, compare, find) | ✅ | Full implementation |
| PE (header, sections, imports) | ✅ | Full implementation |
| PE.getDisasmString | ✅ | Capstone-based, Intel syntax |
| PE.getDisasmNextAddress | ✅ | Capstone-based |
| PE Rich signature | ✅ | |
| PE debug data | ✅ | |
| PE.isSigned | ✅ | Authenticode |
| ELF | ✅ | Full implementation |
| Mach-O | ✅ | Full implementation |
| PDF (version, header comment) | ✅ | |
| JPEG (version from JFIF) | ✅ | |
| DEX (version from header) | ✅ | |
| CFBF (version from header) | ✅ | major.minor format |
| Java Class (version from header) | ✅ | Java SE version mapping |
| Binary.isPlainText | ✅ | |
| Archive (isVerbose, format) | ⚠️ | Stub (isVerbose=false) |

## Known Differences

| ID | Description | ADR | Impact |
|----|-------------|-----|--------|
| D001 | Rule version differences (submodule vs 3.21) | N/A | Detection name/version diffs |
| D002 | Format-specific rules exclude Binary rules | N/A | Eliminates duplicate detections |
| D003 | JavaClass no longer runs Binary rules | N/A | Host API now complete |

## Performance Baseline

| Benchmark | Time (release) | Notes |
|-----------|----------------|-------|
| scan_corpus/ELF64 | ~19ms | minimal ELF |
| scan_corpus/PE32 | ~73ms | minimal PE (Capstone cached) |
| scan_corpus/Zip | ~190ms | payload.zip |
| scan_corpus/DEX | ~203ms | minimal DEX |
| scan_flags/default | ~218ms | payload.zip |
| scan_flags/heuristic | ~273ms | payload.zip |
| scan_flags/all_types | ~854ms | payload.zip |
| scan_flags/deep | ~190ms | payload.zip |
| database_load | ~486ms | full database |
| probe_corpus/ELF64 | ~345ns | format probe only |
| probe_corpus/Zip | ~950ns | format probe only |

## Test Summary

| Category | Count | Status |
|----------|-------|--------|
| Unit tests | 251 | ✅ all pass |
| Integration tests | 167 | ✅ all pass |
| FFI tests | 35 | ✅ all pass |
| Edge corpus tests | 3 | ✅ all pass |
| Fuzz targets | 6 | ✅ compile |
| **Total** | **458** | ✅ 0 failures |
