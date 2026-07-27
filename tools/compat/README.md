# Compatibility tooling

`validate_difference_waivers.py` is the Phase 0 reference validator for
evidence-bound semantic difference waivers.

It consumes:

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
from canonical JSON plus both raw stream hashes. It does not yet fetch or
rehash external content-addressed raw artifacts; that integration remains part
of the full differential harness.

The normative v1 shapes and synthetic examples are under
`docs/design/schemas/`.
