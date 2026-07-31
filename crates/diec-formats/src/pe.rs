//! PE (Portable Executable) format probe.
//!
//! PE files start with the MZ DOS header. The PE signature "PE\0\0" is at
//! the offset stored in `e_lfanew` (DWORD at offset 0x3C). This probe reads
//! the MZ header, validates `e_lfanew`, then checks the PE signature. A
//! successful PE match is strong and supersedes the weak MSDOS match.
//!
//! The PE32/PE64 distinction is made from the `Magic` field of the PE
//! optional header. This probe reads only enough to identify PE32 vs PE64;
//! full section/table parsing is deferred.

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// PE format probe.
#[derive(Debug, Default)]
pub struct PeProbe;

/// MZ DOS header minimum size.
const MZ_MIN_SIZE: u64 = 64;
/// Offset of `e_lfanew` in the MZ header.
const E_LFANEW_OFFSET: u64 = 0x3C;
/// PE signature "PE\0\0".
const PE_SIGNATURE: [u8; 4] = [0x50, 0x45, 0x00, 0x00];
/// Offset of the optional header magic from the PE signature.
const OPT_HDR_MAGIC_OFFSET_FROM_SIG: u64 = 24;
/// PE32 optional header magic.
const PE32_MAGIC: u16 = 0x010B;
/// PE64 (PE32+) optional header magic.
const PE64_MAGIC: u16 = 0x020B;

impl FormatProbe for PeProbe {
    fn file_type(&self) -> FileType {
        FileType::new("PE32")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // Need at least the MZ DOS header.
        if view.len() < MZ_MIN_SIZE {
            return Ok(None);
        }

        // Check MZ magic.
        let mz_magic = view.read_u16_le(0).map_err(ProbeError::Io)?;
        if mz_magic != 0x5A4D {
            return Ok(None);
        }

        // Read e_lfanew (offset to PE header).
        let e_lfanew = view.read_u32_le(E_LFANEW_OFFSET).map_err(ProbeError::Io)?;

        // e_lfanew must point within the file and leave room for the PE
        // signature (4 bytes) + COFF header (20 bytes) + optional header
        // magic (2 bytes) = 26 bytes minimum.
        let pe_sig_offset = u64::from(e_lfanew);
        let min_needed = pe_sig_offset
            .checked_add(OPT_HDR_MAGIC_OFFSET_FROM_SIG + 2)
            .ok_or_else(|| ProbeError::InvalidHeader {
                file_type: FileType::new("PE32"),
                detail: "e_lfanew overflow".into(),
            })?;

        if view.len() < min_needed {
            // e_lfanew points outside the file: not a valid PE.
            return Ok(None);
        }

        // Read and verify PE signature.
        let mut sig = [0u8; 4];
        view.read_exact_at(pe_sig_offset, &mut sig)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("PE32"),
                cause,
            })?;
        if sig != PE_SIGNATURE {
            return Ok(None);
        }

        // Read optional header magic to distinguish PE32 vs PE64.
        let opt_magic_offset = pe_sig_offset + OPT_HDR_MAGIC_OFFSET_FROM_SIG;
        let opt_magic =
            view.read_u16_le(opt_magic_offset)
                .map_err(|cause| ProbeError::Truncated {
                    file_type: FileType::new("PE32"),
                    cause,
                })?;

        let name = match opt_magic {
            PE32_MAGIC => "PE32",
            PE64_MAGIC => "PE64",
            _ => {
                // Unknown optional header magic: still a PE, but we cannot
                // determine 32 vs 64. Report as PE32 with invalid header.
                return Err(ProbeError::InvalidHeader {
                    file_type: FileType::new("PE32"),
                    detail: format!("unknown optional header magic: 0x{opt_magic:04X}"),
                });
            }
        };

        Ok(Some(ProbeOutcome {
            candidate: strong_deferred(name),
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::probe::FormatProbe;
    use diec_core::format::FormatStrength;
    use diec_core::input::{ByteRange, ByteSource, ByteView, MemorySource};

    fn view_of<'a>(src: &'a MemorySource<'a>) -> ByteView<'a> {
        ByteView::new(src, ByteRange::new(0, src.len()).unwrap()).unwrap()
    }

    /// Build a minimal PE32 image with the given optional header magic.
    fn build_minimal_pe(opt_magic: u16) -> Vec<u8> {
        let mut buf = vec![0u8; 256];
        // MZ magic
        buf[0] = 0x4D;
        buf[1] = 0x5A;
        // e_lfanew at 0x3C -> points to offset 0x80
        let e_lfanew: u32 = 0x80;
        buf[0x3C..0x40].copy_from_slice(&e_lfanew.to_le_bytes());
        // PE signature at 0x80
        buf[0x80..0x84].copy_from_slice(&PE_SIGNATURE);
        // Optional header magic at 0x80 + 24 = 0x98
        buf[0x98..0x9A].copy_from_slice(&opt_magic.to_le_bytes());
        buf
    }

    #[test]
    fn pe32_matches() {
        let data = build_minimal_pe(PE32_MAGIC);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PeProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "PE32");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
        assert!(outcome.candidate.deferred_parse);
    }

    #[test]
    fn pe64_matches() {
        let data = build_minimal_pe(PE64_MAGIC);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PeProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "PE64");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn non_pe_does_not_match() {
        let data = [0x7Fu8, 0x45, 0x4C, 0x46, 0x02, 0x01, 0x01, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PeProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn mz_without_pe_sig_does_not_match() {
        let mut buf = vec![0u8; 128];
        buf[0] = 0x4D;
        buf[1] = 0x5A;
        // e_lfanew points to offset 0x40, but no PE sig there
        buf[0x3C..0x40].copy_from_slice(&0x40u32.to_le_bytes());
        let src = MemorySource::new(&buf);
        let view = view_of(&src);
        let probe = PeProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn too_short_does_not_match() {
        let data = [0x4Du8, 0x5A, 0x90, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PeProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn unknown_opt_magic_returns_error() {
        let data = build_minimal_pe(0xABCD);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PeProbe;
        let err = probe.probe(&view).unwrap_err();
        assert!(matches!(err, ProbeError::InvalidHeader { .. }));
    }

    #[test]
    fn e_lfanew_pointing_outside_file_does_not_match() {
        let mut buf = vec![0u8; 256];
        buf[0] = 0x4D;
        buf[1] = 0x5A;
        // e_lfanew = u32::MAX -> points way outside the file
        buf[0x3C..0x40].copy_from_slice(&u32::MAX.to_le_bytes());
        let src = MemorySource::new(&buf);
        let view = view_of(&src);
        let probe = PeProbe;
        // Not a valid PE since e_lfanew points outside the file.
        assert!(probe.probe(&view).unwrap().is_none());
    }
}
