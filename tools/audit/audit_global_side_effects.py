#!/usr/bin/env python3
"""Audit rule files for global side effects (bare assignments without var/let/const).

Rules are evaluated inside an IIFE wrapper (see backend_rquickjs.rs:604-612):
    (function() {
        {rule_source}
        if (typeof detect === 'function') { return detect(); }
        return undefined;
    })();

In sloppy mode, a bare assignment (e.g. `bDetected = true;`) inside a function
creates or mutates a GLOBAL variable. When runtime is reused across files,
these global variables leak from one file's rule evaluation to the next.

This script scans all .sg rule files for bare assignments and classifies them:
  (a) read-only constant  — only assigned once, never read by other rules
  (b) mutable state         — assigned and potentially read across rules
  (c) local to detect()     — inside detect() function scope, still leaks in
                              sloppy mode but isolated by IIFE return

Output: docs/research/data/runtime-reuse-state-audit.json
Report: docs/research/runtime-reuse-state-audit.md
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# --- Configuration ---

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DB_ROOT = WORKSPACE_ROOT / "upstream" / "Detect-It-Easy" / "db"
OUTPUT_JSON = WORKSPACE_ROOT / "docs" / "research" / "data" / "runtime-reuse-state-audit.json"
OUTPUT_MD = WORKSPACE_ROOT / "docs" / "research" / "runtime-reuse-state-audit.md"

# --- Regex patterns ---

# Match bare assignment: identifier = value (not ==, !=, <=, >=, +=, etc.)
# Must not be preceded by var/let/const on the same statement.
# Must not be a property access (obj.prop = or obj[key] =).
# Matches patterns like:
#   bDetected = true;
#   sOptions = "...";
#   sResult = result();
# Does NOT match:
#   var x = 1;  let x = 1;  const x = 1;
#   x == 1;  x != 1;  x <= 1;  x >= 1;
#   obj.prop = 1;  obj[key] = 1;
#   x += 1;  x -= 1; (compound assignments - handled separately)

# Simple assignment: word boundary, identifier, whitespace, single =, not ==
BARE_ASSIGN_RE = re.compile(
    r'(?<![\w.\])])'           # not preceded by word char, dot, bracket
    r'([a-zA-Z_$][a-zA-Z0-9_$]*)'  # identifier
    r'\s*=\s*'                  # = with optional spaces (but not ==)
    r'(?![=])'                  # not followed by another = (i.e., not ==)
)

# Compound assignment: identifier += -= *= /= %= etc.
COMPOUND_ASSIGN_RE = re.compile(
    r'(?<![\w.\])])'
    r'([a-zA-Z_$][a-zA-Z0-9_$]*)'
    r'\s*([+\-*/%&|^]=)'        # compound assignment operator
)

# var/let/const declaration that might precede a bare assignment on a later line
DECLARATION_RE = re.compile(
    r'\b(?:var|let|const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\b'
)

# Property assignment: obj.prop = or obj["key"] =
PROPERTY_ASSIGN_RE = re.compile(
    r'[a-zA-Z_$][a-zA-Z0-9_$]*\s*[.\[]\s*["\']?'
)

# Comment removal (simple: strip // ... and /* ... */)
def strip_comments(source: str) -> str:
    """Remove // line comments and /* */ block comments."""
    # Remove block comments
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
    # Remove line comments (but not inside strings - simple heuristic)
    lines = source.split('\n')
    result = []
    in_string = False
    string_char = None
    for line in lines:
        stripped = []
        i = 0
        while i < len(line):
            ch = line[i]
            if in_string:
                stripped.append(ch)
                if ch == '\\' and i + 1 < len(line):
                    stripped.append(line[i + 1])
                    i += 2
                    continue
                if ch == string_char:
                    in_string = False
                i += 1
            elif ch in ('"', "'", '`'):
                in_string = True
                string_char = ch
                stripped.append(ch)
                i += 1
            elif ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break  # rest is comment
            else:
                stripped.append(ch)
                i += 1
        result.append(''.join(stripped))
    return '\n'.join(result)


