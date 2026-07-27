# Compatibility schema index

Status: Draft

Last updated: 2026-07-27

These schemas define two Phase 0 compatibility sub-pipelines.

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

This proves the bytes materialized for one execution record. The full
differential harness must still bind both executions, their verifications,
normalizations, comparisons and waivers in order.

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

This envelope does not define the complete DIEC semantic result model. It is a
strict executable slice that can be integrated only after that model and the
full differential report are frozen.
