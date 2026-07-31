//! Image format probes (CAP-DISPATCH-007).
//!
//! - JPEG: magic `\xFF\xD8\xFF`.
//! - PNG: magic `\x89PNG\r\n\x1A\n` (8 bytes).

use crate::probe::{FormatProbe, ProbeError, ProbeOutcome, strong_deferred};
use diec_core::format::FileType;
use diec_core::input::ByteView;

/// JPEG format probe.
#[derive(Debug, Default)]
pub struct JpegProbe;

/// PNG format probe.
#[derive(Debug, Default)]
pub struct PngProbe;

/// JPEG magic: `\xFF\xD8\xFF`.
const JPEG_MAGIC: [u8; 3] = [0xFF, 0xD8, 0xFF];
/// PNG magic: `\x89PNG\r\n\x1A\n`.
const PNG_MAGIC: [u8; 8] = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];

impl FormatProbe for JpegProbe {
    fn file_type(&self) -> FileType {
        FileType::new("JPEG")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 3 {
            return Ok(None);
        }
        let mut magic = [0u8; 3];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("JPEG"),
                cause,
            })?;
        if magic == JPEG_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("JPEG"),
            }))
        } else {
            Ok(None)
        }
    }
}

impl FormatProbe for PngProbe {
    fn file_type(&self) -> FileType {
        FileType::new("PNG")
    }

    fn probe(&self, view: &ByteView<'_>) -> Result<Option<ProbeOutcome>, ProbeError> {
        if view.len() < 8 {
            return Ok(None);
        }
        let mut magic = [0u8; 8];
        view.read_exact_at(0, &mut magic)
            .map_err(|cause| ProbeError::Truncated {
                file_type: FileType::new("PNG"),
                cause,
            })?;
        if magic == PNG_MAGIC {
            Ok(Some(ProbeOutcome {
                candidate: strong_deferred("PNG"),
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
    fn jpeg_matches() {
        let data = [0xFFu8, 0xD8, 0xFF, 0xE0, 0x00, 0x10];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = JpegProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "JPEG");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn jpeg_too_short_does_not_match() {
        let data = [0xFFu8, 0xD8];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = JpegProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }

    #[test]
    fn png_matches() {
        let data = PNG_MAGIC.to_vec();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let probe = PngProbe;
        let outcome = probe.probe(&view).unwrap().unwrap();
        assert_eq!(outcome.candidate.file_type.name, "PNG");
        assert_eq!(outcome.candidate.strength, FormatStrength::Strong);
    }

    #[test]
    fn png_too_short_does_not_match() {
        let data = &PNG_MAGIC[..4];
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let probe = PngProbe;
        assert!(probe.probe(&view).unwrap().is_none());
    }
}
