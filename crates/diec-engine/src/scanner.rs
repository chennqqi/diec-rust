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
/// Upstream DIE's `scanProcess` uses an if-else-if chain that picks the
/// first matching format and calls `_processDetect` with that specific
/// file type. `checkFileType` then ensures only rules whose `fileType`
/// matches the detected format are executed. Binary rules (FT_UNKNOWN)
/// do NOT run when a specific format is detected.
///
/// This function mirrors that logic. For executable formats (PE, ELF,
/// MACH, MACHOFAT), only the format-specific rules are run — Binary
/// rules are excluded to avoid false positives from magic byte
/// ambiguities (e.g., CAFEBABE is both Mach-O FAT and Java Class).
///
/// For non-executable formats (JPEG, PNG, PDF, ZIP, etc.), both
/// format-specific and Binary rules are run, because the format-specific
/// host APIs (Jpeg, Pdf, etc.) are not yet implemented and the Binary
/// rules provide the actual detection logic using the generic API.
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

    // Collect all detected format names.
    let detected: Vec<&str> = candidates
        .iter()
        .map(|c| c.file_type.name.as_str())
        .collect();

    // Executable formats: only run format-specific rules (no Binary).
    // This prevents false positives like CAFEBABE matching both Mach-O FAT
    // and Java Class File.
    if detected.iter().any(|&n| n == "PE32" || n == "PE64") {
        return vec!["PE"];
    }
    if detected
        .iter()
        .any(|&n| n == "ELF32" || n == "ELF64" || n == "ELF")
    {
        return vec!["ELF"];
    }
    if detected
        .iter()
        .any(|&n| n == "Mach-O 32" || n == "Mach-O" || n == "Mach-O 64")
    {
        return vec!["MACH"];
    }
    // Java Class must be checked BEFORE Mach-O FAT because CAFEBABE is
    // the magic for both. The JavaClassProbe validates major version >= 45,
    // so a real Java Class file will match both probes, but Java Class is
    // the correct detection. A real Mach-O FAT file (nfat_arch < 45) will
    // only match the Mach-O probe.
    // Binary rules are included because the JavaClass-specific host API
    // is not yet implemented, and the Binary rule (format_bin.Java.1.sg)
    // provides detection via the generic API.
    if detected.contains(&"Java Class") {
        return vec!["JavaClass", "Binary"];
    }
    if detected
        .iter()
        .any(|&n| n == "Mach-O FAT" || n == "Mach-O FAT64")
    {
        return vec!["MACHOFAT"];
    }

    // Non-executable formats: run both format-specific and Binary rules.
    // The format-specific host APIs are not yet implemented, so Binary
    // rules provide the actual detection logic.
    let mut types: Vec<&'static str> = Vec::new();

    if detected.contains(&"MSDOS") {
        types.push("MSDOS");
    }
    if detected.contains(&"APK") {
        types.push("APK");
    }
    if detected.contains(&"JAR") {
        types.push("JAR");
    }
    if detected.contains(&"ZIP") {
        types.push("ZIP");
    }
    if detected.contains(&"DEX") {
        types.push("DEX");
    }
    if detected.contains(&"PDF") {
        types.push("PDF");
    }
    if detected.contains(&"CFBF") {
        types.push("CFBF");
    }
    if detected.contains(&"RAR") {
        types.push("RAR");
    }
    if detected.iter().any(|&n| n == "ISO 9660" || n == "ISO9660") {
        types.push("ISO9660");
    }
    if detected.contains(&"JPEG") {
        types.push("JPEG");
    }
    if detected.contains(&"PNG") {
        types.push("PNG");
    }
    if detected
        .iter()
        .any(|&n| n == "Python Compiled" || n == "PYC")
    {
        types.push("PYC");
    }
    if detected.contains(&"NPM") {
        types.push("NPM");
    }

    // Always include Binary rules for non-executable formats.
    types.push("Binary");

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

