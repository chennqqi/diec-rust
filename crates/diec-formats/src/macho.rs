//! Mach-O format probe.
//!
//! Mach-O files start with a magic number that encodes both the architecture
//! (32 vs 64 bit) and the endianness. FAT (universal) binaries start with
//! `0xCAFEBABE` (big-endian) or `0xBEBAFECA` (little-endian, FAT_64).
//!
//! Magic numbers:
//! - `0xFEEDFACE`: Mach-O 32, big-endian
//! - `0xCEFAEDFE`: Mach-O 32, little-endian (swapped)
//! - `0xFEEDFACF`: Mach-O 64, big-endian
//! - `0xCFFAEDFE`: Mach-O 64, little-endian (swapped)
//! - `0xCAFEBABE`: FAT (universal) binary
//! - `0xBEBAFECA`: FAT_64 binary
//!
//! Note: `0xCAFEBABE` is also the Java class file magic. The Mach-O FAT probe
//! runs before the Java class probe in the dispatch order, so FAT binaries
//! are identified correctly. This is consistent with upstream behavior.

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// Mach-O format probe.
#[derive(Debug, Default)]
pub struct MachOProbe;

// Mach-O magic numbers (as read in big-endian from the first 4 bytes).
const MH_MAGIC_32_BE: u32 = 0xFEEDFACE;
const MH_MAGIC_32_LE: u32 = 0xCEFAEDFE;
const MH_MAGIC_64_BE: u32 = 0xFEEDFACF;
const MH_MAGIC_64_LE: u32 = 0xCFFAEDFE;
const FAT_MAGIC_BE: u32 = 0xCAFEBABE;
const FAT_MAGIC_64_BE: u32 = 0xCAFEBABF;

impl FormatProbe for MachOProbe {
    fn file_type(&self) -> FileType {
        FileType::new("Mach-O")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // Need at least 4 bytes for the magic.
        if view.len() < 4 {
            return Ok(None);
        }

        // Read the magic as big-endian first. Mach-O magics are defined in
        // big-endian terms; the "swapped" variants are the little-endian
        // encodings of the same values.
        let magic_be = view.read_u32_be(0).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("Mach-O"),
            cause,
        })?;
        let magic_le = view.read_u32_le(0).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("Mach-O"),
            cause,
        })?;

        // Check against all known Mach-O magics. We compare both BE and LE
        // readings because the magic itself encodes endianness.
        let name = match magic_be {
            MH_MAGIC_32_BE | MH_MAGIC_32_LE => "Mach-O 32",
            MH_MAGIC_64_BE | MH_MAGIC_64_LE => "Mach-O 64",
            FAT_MAGIC_BE => "Mach-O FAT",
            FAT_MAGIC_64_BE => "Mach-O FAT64",
            _ => {
                // Also check the LE reading for the swapped variants.
                match magic_le {
                    MH_MAGIC_32_LE | MH_MAGIC_32_BE => "Mach-O 32",
                    MH_MAGIC_64_LE | MH_MAGIC_64_BE => "Mach-O 64",
                    FAT_MAGIC_BE => "Mach-O FAT",
                    FAT_MAGIC_64_BE => "Mach-O FAT64",
                    _ => return Ok(None),
                }
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

    #[test]
    fn macho_32_be_matches() {
        let data = 0xFEEDFACEu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O 32");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
        assert!(outcome.candidate.deferred_parse);
    }

    #[test]
    fn macho_32_le_matches() {
        let data = 0xFEEDFACEu32.to_le_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O 32");
    }

    #[test]
    fn macho_64_be_matches() {
        let data = 0xFEEDFACFu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O 64");
    }

    #[test]
    fn macho_64_le_matches() {
        let data = 0xFEEDFACFu32.to_le_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O 64");
    }

    #[test]
    fn fat_matches() {
        let data = 0xCAFEBABEu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O FAT");
    }

    #[test]
    fn fat64_matches() {
        let data = 0xCAFEBABFu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O FAT64");
    }

    #[test]
    fn non_macho_does_not_match() {
        let data = [0x7Fu8, 0x45, 0x4C, 0x46];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn too_short_does_not_match() {
        let data = [0xFEu8, 0xED, 0xFA];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }
}
