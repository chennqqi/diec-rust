//! `diec-output` renders the unified scan result model into canonical JSON
//! and human-readable output.
//!
//! It only performs presentation conversion and never duplicates detection,
//! nesting, ordering or diagnostic logic. Canonical JSON is the stable data
//! plane shared by the library, FFI and modern CLI; the legacy compatibility
//! renderer is separate. See `docs/design/api.md` section 13 and ADR 0003.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Placeholder for the future renderers. Phase 1 only establishes the crate
/// boundary; canonical/legacy renderers land later.
pub fn placeholder() -> &'static str {
    "diec-output skeleton"
}

#[cfg(test)]
mod tests {
    use super::placeholder;

    #[test]
    fn skeleton_is_reachable() {
        assert_eq!(placeholder(), "diec-output skeleton");
    }
}
