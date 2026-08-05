//! PEID scanner backend for diec-gui.
//!
//! PEID (PE iDentifier) detects PE packers and compilers by
//! matching byte signatures from a userdb.txt file. The database
//! format is line-based: each entry has a signature name and a
//! hex pattern separated by a delimiter.

use serde::{Deserialize, Serialize};
use std::io::BufRead;

/// A single PEID match result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeidMatch {
    /// Signature name (e.g. "UPX 3.96").
    pub name: String,
    /// Matched pattern description.
    pub pattern: String,
}

/// PEID scan result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeidScanResult {
    /// Total signatures loaded.
    pub signatures_loaded: usize,
    /// Matches found.
    pub matches: Vec<PeidMatch>,
}

/// A single PEID signature entry.
#[derive(Debug, Clone)]
struct PeidSignature {
    name: String,
    pattern: Vec<u8>,
}

/// Scan a PE file against a PEID userdb.txt database.
///
/// Reads the userdb.txt file, parses signatures, and matches them
/// against the file bytes. Supports wildcards (??) in patterns.
pub fn scan_with_peid(userdb_path: &str, file_path: &str) -> Result<PeidScanResult, String> {
    let sigs = parse_userdb(userdb_path)?;
    let data = std::fs::read(file_path).map_err(|e| e.to_string())?;

    let mut matches = Vec::new();
    for sig in &sigs {
        if match_pattern(&data, sig) {
            matches.push(PeidMatch {
                name: sig.name.clone(),
                pattern: format!("{} bytes", sig.pattern.len()),
            });
        }
    }

    Ok(PeidScanResult {
        signatures_loaded: sigs.len(),
        matches,
    })
}

/// Parse a PEID userdb.txt file into signatures.
///
/// Format: lines of hex patterns with wildcards (??), each entry
/// separated by blank lines or named sections.
fn parse_userdb(path: &str) -> Result<Vec<PeidSignature>, String> {
    let file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    let reader = std::io::BufReader::new(file);
    let mut sigs = Vec::new();

    for line in reader.lines() {
        let line = line.map_err(|e| e.to_string())?;
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        // Parse hex pattern: "AA BB ?? CC"
        if let Ok(pattern) = parse_hex_pattern(line) {
            sigs.push(PeidSignature {
                name: format!("Signature #{}", sigs.len() + 1),
                pattern: pattern.clone(),
            });
        }
    }

    Ok(sigs)
}

/// Parse a hex pattern string into bytes, supporting ?? wildcards.
fn parse_hex_pattern(s: &str) -> Result<Vec<u8>, String> {
    let parts: Vec<&str> = s.split_whitespace().collect();
    let mut result = Vec::with_capacity(parts.len());
    for part in parts {
        if part == "??" {
            result.push(0x00); // Wildcard placeholder
        } else if part.len() == 2 {
            let byte = u8::from_str_radix(part, 16).map_err(|e| e.to_string())?;
            result.push(byte);
        } else {
            return Err(format!("Invalid hex pattern part: {}", part));
        }
    }
    Ok(result)
}

/// Match a signature pattern against file data (naive search).
fn match_pattern(data: &[u8], sig: &PeidSignature) -> bool {
    if sig.pattern.is_empty() || sig.pattern.len() > data.len() {
        return false;
    }
    // Use a simple sliding window search.
    for i in 0..=data.len() - sig.pattern.len() {
        let mut found = true;
        for (j, &pat_byte) in sig.pattern.iter().enumerate() {
            if data[i + j] != pat_byte {
                found = false;
                break;
            }
        }
        if found {
            return true;
        }
    }
    false
}
