//! `diec-rules` owns three boundaries: the original rule assets and source
//! manifest, rule metadata/load diagnostics and disposable derived caches, and
//! the `RuleRuntime`/`HostApi` ports.
//!
//! Rule source files are never formatted or hand-corrected. Unknown syntax,
//! include failures and database conflicts must become explicit errors or
//! compatibility failures, never silently skipped. `HostApi` is defined here
//! and implemented by `diec-engine`'s adapter, so the rule layer does not
//! depend on `diec-formats`. See `docs/design/architecture.md` section 9.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Placeholder for the future rule database and runtime. Phase 1 only
/// establishes the crate boundary; the rule runtime lands in Phase 3.
pub fn placeholder() -> &'static str {
    "diec-rules skeleton"
}

#[cfg(test)]
mod tests {
    use super::placeholder;

    #[test]
    fn skeleton_is_reachable() {
        assert_eq!(placeholder(), "diec-rules skeleton");
    }
}
