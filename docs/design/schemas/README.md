# Compatibility schema index

Status: Draft

Last updated: 2026-07-27

These schemas define the Phase 0 evidence-bound waiver sub-pipeline:

- [`difference-input-report-v1.schema.json`](difference-input-report-v1.schema.json)
  describes executed cases and exact semantic differences;
- [`difference-waiver-registry-v1.schema.json`](difference-waiver-registry-v1.schema.json)
  describes approved waivers for one exact run identity;
- [`difference-waiver-audit-v1.schema.json`](difference-waiver-audit-v1.schema.json)
  describes pass/fail audits and infrastructure errors;
- [`examples/`](examples/) contains synthetic, non-production inputs and their
  reproducible audit.

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
not change during the audit. The full differential harness must additionally
rehash the content-addressed raw artifacts referenced by execution records;
that integration is not claimed by this v1 sub-pipeline.
