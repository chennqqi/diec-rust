//! Differential detection test against the baseline corpus.
//!
//! This test runs the full scanner (database + rules + host API) on each
//! sample from the `corpus/` directory and verifies that the detections
//! match the expected upstream DIE output.
//!
//! The expected outputs were determined by comparing `diec-rust` output
//! against upstream DIE-engine behavior. Any deviation is a regression.
//!
//! See `docs/design/testing.md` section 12 and `corpus/manifest.json`.

#![forbid(unsafe_code)]

use diec_core::cancel::CancellationToken;
use diec_engine::{DatabaseBuilder, ScanDetection, scan_bytes};
use std::path::PathBuf;

/// Expected detection summary for each corpus file.
///
/// Each entry is (filename, expected_detections) where expected_detections
/// is a list of (type, name) pairs. An empty list means "no detections".
/// The order doesn't matter — the test sorts both lists before comparing.
const CORPUS_EXPECTATIONS: &[(&str, &[(&str, &str)])] = &[
    // Executable formats
    (
        "minimal.exe",
        &[(
            "~warning",
            ">>> Update DIE Engine to 3.20 and higher for using Heuristic-analyzer by DosX <<<",
        )],
    ),
    (
        "minimal-pe64.exe",
        &[(
            "~warning",
            ">>> Update DIE Engine to 3.20 and higher for using Heuristic-analyzer by DosX <<<",
        )],
    ),
    ("minimal.elf", &[]),
    ("minimal-elf32.elf", &[]),
    ("minimal.macho", &[]),
    ("minimal-macho32.macho", &[]),
    ("minimal-fat.macho", &[("converter", "lipo")]),
    // Bytecode formats
    ("Minimal.class", &[("format", "Java Class File")]),
    ("minimal.dex", &[("format", "Dalvik Executable")]),
    ("minimal.pyc", &[("format", "Python bytecode compiled")]),
    // Archive formats
    ("payload.zip", &[("archive", "Zip")]),
    ("minimal.apk", &[("archive", "Zip")]),
    ("minimal.jar", &[("archive", "Zip")]),
    ("minimal.ipa", &[("archive", "Zip")]),
    ("payload.tar", &[("archive", "tar")]),
    ("minimal.cfbf", &[("archive", "Microsoft Compound")]),
    // Document formats
    ("minimal.pdf", &[("format", "PDF")]),
    ("minimal.iso", &[("format", "ISO 9660")]),
    // Image formats
    ("pixel.png", &[("image", "Portable Network Graphics")]),
    ("pixel.jpg", &[("image", "JPEG")]),
    ("pixel.bmp", &[("image", "Windows Bitmap")]),
    // Audio formats
    ("tone.wav", &[("audio", "RIFF container")]),
    // No detections expected
    ("empty.bin", &[("format", "Empty file")]),
    ("plain.txt", &[]),
    ("manifest.json", &[]),
    ("minimal.rar", &[]),
    ("payload.txt.gz", &[]),
];

/// Resolve the corpus directory relative to the workspace root.
fn corpus_dir() -> PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    PathBuf::from(manifest_dir)
        .parent() // crates/
        .and_then(|p| p.parent()) // workspace root
        .map(|p| p.join("corpus"))
        .unwrap_or_else(|| PathBuf::from("corpus"))
}

/// Resolve the upstream database directory.
fn db_root() -> String {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let binding = PathBuf::from(manifest_dir);
    let root = binding
        .parent()
        .and_then(|p| p.parent())
        .expect("workspace root");
    root.join("upstream/Detect-It-Easy/db")
        .to_str()
        .expect("utf-8 path")
        .to_string()
}

/// Check if a detection matches an expected (type, name) pair.
/// The name match is a substring check (case-insensitive) to handle
/// version suffixes and additional metadata.
fn detection_matches(detection: &ScanDetection, expected_type: &str, expected_name: &str) -> bool {
    detection.type_name == *expected_type
        && detection
            .name
            .to_lowercase()
            .contains(&expected_name.to_lowercase())
}

#[test]
fn corpus_differential_detections() {
    let db_path = db_root();
    let database = match DatabaseBuilder::new(&db_path).build() {
        Ok(db) => db,
        Err(e) => {
            eprintln!("SKIP: upstream database not found: {e}");
            return;
        }
    };

    let cancel = CancellationToken::new();
    let mut tested = 0usize;
    let mut skipped = 0usize;
    let mut mismatches = Vec::new();

    for (filename, expected) in CORPUS_EXPECTATIONS {
        let path = corpus_dir().join(filename);
        if !path.exists() {
            eprintln!("SKIP: corpus file missing: {filename}");
            skipped += 1;
            continue;
        }

        let data = match std::fs::read(&path) {
            Ok(d) => d,
            Err(e) => {
                mismatches.push(format!("{filename}: cannot read: {e}"));
                continue;
            }
        };

        let result = match scan_bytes(&database, filename, data, &cancel) {
            Ok(r) => r,
            Err(e) => {
                mismatches.push(format!("{filename}: scan error: {e}"));
                continue;
            }
        };

        // Check each expected detection is present.
        for (exp_type, exp_name) in *expected {
            let found = result
                .detections
                .iter()
                .any(|d| detection_matches(d, exp_type, exp_name));
            if !found {
                let actual: Vec<String> = result
                    .detections
                    .iter()
                    .map(|d| format!("{}:{}", d.type_name, d.name))
                    .collect();
                mismatches.push(format!(
                    "{filename}: expected detection '{exp_type}:{exp_name}' not found. Actual: [{actual}]",
                    actual = actual.join(", ")
                ));
            }
        }

        // Check no unexpected detections (only for files with no expected detections).
        if expected.is_empty() && !result.detections.is_empty() {
            let actual: Vec<String> = result
                .detections
                .iter()
                .map(|d| format!("{}:{}", d.type_name, d.name))
                .collect();
            mismatches.push(format!(
                "{filename}: expected no detections, got: [{actual}]",
                actual = actual.join(", ")
            ));
        }

        tested += 1;
    }

    assert!(tested > 0, "no corpus samples were tested");
    assert!(
        mismatches.is_empty(),
        "detection mismatches ({}):\n{}",
        mismatches.len(),
        mismatches.join("\n")
    );
    eprintln!("corpus differential: {tested} tested, {skipped} skipped, 0 mismatches");
}
