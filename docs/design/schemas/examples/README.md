# Difference waiver v1 synthetic examples

These files are documentation-only synthetic inputs. They do not approve a real
compatibility difference and must not be copied into a release waiver registry.

Reproduce the audit with:

```text
python tools/compat/validate_difference_waivers.py \
  --registry docs/design/schemas/examples/difference-waiver-registry-v1.example.json \
  --report docs/design/schemas/examples/difference-input-report-v1.example.json \
  --as-of 2026-07-27 \
  --output docs/design/schemas/examples/difference-waiver-audit-v1.example.json
```

The audit binds both input files by SHA-256. Changing either example requires
regenerating the audit intentionally.

The semantic-normalization files are also documentation-only synthetic data.
Reproduce their golden output with:

```text
python tools/compat/normalize_semantic_projection.py \
  --input docs/design/schemas/examples/semantic-projection-v1.example.json \
  --policy docs/design/schemas/examples/semantic-normalization-policy-v1.example.json \
  --output docs/design/schemas/examples/semantic-normalization-output-v1.example.json
```

The output binds the exact input and policy bytes and records each target
value's before/after hash. It must not be copied as a production normalization
policy.

The raw-execution example uses two harmless text streams under the fixed
content-addressed `raw-artifacts/sha256/` layout. Reproduce its audit with:

```text
python tools/compat/verify_raw_execution.py \
  --manifest docs/design/schemas/examples/raw-execution-v1.example.json \
  --artifact-root docs/design/schemas/examples/raw-artifacts \
  --max-artifact-bytes 1024 \
  --output docs/design/schemas/examples/raw-execution-verification-v1.example.json
```

The zero/one case and executable hashes are synthetic sentinels, not real
provenance.

The framing example combines profiling prefix lines, one JSON document and a
trailing rule error in stdout. Reproduce the lossless projection with:

```text
python tools/compat/project_raw_framing.py \
  --manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --artifact-root docs/design/schemas/examples/raw-artifacts \
  --max-artifact-bytes 1024 \
  --output docs/design/schemas/examples/raw-framing-projection-v1.example.json
```

Its three byte ranges cover the original stdout exactly; neither raw diagnostic
is part of the parsed JSON value or omitted from the projection.

The semantic-result example reuses that verified execution and adds an exact
case contract. Reproduce it with:

```text
python tools/compat/project_semantic_result.py \
  --contract docs/design/schemas/examples/semantic-projection-contract-v1.example.json \
  --manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --artifact-root docs/design/schemas/examples/raw-artifacts \
  --max-artifact-bytes 1024 \
  --output docs/design/schemas/examples/semantic-result-projection-v1.example.json
```

The typed document is an empty normal scan, while profiling prefix, trailing
rule error and stderr remain exact semantic stream records. The contract and
all identities/hashes are synthetic and approve no production baseline.

The two-sided comparison example reuses the upstream execution and pairs it
with a synthetic Rust execution whose producer identity is intentionally
different but whose raw observation is identical. Reproduce all four derived
artifacts with:

```text
python tools/compat/compare_semantic_results.py \
  --comparison-contract docs/design/schemas/examples/semantic-comparison-contract-v1.example.json \
  --projection-contract docs/design/schemas/examples/semantic-projection-contract-v1.example.json \
  --upstream-manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --upstream-artifact-root docs/design/schemas/examples/raw-artifacts \
  --rust-manifest docs/design/schemas/examples/semantic-comparison-rust-execution-v1.example.json \
  --rust-artifact-root docs/design/schemas/examples/raw-artifacts \
  --upstream-projection-output docs/design/schemas/examples/semantic-comparison-upstream-projection-v1.example.json \
  --rust-projection-output docs/design/schemas/examples/semantic-comparison-rust-projection-v1.example.json \
  --comparison-output docs/design/schemas/examples/semantic-comparison-v1.example.json \
  --difference-report-output docs/design/schemas/examples/semantic-comparison-difference-report-v1.example.json \
  --max-artifact-bytes 1024 \
  --repo-root .
```

The result is `exact`; producer-specific projection artifacts differ while
their comparison hashes match. The empty difference report remains a valid
waiver-input shape. Projection failure would write a blocked marker instead.

The authoritative single-case example adds an empty registry for that exact
result and produces both the waiver audit and top-level decision:

```text
python tools/compat/audit_semantic_case.py \
  --comparison-contract docs/design/schemas/examples/semantic-comparison-contract-v1.example.json \
  --projection-contract docs/design/schemas/examples/semantic-projection-contract-v1.example.json \
  --upstream-manifest docs/design/schemas/examples/raw-framing-execution-v1.example.json \
  --upstream-artifact-root docs/design/schemas/examples/raw-artifacts \
  --rust-manifest docs/design/schemas/examples/semantic-comparison-rust-execution-v1.example.json \
  --rust-artifact-root docs/design/schemas/examples/raw-artifacts \
  --upstream-projection-output docs/design/schemas/examples/semantic-comparison-upstream-projection-v1.example.json \
  --rust-projection-output docs/design/schemas/examples/semantic-comparison-rust-projection-v1.example.json \
  --comparison-output docs/design/schemas/examples/semantic-comparison-v1.example.json \
  --difference-report-output docs/design/schemas/examples/semantic-comparison-difference-report-v1.example.json \
  --waiver-registry docs/design/schemas/examples/semantic-case-waiver-registry-v1.example.json \
  --waiver-audit-output docs/design/schemas/examples/semantic-case-waiver-audit-v1.example.json \
  --case-audit-output docs/design/schemas/examples/semantic-case-audit-v1.example.json \
  --as-of 2026-07-27 \
  --max-artifact-bytes 1024 \
  --repo-root .
```

These case-audit files are also documentation-only synthetic data and approve
no real compatibility difference.

The suite example fixes that case and every input hash in an explicit expected
matrix. Its output root must be outside the repository/input root:

```text
python tools/compat/run_compatibility_suite.py \
  --plan docs/design/schemas/examples/compatibility-suite-plan-v1.example.json \
  --input-root . \
  --output-root <temporary-output-root> \
  --repo-root .
```

`<temporary-output-root>/compatibility-report.json` must reproduce
`compatibility-suite-report-v1.example.json` byte for byte. Per-case derived
artifacts remain temporary; the report binds the exact case-audit bytes.
