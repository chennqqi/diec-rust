//! Archive format probes (CAP-DISPATCH-004).
//!
//! Archive detection by magic number:
//! - ZIP/JAR/APK/NPM: local file header magic `PK\x03\x04`. ZIP is the base
//!   format; JAR/APK/NPM are ZIP-based but distinguished by content, not
//!   magic. This probe reports ZIP; APK/JAR/NPM identification is deferred
//!   to content-level analysis.
//! - RAR4: magic `Rar!\x1A\x07\x00`.
//! - RAR5: magic `Rar!\x1A\x07\x01\x00`.
//! - 7Z: magic `7z\xBC\xAF\x27\x1C`.
//! - GZIP: magic `\x1F\x8B`.
//! - TAR: USTAR magic at offset 257 (`ustar`). POSIX/GNU tar use this.
//!   Old-format tar (without ustar) is not detected by magic alone.
//! - ISO9660: magic `CD001` at sector 16 (offset 0x8000, 32768). This
//!   requires reading at a large offset, which is supported by ByteView.
//! - CAB: magic `MSCF` at offset 0.

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// ZIP format probe (base for JAR/APK/NPM).
#[derive(Debug, Default)]
pub struct ZipProbe;

/// RAR format probe (detects RAR4 and RAR5).
#[derive(Debug, Default)]
pub struct RarProbe;

/// 7Z format probe.
#[derive(Debug, Default)]
pub struct SevenZProbe;

/// GZIP format probe.
#[derive(Debug, Default)]
pub struct GzipProbe;

/// TAR format probe (USTAR).
#[derive(Debug, Default)]
pub struct TarProbe;

/// ISO9660 format probe.
#[derive(Debug, Default)]
pub struct Iso9660Probe;

/// CAB format probe.
#[derive(Debug, Default)]
pub struct CabProbe;

/// ZIP local file header magic: `PK\x03\x04`.
const ZIP_MAGIC: [u8; 4] = [0x50, 0x4B, 0x03, 0x04];
/// RAR4 magic: `Rar!\x1A\x07\x00`.
const RAR4_MAGIC: [u8; 7] = [0x52, 0x61, 0x72, 0x21, 0x1A, 0x07, 0x00];
/// RAR5 magic: `Rar!\x1A\x07\x01\x00`.
const RAR5_MAGIC: [u8; 8] = [0x52, 0x61, 0x72, 0x21, 0x1A, 0x07, 0x01, 0x00];
/// 7Z magic: `7z\xBC\xAF\x27\x1C`.
const SEVENZ_MAGIC: [u8; 6] = [0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C];
/// GZIP magic: `\x1F\x8B`.
const GZIP_MAGIC: [u8; 2] = [0x1F, 0x8B];
/// USTAR magic at offset 257 in tar header.
const USTAR_OFFSET: u64 = 257;
/// USTAR magic: `ustar`.
const USTAR_MAGIC: [u8; 5] = [0x75, 0x73, 0x74, 0x61, 0x72];
/// ISO9660 magic at sector 16 (offset 32768).
const ISO9660_OFFSET: u64 = 0x8000;
/// ISO9660 magic: `CD001` at offset 1 within the sector.
const ISO9660_MAGIC_OFFSET: u64 = 1;
/// ISO9660 magic: `CD001`.
const ISO9660_MAGIC: [u8; 5] = [0x43, 0x44, 0x30, 0x30, 0x31];
/// CAB magic: `MSCF`.
const CAB_MAGIC: [u8; 4] = [0x4D, 0x53, 0x43, 0x46];

impl FormatProbe for ZipProbe {
    fn file_type(&self) -> FileType {
        FileType::new("ZIP")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 4 {
            return Ok(None);
        }
        let mut magic = [0u8; 4];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("ZIP"),
                cause,
            })?;
        if magic == ZIP_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("ZIP"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for RarProbe {
    fn file_type(&self) -> FileType {
        FileType::new("RAR")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // RAR5 needs 8 bytes, RAR4 needs 7.
        if view.len() < 8 {
            // Check RAR4 with 7 bytes.
            if view.len() >= 7 {
                let mut magic = [0u8; 7];
                view.read_exact_at(0, &mut magic)
                    .map_err(|cause| ProbeError::Truncated {
                        file_type: FileType::new("RAR"),
                        cause,
                    })?;
                if magic == RAR4_MAGIC {
                    return Ok(Some(ProbeOutcome {
                        candidate: strong_deferred("RAR"),
                    }));
                }
            }
            return Ok(None);
        }
        let mut magic8 = [0u8; 8];
        view.read_exact_at(0, &mut magic8)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("RAR"),
                cause,
            })?;
        if magic8 == RAR5_MAGIC {
            return Ok(Some(ProbeOutcome {
                candidate: strong_deferred("RAR"),
            }));
        }
        // Check RAR4 (first 7 bytes).
        if magic8[..7] == RAR4_MAGIC {
            return Ok(Some(ProbeOutcome {
                candidate: strong_deferred("RAR"),
            }));
        }
        Ok(None)
    }
}

