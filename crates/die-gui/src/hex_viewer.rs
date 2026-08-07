//! Hex viewer backend for die-gui.
//!
//! Reads a range of bytes from a file and returns a structured hex
//! dump for the frontend to render. Also provides byte pattern search
//! for the hex viewer's search functionality.

use serde::{Deserialize, Serialize};

/// A single line of hex dump output.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HexLine {
    /// Offset of the first byte in this line (hex string, e.g. "00000010").
    pub offset: String,
    /// Hex bytes as space-separated string (e.g. "48 89 5C 24 08").
    pub hex: String,
    /// ASCII representation (non-printable chars replaced with '.').
    pub ascii: String,
}

/// Hex dump response containing multiple lines.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HexDump {
    /// Total file size in bytes.
    pub file_size: u64,
    /// Starting offset of this dump.
    pub start_offset: u64,
    /// Hex lines (16 bytes per line).
    pub lines: Vec<HexLine>,
}

/// A single search hit from `search_bytes`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchHit {
    /// Offset where the pattern was found.
    pub offset: u64,
}

/// Search response containing all hits.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    /// Total file size in bytes.
    pub file_size: u64,
    /// All offsets where the pattern was found.
    pub hits: Vec<SearchHit>,
}

/// Read a range of bytes from a file and format as hex dump.
///
/// Reads up to `max_bytes` bytes starting at `offset`. Returns lines
/// of 16 bytes each with offset, hex, and ASCII columns.
pub fn read_hex_dump(path: &str, offset: u64, max_bytes: usize) -> Result<HexDump, String> {
    let metadata = std::fs::metadata(path).map_err(|e| e.to_string())?;
    let file_size = metadata.len();

    if offset >= file_size {
        return Ok(HexDump {
            file_size,
            start_offset: offset,
            lines: Vec::new(),
        });
    }

    let bytes_to_read = std::cmp::min(max_bytes as u64, file_size - offset);
    let mut buf = vec![0u8; bytes_to_read as usize];

    use std::io::{Read, Seek, SeekFrom};
    let mut file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    file.seek(SeekFrom::Start(offset))
        .map_err(|e| e.to_string())?;
    file.read_exact(&mut buf).map_err(|e| e.to_string())?;

    let lines = format_hex_lines(&buf, offset);
    Ok(HexDump {
        file_size,
        start_offset: offset,
        lines,
    })
}

/// Search for a byte pattern in a file starting from `start_offset`.
///
/// The pattern can be either:
/// - A hex string (e.g. "48 89 5C" or "48895C")
/// - An ASCII string (e.g. "Hello")
///
/// Detection: if the pattern contains only hex digits and spaces, it is
/// treated as a hex pattern. Otherwise, it is treated as ASCII.
pub fn search_bytes(
    path: &str,
    pattern: &str,
    start_offset: u64,
    max_hits: usize,
) -> Result<SearchResult, String> {
    let metadata = std::fs::metadata(path).map_err(|e| e.to_string())?;
    let file_size = metadata.len();

    let needle = parse_search_pattern(pattern)?;
    if needle.is_empty() {
        return Ok(SearchResult {
            file_size,
            hits: Vec::new(),
        });
    }

    use std::io::{Read, Seek, SeekFrom};
    let mut file = std::fs::File::open(path).map_err(|e| e.to_string())?;

    // Read the file in chunks and search for the pattern.
    let chunk_size: usize = 65536;
    let overlap = needle.len() - 1;
    let mut buf = vec![0u8; chunk_size + overlap];
    let mut pos = start_offset;
    let mut hits = Vec::new();

    file.seek(SeekFrom::Start(start_offset))
        .map_err(|e| e.to_string())?;

    loop {
        if pos >= file_size || hits.len() >= max_hits {
            break;
        }
        let to_read = std::cmp::min(buf.len() as u64, file_size - pos) as usize;
        let read_buf = &mut buf[..to_read];
        let n = file.read(read_buf).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }

        // Search for needle in the read buffer.
        let data = &buf[..n];
        let mut search_start = 0;
        while let Some(idx) = find_subslice(&data[search_start..], &needle) {
            let abs_offset = pos + search_start as u64 + idx as u64;
            hits.push(SearchHit { offset: abs_offset });
            if hits.len() >= max_hits {
                break;
            }
            search_start += idx + 1;
            if search_start + needle.len() > n {
                break;
            }
        }

        pos += n as u64;
        // Seek back by overlap to catch patterns spanning chunk boundaries.
        if pos < file_size {
            file.seek(SeekFrom::Start(pos.saturating_sub(overlap as u64)))
                .map_err(|e| e.to_string())?;
            pos = pos.saturating_sub(overlap as u64);
        }
    }

    Ok(SearchResult { file_size, hits })
}

/// Parse a search pattern into a byte vector.
///
/// Hex patterns: "48 89 5C", "48895C", "48-89-5C"
/// ASCII patterns: "Hello World"
fn parse_search_pattern(pattern: &str) -> Result<Vec<u8>, String> {
    let trimmed = pattern.trim();
    if trimmed.is_empty() {
        return Ok(Vec::new());
    }

    // Check if the pattern looks like hex (only hex digits, spaces, dashes).
    let cleaned: String = trimmed
        .chars()
        .filter(|c| !c.is_whitespace() && *c != '-')
        .collect();
    if !cleaned.is_empty()
        && cleaned.len().is_multiple_of(2)
        && cleaned.chars().all(|c| c.is_ascii_hexdigit())
    {
        // Parse as hex.
        let mut bytes = Vec::with_capacity(cleaned.len() / 2);
        for chunk in cleaned.as_bytes().chunks(2) {
            let hex_str = std::str::from_utf8(chunk).map_err(|e| e.to_string())?;
            let byte = u8::from_str_radix(hex_str, 16).map_err(|e| e.to_string())?;
            bytes.push(byte);
        }
        Ok(bytes)
    } else {
        // Treat as ASCII string.
        Ok(trimmed.as_bytes().to_vec())
    }
}

