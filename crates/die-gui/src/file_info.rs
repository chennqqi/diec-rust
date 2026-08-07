//! File information: size, hashes, entropy, PE/ELF/Mach-O sections and symbols.
//!
//! Provides the backend for the file info panel and the entropy/hash views.

use serde::{Deserialize, Serialize};

/// File hash digests (MD5, SHA1, SHA256, CRC32).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileHashes {
    /// MD5 hex digest.
    pub md5: String,
    /// SHA-1 hex digest.
    pub sha1: String,
    /// SHA-256 hex digest.
    pub sha256: String,
    /// CRC32 hex digest.
    pub crc32: String,
}

/// Complete file information for the info panel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    /// File path.
    pub path: String,
    /// File name (basename).
    pub file_name: String,
    /// File size in bytes.
    pub size: u64,
    /// File size formatted as human-readable string (e.g. "1.23 MB").
    pub size_human: String,
    /// Shannon entropy of the file content (0.0..=8.0).
    pub entropy: f64,
    /// Hash digests.
    pub hashes: FileHashes,
    /// Detected file format (PE32, ELF64, Mach-O, etc.) or "Unknown".
    pub format: String,
    /// PE/ELF/Mach-O sections (empty for non-binary files).
    pub sections: Vec<SectionInfo>,
    /// PE/ELF/Mach-O symbols (empty for non-binary or stripped files).
    pub symbols: Vec<SymbolInfo>,
}

/// A single section/segment in a binary file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SectionInfo {
    /// Section name (e.g. ".text", ".data").
    pub name: String,
    /// Virtual address (offset in memory).
    pub virtual_address: u64,
    /// Virtual size.
    pub virtual_size: u64,
    /// Raw offset in file.
    pub raw_offset: u64,
    /// Raw size in file.
    pub raw_size: u64,
    /// Section entropy (0.0..=8.0).
    pub entropy: f64,
}

/// A single symbol in a binary file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolInfo {
    /// Symbol name (possibly mangled).
    pub name: String,
    /// Symbol address.
    pub address: u64,
    /// Symbol size (0 if unknown).
    pub size: u64,
    /// Symbol kind (function, data, object, etc.).
    pub kind: String,
}

/// Compute Shannon entropy of a byte buffer.
///
/// Returns a value in [0.0, 8.0] where 8.0 means maximum randomness
/// (uniform distribution of all 256 byte values).
pub fn shannon_entropy(data: &[u8]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    let mut counts = [0u64; 256];
    for &b in data {
        counts[b as usize] += 1;
    }
    let len = data.len() as f64;
    let mut entropy = 0.0;
    for &count in &counts {
        if count == 0 {
            continue;
        }
        let p = count as f64 / len;
        entropy -= p * p.log2();
    }
    entropy
}

/// Format a byte count as a human-readable string.
fn format_size(bytes: u64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    let mut size = bytes as f64;
    let mut unit_idx = 0;
    while size >= 1024.0 && unit_idx < UNITS.len() - 1 {
        size /= 1024.0;
        unit_idx += 1;
    }
    if unit_idx == 0 {
        format!("{} {}", bytes, UNITS[0])
    } else {
        format!("{:.2} {}", size, UNITS[unit_idx])
    }
}

/// Compute MD5, SHA-1, SHA-256, and CRC32 hashes of a file.
fn compute_hashes(data: &[u8]) -> FileHashes {
    use md5::Digest as _;
    let md5 = hex::encode(md5::Md5::digest(data));
    let sha1 = hex::encode(sha1::Sha1::digest(data));
    let sha256 = hex::encode(sha2::Sha256::digest(data));
    let crc32 = format!("{:08X}", crc32fast::hash(data));
    FileHashes {
        md5,
        sha1,
        sha256,
        crc32,
    }
}