/// Return all known rule file types for --alltypes mode.
/// This matches upstream bIsAllTypesScan behavior where all format
/// rules are evaluated regardless of detected format.
fn all_rule_types() -> Vec<&'static str> {
    vec![
        "PE",
        "ELF",
        "MACH",
        "MACHOFAT",
        "MSDOS",
        "Binary",
        "APK",
        "JAR",
        "ZIP",
        "RAR",
        "DEX",
        "PDF",
        "CFBF",
        "ISO9660",
        "JPEG",
        "PNG",
        "PYC",
        "NPM",
        "JavaClass",
    ]
}

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
    flags: crate::host::ScanFlags,
    cancel: &CancellationToken,
) -> Result<ScanResult, ScanError> {
    let data = std::fs::read(path).map_err(|e| ScanError::Input {
        path: path.to_string(),
        detail: e.to_string(),
    })?;

    scan_bytes(database, path, data, flags, cancel)
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
    flags: crate::host::ScanFlags,
    cancel: &CancellationToken,
) -> Result<ScanResult, ScanError> {
    let snapshot = database.snapshot();
    let mut detections = Vec::new();
    let mut diagnostics = Vec::new();

    // Detect the file format to determine which rule types to run.
    // With --alltypes, all file type rules are run (matching upstream
    // bIsAllTypesScan behavior: minimal PE32 also reports MSDOS).
    let active_types = if flags.all_types {
        all_rule_types()
    } else {
        detect_rule_types(&data)
    };

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

        // Create a host with the file data and scan flags.
        let host = Arc::new(BufferHost::new(data.clone(), file_name.to_string()).with_flags(flags));
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

    // Apply --hideunknown filter: remove detections with empty or "Unknown" name.
    if flags.hide_unknown {
        detections.retain(|d| !d.name.is_empty() && d.name != "Unknown");
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
        let result = scan_bytes(
            &database,
            "test.7z",
            data,
            crate::host::ScanFlags::default(),
            &cancel,
        )
        .unwrap();

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
        let result = scan_bytes(
            &database,
            "test.bz2",
            data,
            crate::host::ScanFlags::default(),
            &cancel,
        )
        .unwrap();

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
        let result = scan_bytes(
            &database,
            "random.bin",
            data,
            crate::host::ScanFlags::default(),
            &cancel,
        )
        .unwrap();

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
        let result = scan_bytes(
            &database,
            "test.jpg",
            data,
            crate::host::ScanFlags::default(),
            &cancel,
        )
        .unwrap();

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

    #[test]
    fn scan_rar_signature() {
        let db_path = db_root();
        let database = match DatabaseBuilder::new(&db_path).build() {
            Ok(db) => db,
            Err(_) => {
                eprintln!("Skipping: upstream database not found");
                return;
            }
        };

        // RAR v4 signature: Rar!\x1a\x07\x00 (needs >= 64 bytes)
        let mut data: Vec<u8> = vec![
            0x52, 0x61, 0x72, 0x21, 0x1A, 0x07, 0x00, 0xCF, 0x90, 0x73, 0x00, 0x00, 0x0D, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
        ];
        data.resize(64, 0);

        let cancel = CancellationToken::new();
        let result = scan_bytes(
            &database,
            "test.rar",
            data,
            crate::host::ScanFlags::default(),
            &cancel,
        )
        .unwrap();

        let found = result.detections.iter().any(|d| d.name.contains("RAR"));
        assert!(
            found,
            "Expected RAR detection, got: {:?}",
            result.detections
        );
    }

    #[test]
    fn detect_rule_types_elf() {
        let elf_header: Vec<u8> = vec![
            0x7F, 0x45, 0x4C, 0x46, 0x02, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x02, 0x00, 0x3E, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00,
            0x38, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ];

        let types = detect_rule_types(&elf_header);
        assert!(
            types.contains(&"ELF"),
            "Expected ELF in detected types, got: {:?}",
            types
        );
        // ELF is an executable format — Binary rules should NOT run.
        assert!(
            !types.contains(&"Binary"),
            "Binary should not be included for ELF files, got: {:?}",
            types
        );
    }

    #[test]
    fn detect_rule_types_macho_fat() {
        // Mach-O FAT magic is CAFEBABE — same as Java Class File.
        // Binary rules must NOT run to avoid false positive.
        let macho_fat_header: Vec<u8> = vec![0xCA, 0xFE, 0xBA, 0xBE, 0x00, 0x00, 0x00, 0x02];

        let types = detect_rule_types(&macho_fat_header);
        assert!(
            types.contains(&"MACHOFAT"),
            "Expected MACHOFAT in detected types, got: {:?}",
            types
        );
        // Binary rules should NOT run for Mach-O FAT to avoid
        // false positive Java Class File detection (CAFEBABE ambiguity).
        assert!(
            !types.contains(&"Binary"),
            "Binary should not be included for Mach-O FAT files, got: {:?}",
            types
        );
    }

    #[test]
    fn detect_rule_types_jpeg_includes_binary() {
        // JPEG is a non-executable format — Binary rules SHOULD run
        // because the JPEG host API is not yet implemented.
        let jpeg_header: Vec<u8> = vec![
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        ];

        let types = detect_rule_types(&jpeg_header);
        assert!(
            types.contains(&"JPEG"),
            "Expected JPEG in detected types, got: {:?}",
            types
        );
        assert!(
            types.contains(&"Binary"),
            "Binary should be included for JPEG files, got: {:?}",
            types
        );
    }
}
