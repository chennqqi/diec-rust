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
`getMemoryMap` construction remains outside this spike.
`find_signature` is a separate operation with control-record, SigByte, and
plain-hex branches; this spike does not approximate it by looping the raw
matcher.

Tests consume
`docs/research/data/signature-pattern-inventory.json`, a deterministic
inventory generated from the fixed 292-rule runtime trace.
Additional tests compare 16 context-free and 7 memory-map cases directly with
the pinned Qt 5 XBinary harness baseline.
