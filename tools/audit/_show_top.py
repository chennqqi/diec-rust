#!/usr/bin/env python3
"""Show top bare-assignment variables from audit results."""
import json
from pathlib import Path

audit = json.loads(
    Path("docs/research/data/runtime-reuse-state-audit.json").read_text(encoding="utf-8")
)

items = [
    (name, info)
    for name, info in audit["classification"].items()
    if info["classification"] == "b_pure_global"
]
items.sort(key=lambda x: -x[1]["occurrence_count"])

print("Top 30 pure global variables:")
print(f"{'Variable':<30s} {'Occurrences':>12s} {'Files':>6s}  Example context")
print("-" * 100)
for name, info in items[:30]:
    ctx = info["occurrences"][0]["context"][:60]
    print(f"{name:<30s} {info['occurrence_count']:>12d} {info['file_count']:>6d}  {ctx}")

print()
print("Top 10 mixed (c) variables:")
c_items = [
    (name, info)
    for name, info in audit["classification"].items()
    if info["classification"] == "c_mixed"
]
c_items.sort(key=lambda x: -x[1]["occurrence_count"])
for name, info in c_items[:10]:
    ctx = info["occurrences"][0]["context"][:60]
    print(f"{name:<30s} {info['occurrence_count']:>12d} {info['file_count']:>6d}  {ctx}")
