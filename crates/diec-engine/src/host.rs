//! Host API adapter bridging `diec-rules::HostApi` to file bytes.
//!
//! This adapter provides the `HostApi` implementation that rule scripts
//! use to access binary file data. It wraps an `OwnedSource` and provides
//! read primitives, signature checking, and string reading.

use diec_core::format::FileType;
use diec_core::input::{ByteSource, ByteView, OwnedSource};
use diec_rules::host_api::{HostApi, HostApiError};
use diec_rules::host_api_bridge::{match_signature, parse_signature};
use std::sync::Arc;

/// A simple host API backed by an in-memory byte buffer.
///
/// This adapter provides the core `Binary_Script` host API methods
/// by reading directly from the owned byte source. Format-specific
/// methods (PE sections, ELF segments, etc.) are not implemented here.
/// Scan options that control rule behavior (deep, heuristic, verbose, etc.).
/// These map to upstream CLI flags: --deepscan, --heuristicscan, --verbose,
/// --aggressivescan, --alltypes, --hideunknown.
#[derive(Debug, Clone, Copy, Default)]
pub struct ScanFlags {
    /// Deep scan mode (--deepscan).
    pub deep: bool,
    /// Heuristic scan mode (--heuristicscan).
    pub heuristic: bool,
    /// Verbose output (--verbose).
    pub verbose: bool,
    /// Aggressive scan mode (--aggressivescan).
    pub aggressive: bool,
    /// All types scan mode (--alltypes).
    pub all_types: bool,
    /// Hide unknown detections (--hideunknown).
    pub hide_unknown: bool,
}

/// A host API implementation backed by an in-memory byte buffer.
/// Provides file data access and scan mode flags to the rule runtime.
pub struct BufferHost {
    /// The file type context.
    file_type: FileType,
    /// The owned byte source.
    source: OwnedSource,
    /// The file name.
    file_name: String,
    /// Scan flags controlling rule behavior.
    flags: ScanFlags,
}

impl BufferHost {
    /// Create a new `BufferHost` from a byte buffer and file name.
    pub fn new(data: Vec<u8>, file_name: String) -> Self {
        let arc_data: Arc<[u8]> = Arc::from(data);
        let source = OwnedSource::new(arc_data);
        let file_type = determine_file_type(&file_name);
        Self {
            file_type,
            source,
            file_name,
            flags: ScanFlags::default(),
        }
    }

    /// Create a `BufferHost` for a specific file type.
    pub fn with_type(data: Vec<u8>, file_name: String, file_type: &str) -> Self {
        let arc_data: Arc<[u8]> = Arc::from(data);
        let source = OwnedSource::new(arc_data);
        Self {
            file_type: FileType::new(file_type),
            source,
            file_name,
            flags: ScanFlags::default(),
        }
    }

    /// Set scan flags on this host.
    pub fn with_flags(mut self, flags: ScanFlags) -> Self {
        self.flags = flags;
        self
    }

    /// Get the underlying data as a slice.
    fn data(&self) -> &[u8] {
        self.source.as_slice()
    }
}

/// Determine the file type from the file name extension.
fn determine_file_type(name: &str) -> FileType {
    let lower = name.to_lowercase();
    if lower.ends_with(".exe") || lower.ends_with(".dll") || lower.ends_with(".sys") {
        FileType::new("PE")
    } else if lower.ends_with(".so") || lower.ends_with(".o") || lower.ends_with(".elf") {
        FileType::new("ELF")
    } else if lower.ends_with(".dylib") || lower.ends_with(".macho") {
        FileType::new("MACH")
    } else {
        FileType::new("Binary")
    }
}

impl HostApi for BufferHost {
    fn file_type(&self) -> &FileType {
        &self.file_type
    }

