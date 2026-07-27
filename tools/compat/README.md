# Compatibility tooling

Phase 0 currently provides three strict compatibility sub-pipeline tools:

- `verify_raw_execution.py` validates a versioned execution record and rehashes
  its content-addressed stdout/stderr/runtime-log bytes;
- `normalize_semantic_projection.py` applies only evidence-backed, closed-set
  semantic transforms;
- `validate_difference_waivers.py` audits evidence-bound semantic difference
  waivers.

## Raw execution verification

Raw streams use a fixed layout below an explicit artifact root:

```text
sha256/<lowercase-sha256>
```

The manifest contains only digest and byte length, never a caller-controlled
path. Example:

```text
python tools/compat/verify_raw_execution.py \
  --manifest docs/design/schemas/examples/raw-execution-v1.example.json \
  --artifact-root docs/design/schemas/examples/raw-artifacts \
  --output raw-execution-verification.json
```

The verifier rejects duplicate/unknown JSON fields, missing streams,
non-canonical identity, symlink/reparse/non-regular files, size/hash mismatch,
file mutation, and declared totals above `--max-artifact-bytes`. Manifest and
artifacts are read without modification. CPU time and peak memory are explicit
nullable values; named budget counters remain exact integers. The contracts are
`raw-execution-v1.schema.json` and
`raw-execution-verification-v1.schema.json`.

Exit code `0` means all referenced bytes were verified; `2` means the manifest,
identity, budget, filesystem object, size, or hash was invalid. Failures do not
produce a passing audit.

## Semantic normalization

`normalize_semantic_projection.py` binds one exact run identity and case to
single JSON Pointer targets. Each policy rule specifies an approved transform,
exact replacement count, and exact complete normalized value. See
`semantic-projection-v1.schema.json`,
`semantic-normalization-policy-v1.schema.json`, and
`semantic-normalization-output-v1.schema.json`.

## Difference waiver audit

The waiver validator consumes:

- one registry bound to exactly one platform, upstream commit, and Rust schema;
- one semantic difference report with the same identity;
- an explicit audit date.

Example:

```text
python tools/compat/validate_difference_waivers.py \
  --registry docs/design/schemas/examples/difference-waiver-registry-v1.example.json \
  --report docs/design/schemas/examples/difference-input-report-v1.example.json \
  --as-of 2026-07-27
```

Exit codes:

- `0`: every reported difference has one exact approved waiver, and no waiver
  is expired, stale, or unevaluated;
- `1`: the inputs are valid, but the waiver audit fails;
- `2`: schema, identity, fingerprint, repository reference, or JSON parsing
  failed.

The validator is read-only with respect to registry and report inputs and
records their SHA-256 in its audit. It recomputes every difference fingerprint
from canonical JSON plus both raw stream hashes.

The normative v1 shapes and synthetic examples are under
`docs/design/schemas/`. The three tools remain standalone slices; the full
differential harness must still enforce their ordering and carry their exact
audit hashes in one report.