impl FormatProbe for SevenZProbe {
    fn file_type(&self) -> FileType {
        FileType::new("7Z")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 6 {
            return Ok(None);
        }
        let mut magic = [0u8; 6];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("7Z"),
                cause,
            })?;
        if magic == SEVENZ_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("7Z"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for GzipProbe {
    fn file_type(&self) -> FileType {
        FileType::new("GZIP")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 2 {
            return Ok(None);
        }
        let mut magic = [0u8; 2];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("GZIP"),
                cause,
            })?;
        if magic == GZIP_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("GZIP"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for TarProbe {
    fn file_type(&self) -> FileType {
        FileType::new("TAR")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // USTAR magic is at offset 257, need at least 262 bytes.
        if view.len() < USTAR_OFFSET + 5 {
            return Ok(None);
        }
        let mut magic = [0u8; 5];
        view.read_exact_at(USTAR_OFFSET, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("TAR"),
                cause,
            })?;
        if magic == USTAR_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("TAR"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for Iso9660Probe {
    fn file_type(&self) -> FileType {
        FileType::new("ISO9660")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // ISO9660 volume descriptor is at sector 16 (offset 0x8000).
        // The magic `CD001` is at offset 1 within the sector.
        let magic_abs = ISO9660_OFFSET + ISO9660_MAGIC_OFFSET;
        if view.len() < magic_abs + 5 {
            return Ok(None);
        }
        let mut magic = [0u8; 5];
        view.read_exact_at(magic_abs, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("ISO9660"),
                cause,
            })?;
        if magic == ISO9660_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("ISO9660"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for CabProbe {
    fn file_type(&self) -> FileType {
        FileType::new("CAB")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 4 {
            return Ok(None);
        }
        let mut magic = [0u8; 4];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("CAB"),
                cause,
            })?;
        if magic == CAB_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("CAB"),
            }))
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
    fn zip_matches() {
        let data = [0x50u8, 0x4B, 0x03, 0x04, 0x14, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ZipProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "ZIP");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn zip_too_short_does_not_match() {
        let data = [0x50u8, 0x4B, 0x03];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ZipProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn rar4_matches() {
        let data = RAR4_MAGIC.to_vec();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = RarProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "RAR");
    }

    #[test]
    fn rar5_matches() {
        let data = RAR5_MAGIC.to_vec();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = RarProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "RAR");
    }

    #[test]
    fn rar_too_short_does_not_match() {
        let data = &RAR4_MAGIC[..5];
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = RarProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn sevenz_matches() {
        let data = SEVENZ_MAGIC.to_vec();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = SevenZProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "7Z");
    }

    #[test]
    fn gzip_matches() {
        let data = [0x1Fu8, 0x8B, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = GzipProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "GZIP");
    }

    #[test]
    fn tar_matches() {
        // Minimal tar: 512-byte header with ustar magic at offset 257.
        let mut data = vec![0u8; 512];
        data[257..262].copy_from_slice(&USTAR_MAGIC);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = TarProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "TAR");
    }

    #[test]
    fn tar_too_short_does_not_match() {
        let data = vec![0u8; 256];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = TarProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn iso9660_matches() {
        // Sector 16 starts at 0x8000, magic CD001 at offset 1.
        let mut data = vec![0u8; 0x8000 + 6];
        data[0x8000 + 1..0x8000 + 6].copy_from_slice(&ISO9660_MAGIC);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = Iso9660Probe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "ISO9660");
    }

    #[test]
    fn iso9660_too_short_does_not_match() {
        let data = vec![0u8; 0x8000];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = Iso9660Probe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn cab_matches() {
        let data = [0x4Du8, 0x53, 0x43, 0x46, 0x00, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = CabProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "CAB");
    }

    // --- Malformed / non-matching tests ---

    #[test]
    fn zip_non_zip_does_not_match() {
        let data = [0x50u8, 0x4B, 0x05, 0x06]; // empty archive sig, not local file header
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ZipProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn rar_non_rar_does_not_match() {
        let data = [0x52u8, 0x61, 0x72, 0x21, 0x00, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = RarProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn sevenz_non_sevenz_does_not_match() {
        let data = [0x37u8, 0x7A, 0x00, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = SevenZProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn sevenz_too_short_does_not_match() {
        let data = &SEVENZ_MAGIC[..5];
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = SevenZProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn gzip_non_gzip_does_not_match() {
        let data = [0x1Fu8, 0x00, 0x08, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = GzipProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn gzip_too_short_does_not_match() {
        let data = [0x1Fu8];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = GzipProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn tar_non_ustar_does_not_match() {
        let mut data = vec![0u8; 512];
        // "gnuta" is not "ustar"
        data[257..262].copy_from_slice(b"gnuta");
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = TarProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn tar_boundary_exact_262_bytes_matches() {
        // Exactly enough bytes for ustar magic at offset 257 (257 + 5 = 262).
        let mut data = vec![0u8; 262];
        data[257..262].copy_from_slice(&USTAR_MAGIC);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = TarProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn tar_boundary_261_bytes_does_not_match() {
        // One byte short of the ustar magic end.
        let mut data = vec![0u8; 261];
        data[257..261].copy_from_slice(&USTAR_MAGIC[..4]);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = TarProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn iso9660_non_iso_does_not_match() {
        let mut data = vec![0u8; 0x8006];
        data[0x8001..0x8006].copy_from_slice(b"BEER0");
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = Iso9660Probe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn iso9660_boundary_exact_magic_end_matches() {
        // Exactly enough bytes: 0x8000 + 1 + 5 = 0x8006.
        let mut data = vec![0u8; 0x8006];
        data[0x8001..0x8006].copy_from_slice(&ISO9660_MAGIC);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = Iso9660Probe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn iso9660_boundary_one_byte_short_does_not_match() {
        let mut data = vec![0u8; 0x8005];
        data[0x8001..0x8005].copy_from_slice(&ISO9660_MAGIC[..4]);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = Iso9660Probe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn cab_non_cab_does_not_match() {
        // MSCE instead of MSCF.
        let data = [0x4Du8, 0x53, 0x43, 0x45, 0x00, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = CabProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn cab_too_short_does_not_match() {
        let data = [0x4Du8, 0x53, 0x43];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = CabProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    // --- Boundary tests: exact minimum size ---

    #[test]
    fn zip_boundary_exact_4_bytes_matches() {
        let data = ZIP_MAGIC;
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ZipProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn zip_boundary_3_bytes_does_not_match() {
        let data = &ZIP_MAGIC[..3];
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = ZipProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn rar4_boundary_exact_7_bytes_matches() {
        let data = &RAR4_MAGIC;
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = RarProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn rar5_boundary_exact_8_bytes_matches() {
        let data = &RAR5_MAGIC;
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = RarProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn sevenz_boundary_exact_6_bytes_matches() {
        let data = &SEVENZ_MAGIC;
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = SevenZProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn gzip_boundary_exact_2_bytes_matches() {
        let data = &GZIP_MAGIC;
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = GzipProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn cab_boundary_exact_4_bytes_matches() {
        let data = &CAB_MAGIC;
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = CabProbe;
        assert!(probe.probe(&view).unwrap().is_some());
    }

    #[test]
    fn empty_input_does_not_match_any_archive() {
        let data: [u8; 0] = [];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        assert!(ZipProbe.probe(&view).unwrap().is_none());
        assert!(RarProbe.probe(&view).unwrap().is_none());
        assert!(SevenZProbe.probe(&view).unwrap().is_none());
        assert!(GzipProbe.probe(&view).unwrap().is_none());
        assert!(TarProbe.probe(&view).unwrap().is_none());
        assert!(Iso9660Probe.probe(&view).unwrap().is_none());
        assert!(CabProbe.probe(&view).unwrap().is_none());
    }
}
