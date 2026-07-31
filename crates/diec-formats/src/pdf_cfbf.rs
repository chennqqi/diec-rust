//! PDF and CFBF (Compound File Binary Format) probes (CAP-DISPATCH-006).
//!
//! - PDF: magic `%PDF-` (5 bytes).
//! - CFBF: Compound File Binary Format (OLE2). Magic at offset 0 is
//!   `D0 CF 11 E0 A1 B1 1A E1` (8 bytes).

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// PDF format probe.
#[derive(Debug, Default)]
pub struct PdfProbe;

/// CFBF (Compound File Binary Format / OLE2) probe.
#[derive(Debug, Default)]
pub struct CfbfProbe;

/// PDF magic: `%PDF-`.
const PDF_MAGIC: [u8; 5] = [0x25, 0x50, 0x44, 0x46, 0x2D];
/// CFBF magic (8 bytes).
const CFBF_MAGIC: [u8; 8] = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];

impl FormatProbe for PdfProbe {
    fn file_type(&self) -> FileType {
        FileType::new("PDF")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 5 {
            return Ok(None);
        }
        let mut magic = [0u8; 5];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("PDF"),
                cause,
            })?;
        if magic == PDF_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("PDF"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for CfbfProbe {
    fn file_type(&self) -> FileType {
        FileType::new("CFBF")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 8 {
            return Ok(None);
        }
        let mut magic = [0u8; 8];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("CFBF"),
                cause,
            })?;
        if magic == CFBF_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("CFBF"),
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
    fn pdf_matches() {
        let data = b"%PDF-1.4\nrest of file";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = PdfProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "PDF");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn pdf_too_short_does_not_match() {
        let data = b"%PDF";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = PdfProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn pdf_non_pdf_does_not_match() {
        let data = b"Hello World!";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = PdfProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn cfbf_matches() {
        let mut data = CFBF_MAGIC.to_vec();
        data.extend_from_slice(&[0u8; 24]);
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = CfbfProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "CFBF");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn cfbf_too_short_does_not_match() {
        let data = &CFBF_MAGIC[..4];
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = CfbfProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn cfbf_non_cfbf_does_not_match() {
        let data = [0xFFu8; 16];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = CfbfProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }
}
