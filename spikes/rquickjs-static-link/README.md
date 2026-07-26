# rquickjs static-link spike

Phase 0 feasibility probe only. The Rust `staticlib` creates a real
rquickjs/QuickJS-NG runtime and context from a C caller, evaluates `40 + 2`,
repeats creation/destruction, validates null handling, and contains a Rust
panic at the C ABI boundary.

Run Windows MSVC dynamic-CRT and static-CRT variants:

```cmd
run-windows-msvc.cmd
run-windows-msvc.cmd --static-crt
```

Run the Linux GNU variant from an environment with Rust 1.88 and a C
compiler:

```sh
./run-linux-gnu.sh
```

This spike does not define the production ABI or select the runtime by
itself.
