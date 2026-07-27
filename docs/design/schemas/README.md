# Compatibility schema index

Status: Draft

Last updated: 2026-07-27

These schemas define the independently executable Phase 0 compatibility
sub-pipelines and their evidence bindings.

The evidence-bound waiver schemas are:

- [`difference-input-report-v1.schema.json`](difference-input-report-v1.schema.json)
  describes executed cases and exact semantic differences;
- [`difference-waiver-registry-v1.schema.json`](difference-waiver-registry-v1.schema.json)
  describes approved waivers for one exact run identity;
- [`difference-waiver-audit-v1.schema.json`](difference-waiver-audit-v1.schema.json)
  describes pass/fail audits and infrastructure errors.

The audited semantic-normalization schemas are:

- [`semantic-projection-v1.schema.json`](semantic-projection-v1.schema.json)
  wraps one versioned case projection;
- [`semantic-normalization-policy-v1.schema.json`](semantic-normalization-policy-v1.schema.json)
  binds exact identity, case, JSON Pointer and approved transform;
- [`semantic-normalization-output-v1.schema.json`](semantic-normalization-output-v1.schema.json)
  records the derived value and input, policy, target-value and output hashes.

The raw-execution evidence schemas are:

- [`raw-execution-v1.schema.json`](raw-execution-v1.schema.json) records one
  exact producer/case identity, argv/environment/termination, and raw stream
  digest/length pairs, plus explicit nullable resource measurements;
- [`raw-execution-verification-v1.schema.json`](raw-execution-verification-v1.schema.json)
  records the streamed content rehash result and verification budget.

The lossless framing schema is
[`raw-framing-projection-v1.schema.json`](raw-framing-projection-v1.schema.json).
It binds a raw execution verification and covers stdout with ordered,
contiguous raw/strict-JSON byte ranges.

The typed legacy CLI semantic projection schemas are:

- [`semantic-projection-contract-v1.schema.json`](semantic-projection-contract-v1.schema.json)
  freezes the shared compatibility target and expected output shape for one
  case;
- [`semantic-result-v1.schema.json`](semantic-result-v1.schema.json) defines
  normal scan trees, entropy, ordered info/struct values, CLI errors, all raw
  streams, termination, producer identity and explicit projection failures;
- [`semantic-result-projection-v1.schema.json`](semantic-result-projection-v1.schema.json)
  places that payload in the normalizer-compatible projection envelope.

The audited two-sided comparison schemas are:

- [`semantic-comparison-contract-v1.schema.json`](semantic-comparison-contract-v1.schema.json)
  binds the exact projection contract bytes, optional normalization policy,
  required `exact`/`semantic` equivalence and fixed difference budget;
- [`semantic-comparison-v1.schema.json`](semantic-comparison-v1.schema.json)
  records both rebuilt projections, optional normalization audits, raw and
  semantic equality, contract hashes, requirement result and difference
  artifact identity;
- [`semantic-difference-blocked-v1.schema.json`](semantic-difference-blocked-v1.schema.json)
  replaces the difference output when projection fails or the complete
  difference set exceeds the fixed budget, so stale valid reports cannot be
  consumed.

The authoritative single-case decision is
[`semantic-case-audit-v1.schema.json`](semantic-case-audit-v1.schema.json).
It embeds the rebuilt comparison and exact waiver audit, binds all four
generated/input artifacts by byte and canonical SHA-256, and has only
`pass`, `fail`, or `infrastructure_error` outcomes.

The typed-legacy multi-case schemas are:

- [`compatibility-suite-plan-v1.schema.json`](compatibility-suite-plan-v1.schema.json)
  freezes the ordered expected case matrix and exact input artifact hashes;
- [`compatibility-suite-report-v1.schema.json`](compatibility-suite-report-v1.schema.json)
  indexes the generated case audits and aggregates result, platform,
  capability, comparison, classification and waiver counts.

[`examples/`](examples/) contains synthetic, non-production inputs and
reproducible outputs for all compatibility sub-pipelines.

