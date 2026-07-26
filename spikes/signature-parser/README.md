# signature parser spike

This is an isolated Phase 0 pure-Rust feasibility spike. It models the
signature records consumed by pinned
`horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`.
It is not part of the future Cargo workspace or a stable API.

The parser supports literal hex and quoted Latin-1 strings, wildcards, byte
classes, bounded find, relative-offset and absolute-address records. Unknown,
odd-width, unbalanced, and unsupported input returns a structured error instead
of silently becoming a mismatch.

The raw matcher intentionally refuses relative-offset and absolute-address
records because their behavior depends on the upstream format memory map,
endianness, and file type. Those operations are parsed losslessly and require a
future context-aware differential harness.

Tests consume
`docs/research/data/signature-pattern-inventory.json`, a deterministic
inventory generated from the fixed 292-rule runtime trace.
