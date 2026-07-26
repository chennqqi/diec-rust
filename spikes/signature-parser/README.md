# signature parser spike

This is an isolated Phase 0 pure-Rust feasibility spike. It models the
signature records consumed by pinned
`horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`.
It is not part of the future Cargo workspace or a stable API.

The parser supports literal hex and quoted Latin-1 strings, wildcards, byte
classes, bounded find, relative-offset and absolute-address records. Unknown,
odd-width, unbalanced, and unsupported input returns a structured error instead
of silently becoming a mismatch.

The raw matcher models `compareSignature` only. It intentionally refuses
relative-offset and absolute-address records when no context is supplied.
`matches_with_memory_map` accepts an explicit, pure-Rust memory map and covers
generic address records, endianness, COM/MS-DOS branches, and the AmigaHunk
relative-width quirk. Synthetic PE, ELF, Mach-O, COM, MS-DOS, and AmigaHunk
vectors agree 7/7 with the pinned XBinary harness; real format-specific
`getMemoryMap` construction for generated PE32/64, ELF32/64, Mach-O32/64, COM,
MS-DOS, and AmigaHunk files also agrees 9/9. Malformed map variants remain
outside this spike.
`find_raw` and `find_with_memory_map` independently model the control-record,
SigByte, and plain-hex `find_signature` branches, including their anchor
selection and class-table differences. They are not implemented as a loop over
the raw matcher. `find_binary_wrapper` adds the pinned `Binary_Script` range
normalization used by `findSignature`, `fSig`, and `isSignaturePresent`, while
keeping parse quirks and errors explicit.

Tests consume
`docs/research/data/signature-pattern-inventory.json`, a deterministic
inventory generated from the fixed 292-rule runtime trace.
Additional tests compare 16 context-free, 7 synthetic memory-map, and 9
parser-derived memory-map cases directly with the pinned Qt 5 XBinary harness
baseline. A separate 19-case differential covers all three `find_signature`
branches. Twenty-one wrapper-level cases invoke pinned
`Binary_Script::compare`, `compareEP`, `compareOverlay`, `findSignature`,
`fSig`, and `isSignaturePresent` end-to-end. They distinguish cached compare
fast paths from the record matcher at strict boundaries, including Qt 5's
negative-position `QString::mid` clamp, and verify search range clamping plus
the `size == -1` convention.
The shared harness also has three overlay-context cases proving that the
current `FILEPART_OVERLAY` state is independent from nested-overlay
offset/size/presence. That context model belongs to the host/runtime spike,
not this signature parser.
Fifteen additional shared-harness cases pin file-suffix and header-text
construction for the adjacent host/runtime spike; they are intentionally not
implemented in this signature parser.