/// Detect the binary format from magic bytes.
fn detect_format(data: &[u8]) -> String {
    if data.len() < 4 {
        return "Unknown".to_string();
    }
    // PE: MZ header at start, PE signature at e_lfanew offset.
    if data.starts_with(b"MZ") {
        if data.len() >= 0x40 {
            let pe_offset =
                u32::from_le_bytes([data[0x3c], data[0x3d], data[0x3e], data[0x3f]]) as usize;
            if pe_offset + 4 <= data.len() && &data[pe_offset..pe_offset + 4] == b"PE\0\0" {
                // Check machine type for 32 vs 64 bit.
                if pe_offset + 6 <= data.len() {
                    let machine = u16::from_le_bytes([data[pe_offset + 4], data[pe_offset + 5]]);
                    return match machine {
                        0x14c => "PE32".to_string(),
                        0x8664 => "PE32+".to_string(),
                        _ => "PE".to_string(),
                    };
                }
                return "PE".to_string();
            }
        }
        return "DOS MZ".to_string();
    }
    // ELF: 0x7f 'E' 'L' 'F'
    if data.starts_with(b"\x7fELF") {
        return match data.get(4) {
            Some(1) => "ELF32".to_string(),
            Some(2) => "ELF64".to_string(),
            _ => "ELF".to_string(),
        };
    }
    // Mach-O FAT (Universal Binary): 0xCAFEBABE (big-endian) or
    // 0xBEBAFECA (little-endian). Contains multiple architecture slices.
    let magic_be = u32::from_be_bytes([data[0], data[1], data[2], data[3]]);
    if magic_be == 0xCAFEBABE || magic_be == 0xBEBAFECA {
        return "Mach-O FAT".to_string();
    }

    // Mach-O: 0xFEEDFACE/0xFEEDFACF (32/64-bit big-endian)
    //         0xCEFAEDFE/0xCFFAEDFE (32/64-bit little-endian)
    let magic = u32::from_be_bytes([data[0], data[1], data[2], data[3]]);
    match magic {
        0xFEEDFACE => "Mach-O 32".to_string(),
        0xFEEDFACF => "Mach-O 64".to_string(),
        _ => {
            let magic_le = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
            match magic_le {
                0xFEEDFACE => "Mach-O 32".to_string(),
                0xFEEDFACF => "Mach-O 64".to_string(),
                _ => "Unknown".to_string(),
            }
        }
    }
}

/// Parse PE sections, imports, and exports using goblin.
fn parse_pe_sections(data: &[u8]) -> (Vec<SectionInfo>, Vec<SymbolInfo>) {
    let mut sections = Vec::new();
    let mut symbols = Vec::new();

    if let Ok(goblin::Object::PE(pe)) = goblin::Object::parse(data) {
        for sec in &pe.sections {
            let name = String::from_utf8_lossy(
                &sec.name[..sec.name.iter().position(|&b| b == 0).unwrap_or(8)],
            )
            .to_string();
            let raw_start = sec.pointer_to_raw_data as usize;
            let raw_end = raw_start
                .saturating_add(sec.size_of_raw_data as usize)
                .min(data.len());
            let sec_data = &data[raw_start..raw_end];
            sections.push(SectionInfo {
                name,
                virtual_address: sec.virtual_address as u64,
                virtual_size: sec.virtual_size as u64,
                raw_offset: sec.pointer_to_raw_data as u64,
                raw_size: sec.size_of_raw_data as u64,
                entropy: shannon_entropy(sec_data),
            });
        }
        // Exports
        for export in &pe.exports {
            if let Some(ref name) = export.name {
                symbols.push(SymbolInfo {
                    name: name.to_string(),
                    address: export.rva as u64,
                    size: export.size as u64,
                    kind: "export".to_string(),
                });
            }
        }
        // Imports — goblin provides PE imports as (DLL name, import name, RVA)
        for import in &pe.imports {
            symbols.push(SymbolInfo {
                name: format!("{}.{}", import.dll, import.name),
                address: import.offset as u64,
                size: 0,
                kind: "import".to_string(),
            });
        }
    }

    (sections, symbols)
}

/// Parse ELF sections and symbols using goblin.
fn parse_elf_sections(data: &[u8]) -> (Vec<SectionInfo>, Vec<SymbolInfo>) {
    let mut sections = Vec::new();
    let mut symbols = Vec::new();

    if let Ok(goblin::Object::Elf(elf)) = goblin::Object::parse(data) {
        for sec in &elf.section_headers {
            let name = elf
                .shdr_strtab
                .get_at(sec.sh_name)
                .unwrap_or("?")
                .to_string();
            let sec_data = &data[sec.sh_offset as usize..(sec.sh_offset + sec.sh_size) as usize];
            sections.push(SectionInfo {
                name,
                virtual_address: sec.sh_addr,
                virtual_size: sec.sh_size,
                raw_offset: sec.sh_offset,
                raw_size: sec.sh_size,
                entropy: shannon_entropy(sec_data),
            });
        }
        for sym in &elf.syms {
            if let Some(name) = elf.strtab.get_at(sym.st_name) {
                symbols.push(SymbolInfo {
                    name: name.to_string(),
                    address: sym.st_value,
                    size: sym.st_size,
                    kind: match sym.st_type() {
                        2 => "function".to_string(),
                        1 => "data".to_string(),
                        0 => "notype".to_string(),
                        _ => "other".to_string(),
                    },
                });
            }
        }
    }

    (sections, symbols)
}

