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

pub mod archive;
pub mod dex_class_pyc;
pub mod elf;
pub mod image;
pub mod macho;
pub mod msdos;
pub mod pdf_cfbf;
pub mod pe;
pub mod probe;

pub use probe::{FormatProbe, PROBE_TABLE_VERSION, ProbeError, ProbeOutcome, ProbeTable};

/// Placeholder retained for backward compatibility; format modules land in
/// Phase 2.
pub fn placeholder() -> &'static str {
    "diec-formats"
}

#[cfg(test)]
mod tests {
    use super::*;
    use diec_core::format::FormatStrength;
    use diec_core::input::{ByteRange, ByteSource, ByteView, MemorySource};

    fn view_of<'a>(src: &'a MemorySource<'a>) -> ByteView<'a> {
        ByteView::new(src, ByteRange::new(0, src.len()).unwrap()).unwrap()
    }

    #[test]
    fn placeholder_is_reachable() {
        assert_eq!(placeholder(), "diec-formats");
    }

    #[test]
    fn default_table_detects_pe32() {
        let mut buf = vec![0u8; 256];
        // MZ magic
        buf[0] = 0x4D;
        buf[1] = 0x5A;
        // e_lfanew -> 0x80
        buf[0x3C..0x40].copy_from_slice(&0x80u32.to_le_bytes());
        // PE sig
        buf[0x80..0x84].copy_from_slice(&[0x50, 0x45, 0x00, 0x00]);
        // PE32 opt magic at 0x98
        buf[0x98..0x9A].copy_from_slice(&0x010Bu16.to_le_bytes());
        let src = MemorySource::new(&buf);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty(), "unexpected errors: {errs:?}");
        // MSDOS weak + PE32 strong
        assert_eq!(cands.len(), 2);
        assert_eq!(cands[0].file_type.name, "MSDOS");
        assert_eq!(cands[0].strength, FormatStrength::Weak);
        assert_eq!(cands[1].file_type.name, "PE32");
        assert_eq!(cands[1].strength, FormatStrength::Strong);
    }

    #[test]
    fn default_table_detects_elf64() {
        let data = [0x7Fu8, 0x45, 0x4C, 0x46, 0x02, 0x01, 0x01, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty());
        // Only ELF matches (MSDOS/PE/Mach-O do not)
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].file_type.name, "ELF64");
        assert_eq!(cands[0].strength, FormatStrength::Strong);
    }

    #[test]
    fn default_table_detects_macho_64() {
        let data = 0xFEEDFACFu32.to_be_bytes();
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty());
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].file_type.name, "Mach-O 64");
    }

    #[test]
    fn default_table_detects_zip() {
        let data = [0x50u8, 0x4B, 0x03, 0x04, 0x14, 0x00, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty());
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].file_type.name, "ZIP");
    }

    #[test]
    fn default_table_detects_pdf() {
        let data = b"%PDF-1.4\nrest";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty());
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].file_type.name, "PDF");
    }

    #[test]
    fn default_table_detects_dex() {
        let data = b"dex\n035\0extra";
        let src = MemorySource::new(data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty());
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].file_type.name, "DEX");
    }

    #[test]
    fn default_table_detects_png() {
        let data = [0x89u8, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(errs.is_empty());
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].file_type.name, "PNG");
    }

    #[test]
    fn default_table_no_match_for_unknown() {
        let data = [0x00u8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(cands.is_empty());
        assert!(errs.is_empty());
    }

    #[test]
    fn default_table_empty_input_no_match() {
        let data: [u8; 0] = [];
        let src = MemorySource::new(&data);
        let view = view_of(&src);
        let table = ProbeTable::default_phase2();
        let (cands, errs) = table.probe_all(&view);
        assert!(cands.is_empty());
        assert!(errs.is_empty());
    }
}
