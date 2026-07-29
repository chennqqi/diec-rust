# rquickjs rule runtime spike

This is an isolated Phase 0 research program, not part of the future
`diec-rust` Cargo workspace or public API.

It evaluates a pinned rquickjs/QuickJS-NG release against the same fixed rule
corpus and runtime fixtures used by `spikes/boa-rule-runtime`. It also probes
the native engine's counted interrupt, cross-thread cancellation, same-context
recovery, cooperative native HostApi cancellation, monotonic VM/native
deadlines, focused Qt-oracle-backed `U24`/`shru64` behavior, and memory
and stack limits with same-context recovery, and records the Windows MSVC
build cost. It also verifies that a Rust native callback panic is caught by
the pinned rquickjs trampoline, resumed at the Rust eval boundary, and leaves
the same context usable.

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

`trace-binary-detects` invokes all 292 `detect` functions in that fixed order
with a bounded diagnostic fallback. The implemented byte/string/size methods
follow pinned XScanEngine and die_script contracts. `Binary.c`/`compare` use
the adjacent pure-Rust signature spike and preserve the pinned Qt 5 header
fast path, strict boundary, and negative-offset clamp; generic unknown syntax
is an explicit diagnostic. `fSig`, `findSignature`, and
`isSignaturePresent` share the same oracle-backed pure-Rust search adapter,
including EOF range clamping and `size == -1`. Compare and search calls,
quirks, and errors are counted separately. Overlay methods consume an explicit
`BinaryHostContext` whose current file-part is independent from the current
parser's nested-overlay offset and size; their calls are traced separately.
`BinaryStringContext` separately derives the Qt-style file suffix and pinned
text classification/header decoding facts. `getFileSuffix`,
`getHeaderString`, `isPlainText`, and `isUTF8Text` are native adapters whose
calls are also traced; 15 focused Qt5 wrapper cases cover their deterministic
behavior.
Its accepted calls and emitted detections are gap-inventory data, not
compatibility evidence.

`verify-binary-corpus` runs the same 292-rule lifecycle over all 14 generated
Nintendo samples and compares ordered results with the pinned Qt oracle. It
also counts every normal QuickJS-NG interrupt callback with one monotonic
counter per sample runtime. Binary signature compare/search also records one
native cooperative checkpoint at HostApi entry and before every 4096th
searched candidate; a rejected callback interrupts a single in-flight native
search. The command records `Runtime::memory_usage()` after runtime creation,
initialization, every rule, and final reporting. These memory
snapshots are lifecycle checkpoints, not a transient in-eval allocator
high-water measurement. Large raw reports belong in temporary storage; only
the stable projection and its reproducible summary are versioned.

The `verify-pe-rule`, `verify-elf-rule`, `verify-macho-rule`,
`verify-dex-rule`, `verify-apk-rule`, `verify-archive-rule`, and
`verify-pdf-rule` reports also include one normal interrupt counter and three
memory lifecycle checkpoints for every isolated case runtime. Together they
form a 25-case representative cross-format matrix; they do not claim full
format or all-rule runtime scaling.