/// Parse Mach-O sections and symbols using goblin.
fn parse_macho_sections(data: &[u8]) -> (Vec<SectionInfo>, Vec<SymbolInfo>) {
    let mut sections = Vec::new();
    let mut symbols = Vec::new();

    // goblin::Object::Mach is an enum (Mach::Binary for single-arch).
    if let Ok(goblin::Object::Mach(mach)) = goblin::Object::parse(data)
        && let goblin::mach::Mach::Binary(macho) = mach
    {
        for seg in macho.segments.iter() {
            if let Ok(sec_iter) = seg.sections() {
                for (sec, sec_data) in sec_iter {
                    let name = sec.name().unwrap_or_default();
                    sections.push(SectionInfo {
                        name: name.to_string(),
                        virtual_address: sec.addr,
                        virtual_size: sec.size,
                        raw_offset: sec.offset as u64,
                        raw_size: sec.size,
                        entropy: shannon_entropy(sec_data),
                    });
                }
            }
        }
        for (name, nlist) in macho.symbols().flatten() {
            if nlist.is_stab() {
                continue;
            }
            symbols.push(SymbolInfo {
                name: name.to_string(),
                address: nlist.n_value,
                size: 0,
                kind: if nlist.get_type() == 0x0f {
                    "function".to_string()
                } else {
                    "symbol".to_string()
                },
            });
        }
    }

    (sections, symbols)
}

/// Gather complete file information for the given path.
///
/// Reads the file, computes hashes and entropy, detects the format,
/// and parses PE/ELF/Mach-O sections and symbols if applicable.
pub fn gather_file_info(path: &str) -> Result<FileInfo, String> {
    let data = std::fs::read(path).map_err(|e| e.to_string())?;
    let file_name = std::path::Path::new(path)
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string());

    let format = detect_format(&data);
    let hashes = compute_hashes(&data);
    let entropy = shannon_entropy(&data);

    let (sections, symbols) = match format.as_str() {
        "PE32" | "PE32+" | "PE" => parse_pe_sections(&data),
        "ELF32" | "ELF64" | "ELF" => parse_elf_sections(&data),
        "Mach-O 32" | "Mach-O 64" => parse_macho_sections(&data),
        _ => (Vec::new(), Vec::new()),
    };

    Ok(FileInfo {
        path: path.to_string(),
        file_name,
        size: data.len() as u64,
        size_human: format_size(data.len() as u64),
        entropy,
        hashes,
        format,
        sections,
        symbols,
    })
}

/// Compute entropy for a file region (for the entropy view).
///
/// Returns entropy values for fixed-size blocks of the file,
/// suitable for plotting an entropy graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyGraph {
    /// Block size in bytes.
    pub block_size: u64,
    /// Entropy value for each block.
    pub blocks: Vec<f64>,
    /// Overall file entropy.
    pub overall: f64,
}

/// Compute entropy graph data for a file.
pub fn compute_entropy_graph(path: &str, block_size: Option<u64>) -> Result<EntropyGraph, String> {
    let data = std::fs::read(path).map_err(|e| e.to_string())?;
    let bs = block_size.unwrap_or(256) as usize;
    let bs = bs.max(1);
    let mut blocks = Vec::new();
    for chunk in data.chunks(bs) {
        blocks.push(shannon_entropy(chunk));
    }
    let overall = shannon_entropy(&data);
    Ok(EntropyGraph {
        block_size: bs as u64,
        blocks,
        overall,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_format_macho_fat_be() {
        // FAT Mach-O magic (big-endian): 0xCAFEBABE
        let data = [0xCA, 0xFE, 0xBA, 0xBE, 0, 0, 0, 0];
        assert_eq!(detect_format(&data), "Mach-O FAT");
    }

    #[test]
    fn test_detect_format_macho_fat_le() {
        // FAT Mach-O magic (little-endian): 0xBEBAFECA
        let data = [0xBE, 0xBA, 0xFE, 0xCA, 0, 0, 0, 0];
        assert_eq!(detect_format(&data), "Mach-O FAT");
    }

    #[test]
    fn test_detect_format_macho_64() {
        // Mach-O 64-bit magic (big-endian): 0xFEEDFACF
        let data = [0xFE, 0xED, 0xFA, 0xCF, 0, 0, 0, 0];
        assert_eq!(detect_format(&data), "Mach-O 64");
    }

    #[test]
    fn test_detect_format_pe32() {
        // Minimal PE32: MZ header + e_lfanew pointing to PE signature
        let mut data = vec![0u8; 0x80];
        data[0] = b'M';
        data[1] = b'Z';
        // e_lfanew at 0x3c = 0x40
        data[0x3c] = 0x40;
        // PE signature at 0x40
        data[0x40] = b'P';
        data[0x41] = b'E';
        data[0x42] = 0;
        data[0x43] = 0;
        // Machine type at 0x44 = 0x14c (i386)
        data[0x44] = 0x4c;
        data[0x45] = 0x01;
        assert_eq!(detect_format(&data), "PE32");
    }

    #[test]
    fn test_detect_format_elf64() {
        // ELF 64-bit
        let data = [0x7f, b'E', b'L', b'F', 2, 0, 0, 0];
        assert_eq!(detect_format(&data), "ELF64");
    }

    #[test]
    fn test_detect_format_unknown() {
        let data = [0x00, 0x01, 0x02, 0x03];
        assert_eq!(detect_format(&data), "Unknown");
    }

    #[test]
    fn test_detect_format_too_short() {
        let data = [0x00, 0x01];
        assert_eq!(detect_format(&data), "Unknown");
    }
}
