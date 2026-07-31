//! Scan orchestration: run rules against file bytes and collect results.
//!
//! The scanner creates a rule runtime per rule, loads the database
//! framework (init + includes), and evaluates each rule in isolation.
//! Results are aggregated into a `ScanResult`.

use crate::database::Database;
use crate::host::BufferHost;
use diec_core::cancel::CancellationToken;
use diec_rules::backend_rquickjs::RquickjsRuntime;
use diec_rules::runtime::{DatabaseSnapshot, RuleRuntime, RuntimeConfig};
use std::sync::Arc;

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
/// Each rule is evaluated in its own runtime instance to avoid
/// global scope pollution between rules.
pub fn scan_bytes(
    database: &Database,
    file_name: &str,
    data: Vec<u8>,
    cancel: &CancellationToken,
) -> Result<ScanResult, ScanError> {
    let snapshot = database.snapshot();
    let mut detections = Vec::new();
    let mut diagnostics = Vec::new();

    for rule in &snapshot.rules {
        if cancel.is_cancelled() {
            return Err(ScanError::Cancelled);
        }

        // Create a fresh runtime for each rule.
        let mut runtime = match RquickjsRuntime::new(RuntimeConfig::default()) {
            Ok(rt) => rt,
            Err(e) => {
                diagnostics.push(format!("runtime create error: {e}"));
                continue;
            }
        };

        // Create a host with the file data.
        let host = Arc::new(BufferHost::new(data.clone(), file_name.to_string()));
        if let Err(e) = runtime.register_host_api(host.clone()) {
            diagnostics.push(format!("host API error: {e}"));
            continue;
        }

        // Load a single-rule snapshot with the framework scripts.
        // Only include the type init script that matches the rule's file type.
        let rule_type_init: Vec<(String, String)> = snapshot
            .type_init_scripts
            .iter()
            .filter(|(ft, _)| ft == &rule.file_type)
            .cloned()
            .collect();
        let single_snapshot = DatabaseSnapshot {
            rules: vec![rule.clone()],
            init_script: snapshot.init_script.clone(),
            type_init_scripts: rule_type_init,
            include_scripts: snapshot.include_scripts.clone(),
        };

        if let Err(e) = runtime.load_database(&single_snapshot) {
            // Skip rules that fail to load (e.g. syntax errors).
            let _ = e;
            continue;
        }

        // Initialize the runtime (execute init scripts).
        let host_ref: &dyn diec_rules::host_api::HostApi = &*host;
        if let Err(e) = runtime.init(host_ref) {
            diagnostics.push(format!("init error in {}: {e}", rule.path));
            continue;
        }

        // Evaluate the rule.
        match runtime.evaluate_rule(rule, host_ref, cancel) {
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
}