def find_bare_assignments(source: str) -> list[tuple[int, str, str]]:
    """Find bare assignments in source code.

    Returns list of (line_number, variable_name, full_match).
    """
    clean = strip_comments(source)
    lines = clean.split('\n')
    findings = []

    for line_num, line in enumerate(lines, 1):
        # Skip empty lines
        stripped = line.strip()
        if not stripped:
            continue

        # Find all bare assignments on this line
        for match in BARE_ASSIGN_RE.finditer(line):
            var_name = match.group(1)
            full_match = match.group(0)

            # Check if this is actually a declaration (var/let/const before it)
            prefix = line[:match.start()]
            if re.search(r'\b(?:var|let|const)\s*$', prefix):
                continue  # This is a declaration, skip

            # Check if it's a property assignment (preceded by . or [)
            if re.search(r'[.\[]\s*$', prefix):
                continue

            # Check if it's a destructuring or other complex pattern
            # (e.g., `var [a, b] = ...` — the prefix would have var)
            # Already handled by the var/let/const check above

            # Check if identifier is a known global that's intentionally shared
            # (these are set by the framework, not by rules)
            if var_name in ('__diec_results', '__diec_block_list',
                            '__diec_meta', 'meta', '_setResult', '_setLang',
                            '_error', '_log', '_getEngineVersion',
                            '_getQtVersion', '_isStop', 'includeScript',
                            'detect', 'result'):
                continue

            findings.append((line_num, var_name, stripped))

        # Also check compound assignments
        for match in COMPOUND_ASSIGN_RE.finditer(line):
            var_name = match.group(1)
            op = match.group(2)
            full_match = match.group(0)

            # Skip if preceded by var/let/const
            prefix = line[:match.start()]
            if re.search(r'\b(?:var|let|const)\s*$', prefix):
                continue

            if var_name in ('__diec_results', '__diec_block_list',
                            '__diec_meta', 'meta', '_setResult', '_setLang',
                            '_error', '_log', '_getEngineVersion',
                            '_getQtVersion', '_isStop', 'includeScript',
                            'detect', 'result'):
                continue

            findings.append((line_num, var_name, stripped))

    return findings


def audit_all_rules() -> dict:
    """Audit all .sg rule files for global side effects."""
    if not DB_ROOT.is_dir():
        print(f"ERROR: database root not found: {DB_ROOT}", file=sys.stderr)
        sys.exit(1)

    # Collect all .sg files
    sg_files = sorted(DB_ROOT.rglob("*.sg"))
    print(f"Scanning {len(sg_files)} rule files...")

    # Results: var_name -> list of (file, line, context)
    bare_assignments = defaultdict(list)
    # Declarations: var_name -> set of files that declare it
    declarations = defaultdict(set)
    # Per-file findings
    per_file = {}

    for sg_file in sg_files:
        rel_path = sg_file.relative_to(DB_ROOT).as_posix()
        try:
            source = sg_file.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f"  WARNING: could not read {rel_path}: {e}", file=sys.stderr)
            continue

        findings = find_bare_assignments(source)
        if findings:
            per_file[rel_path] = []
            for line_num, var_name, context in findings:
                bare_assignments[var_name].append({
                    "file": rel_path,
                    "line": line_num,
                    "context": context[:200],  # truncate long lines
                })
                per_file[rel_path].append({
                    "line": line_num,
                    "variable": var_name,
                    "context": context[:200],
                })

        # Track declarations
        clean = strip_comments(source)
        for match in DECLARATION_RE.finditer(clean):
            declarations[match.group(1)].add(rel_path)

    # Classify variables
    # (a) declared with var/let/const in the same file (local, but still leaks
    #     in sloppy mode if the bare assignment is in a nested function)
    # (b) never declared anywhere — pure global leak
    # (c) declared in some files but bare-assigned in others
    classification = {}
    for var_name, occurrences in bare_assignments.items():
        files_with_bare = {occ["file"] for occ in occurrences}
        files_with_decl = declarations.get(var_name, set())

        # Check: is the variable declared in the SAME file as the bare assignment?
        same_file_declared = files_with_bare & files_with_decl

        # Is it declared in the framework (init/read include)?
        # We can't easily check this, but known framework globals are excluded above

        classification[var_name] = {
            "occurrence_count": len(occurrences),
            "file_count": len(files_with_bare),
            "files": sorted(files_with_bare),
            "declared_in_same_file": bool(same_file_declared),
            "declared_in_other_files": bool(files_with_decl - files_with_bare),
            "declaration_files": sorted(files_with_decl) if files_with_decl else [],
            "classification": (
                "b_pure_global" if not files_with_decl
                else "c_mixed" if files_with_decl - files_with_bare
                else "a_same_file_declared"
            ),
            "occurrences": occurrences,
        }

    # Sort by classification then by occurrence count
    sorted_classification = dict(
        sorted(classification.items(),
               key=lambda x: (x[1]["classification"], -x[1]["occurrence_count"]))
    )

    result = {
        "schema": 1,
        "audited_at": "2026-08-04",
        "db_root": str(DB_ROOT.relative_to(WORKSPACE_ROOT)),
        "total_files": len(sg_files),
        "files_with_bare_assignments": len(per_file),
        "total_bare_assignment_occurrences": sum(len(v) for v in per_file.values()),
        "unique_bare_variables": len(bare_assignments),
        "classification": sorted_classification,
        "per_file": dict(sorted(per_file.items())),
        "summary": {
            "b_pure_global": sum(1 for v in classification.values()
                                 if v["classification"] == "b_pure_global"),
            "c_mixed": sum(1 for v in classification.values()
                           if v["classification"] == "c_mixed"),
            "a_same_file_declared": sum(1 for v in classification.values()
                                        if v["classification"] == "a_same_file_declared"),
        },
    }

    return result


