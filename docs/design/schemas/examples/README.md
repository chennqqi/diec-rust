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
