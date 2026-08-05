//! Hex viewer backend for diec-gui.
//!
//! Reads a range of bytes from a file and returns a structured hex
//! dump for the frontend to render.

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
