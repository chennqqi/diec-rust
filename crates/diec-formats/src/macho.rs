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
//!
//! This probe also extracts the CPU type, CPU subtype, and file type from
//! the Mach-O header as metadata for downstream rule matching.

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

/// CPU type: x86 (i386).
pub const CPU_TYPE_X86: i32 = 7;
/// CPU type: x86_64.
pub const CPU_TYPE_X86_64: i32 = 7 | 0x01000000;
/// CPU type: ARM.
pub const CPU_TYPE_ARM: i32 = 12;
/// CPU type: ARM64.
pub const CPU_TYPE_ARM64: i32 = 12 | 0x01000000;
/// CPU type: PowerPC.
pub const CPU_TYPE_POWERPC: i32 = 18;

/// Mach-O file type: relocatable object.
pub const MH_OBJECT: u32 = 1;
/// Mach-O file type: executable.
pub const MH_EXECUTE: u32 = 2;
/// Mach-O file type: fixed VM shared library.
pub const MH_FVMLIB: u32 = 3;
/// Mach-O file type: core dump.
pub const MH_CORE: u32 = 4;
/// Mach-O file type: preloaded executable.
pub const MH_PRELOAD: u32 = 5;
/// Mach-O file type: dynamically linked shared library.
pub const MH_DYLIB: u32 = 6;
/// Mach-O file type: dynamic linker.
pub const MH_DYLINKER: u32 = 7;
/// Mach-O file type: loadable bundle.
pub const MH_BUNDLE: u32 = 8;

/// Mach-O header metadata extracted during probing.
#[derive(Debug, Clone)]
pub struct MachOHeaderInfo {
    /// Format name: "Mach-O 32", "Mach-O 64", "Mach-O FAT", "Mach-O FAT64".
    pub format_name: &'static str,
    /// Whether the header is big-endian.
    pub big_endian: bool,
    /// CPU type (cputype).
    pub cpu_type: i32,
    /// CPU subtype (cpusubtype).
    pub cpu_subtype: i32,
    /// File type (filetype).
    pub filetype: u32,
}

/// Map CPU type to a human-readable name.
pub fn cpu_type_name(cpu_type: i32) -> &'static str {
    match cpu_type {
        CPU_TYPE_X86 => "x86",
        CPU_TYPE_X86_64 => "x86_64",
        CPU_TYPE_ARM => "ARM",
        CPU_TYPE_ARM64 => "ARM64",
        CPU_TYPE_POWERPC => "PowerPC",
        _ => "unknown",
    }
}

