//! Scan orchestration: run rules against file bytes and collect results.
//!
//! The scanner creates a rule runtime per rule, loads the database
//! framework (init + includes), and evaluates each rule in isolation.
//! Results are aggregated into a `ScanResult`.

use crate::database::Database;
use crate::host::BufferHost;
use diec_core::cancel::CancellationToken;
use diec_core::input::{ByteRange, ByteSource, ByteView, MemorySource};
use diec_formats::probe::ProbeTable;
use diec_rules::backend_rquickjs::RquickjsRuntime;
use diec_rules::runtime::{DatabaseSnapshot, RuleRuntime, RuntimeConfig};
use std::sync::Arc;

/// Detect the file format and return the set of rule file types that
/// should be run.
///
/// Upstream DIE dispatches by detected format:
/// - PE32/MSDOS → run "PE" rules + "Binary" rules
/// - ELF → run "ELF" rules + "Binary" rules
/// - Mach-O → run "MACH" rules + "Binary" rules
/// - No specific format → run "Binary" rules only
///
/// "Binary" rules always run because they contain generic archive,
/// image, audio, and other format detections that apply to any file.
fn detect_rule_types(data: &[u8]) -> Vec<&'static str> {
    let source = MemorySource::new(data);
    let range = ByteRange::new(0, source.len()).unwrap_or(ByteRange {
        start: 0,
        length: 0,
    });
    let view = match ByteView::new(&source, range) {
        Some(v) => v,
        None => return vec!["Binary"],
    };

    let table = ProbeTable::default_phase2();
    let (candidates, _errors) = table.probe_all(&view);

    let mut types: Vec<&'static str> = vec!["Binary"];

    for cand in &candidates {
        match cand.file_type.name.as_str() {
            "PE32" | "MSDOS" => {
                if !types.contains(&"PE") {
                    types.push("PE");
                }
            }
            "ELF" => {
                if !types.contains(&"ELF") {
                    types.push("ELF");
                }
            }
            "Mach-O" if !types.contains(&"MACH") => {
                types.push("MACH");
            }
            _ => {}
        }
    }

    types
}

/// Error type for scan operations.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ScanError {
    /// Database loading or initialization failed.
    DatabaseInit {
        /// Error detail.
        detail: String,
    },
    /// Host API registration failed.
    HostApi {
        /// Error detail.
        detail: String,
    },
    /// Rule evaluation failed.
    RuleEval {
        /// The rule path that failed.
        path: String,
        /// Error detail.
        detail: String,
    },
    /// Input I/O error.
    Input {
        /// The file path that could not be read.
        path: String,
        /// Error detail.
        detail: String,
    },
    /// The operation was cancelled.
    Cancelled,
}

impl std::fmt::Display for ScanError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ScanError::DatabaseInit { detail } => {
                write!(f, "database initialization failed: {detail}")
            }
            ScanError::HostApi { detail } => write!(f, "host API error: {detail}"),
            ScanError::RuleEval { path, detail } => {
                write!(f, "rule evaluation error in {path}: {detail}")
            }
            ScanError::Input { path, detail } => {
                write!(f, "input error reading {path}: {detail}")
            }
            ScanError::Cancelled => write!(f, "scan cancelled"),
        }
    }
}

impl std::error::Error for ScanError {}

/// A single detection result from scanning.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScanDetection {
    /// The file type that produced this detection.
    pub file_type: String,
    /// The detection type (e.g. "archive", "compiler", "linker").
    pub type_name: String,
    /// The detection name (e.g. "7-Zip", "Borland C++").
    pub name: String,
    /// Optional version string.
    pub version: Option<String>,
    /// Optional options/info string.
    pub options: Option<String>,
}

/// The result of scanning a single file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScanResult {
    /// The file path that was scanned.
    pub path: String,
    /// All detections found.
    pub detections: Vec<ScanDetection>,
    /// Diagnostics (errors, warnings) encountered during scanning.
    pub diagnostics: Vec<String>,
}

