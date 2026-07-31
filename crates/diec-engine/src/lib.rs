//! `diec-engine` is the sole scan orchestration layer.
//!
//! A request runs: option/input/hard-limit validation, immutable database
//! snapshot fixation, scan context creation, ordered format probe collection,
//! host adapter construction, global/type init and ordered rule execution,
//! detection/diagnostic/child-work aggregation, and bounded work-queue
//! processing of resource/overlay/archive file-parts. CLI, FFI and output
//! crates never duplicate any detection branch. See
//! `docs/design/architecture.md` section 10.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Placeholder for the future scan service. Phase 1 only establishes the crate
/// boundary; the scan pipeline lands in Phase 2/3.
pub fn placeholder() -> &'static str {
    "diec-engine skeleton"
}

#[cfg(test)]
mod tests {
    use super::placeholder;

    #[test]
    fn skeleton_is_reachable() {
        assert_eq!(placeholder(), "diec-engine skeleton");
    }
}
