//! DEX, Java Class and PYC format probes (CAP-DISPATCH-005).
//!
//! - DEX: magic `dex\n035\0` (or `dex\n036\0`, `dex\n037\0`, `dex\n038\0`,
//!   `dex\n039\0`, `dex\n040\0`).
//! - Java Class: magic `0xCAFEBABE` (big-endian). Note: Mach-O FAT also uses
//!   `0xCAFEBABE`; the Mach-O probe runs before this one in the dispatch
//!   order, so FAT binaries are identified first. A Java class file has
//!   major/minor version fields after the magic that a FAT binary does not.
//! - PYC: Python compiled bytecode. Magic varies by version; the first 4
//!   bytes are a version-specific magic number. We use a heuristic: the magic
//!   is a 16-bit field followed by a `\r\n` (0x0D 0x0A) at bytes 2-3. This
//!   pattern is shared by all CPython PYC formats from 2.0 onward.

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// DEX format probe.
#[derive(Debug, Default)]
pub struct DexProbe;

/// Java Class format probe.
#[derive(Debug, Default)]
pub struct JavaClassProbe;

/// PYC (Python compiled) format probe.
#[derive(Debug, Default)]
pub struct PycProbe;

/// DEX magic prefix: `dex\n`.
const DEX_MAGIC_PREFIX: [u8; 4] = [0x64, 0x65, 0x78, 0x0A];
/// DEX magic is 8 bytes: `dex\n035\0` etc. The version is 3 ASCII digits
/// at offset 4-6, followed by `\0` at offset 7.
const DEX_MAGIC_LEN: u64 = 8;
/// Java Class magic: `0xCAFEBABE` big-endian.
const JAVA_CLASS_MAGIC: u32 = 0xCAFEBABE;

impl FormatProbe for DexProbe {
    fn file_type(&self) -> FileType {
        FileType::new("DEX")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < DEX_MAGIC_LEN {
            return Ok(None);
        }
        let mut magic = [0u8; 4];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("DEX"),
                cause,
            })?;
        if magic != DEX_MAGIC_PREFIX {
            return Ok(None);
        }
        // Verify version digits at offset 4-6 are ASCII digits and byte 7 is 0.
        let d4 = view.read_u8(4).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("DEX"),
            cause,
        })?;
        let d5 = view.read_u8(5).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("DEX"),
            cause,
        })?;
        let d6 = view.read_u8(6).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("DEX"),
            cause,
        })?;
        let d7 = view.read_u8(7).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("DEX"),
            cause,
        })?;
        if d4.is_ascii_digit() && d5.is_ascii_digit() && d6.is_ascii_digit() && d7 == 0 {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("DEX"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for JavaClassProbe {
    fn file_type(&self) -> FileType {
        FileType::new("Java Class")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // Java class needs at least 8 bytes: 4 magic + 2 minor_version + 2 major_version.
        if view.len() < 8 {
            return Ok(None);
        }
        let magic = view.read_u32_be(0).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("Java Class"),
            cause,
        })?;
        if magic != JAVA_CLASS_MAGIC {
            return Ok(None);
        }
        // Read major version to validate. Java class major versions range
        // from 45 (Java 1) upward. FAT binaries have a different structure
        // after the magic (nfat_arch count), so this helps distinguish.
        let major = view.read_u16_be(6).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("Java Class"),
            cause,
        })?;
        if major >= 45 {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("Java Class"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for PycProbe {
    fn file_type(&self) -> FileType {
        FileType::new("PYC")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // PYC needs at least 4 bytes for the magic number.
        if view.len() < 4 {
            return Ok(None);
        }
        // CPython PYC magic: 2-byte version-specific magic + 0x0D 0x0A (\r\n).
        // This pattern is shared by all CPython 2.0+ PYC formats.
        let m0 = view.read_u8(0).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("PYC"),
            cause,
        })?;
        let m1 = view.read_u8(1).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("PYC"),
            cause,
        })?;
        let m2 = view.read_u8(2).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("PYC"),
            cause,
        })?;
        let m3 = view.read_u8(3).map_err(|cause| ProbeError::Truncated {
            file_type: FileType::new("PYC"),
            cause,
        })?;
        // Check for \r\n at bytes 2-3.
        if m2 == 0x0D && m3 == 0x0A {
            // The first two bytes are a version-specific magic. We accept
            // any non-zero value as a weak heuristic. A more precise check
            // would enumerate known magic numbers, but that is deferred.
            if m0 != 0 || m1 != 0 {
                Ok(Some(ProbeOutcome {
                    candidate: strong_deferred("PYC"),
                }))
            } else {
                Ok(None)
            }
        } else {
            Ok(None)
        }
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
    fn dex_matches() {
        let data = b"dex\n035\0extra bytes here";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = DexProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "DEX");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn dex_other_versions_match() {
        for ver in &["036", "037", "038", "039", "040"] {
            let mut data = vec![0x64, 0x65, 0x78, 0x0A];
            data.extend_from_slice(ver.as_bytes());
            data.push(0);
            data.extend_from_slice(b"more");
            let src = MemorySource::new(&data);
            let view = view_of(&src);
            let probe = DexProbe;
            assert!(probe.probe(&view).unwrap().is_some(), "version {ver}");
        }
    }

    #[test]
    fn dex_bad_version_does_not_match() {
        let data = b"dex\nabc\0extra";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = DexProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn dex_too_short_does_not_match() {
        let data = b"dex\n";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = DexProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn java_class_matches() {
        // magic + minor_version(0) + major_version(52 = Java 8)
        let mut data = 0xCAFEBABEu32.to_be_bytes().to_vec();
        data.extend_from_slice(&0u16.to_be_bytes()); // minor
        data.extend_from_slice(&52u16.to_be_bytes()); // major
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = JavaClassProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "Java Class");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn java_class_too_low_major_does_not_match() {
        let mut data = 0xCAFEBABEu32.to_be_bytes().to_vec();
        data.extend_from_slice(&0u16.to_be_bytes());
        data.extend_from_slice(&44u16.to_be_bytes()); // major < 45
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = JavaClassProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn java_class_too_short_does_not_match() {
        let data = 0xCAFEBABEu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = JavaClassProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn pyc_matches() {
        // Python 3.8 PYC magic: 0x550D 0x0A -> bytes [0x55, 0x0D, 0x0D, 0x0A]
        // Actually the magic is [0x55, 0x0D, 0x0D, 0x0A] but the \r\n is at
        // bytes 2-3. Let's use a known magic: 0x420D 0x0A = [0x42, 0x0D, 0x0D, 0x0A]
        let data = [0x42u8, 0x0D, 0x0D, 0x0A, 0x00, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PycProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "PYC");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn pyc_no_crlf_does_not_match() {
        let data = [0x42u8, 0x0D, 0x0A, 0x0D];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PycProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn pyc_zero_magic_does_not_match() {
        let data = [0x00u8, 0x00, 0x0D, 0x0A];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PycProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn pyc_too_short_does_not_match() {
        let data = [0x42u8, 0x0D, 0x0D];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PycProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }
}