    fn view(&self) -> &ByteView<'_> {
        // Create a temporary view on each call. This is not ideal but
        // works for the current usage where view() is rarely called.
        // A proper solution would use self-referential types or
        // restructure the trait to avoid the lifetime issue.
        unimplemented!("ByteView lifetime prevents storing it; use data() directly")
    }

    fn read_u8(&self, offset: u64) -> Result<u8, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        if idx >= data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(data[idx])
    }

    fn read_u16_le(&self, offset: u64) -> Result<u16, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(2).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(u16::from_le_bytes([data[idx], data[idx + 1]]))
    }

    fn read_u16_be(&self, offset: u64) -> Result<u16, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(2).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(u16::from_be_bytes([data[idx], data[idx + 1]]))
    }

    fn read_u24_le(&self, offset: u64) -> Result<u32, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(3).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(u32::from_le_bytes([
            data[idx],
            data[idx + 1],
            data[idx + 2],
            0,
        ]))
    }

    fn read_u24_be(&self, offset: u64) -> Result<u32, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(3).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(u32::from_be_bytes([
            data[idx],
            data[idx + 1],
            data[idx + 2],
            0,
        ]))
    }

    fn read_u32_le(&self, offset: u64) -> Result<u32, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(4).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(u32::from_le_bytes([
            data[idx],
            data[idx + 1],
            data[idx + 2],
            data[idx + 3],
        ]))
    }

    fn read_u32_be(&self, offset: u64) -> Result<u32, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(4).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        Ok(u32::from_be_bytes([
            data[idx],
            data[idx + 1],
            data[idx + 2],
            data[idx + 3],
        ]))
    }

    fn read_u64_le(&self, offset: u64) -> Result<u64, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(8).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        let mut bytes = [0u8; 8];
        bytes.copy_from_slice(&data[idx..end]);
        Ok(u64::from_le_bytes(bytes))
    }

    fn read_u64_be(&self, offset: u64) -> Result<u64, HostApiError> {
        let data = self.data();
        let idx = offset as usize;
        let end = idx.checked_add(8).ok_or(HostApiError::OutOfBounds {
            offset,
            file_size: data.len() as u64,
        })?;
        if end > data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: data.len() as u64,
            });
        }
        let mut bytes = [0u8; 8];
        bytes.copy_from_slice(&data[idx..end]);
        Ok(u64::from_be_bytes(bytes))
    }

    fn read_i8(&self, offset: u64) -> Result<i8, HostApiError> {
        self.read_u8(offset).map(|v| v as i8)
    }

    fn read_i16_le(&self, offset: u64) -> Result<i16, HostApiError> {
        self.read_u16_le(offset).map(|v| v as i16)
    }

    fn read_i32_le(&self, offset: u64) -> Result<i32, HostApiError> {
        self.read_u32_le(offset).map(|v| v as i32)
    }

    fn read_i64_le(&self, offset: u64) -> Result<i64, HostApiError> {
        self.read_u64_le(offset).map(|v| v as i64)
    }

    fn file_size(&self) -> u64 {
        self.source.len()
    }

    fn check_signature(&self, offset: u64, signature: &str) -> Result<bool, HostApiError> {
        let elements =
            parse_signature(signature).map_err(|detail| HostApiError::InvalidSignature {
                pattern: signature.into(),
                detail,
            })?;
        Ok(match_signature(self.data(), offset as usize, &elements))
    }

    fn find_signature(&self, start: u64, signature: &str) -> Result<Option<u64>, HostApiError> {
        let elements =
            parse_signature(signature).map_err(|detail| HostApiError::InvalidSignature {
                pattern: signature.into(),
                detail,
            })?;
        let data = self.data();
        let start = start as usize;
        if elements.is_empty()
            || start
                .checked_add(elements.len())
                .is_none_or(|end| end > data.len())
        {
            return Ok(None);
        }
        for i in start..=data.len() - elements.len() {
            if match_signature(data, i, &elements) {
                return Ok(Some(i as u64));
            }
        }
        Ok(None)
    }

    fn find_signature_in_range(
        &self,
        start: u64,
        end: u64,
        signature: &str,
    ) -> Result<Option<u64>, HostApiError> {
        let elements =
            parse_signature(signature).map_err(|detail| HostApiError::InvalidSignature {
                pattern: signature.into(),
                detail,
            })?;
        let data = self.data();
        let start = start as usize;
        let end = (end as usize).min(data.len());
        if elements.is_empty()
            || start >= end
            || end < elements.len()
            || start > end - elements.len()
        {
            return Ok(None);
        }
        for i in start..=end - elements.len() {
            if match_signature(data, i, &elements) {
                return Ok(Some(i as u64));
            }
        }
        Ok(None)
    }

    fn read_string(&self, offset: u64, max_len: u64) -> Result<String, HostApiError> {
        let data = self.data();
        let start = offset as usize;
        let max = if max_len == 0 {
            data.len()
        } else {
            (start + max_len as usize).min(data.len())
        };
        if start >= data.len() {
            return Ok(String::new());
        }
        let end = data[start..max]
            .iter()
            .position(|&b| b == 0)
            .map(|p| start + p)
            .unwrap_or(max);
        String::from_utf8(data[start..end].to_vec()).map_err(|e| HostApiError::Internal {
            detail: format!("invalid UTF-8 at offset {offset}: {e}"),
        })
    }

    fn file_name(&self) -> &str {
        &self.file_name
    }

    fn entry_point(&self) -> Result<u64, HostApiError> {
        Ok(0)
    }

    fn is_deep(&self) -> bool {
        self.flags.deep
    }

    fn is_heuristic(&self) -> bool {
        self.flags.heuristic
    }

    fn is_aggressive(&self) -> bool {
        self.flags.aggressive
    }

    fn is_verbose(&self) -> bool {
        self.flags.verbose
    }

    fn is_recursive(&self) -> bool {
        false
    }

    fn entropy(&self, offset: u64, size: u64) -> Result<f64, HostApiError> {
        let data = self.data();
        let start = offset as usize;
        let end = (start + size as usize).min(data.len());
        if start >= end {
            return Ok(0.0);
        }
        let mut counts = [0u32; 256];
        for &b in &data[start..end] {
            counts[b as usize] += 1;
        }
        let total = (end - start) as f64;
        let mut entropy = 0.0;
        for &count in &counts {
            if count > 0 {
                let p = count as f64 / total;
                entropy -= p * p.log2();
            }
        }
        Ok(entropy)
    }

    fn md5(&self, _offset: u64, _size: u64) -> Result<String, HostApiError> {
        Err(HostApiError::NotImplemented {
            method: "md5".into(),
        })
    }

    fn crc32(&self, _offset: u64, _size: u64) -> Result<u32, HostApiError> {
        Err(HostApiError::NotImplemented {
            method: "crc32".into(),
        })
    }

    fn pe_import_libraries(&self) -> Vec<String> {
        pe::parse_imports(self.data()).libraries
    }

    fn pe_import_functions(&self) -> Vec<String> {
        pe::parse_imports(self.data())
            .functions
            .into_iter()
            .map(|f| f.name)
            .collect()
    }

    fn pe_export_names(&self) -> Vec<String> {
        pe::parse_exports(self.data()).names
    }
}