The reference validator is
[`tools/compat/validate_difference_waivers.py`](../../../tools/compat/validate_difference_waivers.py).
It enforces constraints beyond declarative JSON Schema, including repository
reference existence, date ordering, canonical fingerprint recomputation,
identity equality, expiration and stale/unmatched detection.

## Canonical fingerprint

For each difference, construct an object with exactly these fields:

```text
case_id
json_pointer
classification
failure_kind
left_raw_sha256
right_raw_sha256
upstream_value
rust_value
```

Serialize as UTF-8 JSON with object keys sorted, no insignificant whitespace,
non-ASCII characters preserved, and non-finite numbers rejected. The lowercase
SHA-256 of those bytes is `diff_fingerprint`.

Both the report producer and validator compute this value. A report containing
a stale or fabricated fingerprint is an `infrastructure_error`, not a waivable
difference.

## Audit semantics

- Registry and report identity must match exactly.
- A waiver matches all seven identity/difference fields, not only case/path.
- `as_of >= expires` is expired.
- A waiver whose case ran but exact difference disappeared or changed is stale.
- A waiver whose case did not run is unmatched.
- A difference without one exact active waiver is unmatched.
- Any non-empty expired/stale/unmatched list fails the audit.
- Invalid schema, identity, fingerprint or evidence is
  `infrastructure_error`.
- `as_of` is `null` only when the supplied audit date itself cannot be parsed;
  valid pass/fail audits always carry the canonical explicit date.

v1 supports semantic RFC 6901 JSON Pointer targets only. It intentionally does
not support wildcard, root-document or raw whole-stream waivers. Raw-only byte
range support requires a future schema with exact artifact/range identity.

The validator records registry/report hashes and verifies those input files did
not change during the audit.

## Raw execution evidence

The reference verifier is
[`tools/compat/verify_raw_execution.py`](../../../tools/compat/verify_raw_execution.py).
An artifact reference contains only lowercase SHA-256 and byte length. Its path
is derived as `sha256/<digest>` below an explicit root; manifests cannot inject
absolute paths, `..`, separators, or globs.

The verifier validates the total declared size before resolving any artifact,
then reads each regular non-reparse file in bounded chunks. It checks size,
SHA-256 and file identity before/during/after reading, re-reads the bounded
manifest, refuses source overwrite, and emits deterministic UTF-8/LF audit
bytes. stdout and stderr are mandatory; runtime logs remain a separate optional
raw stream.

This proves the bytes materialized for one execution record. The single-case
auditor binds both executions, their derived comparison and waiver decision in
order; the suite runner binds the complete planned typed-legacy matrix.
Release policy/signing remains open.

## Lossless framing

The reference projector is
[`tools/compat/project_raw_framing.py`](../../../tools/compat/project_raw_framing.py).
It first verifies all execution artifacts, then re-reads stdout with the same
bounded size/hash/identity checks. Object/array candidates are recognized only
at stream or LF-delimited line start, matching the fixed CLI evidence. Balanced
candidates must also be strict UTF-8 JSON with unique keys and finite values.
Candidate scanning advances monotonically: balanced-invalid candidates are
kept whole as raw, mismatches resume after the conflicting byte, and an
unterminated candidate consumes to EOF. Nested retry cannot create quadratic
work.

v1 also freezes an 8 MiB per-document limit, 4096 JSON documents and nesting
256. Hitting any limit preserves uncovered bytes as raw and emits
`projection_limit_reached` with ordered reasons; it never becomes an empty
successful projection.

The output segments cover every byte exactly once and retain raw SHA-256 for
JSON documents as well as prefixes, separators, invalid candidates and trailing
diagnostics. Parsed JSON and its canonical hash are additional projections;
they never replace the source bytes. `no_json_document` is explicit and cannot
be interpreted as empty successful output.

## Typed legacy CLI semantic projection

The reference projector is
[`tools/compat/project_semantic_result.py`](../../../tools/compat/project_semantic_result.py).
It consumes a strict case contract plus one raw execution manifest. The
contract identity must match the execution case, platform and case-manifest
hash. An upstream execution must additionally have the exact target upstream
revision; a Rust execution retains its distinct producer revision while using
the same target identity.

