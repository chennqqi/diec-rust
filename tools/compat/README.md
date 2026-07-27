# Compatibility tooling

Phase 0 currently provides seven strict compatibility sub-pipeline tools:

- `verify_raw_execution.py` validates a versioned execution record and rehashes
  its content-addressed stdout/stderr/runtime-log bytes;
- `project_raw_framing.py` creates a lossless byte-range projection of verified
  stdout, including every prefix/trailing diagnostic;
- `project_semantic_result.py` projects one contract-bound legacy CLI result
  into a closed typed model without dropping raw streams;
- `normalize_semantic_projection.py` applies only evidence-backed, closed-set
  semantic transforms;
- `compare_semantic_results.py` rebuilds both projections from raw evidence,
  optionally normalizes both sides, and emits an ordered semantic comparison;
- `validate_difference_waivers.py` audits evidence-bound semantic difference
  waivers;
- `audit_semantic_case.py` rebuilds one two-sided comparison and applies the
  exact waiver audit as one authoritative case decision.

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

## Lossless raw framing

The framing projector always runs raw execution verification first, then
re-reads stdout with the same size/hash/file-identity checks:

```text
python tools/compat/project_raw_framing.py \
  --manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --artifact-root docs/design/schemas/examples/raw-artifacts \
  --output raw-framing-projection.json
```

`raw-framing-projection-v1.schema.json` represents the entire stdout as
contiguous ordered byte ranges. Strict object/array JSON documents beginning at
stream or line start receive parsed values and raw/canonical hashes; all other
bytes stay in `raw` segments. Invalid UTF-8/JSON, duplicate keys, non-finite
numbers, prefixes, separators and trailing diagnostics are never discarded.
The projector caps one JSON document at 8 MiB, documents at 4096 and nesting at
256; a limit preserves remaining raw bytes and emits
`projection_limit_reached` plus exact reasons. `documents_found` describes
framing only and is not a differential pass.

## Typed semantic result

`project_semantic_result.py` requires both a raw execution and a strict
`semantic-projection-contract-v1`:

```text
python tools/compat/project_semantic_result.py \
  --contract docs/design/schemas/examples/semantic-projection-contract-v1.example.json \
  --manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --artifact-root docs/design/schemas/examples/raw-artifacts \
  --output semantic-result-projection.json
```

The contract supplies the shared upstream target/oracle identity and expected
legacy CLI output kind/count; producer revision remains side-specific. The
projector re-verifies every artifact, rebuilds framing, and types normal scan,
entropy, info, struct and normal-scan error documents. It retains raw stdout
segments plus stderr/runtime log as lossless line records: comparison holds
UTF-8 or base64 body/ending, while evidence holds the correlated exact
offset/size/hash. Unknown fields/shapes, document-count drift and framing limits
produce an auditable
`projection_failure` with the original value still present.

Future two-sided equality compares only `semantic.comparison`.
`semantic.producer` and `semantic.evidence` bind side-specific provenance and
must not create false detection differences.

Exit code `0` is a valid passing projection, `1` is a valid
`projection_failure`, and `2` is invalid identity/evidence/filesystem input.
The schemas are `semantic-projection-contract-v1.schema.json`,
`semantic-result-v1.schema.json`, and
`semantic-result-projection-v1.schema.json`.

## Semantic normalization

`normalize_semantic_projection.py` binds one exact run identity and case to
single JSON Pointer targets. Each policy rule specifies an approved transform,
exact replacement count, and exact complete normalized value. See
`semantic-projection-v1.schema.json`,
`semantic-normalization-policy-v1.schema.json`, and
`semantic-normalization-output-v1.schema.json`.

## Audited two-sided semantic comparison

The comparator consumes one shared comparison contract, one shared projection
contract, and two raw execution manifests. It does not trust caller-produced
projection or normalization artifacts: it rebuilds and persists both sides in
the required order.

```text
python tools/compat/compare_semantic_results.py \
  --comparison-contract docs/design/schemas/examples/semantic-comparison-contract-v1.example.json \
  --projection-contract docs/design/schemas/examples/semantic-projection-contract-v1.example.json \
  --upstream-manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --upstream-artifact-root docs/design/schemas/examples/raw-artifacts \
  --rust-manifest docs/design/schemas/examples/semantic-comparison-rust-execution-v1.example.json \
  --rust-artifact-root docs/design/schemas/examples/raw-artifacts \
  --upstream-projection-output upstream-projection.json \
  --rust-projection-output rust-projection.json \
  --comparison-output semantic-comparison.json \
  --difference-report-output semantic-differences.json
```

An optional shared normalization policy requires two explicit normalization
outputs. Equality is recursive and strict over `semantic.comparison`: object
keys are traversed in sorted order, arrays remain ordered, JSON types remain
distinct except that integer and finite floating representations of the same
number compare equal, and missing values are not confused with JSON `null`.
Every difference has a stable RFC 6901 pointer below `/comparison`, explicit
presence state, both raw-observation hashes and a recomputed waiver-compatible
fingerprint. The complete difference set is capped at exactly 10,000 entries;
the comparator never publishes a partial valid difference report.

`exact` requires identical termination and raw stdout/stderr/runtime-log
references as well as semantic equality. `semantic_equal` preserves a raw
difference while recording semantic equality. `different`,
`projection_failure`, and `comparison_limit_reached` fail either equivalence
requirement. A projection failure skips configured normalization.

Exit code `0` means the contract's `exact` or `semantic` requirement was met;
`1` means a valid comparison did not meet it; `2` means projection failure,
difference-limit exhaustion, or invalid infrastructure input. Successful
comparisons always replace the difference output with a valid v1 report.
Projection/limit failures replace it with a versioned blocked marker that the
waiver validator rejects, preventing a stale earlier report from being reused.

The contracts are
`semantic-comparison-contract-v1.schema.json`,
`semantic-comparison-v1.schema.json`, and
`semantic-difference-blocked-v1.schema.json`.

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
`docs/design/schemas/`.

## Authoritative single-case audit

`audit_semantic_case.py` is the trusted entry point for one typed legacy CLI
case. It accepts the comparator's raw inputs plus one exact waiver registry,
rebuilds every intermediate artifact, and writes the comparison, difference
report, waiver audit and `semantic-case-audit-v1` result. It freezes and re-reads
the registry and generated artifacts, records both byte and canonical hashes,
and rejects output collisions or outputs below either raw artifact root.

An `exact` result, or `semantic_equal` under a semantic requirement, passes when
the waiver registry has no stale entries. A `different` result passes only when
every difference has one exact current waiver. Raw-only mismatch under an exact
requirement is deliberately not waivable in v1. Projection failure, difference
limit exhaustion, invalid inputs and mutation are `infrastructure_error`; the
tool overwrites the waiver output with a non-passing infrastructure audit.

Exit codes are `0` for pass, `1` for a valid failed requirement/audit, and `2`
for infrastructure error. A reproducible full invocation is in
`docs/design/schemas/examples/README.md`.

The tools remain partially integrated slices: engine-only/modern typed
variants, multi-case aggregation and the full differential report still need
integration.