/// PE format parsing helpers for batch table extraction.
///
/// These functions parse PE import/export tables in pure Rust, avoiding
/// the per-byte JS→Rust FFI overhead that makes QuickJS-based parsing
/// extremely slow for files with thousands of exports/imports.
pub mod pe {
    /// Parsed import table data.
    pub struct ImportData {
        /// Library names (one per import descriptor).
        pub libraries: Vec<String>,
        /// Function names (flattened across all libraries).
        pub functions: Vec<ImportFunction>,
    }

    /// A single imported function.
    pub struct ImportFunction {
        /// Library that exports this function.
        #[allow(dead_code)]
        pub lib: String,
        /// Function name (empty for ordinal imports).
        pub name: String,
    }

    /// Parsed export table data.
    pub struct ExportData {
        /// Named export function names.
        pub names: Vec<String>,
    }

    /// Read a little-endian u32 from data at the given offset.
    fn read_u32_le(data: &[u8], offset: usize) -> Option<u32> {
        let end = offset.checked_add(4)?;
        if end > data.len() {
            return None;
        }
        Some(u32::from_le_bytes([
            data[offset],
            data[offset + 1],
            data[offset + 2],
            data[offset + 3],
        ]))
    }

    /// Read a little-endian u16 from data at the given offset.
    fn read_u16_le(data: &[u8], offset: usize) -> Option<u16> {
        let end = offset.checked_add(2)?;
        if end > data.len() {
            return None;
        }
        Some(u16::from_le_bytes([data[offset], data[offset + 1]]))
    }