/// Scan a single file against the database.
///
/// This is the main entry point for scanning. It reads the file,
/// creates a host adapter, and evaluates all applicable rules.
pub fn scan_once(
    database: &Database,
    path: &str,
    cancel: &CancellationToken,
) -> Result<ScanResult, ScanError> {
    let data = std::fs::read(path).map_err(|e| ScanError::Input {
        path: path.to_string(),
        detail: e.to_string(),
    })?;

    scan_bytes(database, path, data, cancel)
}

/// Scan a byte buffer against the database.
///
/// Rules are grouped by file type. One runtime is created per file
/// type group, and each rule is evaluated in an isolated scope within
/// that runtime. This avoids the overhead of creating a runtime per
/// rule while preventing scope pollution between rules.
pub fn scan_bytes(
    database: &Database,
    file_name: &str,
    data: Vec<u8>,
    cancel: &CancellationToken,
) -> Result<ScanResult, ScanError> {
    let snapshot = database.snapshot();
    let mut detections = Vec::new();
    let mut diagnostics = Vec::new();

    // Detect the file format to determine which rule types to run.
    let active_types = detect_rule_types(&data);

    // Group rules by file type, but only for types that match the
    // detected format.
    let mut groups: std::collections::BTreeMap<&str, Vec<&diec_rules::runtime::LoadedRule>> =
        std::collections::BTreeMap::new();
    for rule in &snapshot.rules {
        if active_types.contains(&rule.file_type.as_str()) {
            groups.entry(&rule.file_type).or_default().push(rule);
        }
    }

    // Process each file type group with a shared runtime.
    for (file_type, rules) in &groups {
        if cancel.is_cancelled() {
            return Err(ScanError::Cancelled);
        }

        // Create one runtime for this file type.
        let mut runtime = match RquickjsRuntime::new(RuntimeConfig::default()) {
            Ok(rt) => rt,
            Err(e) => {
                diagnostics.push(format!("runtime create error for {file_type}: {e}"));
                continue;
            }
        };

        // Create a host with the file data.
        let host = Arc::new(BufferHost::new(data.clone(), file_name.to_string()));
        if let Err(e) = runtime.register_host_api(host.clone()) {
            diagnostics.push(format!("host API error for {file_type}: {e}"));
            continue;
        }

        // Load the framework (init + type init + includes) with no rules.
        // Only include the type init script that matches this file type.
        let type_init: Vec<(String, String)> = snapshot
            .type_init_scripts
            .iter()
            .filter(|(ft, _)| ft == file_type)
            .cloned()
            .collect();
        let framework_snapshot = DatabaseSnapshot {
            rules: Vec::new(),
            init_script: snapshot.init_script.clone(),
            type_init_scripts: type_init,
            include_scripts: snapshot.include_scripts.clone(),
        };

        if let Err(e) = runtime.load_database(&framework_snapshot) {
            diagnostics.push(format!("load_database error for {file_type}: {e}"));
            continue;
        }

        // Initialize the runtime (execute type init scripts).
        let host_ref: &dyn diec_rules::host_api::HostApi = &*host;
        if let Err(e) = runtime.init(host_ref) {
            diagnostics.push(format!("init error for {file_type}: {e}"));
            continue;
        }

        // Evaluate each rule in an isolated scope.
        for rule in rules {
            if cancel.is_cancelled() {
                return Err(ScanError::Cancelled);
            }

            match runtime.evaluate_rule_source(&rule.path, &rule.source, cancel) {
                Ok(results) => {
                    for result in results {
                        detections.push(ScanDetection {
                            file_type: rule.file_type.clone(),
                            type_name: result.type_name,
                            name: result.name,
                            version: if result.version.is_empty() {
                                None
                            } else {
                                Some(result.version)
                            },
                            options: if result.options.is_empty() {
                                None
                            } else {
                                Some(result.options)
                            },
                        });
                    }
                }
                Err(e) => {
                    diagnostics.push(format!("{}: {}", rule.path, e));
                }
            }
        }

        runtime.shutdown();
    }

    Ok(ScanResult {
        path: file_name.to_string(),
        detections,
        diagnostics,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::database::DatabaseBuilder;

    fn db_root() -> String {
        let manifest = env!("CARGO_MANIFEST_DIR");
        let root = std::path::Path::new(manifest)
            .parent()
            .and_then(|p| p.parent())
            .expect("workspace root");
        root.join("upstream/Detect-It-Easy/db")
            .to_str()
            .expect("utf-8 path")
            .to_string()
    }

    #[test]
    fn scan_7z_signature() {
        let db_path = db_root();
        let database = match DatabaseBuilder::new(&db_path).build() {
            Ok(db) => db,
            Err(_) => {
                eprintln!("Skipping: upstream database not found");
                return;
            }
        };

        // 7z magic: 37 7A BC AF 27 1C + version bytes
        let mut data = vec![0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C, 0x00, 0x04];
        data.resize(64, 0);

        let cancel = CancellationToken::new();
        let result = scan_bytes(&database, "test.7z", data, &cancel).unwrap();

        let found = result.detections.iter().any(|d| d.name == "7-Zip");
        assert!(
            found,
            "Expected 7-Zip detection, got: {:?}",
            result.detections
        );
    }

    #[test]
    fn scan_bzip_signature() {
        let db_path = db_root();
        let database = match DatabaseBuilder::new(&db_path).build() {
            Ok(db) => db,
            Err(_) => {
                eprintln!("Skipping: upstream database not found");
                return;
            }
        };

        // BZip2 magic: "BZh" + level digit + block magic 314159265359
        let mut data = b"BZh9".to_vec();
        data.extend_from_slice(&[0x31, 0x41, 0x59, 0x26, 0x53, 0x59]);
        data.resize(64, 0);

        let cancel = CancellationToken::new();
        let result = scan_bytes(&database, "test.bz2", data, &cancel).unwrap();

        let found = result
            .detections
            .iter()
            .any(|d| d.name.contains("BZip") || d.name.contains("bzip"));
        assert!(
            found,
            "Expected BZip detection, got: {:?}",
            result.detections
        );
    }

    #[test]
    fn scan_random_data_no_false_positive() {
        let db_path = db_root();
        let database = match DatabaseBuilder::new(&db_path).build() {
            Ok(db) => db,
            Err(_) => {
                eprintln!("Skipping: upstream database not found");
                return;
            }
        };

        // Random data that shouldn't match any specific format.
        let data: Vec<u8> = (0..128).map(|i| (i * 7 + 13) as u8).collect();

        let cancel = CancellationToken::new();
        let result = scan_bytes(&database, "random.bin", data, &cancel).unwrap();

        // Random data should not produce specific format detections.
        let has_specific = result
            .detections
            .iter()
            .any(|d| d.name == "7-Zip" || d.name == "GZIP" || d.name == "BZip");
        assert!(
            !has_specific,
            "Random data should not produce specific detections: {:?}",
            result.detections
        );
    }

    #[test]
    fn scan_jpeg_signature() {
        let db_path = db_root();
        let database = match DatabaseBuilder::new(&db_path).build() {
            Ok(db) => db,
            Err(_) => {
                eprintln!("Skipping: upstream database not found");
                return;
            }
        };

        // JPEG magic: FF D8 FF E0 + JFIF
        let mut data = vec![
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
        ];
        data.resize(64, 0);

        let cancel = CancellationToken::new();
        let result = scan_bytes(&database, "test.jpg", data, &cancel).unwrap();

        let found = result
            .detections
            .iter()
            .any(|d| d.name.contains("JPEG") || d.name.contains("jpeg"));
        assert!(
            found,
            "Expected JPEG detection, got: {:?}",
            result.detections
        );
    }
}
