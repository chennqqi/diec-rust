# rquickjs rule runtime spike

This is an isolated Phase 0 research program, not part of the future
`diec-rust` Cargo workspace or public API.

It evaluates a pinned rquickjs/QuickJS-NG release against the same fixed rule
corpus and runtime fixtures used by `spikes/boa-rule-runtime`. It also probes
the native engine's interrupt and memory limits and records the Windows MSVC
build cost.

The spike must not modify or normalize any upstream rule file. The optional
`eval-isolated-compat` experiment applies one length-preserving, source-identity
guarded in-memory overlay after reading the original Nintendo rule. It reports
the expected source SHA-256 and refuses size/declaration drift. This is a
feasibility probe, not a production rule transformer or a runtime decision.

`detect-nintendo` goes one step further: it registers the minimal Rust byte
HostApi used by the fixed Nintendo rule, then uses one shared context to
evaluate the real global `_init`, Binary `_init`, and their `_debug`,
`_runtime_helpers`, `language`, and `read` includes unchanged. It applies the
compatibility overlay in memory and compares all 14 generated PS3/PS Vita
fixtures with the versioned Qt oracle baseline. It does not execute the full
Binary rule set.

`eval-binary-lifecycle` consumes the versioned Linux Qt5 profiling order,
evaluates the real init/include chain and all 292 Binary rule programs in one
context, and applies three path/size/declaration-pinned, length-preserving
legacy overlays. `eval-binary-lifecycle-raw` runs the same sequence unchanged
and intentionally reports the three known modern-JavaScript failures. These
commands evaluate top-level rule code only; they do not call every `detect`.