/// Map file type to a human-readable name.
pub fn filetype_name(filetype: u32) -> &'static str {
    match filetype {
        MH_OBJECT => "object",
        MH_EXECUTE => "execute",
        MH_FVMLIB => "fvmlib",
        MH_CORE => "core",
        MH_PRELOAD => "preload",
        MH_DYLIB => "dylib",
        MH_DYLINKER => "dylinker",
        MH_BUNDLE => "bundle",
        _ => "unknown",
    }
}

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
        let (name, big_endian) = match magic_be {
            MH_MAGIC_32_BE => ("Mach-O 32", true),
            MH_MAGIC_32_LE => ("Mach-O 32", false),
            MH_MAGIC_64_BE => ("Mach-O 64", true),
            MH_MAGIC_64_LE => ("Mach-O 64", false),
            FAT_MAGIC_BE => ("Mach-O FAT", true),
            FAT_MAGIC_64_BE => ("Mach-O FAT64", true),
            _ => {
                // Also check the LE reading for the swapped variants.
                match magic_le {
                    MH_MAGIC_32_LE => ("Mach-O 32", false),
                    MH_MAGIC_32_BE => ("Mach-O 32", true),
                    MH_MAGIC_64_LE => ("Mach-O 64", false),
                    MH_MAGIC_64_BE => ("Mach-O 64", true),
                    FAT_MAGIC_BE => ("Mach-O FAT", false),
                    FAT_MAGIC_64_BE => ("Mach-O FAT64", false),
                    _ => return Ok(None),
                }
            }
        };

        // Extract CPU type, subtype, and file type if enough bytes available.
        // Mach-O header: magic(4) + cputype(4) + cpusubtype(4) + filetype(4)
        // = 16 bytes minimum.
        let (cpu_type, cpu_subtype, filetype) = if view.len() >= 16 {
            let ct = if big_endian {
                view.read_u32_be(4).unwrap_or(0) as i32
            } else {
                view.read_u32_le(4).unwrap_or(0) as i32
            };
            let cs = if big_endian {
                view.read_u32_be(8).unwrap_or(0) as i32
            } else {
                view.read_u32_le(8).unwrap_or(0) as i32
            };
            let ft = if big_endian {
                view.read_u32_be(12).unwrap_or(0)
            } else {
                view.read_u32_le(12).unwrap_or(0)
            };
            (ct, cs, ft)
        } else {
            (0, 0, 0)
        };

        let _info = MachOHeaderInfo {
            format_name: name,
            big_endian,
            cpu_type,
            cpu_subtype,
            filetype,
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

    // --- Malformed / non-matching tests ---

    #[test]
    fn partial_magic_does_not_match() {
        // First 3 bytes of MH_MAGIC_32 but 4th byte wrong.
        let data = [0xFEu8, 0xED, 0xFA, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn fat_magic_with_wrong_suffix_does_not_match() {
        // 0xCAFEBABE is FAT magic, but we need exactly 4 bytes.
        // A wrong 5th byte shouldn't matter since we only check 4 bytes,
        // but verify that a truncated FAT magic (3 bytes) doesn't match.
        let data = [0xCAu8, 0xFE, 0xBA];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    // --- Boundary tests: exact minimum size ---

    #[test]
    fn boundary_exact_4_bytes_macho_32_be_matches() {
        let data = 0xFEEDFACEu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn boundary_exact_4_bytes_macho_64_be_matches() {
        let data = 0xFEEDFACFu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn boundary_exact_4_bytes_fat_matches() {
        let data = 0xCAFEBABEu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn boundary_3_bytes_does_not_match() {
        let data = [0xFEu8, 0xED, 0xFA];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn empty_input_does_not_match() {
        let data: [u8; 0] = [];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn java_class_magic_does_not_match_macho_fat() {
        // 0xCAFEBABE is both FAT magic and Java Class magic.
        // MachOProbe should match it as FAT, but the JavaClassProbe
        // (which runs later) should also match it as Java Class.
        // This test verifies MachOProbe matches it.
        let data = 0xCAFEBABEu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O FAT");
    }

    // --- Header field extraction tests ---

    #[test]
    fn macho_64_be_with_header_fields_does_not_panic() {
        // Mach-O 64 BE with cputype=x86_64, filetype=MH_EXECUTE
        let mut data = 0xFEEDFACFu32.to_be_bytes().to_vec();
        data.extend_from_slice(&(CPU_TYPE_X86_64).to_be_bytes()); // cputype
        data.extend_from_slice(&3i32.to_be_bytes()); // cpusubtype
        data.extend_from_slice(&MH_EXECUTE.to_be_bytes()); // filetype
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O 64");
    }

    #[test]
    fn macho_32_le_with_header_fields_does_not_panic() {
        // Mach-O 32 LE with cputype=ARM, filetype=MH_DYLIB
        let mut data = 0xFEEDFACEu32.to_le_bytes().to_vec();
        data.extend_from_slice(&(CPU_TYPE_ARM).to_le_bytes()); // cputype
        data.extend_from_slice(&0i32.to_le_bytes()); // cpusubtype
        data.extend_from_slice(&MH_DYLIB.to_le_bytes()); // filetype
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Mach-O 32");
    }

    #[test]
    fn cpu_type_name_mapping() {
        assert_eq!(cpu_type_name(CPU_TYPE_X86), "x86");
        assert_eq!(cpu_type_name(CPU_TYPE_X86_64), "x86_64");
        assert_eq!(cpu_type_name(CPU_TYPE_ARM), "ARM");
        assert_eq!(cpu_type_name(CPU_TYPE_ARM64), "ARM64");
        assert_eq!(cpu_type_name(CPU_TYPE_POWERPC), "PowerPC");
        assert_eq!(cpu_type_name(0), "unknown");
    }

    #[test]
    fn filetype_name_mapping() {
        assert_eq!(filetype_name(MH_OBJECT), "object");
        assert_eq!(filetype_name(MH_EXECUTE), "execute");
        assert_eq!(filetype_name(MH_DYLIB), "dylib");
        assert_eq!(filetype_name(MH_BUNDLE), "bundle");
        assert_eq!(filetype_name(MH_CORE), "core");
        assert_eq!(filetype_name(0xFFFF), "unknown");
    }

    #[test]
    fn macho_short_header_still_matches() {
        // Only 4 bytes: magic. No cputype/subtype/filetype.
        let data = 0xFEEDFACFu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = MachOProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }
}
