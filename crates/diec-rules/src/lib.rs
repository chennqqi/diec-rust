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

pub mod budget;
pub mod error;
pub mod host_api;
pub mod include_graph;
pub mod inventory;
pub mod manifest;
pub mod order_manifest;
pub mod runtime;

#[cfg(test)]
mod tests {
    #[test]
    fn crate_loads() {
        // Smoke test: ensure all modules compile and link.
        let _ = super::budget::RuleBudgetProfile::MODERN;
    }
}
