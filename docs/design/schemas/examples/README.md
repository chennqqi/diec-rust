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