/// Find the first occurrence of `needle` in `haystack`.
fn find_subslice(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || needle.len() > haystack.len() {
        return None;
    }
    haystack.windows(needle.len()).position(|w| w == needle)
}

/// Format raw bytes into hex dump lines (16 bytes per line).
fn format_hex_lines(data: &[u8], base_offset: u64) -> Vec<HexLine> {
    data.chunks(16)
        .enumerate()
        .map(|(i, chunk)| {
            let offset = base_offset + (i * 16) as u64;
            let hex: Vec<String> = chunk.iter().map(|b| format!("{:02X}", b)).collect();
            let ascii: String = chunk
                .iter()
                .map(|&b| {
                    if (32..=126).contains(&b) {
                        b as char
                    } else {
                        '.'
                    }
                })
                .collect();
            HexLine {
                offset: format!("{:08X}", offset),
                hex: hex.join(" "),
                ascii,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_parse_hex_pattern() {
        assert_eq!(parse_search_pattern("48 89").unwrap(), vec![0x48, 0x89]);
        assert_eq!(parse_search_pattern("4889").unwrap(), vec![0x48, 0x89]);
        assert_eq!(parse_search_pattern("48-89").unwrap(), vec![0x48, 0x89]);
    }

    #[test]
    fn test_parse_ascii_pattern() {
        assert_eq!(
            parse_search_pattern("Hello").unwrap(),
            vec![b'H', b'e', b'l', b'l', b'o']
        );
    }

    #[test]
    fn test_parse_empty_pattern() {
        assert_eq!(parse_search_pattern("").unwrap(), Vec::<u8>::new());
        assert_eq!(parse_search_pattern("   ").unwrap(), Vec::<u8>::new());
    }

    #[test]
    fn test_search_bytes_finds_pattern() {
        // Create a temp file with known content.
        let mut tmp = tempfile::NamedTempFile::new().unwrap();
        tmp.write_all(b"Hello World Hello Again").unwrap();
        tmp.flush().unwrap();

        let result = search_bytes(tmp.path().to_str().unwrap(), "Hello", 0, 100).unwrap();
        assert_eq!(result.hits.len(), 2);
        assert_eq!(result.hits[0].offset, 0);
        assert_eq!(result.hits[1].offset, 12);
    }

    #[test]
    fn test_search_bytes_hex_pattern() {
        let mut tmp = tempfile::NamedTempFile::new().unwrap();
        tmp.write_all(&[0x48, 0x89, 0x5C, 0x24, 0x08, 0x48, 0x89, 0x5C])
            .unwrap();
        tmp.flush().unwrap();

        let result = search_bytes(tmp.path().to_str().unwrap(), "48 89 5C", 0, 100).unwrap();
        assert_eq!(result.hits.len(), 2);
        assert_eq!(result.hits[0].offset, 0);
        assert_eq!(result.hits[1].offset, 5);
    }

    #[test]
    fn test_search_bytes_start_offset() {
        let mut tmp = tempfile::NamedTempFile::new().unwrap();
        // Use "XY" which is not a valid hex pattern (X is not a hex digit).
        tmp.write_all(b"XY XY XY XY").unwrap();
        tmp.flush().unwrap();

        // "XY" appears at offsets 0, 3, 6, 9 in "XY XY XY XY".
        // Starting from offset 3, we should find 3 hits: at 3, 6, 9.
        let result = search_bytes(tmp.path().to_str().unwrap(), "XY", 3, 100).unwrap();
        assert!(
            result.hits.len() >= 3,
            "Expected at least 3 hits, got {}: {:?}",
            result.hits.len(),
            result.hits
        );
        assert_eq!(result.hits[0].offset, 3);
    }

    #[test]
    fn test_search_bytes_max_hits() {
        let mut tmp = tempfile::NamedTempFile::new().unwrap();
        tmp.write_all(b"AAAAAAAAAA").unwrap();
        tmp.flush().unwrap();

        let result = search_bytes(tmp.path().to_str().unwrap(), "A", 0, 3).unwrap();
        assert_eq!(result.hits.len(), 3);
    }

    #[test]
    fn test_read_hex_dump_empty_file() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let result = read_hex_dump(tmp.path().to_str().unwrap(), 0, 4096).unwrap();
        assert_eq!(result.file_size, 0);
        assert!(result.lines.is_empty());
    }

    #[test]
    fn test_read_hex_dump_offset_beyond_file() {
        let mut tmp = tempfile::NamedTempFile::new().unwrap();
        tmp.write_all(b"Hello").unwrap();
        tmp.flush().unwrap();

        let result = read_hex_dump(tmp.path().to_str().unwrap(), 100, 4096).unwrap();
        assert_eq!(result.file_size, 5);
        assert!(result.lines.is_empty());
    }
}
