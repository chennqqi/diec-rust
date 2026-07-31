//! ELF (Executable and Linkable Format) probe.
//!
//! ELF files start with the magic `\x7FELF`. The class byte at offset 4
//! distinguishes ELF32 (1) from ELF64 (2). This probe reads only the first
//! 5 bytes to identify the format; full section/table parsing is deferred.

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// ELF format probe.
#[derive(Debug, Default)]
pub struct ElfProbe;

/// ELF magic: `\x7FELF`.
const ELF_MAGIC: [u8; 4] = [0x7F, 0x45, 0x4C, 0x46];
/// Offset of the class byte (EI_CLASS).
const EI_CLASS_OFFSET: u64 = 4;
/// ELFCLASS32.
const ELFCLASS32: u8 = 1;
/// ELFCLASS64.
const ELFCLASS64: u8 = 2;

impl FormatProbe for ElfProbe {
    fn file_type(&self) -> FileType {
        FileType::new("ELF")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        // Need at least 5 bytes: 4 magic + 1 class byte.
        if view.len() < 5 {
            return Ok(None);
        }

        // Read and verify ELF magic.
        let mut magic = [0u8; 4];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("ELF"),
                cause,
            })?;
        if magic != ELF_MAGIC {
            return Ok(None);
        }

        // Read class byte to distinguish ELF32 vs ELF64.
        let class = view
            .read_u8(EI_CLASS_OFFSET)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("ELF"),
                cause,
            })?;

        let name = match class {
            ELFCLASS32 => "ELF32",
            ELFCLASS64 => "ELF64",
            _ => {
                return Err(ProbeError::InvalidHeader {
                    file_type: FileType::new("ELF"),
                    detail: format!("unknown ELF class: {class}"),
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

    #[test]
    fn elf32_matches() {
        let mut data = vec![0x7Fu8, 0x45, 0x4C, 0x46, ELFCLASS32];
        data.extend_from_slice(&[0x01, 0x01, 0x00, 0x00]);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ElfProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "ELF32");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
        assert!(outcome.candidate.deferred_parse);
    }

    #[test]
    fn elf64_matches() {
        let mut data = vec![0x7Fu8, 0x45, 0x4C, 0x46, ELFCLASS64];
        data.extend_from_slice(&[0x02, 0x01, 0x00, 0x00]);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ElfProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "ELF64");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn non_elf_does_not_match() {
        let data = [0x4Du8, 0x5A, 0x90, 0x00, 0x01];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ElfProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn too_short_does_not_match() {
        let data = [0x7Fu8, 0x45, 0x4C];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ElfProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn unknown_class_returns_error() {
        let data = [0x7Fu8, 0x45, 0x4C, 0x46, 0x03];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = ElfProbe;
        let err = probe.probe(&view).unwrap_err();
        assert!(matches!(err, ProbeError::InvalidHeader { .. }));
    }
}
