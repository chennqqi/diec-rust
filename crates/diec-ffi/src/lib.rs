//! `diec-ffi` is the experimental C ABI adapter.
//!
//! It exposes opaque handles, fixed-layout C types, explicit ownership and
//! release functions, thread-safety annotations and an ABI version. Panics
//! never cross the FFI boundary. The C ABI remains experimental during Phase 1
//! and is stabilized in Phase 5. See `docs/design/c-abi.md`.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Placeholder ABI version. The real versioned ABI lands in Phase 5.
pub const DIEC_ABI_VERSION_EXPERIMENTAL: u32 = 0;

#[cfg(test)]
mod tests {
    use super::DIEC_ABI_VERSION_EXPERIMENTAL;

    #[test]
    fn abi_version_is_zero_during_phase1() {
        assert_eq!(DIEC_ABI_VERSION_EXPERIMENTAL, 0);
    }
}
