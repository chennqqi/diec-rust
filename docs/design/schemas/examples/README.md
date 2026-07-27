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