    /// Read a NUL-terminated ASCII string starting at the given offset,
    /// up to 256 bytes.
    fn read_cstr(data: &[u8], offset: usize) -> String {
        let max = (offset + 256).min(data.len());
        let end = data[offset..max]
            .iter()
            .position(|&b| b == 0)
            .map(|p| offset + p)
            .unwrap_or(max);
        String::from_utf8_lossy(&data[offset..end]).to_string()
    }

    /// PE section header info.
    struct SectionInfo {
        virtual_address: u32,
        virtual_size: u32,
        raw_offset: u32,
        raw_size: u32,
    }

    /// Parse the PE section table.
    fn parse_sections(data: &[u8]) -> Option<(Vec<SectionInfo>, usize, bool)> {
        if data.len() < 64 {
            return None;
        }
        // Check MZ signature.
        if data[0] != 0x4D || data[1] != 0x5A {
            return None;
        }
        let e_lfanew = read_u32_le(data, 0x3C)? as usize;
        if e_lfanew + 24 > data.len() {
            return None;
        }
        // Check PE signature.
        if &data[e_lfanew..e_lfanew + 4] != b"PE\0\0" {
            return None;
        }
        let coff_off = e_lfanew + 4;
        let num_sections = read_u16_le(data, coff_off + 2)? as usize;
        let opt_hdr_size = read_u16_le(data, coff_off + 16)? as usize;
        let opt_off = coff_off + 20;
        if opt_off + 2 > data.len() {
            return None;
        }
        let magic = read_u16_le(data, opt_off)?;
        let is_64 = magic == 0x20B;
        // Data directory start.
        let dd_off = opt_off + if is_64 { 112 } else { 96 };
        let sect_off = opt_off + opt_hdr_size;
        let mut sections = Vec::with_capacity(num_sections);
        for i in 0..num_sections {
            let s = sect_off + i * 40;
            if s + 40 > data.len() {
                break;
            }
            sections.push(SectionInfo {
                virtual_address: read_u32_le(data, s + 12).unwrap_or(0),
                virtual_size: read_u32_le(data, s + 8).unwrap_or(0),
                raw_offset: read_u32_le(data, s + 20).unwrap_or(0),
                raw_size: read_u32_le(data, s + 16).unwrap_or(0),
            });
        }
        Some((sections, dd_off, is_64))
    }

    /// Convert an RVA to a file offset using the section table.
    fn rva_to_offset(sections: &[SectionInfo], rva: u32) -> Option<usize> {
        for s in sections {
            let size = s.virtual_size.max(s.raw_size);
            if rva >= s.virtual_address && rva < s.virtual_address + size {
                return Some((s.raw_offset + (rva - s.virtual_address)) as usize);
            }
        }
        None
    }