The projector rehashes every content-addressed artifact and reconstructs raw
framing before reading semantic values. It accepts only the documented normal
scan, entropy, info, struct and normal-scan error shapes. Raw prefixes,
separators and trailing diagnostics are split into lossless ordered line
records. `comparison` keeps the exact UTF-8 or base64 body and its
`none`/`lf`/`crlf` ending; a correlated `evidence.raw_streams` map keeps every
raw offset/size/hash. stderr and runtime logs follow the same rule.
Unknown fields/shapes, unexpected document counts and framing limits emit
`projection_failure` and preserve the unclassified value instead of becoming
empty success.

Only the `comparison` subtree (output, termination and streams) is input to
two-sided semantic equality. Producer and evidence fields stay in the same
artifact as provenance but are intentionally side-specific.

This v1 is complete for the observed fixed legacy CLI JSON variants listed in
[`docs/research/cli-json-schema-inventory.md`](../../research/cli-json-schema-inventory.md).
It does not claim that engine-only harness payloads or the future modern
canonical `ScanReport` are frozen.

## Normalization semantics

The reference normalizer is
[`tools/compat/normalize_semantic_projection.py`](../../../tools/compat/normalize_semantic_projection.py).
Its JSON Pointers are relative to the input `semantic` value. v1 has a closed
transform set:

- `qobject_address_v1`;
- `profiling_elapsed_ms_v1`.

Every rule also supplies the exact complete value expected after
normalization and the exact replacement count. A missing/non-string target,
identity or case drift, unknown field/transform, changed surrounding text, or
replacement-count drift is an infrastructure error. Input and policy files
are re-read before output is written and may never be overwritten by it.

The generic envelope alone does not define a DIEC payload. The strict legacy
CLI payload is `semantic-result-v1`; engine-only and modern canonical payloads
remain separate open schema work.

## Audited two-sided comparison

The reference comparator is
[`tools/compat/compare_semantic_results.py`](../../../tools/compat/compare_semantic_results.py).
It consumes raw execution manifests and rebuilds both framing/semantic
projections itself. If a shared policy is configured, both normalization
outputs are then rebuilt before comparison. Contract and policy identity use
their exact artifact SHA-256, not only parsed canonical content.

Only each projection's `semantic.comparison` subtree is compared. Objects use
sorted key traversal, arrays preserve order, JSON types are strict except
numerically equal finite integer/float forms, and missing values use explicit
presence records. Difference pointers are RFC 6901 paths relative to
`semantic`, beginning at `/comparison`; reports retain both producer-specific
projection evidence and a raw-observation hash over termination plus all raw
stream references.

The result is `exact`, `semantic_equal`, `different`,
`projection_failure`, or `comparison_limit_reached`. A valid difference-input
report is emitted for the first three, including an empty list when equal.
Failure/limit results instead overwrite the designated output with a blocked
marker that deliberately does not satisfy `difference-input-report-v1`.
Therefore projection failure, resource exhaustion, and a stale earlier report
cannot become waivable success. v1 requires the complete ordered difference set
to fit within 10,000 entries.

The authoritative wrapper is
[`tools/compat/audit_semantic_case.py`](../../../tools/compat/audit_semantic_case.py).
It closes the single-case path through comparison and exact waiver application
for the typed legacy CLI. Raw-only mismatch under an exact requirement has no
semantic difference pointer and cannot be waived in v1. A semantic mismatch
passes only when every current difference is applied and no waiver is stale,
expired or unmatched. Blocked comparison results overwrite the waiver output
with an infrastructure audit.

The multi-case reference runner is
[`tools/compat/run_compatibility_suite.py`](../../../tools/compat/run_compatibility_suite.py).
It never accepts a directory scan as the expected case set: its versioned plan
lists every case and binds every non-content-addressed input file by SHA-256.
It runs all planned entries in order, verifies plan/case identity, re-reads
inputs and derived case evidence, then reports strict result precedence:
infrastructure error, valid failure, pass.
Each run requires a fresh empty output root disjoint from the input root, so
stale case artifacts cannot be mistaken for current results.

This closes the typed-legacy multi-case report path. Engine-only and modern
typed variants, real Windows/macOS execution matrices, release approval,
signing and publication remain open.
