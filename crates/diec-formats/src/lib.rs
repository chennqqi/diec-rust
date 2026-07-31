//! `diec-formats` provides format probing and safe parsing, returning format
//! facts via checked input.
//!
//! It does not decide whether to scan overlays, enable aggressive mode or
//! which rule to run first. Format candidates are driven by an explicit,
//! versioned ordered probe table. Parsers access bytes only through
//! `diec-core`'s checked input and never write final detections or read the
//! rule database. See `docs/design/architecture.md` section 8.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Placeholder for the future format probe table. Phase 1 only establishes the
/// crate boundary; format modules land in Phase 2.
pub fn placeholder() -> &'static str {
    "diec-formats skeleton"
}

#[cfg(test)]
mod tests {
    use super::placeholder;

    #[test]
    fn skeleton_is_reachable() {
        assert_eq!(placeholder(), "diec-formats skeleton");
    }
}
