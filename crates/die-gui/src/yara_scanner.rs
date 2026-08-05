//! YARA scanning backend for die-gui.
//!
//! Uses `yara-x` (pure Rust YARA implementation) to compile and
//! run YARA rules against file data.
//!
//! Note: `yara-x` types are `!Send`, so all operations must run
//! in a `spawn_blocking` context when called from async Tauri commands.

use serde::{Deserialize, Serialize};
use yara_x::{Compiler, Scanner};

/// A single YARA match result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct YaraMatch {
    /// Rule name that matched.
    pub rule: String,
    /// Rule namespace.
    pub namespace: String,
    /// Rule tags.
    pub tags: Vec<String>,
}

/// YARA scan result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct YaraScanResult {
    /// Number of matching rules.
    pub match_count: usize,
    /// Matches found.
    pub matches: Vec<YaraMatch>,
}

/// Compile YARA rules and scan a file.
///
/// Compiles the given rule source, reads the target file, and
/// scans it. Returns matching rules.
pub fn scan_with_yara(rules_source: &str, file_path: &str) -> Result<YaraScanResult, String> {
    let mut compiler = Compiler::new();
    compiler
        .add_source(rules_source)
        .map_err(|e| format!("YARA compile error: {}", e))?;
    let rules = compiler.build();

    let data = std::fs::read(file_path).map_err(|e| e.to_string())?;
    let mut scanner = Scanner::new(&rules);
    let results = scanner
        .scan(&data)
        .map_err(|e| format!("YARA scan error: {}", e))?;

    let matches: Vec<YaraMatch> = results
        .matching_rules()
        .map(|rule| YaraMatch {
            rule: rule.identifier().to_string(),
            namespace: rule.namespace().to_string(),
            tags: rule.tags().map(|t| t.identifier().to_string()).collect(),
        })
        .collect();

    let match_count = matches.len();
    Ok(YaraScanResult {
        match_count,
        matches,
    })
}
