# rquickjs rule runtime spike

This is an isolated Phase 0 research program, not part of the future
`diec-rust` Cargo workspace or public API.

It evaluates a pinned rquickjs/QuickJS-NG release against the same fixed rule
corpus and runtime fixtures used by `spikes/boa-rule-runtime`. It also probes
the native engine's interrupt and memory limits and records the Windows MSVC
build cost.

The spike must not modify or normalize any upstream rule bytes.
