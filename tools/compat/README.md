# Compatibility tooling

Phase 0 currently provides five strict compatibility sub-pipeline tools:

- `verify_raw_execution.py` validates a versioned execution record and rehashes
  its content-addressed stdout/stderr/runtime-log bytes;
- `project_raw_framing.py` creates a lossless byte-range projection of verified
  stdout, including every prefix/trailing diagnostic;
- `project_semantic_result.py` projects one contract-bound legacy CLI result
  into a closed typed model without dropping raw streams;
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
`docs/design/schemas/`. The tools remain partially integrated slices; typed
engine-only variants, a two-sided comparator and the full differential report
must still enforce complete ordering and carry every audit hash.