def write_report(audit: dict) -> None:
    """Write markdown report."""
    lines = [
        "# Runtime Reuse State Audit",
        "",
        f"Audited: {audit['audited_at']}",
        f"Database: `{audit['db_root']}`",
        f"Total files: {audit['total_files']}",
        f"Files with bare assignments: {audit['files_with_bare_assignments']}",
        f"Total bare assignment occurrences: {audit['total_bare_assignment_occurrences']}",
        f"Unique bare variables: {audit['unique_bare_variables']}",
        "",
        "## Summary",
        "",
        "| Classification | Count | Description |",
        "|---------------|-------|-------------|",
        f"| b_pure_global | {audit['summary']['b_pure_global']} | "
        "Never declared with var/let/const — pure global leak |",
        f"| c_mixed | {audit['summary']['c_mixed']} | "
        "Declared in some files, bare-assigned in others |",
        f"| a_same_file_declared | {audit['summary']['a_same_file_declared']} | "
        "Declared with var/let/const in the same file (may still leak in sloppy mode) |",
        "",
        "## Methodology",
        "",
        "Rules are evaluated inside an IIFE wrapper:",
        "```js",
        "(function() {",
        "    {rule_source}",
        "    if (typeof detect === 'function') { return detect(); }",
        "    return undefined;",
        "})();",
        "```",
        "",
        "In sloppy mode, a bare assignment (e.g. `bDetected = true;`) inside",
        "a function creates or mutates a GLOBAL variable. When runtime is",
        "reused across files, these global variables leak from one file's",
        "rule evaluation to the next.",
        "",
        "This audit scans all `.sg` rule files for bare assignments",
        "(assignments without `var`/`let`/`const`) and classifies them.",
        "",
        "## Risk Assessment",
        "",
        "### (b) Pure global — highest risk",
        "",
        "These variables are never declared with `var`/`let`/`const` in any",
        "rule file. In sloppy mode, the first rule to assign them creates a",
        "global. Subsequent rules in the same runtime will see the stale",
        "value from the previous file's scan.",
        "",
        "These MUST be reset before reusing the runtime for a new file.",
        "",
    ]

    # List b_pure_global variables
    b_vars = [(name, info) for name, info in audit["classification"].items()
              if info["classification"] == "b_pure_global"]
    if b_vars:
        lines.append("| Variable | Occurrences | Files |")
        lines.append("|----------|-------------|-------|")
        for name, info in sorted(b_vars, key=lambda x: -x[1]["occurrence_count"]):
            lines.append(
                f"| `{name}` | {info['occurrence_count']} | "
                f"{info['file_count']} |"
            )
    else:
        lines.append("None found.")

    lines.extend([
        "",
        "### (c) Mixed — medium risk",
        "",
        "These variables are declared with `var`/`let`/`const` in some files",
        "but bare-assigned in others. The bare-assigned occurrences leak to",
        "global scope.",
        "",
    ])
    c_vars = [(name, info) for name, info in audit["classification"].items()
              if info["classification"] == "c_mixed"]
    if c_vars:
        lines.append("| Variable | Bare occurrences | Declared in files |")
        lines.append("|----------|-----------------|-------------------|")
        for name, info in sorted(c_vars, key=lambda x: -x[1]["occurrence_count"]):
            lines.append(
                f"| `{name}` | {info['occurrence_count']} | "
                f"{len(info['declaration_files'])} |"
            )
    else:
        lines.append("None found.")

    lines.extend([
        "",
        "### (a) Same-file declared — lower risk",
        "",
        "These variables are declared with `var`/`let`/`const` in the same",
        "file where they are bare-assigned. The declaration may or may not",
        "prevent global leakage depending on scope:",
        "- If `var x` is at the top level of the rule (inside IIFE), it is",
        "  function-scoped and does NOT leak.",
        "- If `var x` is inside `detect()` but the bare assignment is in a",
        "  nested function, it DOES leak to the IIFE scope, not global.",
        "",
        "These need manual review to confirm they are function-scoped.",
        "",
    ])
    a_vars = [(name, info) for name, info in audit["classification"].items()
              if info["classification"] == "a_same_file_declared"]
    if a_vars:
        lines.append("| Variable | Occurrences | Files |")
        lines.append("|----------|-------------|-------|")
        for name, info in sorted(a_vars, key=lambda x: -x[1]["occurrence_count"]):
            lines.append(
                f"| `{name}` | {info['occurrence_count']} | "
                f"{info['file_count']} |"
            )
    else:
        lines.append("None found.")

    lines.extend([
        "",
        "## Reset Strategy",
        "",
        "Before reusing a runtime for a new file, execute a reset script that",
        "clears all (b) and (c) classified variables:",
        "",
        "```js",
    ])
    reset_vars = [name for name, info in audit["classification"].items()
                  if info["classification"] in ("b_pure_global", "c_mixed")]
    if reset_vars:
        # Generate reset script
        for var_name in sorted(reset_vars):
            lines.append(f"try {{ {var_name} = undefined; }} catch(e) {{}}")
    else:
        lines.append("// No variables to reset")
    lines.extend([
        "```",
        "",
        "## Conclusion",
        "",
    ])

    if audit['summary']['b_pure_global'] > 0:
        lines.extend([
            f"Found **{audit['summary']['b_pure_global']}** pure global variables",
            f"that leak across files. Runtime reuse requires a reset script",
            f"clearing these variables before each file scan.",
            "",
            "The reset script above must be executed after `clear_results()`",
            "and before evaluating the first rule for a new file.",
        ])
    else:
        lines.extend([
            "No pure global variables found. Runtime reuse is safe without",
            "a reset script (subject to differential testing confirmation).",
        ])

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"Report written to: {OUTPUT_MD}")


def main() -> None:
    audit = audit_all_rules()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8'
    )
    print(f"JSON written to: {OUTPUT_JSON}")

    write_report(audit)

    # Print summary
    print()
    print("=" * 60)
    print(f"Total files:                  {audit['total_files']}")
    print(f"Files with bare assignments:  {audit['files_with_bare_assignments']}")
    print(f"Total bare assignments:       {audit['total_bare_assignment_occurrences']}")
    print(f"Unique bare variables:        {audit['unique_bare_variables']}")
    print()
    print("Classification:")
    print(f"  (b) pure global:     {audit['summary']['b_pure_global']}")
    print(f"  (c) mixed:           {audit['summary']['c_mixed']}")
    print(f"  (a) same-file decl:  {audit['summary']['a_same_file_declared']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
