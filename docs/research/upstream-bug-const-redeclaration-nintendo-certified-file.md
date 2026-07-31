# Upstream Bug Report: `const` redeclaration in `format_bin.Nintendo-certified-file.1.sg`

## Summary

The rule file `db/Binary/format_bin.Nintendo-certified-file.1.sg` contains a
`const` redeclaration of the variable `tp` that was already declared with `var`
in the same function scope. This is accepted by QtScript (the JS engine used by
upstream DIE) but rejected by modern ECMAScript engines such as QuickJS, V8, and
SpiderMonkey, producing a `SyntaxError: invalid redefinition of a variable`.

## Upstream repository

- **Repo**: https://github.com/horsicq/Detect-It-Easy
- **Branch**: master
- **Commit**: `4b675ffdd7400087699c13950b95cbf3703990fe`
- **File**: `db/Binary/format_bin.Nintendo-certified-file.1.sg`
- **Author**: Kae (TG @kaens)

## Affected lines

Lines 10 and 15 (inside `function detect()`):

```javascript
function detect() {
    if (X.c("'SCE'00")) {
        var tp, e;                          // line 10: var tp
        if (X.c('0000 0002', 4)) e = _BE;   // line 11
        else if (X.c('0300 0000', 4)) e = _LE; // line 12
        else return;
        // PS3/Vita Certified File
        const attr = X.U16(8, e), tp = X.U16(0xA, e), ... // line 15: const tp (REDECLARATION)
```

## Root cause

Line 10 declares `var tp` (function-scoped).
Line 15 declares `const tp` in the same function scope as part of a
multi-variable `const` statement.

In QtScript (based on old Qt's JavaScriptCore), `const` redeclaration of a
`var` in the same scope is silently allowed — the `const` binding shadows or
overwrites the `var` binding without error.

In QuickJS (and per ECMAScript spec §13.3.1 / §8.1.1), redeclaring a `var`
binding with `const` in the same scope is a `SyntaxError`.

## Error message (QuickJS)

```
SyntaxError: invalid redefinition of a variable
```

## Reproduction

1. Load the rule in any spec-compliant JS engine (QuickJS, V8, SpiderMonkey).
2. Evaluate the `detect()` function source.
3. Observe `SyntaxError: invalid redefinition of a variable`.

Alternatively, using the `diec-rust` project (which uses QuickJS via `rquickjs`):

```sh
diec --output json <any_file>
# diagnostics includes:
# "Binary/format_bin.Nintendo-certified-file.1.sg: script exception in
#  'Binary/format_bin.Nintendo-certified-file.1.sg': SyntaxError:
#  invalid redefinition of a variable"
```

## Suggested fix

Remove the `tp` from the `var` declaration on line 10 (keep only `var e;`),
since `tp` is properly declared as `const` on line 15.

```diff
-        var tp, e;
+        var e;
```

Alternatively, rename the `const tp` on line 15 to a different variable name
(e.g., `const tpVal`), but the first option is simpler and the `var tp` on
line 10 is never used before the `const tp` assignment.

## Impact

- The rule fails to load in any JS engine that enforces ECMAScript lexical
  declaration rules.
- No detection for "Unknown Certified File" / "Nintendō signed ELF/PRX" is
  produced.
- As more tools migrate from QtScript to modern JS engines (e.g., QuickJS),
  this rule will break for all of them.

## Environment

- **diec-rust**: uses `rquickjs` (QuickJS binding for Rust)
- **QuickJS version**: as bundled in `rquickjs` crate
- **OS**: Windows / Linux / macOS (engine-independent issue)
