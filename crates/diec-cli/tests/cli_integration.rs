//! CLI integration tests.
//!
//! These tests invoke the `diec` binary end-to-end against the
//! upstream rule database and verify output and exit codes.

use std::io::Write;
use std::process::Command;

/// Find the upstream database directory.
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

/// Find the built `diec` binary.
fn diec_binary() -> String {
    let manifest = env!("CARGO_MANIFEST_DIR");
    let target = std::path::Path::new(manifest)
        .parent()
        .and_then(|p| p.parent())
        .expect("workspace root")
        .join("target/debug/diec");
    // On Windows, add .exe extension.
    let path = if cfg!(windows) {
        let mut p = target.to_path_buf();
        p.set_extension("exe");
        p
    } else {
        target
    };
    path.to_str().expect("utf-8 path").to_string()
}

/// Write test data to a temp file and return its path.
fn write_temp_file(name: &str, data: &[u8]) -> String {
    let dir = std::env::temp_dir().join("diec_cli_tests");
    std::fs::create_dir_all(&dir).ok();
    let path = dir.join(name);
    let mut f = std::fs::File::create(&path).expect("create temp file");
    f.write_all(data).expect("write temp file");
    path.to_str().expect("utf-8 path").to_string()
}

/// Run the diec binary with the given arguments.
fn run_diec(args: &[&str]) -> (bool, String, String) {
    let bin = diec_binary();
    let output = Command::new(&bin)
        .args(args)
        .output()
        .expect("failed to execute diec");
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    (output.status.success(), stdout, stderr)
}

#[test]
fn cli_scans_7z_file() {
    if !std::path::Path::new(&db_root()).is_dir() {
        eprintln!("Skipping: upstream database not found");
        return;
    }
    if !std::path::Path::new(&diec_binary()).exists() {
        eprintln!("Skipping: diec binary not built");
        return;
    }

    // 7z magic: 37 7A BC AF 27 1C + version bytes
    let mut data = vec![0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C, 0x00, 0x04];
    data.resize(64, 0);
    let path = write_temp_file("test_cli.7z", &data);

    let db = db_root();
    let (success, stdout, stderr) = run_diec(&["--db", &db, &path]);

    assert!(success, "diec should exit 0, stderr: {stderr}");
    assert!(
        stdout.contains("7-Zip"),
        "stdout should contain 7-Zip detection: {stdout}"
    );
}

#[test]
fn cli_json_output() {
    if !std::path::Path::new(&db_root()).is_dir() {
        eprintln!("Skipping: upstream database not found");
        return;
    }
    if !std::path::Path::new(&diec_binary()).exists() {
        eprintln!("Skipping: diec binary not built");
        return;
    }

    let mut data = vec![0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C, 0x00, 0x04];
    data.resize(64, 0);
    let path = write_temp_file("test_cli_json.7z", &data);

    let (success, stdout, _stderr) = run_diec(&["--db", &db_root(), "--output", "json", &path]);

    assert!(success, "diec should exit 0");
    assert!(
        stdout.contains("\"7-Zip\""),
        "JSON should contain 7-Zip: {stdout}"
    );
    assert!(
        stdout.contains("\"detections\""),
        "JSON should have detections array: {stdout}"
    );
    assert!(
        stdout.trim_start().starts_with('{'),
        "JSON should start with {{: {stdout}"
    );
}

#[test]
fn cli_version_flag() {
    if !std::path::Path::new(&diec_binary()).exists() {
        eprintln!("Skipping: diec binary not built");
        return;
    }

    let (success, stdout, _stderr) = run_diec(&["--version"]);
    assert!(success);
    assert!(stdout.starts_with("diec "), "version output: {stdout}");
}

#[test]
fn cli_help_flag() {
    if !std::path::Path::new(&diec_binary()).exists() {
        eprintln!("Skipping: diec binary not built");
        return;
    }

    let (success, _stdout, stderr) = run_diec(&["--help"]);
    assert!(success);
    assert!(
        stderr.contains("Usage:"),
        "help should contain Usage: {stderr}"
    );
}

#[test]
fn cli_no_args_exits_with_usage_error() {
    if !std::path::Path::new(&diec_binary()).exists() {
        eprintln!("Skipping: diec binary not built");
        return;
    }

    let (success, _stdout, stderr) = run_diec(&[]);
    assert!(!success, "diec with no args should fail");
    assert!(
        stderr.contains("no input files") || stderr.contains("Usage:"),
        "stderr should mention no input files: {stderr}"
    );
}

#[test]
fn cli_scans_bzip2_file() {
    if !std::path::Path::new(&db_root()).is_dir() {
        eprintln!("Skipping: upstream database not found");
        return;
    }
    if !std::path::Path::new(&diec_binary()).exists() {
        eprintln!("Skipping: diec binary not built");
        return;
    }

    // BZip2 magic: "BZh" + level + block magic
    let mut data = b"BZh9".to_vec();
    data.extend_from_slice(&[0x31, 0x41, 0x59, 0x26, 0x53, 0x59]);
    data.resize(64, 0);
    let path = write_temp_file("test_cli.bz2", &data);

    let db = db_root();
    let (success, stdout, stderr) = run_diec(&["--db", &db, &path]);

    assert!(success, "diec should exit 0, stderr: {stderr}");
    assert!(
        stdout.to_lowercase().contains("bzip"),
        "stdout should contain BZip detection: {stdout}"
    );
}