    /// Parse the PE import table.
    pub fn parse_imports(data: &[u8]) -> ImportData {
        let mut result = ImportData {
            libraries: Vec::new(),
            functions: Vec::new(),
        };
        let (sections, dd_off, is_64) = match parse_sections(data) {
            Some(v) => v,
            None => return result,
        };
        // Import table is data directory index 1.
        let import_rva = match read_u32_le(data, dd_off + 8) {
            Some(v) if v != 0 => v,
            _ => return result,
        };
        let import_size = read_u32_le(data, dd_off + 12).unwrap_or(0);
        let import_off = match rva_to_offset(&sections, import_rva) {
            Some(v) => v,
            None => return result,
        };
        let desc_end = (import_off + import_size as usize).min(data.len());
        let thunk_size = if is_64 { 8 } else { 4 };
        let mut desc_off = import_off;
        let mut lib_idx = 0u32;
        // Limit to prevent malformed files from causing excessive work.
        while desc_off + 20 <= desc_end && lib_idx < 4096 {
            let oft = read_u32_le(data, desc_off).unwrap_or(0);
            let name_rva = read_u32_le(data, desc_off + 12).unwrap_or(0);
            let ft = read_u32_le(data, desc_off + 16).unwrap_or(0);
            if oft == 0 && name_rva == 0 && ft == 0 {
                break;
            }
            // Read library name.
            let lib_name = match rva_to_offset(&sections, name_rva) {
                Some(name_off) => read_cstr(data, name_off),
                None => String::new(),
            };
            result.libraries.push(lib_name.clone());
            // Parse thunks.
            let thunk_rva = if oft != 0 { oft } else { ft };
            if thunk_rva != 0
                && let Some(thunk_off) = rva_to_offset(&sections, thunk_rva)
            {
                parse_thunks(
                    data,
                    &sections,
                    thunk_off,
                    thunk_size,
                    is_64,
                    &lib_name,
                    &mut result.functions,
                );
            }
            desc_off += 20;
            lib_idx += 1;
        }
        result
    }

    /// Parse import thunks for a single library.
    fn parse_thunks(
        data: &[u8],
        sections: &[SectionInfo],
        thunk_off: usize,
        thunk_size: usize,
        is_64: bool,
        lib_name: &str,
        functions: &mut Vec<ImportFunction>,
    ) {
        let mut fn_idx = 0u32;
        while fn_idx < 65536 {
            let pos = thunk_off + fn_idx as usize * thunk_size;
            if pos + thunk_size > data.len() {
                break;
            }
            let (lo, hi) = if is_64 {
                (
                    read_u32_le(data, pos).unwrap_or(0),
                    read_u32_le(data, pos + 4).unwrap_or(0),
                )
            } else {
                (read_u32_le(data, pos).unwrap_or(0), 0u32)
            };
            if lo == 0 && hi == 0 {
                break;
            }
            let is_ordinal = if is_64 {
                (hi & 0x80000000) != 0
            } else {
                (lo & 0x80000000) != 0
            };
            if is_ordinal {
                functions.push(ImportFunction {
                    lib: lib_name.to_string(),
                    name: String::new(),
                });
            } else {
                let fn_name_rva = lo & 0x7FFFFFFF;
                let fn_name = match rva_to_offset(sections, fn_name_rva) {
                    Some(fn_off) if fn_off + 2 < data.len() => read_cstr(data, fn_off + 2),
                    _ => String::new(),
                };
                functions.push(ImportFunction {
                    lib: lib_name.to_string(),
                    name: fn_name,
                });
            }
            fn_idx += 1;
        }
    }

    /// Parse the PE export table.
    pub fn parse_exports(data: &[u8]) -> ExportData {
        let mut result = ExportData { names: Vec::new() };
        let (sections, dd_off, _is_64) = match parse_sections(data) {
            Some(v) => v,
            None => return result,
        };
        // Export table is data directory index 0.
        let export_rva = match read_u32_le(data, dd_off) {
            Some(v) if v != 0 => v,
            _ => return result,
        };
        let export_off = match rva_to_offset(&sections, export_rva) {
            Some(v) => v,
            None => return result,
        };
        if export_off + 40 > data.len() {
            return result;
        }
        let num_names = read_u32_le(data, export_off + 24).unwrap_or(0);
        let addr_of_names = read_u32_le(data, export_off + 32).unwrap_or(0);
        if num_names == 0 || addr_of_names == 0 {
            return result;
        }
        let names_off = match rva_to_offset(&sections, addr_of_names) {
            Some(v) => v,
            None => return result,
        };
        let max_names = num_names.min(65536) as usize;
        result.names.reserve(max_names);
        for i in 0..max_names {
            let pos = names_off + i * 4;
            if pos + 4 > data.len() {
                break;
            }
            let name_rva = read_u32_le(data, pos).unwrap_or(0);
            let name = match rva_to_offset(&sections, name_rva) {
                Some(name_off) => read_cstr(data, name_off),
                None => String::new(),
            };
            result.names.push(name);
        }
        result
    }
}
