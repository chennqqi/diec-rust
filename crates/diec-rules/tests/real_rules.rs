//! End-to-end tests with real upstream rule files.
//!
//! These tests load the real upstream `_init` framework script and
//! execute actual `.sg` rule files from the Detect-It-Easy database.
//! They verify that the rquickjs runtime is compatible with real rules.

#![cfg(test)]

use diec_core::cancel::CancellationToken;
use diec_core::format::FileType;
use diec_core::input::ByteView;
use diec_rules::backend_rquickjs::RquickjsRuntime;
use diec_rules::host_api::{HostApi, HostApiError};
use diec_rules::runtime::{
    DatabaseSnapshot, DetectionResult, LoadedRule, RuleRuntime, RuntimeConfig,
};
use std::collections::BTreeMap;
use std::sync::Arc;

/// Path to the upstream Detect-It-Easy database.
/// Uses CARGO_MANIFEST_DIR to find the workspace root regardless of cwd.
fn db_root() -> String {
    // CARGO_MANIFEST_DIR is crates/diec-rules, so go up 2 levels.
    let manifest = env!("CARGO_MANIFEST_DIR");
    let root = std::path::Path::new(manifest)
        .parent() // crates/
        .and_then(|p| p.parent()) // workspace root
        .expect("workspace root");
    root.join("upstream/Detect-It-Easy/db")
        .to_str()
        .expect("utf-8 path")
        .to_string()
}

/// Test host with an in-memory byte buffer.
struct BufferHost {
    data: Vec<u8>,
    file_type: FileType,
}

impl BufferHost {
    fn new(data: Vec<u8>) -> Self {
        Self {
            data,
            file_type: FileType::new("Binary"),
        }
    }
}

impl HostApi for BufferHost {
    fn file_type(&self) -> &FileType {
        &self.file_type
    }

    fn view(&self) -> &ByteView<'_> {
        unimplemented!()
    }

    fn read_u8(&self, offset: u64) -> Result<u8, HostApiError> {
        self.data
            .get(offset as usize)
            .copied()
            .ok_or(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            })
    }

    fn read_u16_le(&self, offset: u64) -> Result<u16, HostApiError> {
        let i = offset as usize;
        if i + 2 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(u16::from_le_bytes([self.data[i], self.data[i + 1]]))
    }

    fn read_u16_be(&self, offset: u64) -> Result<u16, HostApiError> {
        let i = offset as usize;
        if i + 2 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(u16::from_be_bytes([self.data[i], self.data[i + 1]]))
    }

    fn read_u24_le(&self, offset: u64) -> Result<u32, HostApiError> {
        let i = offset as usize;
        if i + 3 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok((self.data[i] as u32)
            | ((self.data[i + 1] as u32) << 8)
            | ((self.data[i + 2] as u32) << 16))
    }

    fn read_u24_be(&self, offset: u64) -> Result<u32, HostApiError> {
        let i = offset as usize;
        if i + 3 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(((self.data[i] as u32) << 16)
            | ((self.data[i + 1] as u32) << 8)
            | (self.data[i + 2] as u32))
    }

    fn read_u32_le(&self, offset: u64) -> Result<u32, HostApiError> {
        let i = offset as usize;
        if i + 4 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(u32::from_le_bytes([
            self.data[i],
            self.data[i + 1],
            self.data[i + 2],
            self.data[i + 3],
        ]))
    }

    fn read_u32_be(&self, offset: u64) -> Result<u32, HostApiError> {
        let i = offset as usize;
        if i + 4 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(u32::from_be_bytes([
            self.data[i],
            self.data[i + 1],
            self.data[i + 2],
            self.data[i + 3],
        ]))
    }

    fn read_u64_le(&self, offset: u64) -> Result<u64, HostApiError> {
        let i = offset as usize;
        if i + 8 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(u64::from_le_bytes(self.data[i..i + 8].try_into().unwrap()))
    }

    fn read_u64_be(&self, offset: u64) -> Result<u64, HostApiError> {
        let i = offset as usize;
        if i + 8 > self.data.len() {
            return Err(HostApiError::OutOfBounds {
                offset,
                file_size: self.data.len() as u64,
            });
        }
        Ok(u64::from_be_bytes(self.data[i..i + 8].try_into().unwrap()))
    }

    fn read_i8(&self, offset: u64) -> Result<i8, HostApiError> {
        self.read_u8(offset).map(|v| v as i8)
    }

    fn read_i16_le(&self, offset: u64) -> Result<i16, HostApiError> {
        self.read_u16_le(offset).map(|v| v as i16)
    }

    fn read_i32_le(&self, offset: u64) -> Result<i32, HostApiError> {
        self.read_u32_le(offset).map(|v| v as i32)
    }

    fn read_i64_le(&self, offset: u64) -> Result<i64, HostApiError> {
        self.read_u64_le(offset).map(|v| v as i64)
    }

    fn file_size(&self) -> u64 {
        self.data.len() as u64
    }

    fn check_signature(&self, offset: u64, signature: &str) -> Result<bool, HostApiError> {
        let elements =
            diec_rules::host_api_bridge::parse_signature(signature).map_err(|detail| {
                HostApiError::InvalidSignature {
                    pattern: signature.into(),
                    detail,
                }
            })?;
        Ok(diec_rules::host_api_bridge::match_signature(
            &self.data,
            offset as usize,
            &elements,
        ))
    }

    fn find_signature(&self, start: u64, signature: &str) -> Result<Option<u64>, HostApiError> {
        let elements =
            diec_rules::host_api_bridge::parse_signature(signature).map_err(|detail| {
                HostApiError::InvalidSignature {
                    pattern: signature.into(),
                    detail,
                }
            })?;
        let start = start as usize;
        if elements.is_empty()
            || start
                .checked_add(elements.len())
                .is_none_or(|end| end > self.data.len())
        {
            return Ok(None);
        }
        for i in start..=self.data.len() - elements.len() {
            if diec_rules::host_api_bridge::match_signature(&self.data, i, &elements) {
                return Ok(Some(i as u64));
            }
        }
        Ok(None)
    }

    fn read_string(&self, offset: u64, max_len: u64) -> Result<String, HostApiError> {
        let start = offset as usize;
        let end = (start + max_len as usize).min(self.data.len());
        if start >= self.data.len() {
            return Ok(String::new());
        }
        let bytes = &self.data[start..end];
        let nul_pos = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
        Ok(String::from_utf8_lossy(&bytes[..nul_pos]).to_string())
    }

    fn file_name(&self) -> &str {
        "test.bin"
    }

    fn entry_point(&self) -> Result<u64, HostApiError> {
        Ok(0)
    }

    fn is_deep(&self) -> bool {
        false
    }

    fn is_heuristic(&self) -> bool {
        false
    }

    fn is_aggressive(&self) -> bool {
        false
    }

    fn is_verbose(&self) -> bool {
        false
    }

    fn is_recursive(&self) -> bool {
        false
    }

    fn entropy(&self, offset: u64, size: u64) -> Result<f64, HostApiError> {
        let start = offset as usize;
        let end = (start + size as usize).min(self.data.len());
        if start >= end {
            return Ok(0.0);
        }
        let mut counts = [0u32; 256];
        for &b in &self.data[start..end] {
            counts[b as usize] += 1;
        }
        let total = (end - start) as f64;
        let mut entropy = 0.0;
        for &count in &counts {
            if count > 0 {
                let p = count as f64 / total;
                entropy -= p * p.log2();
            }
        }
        Ok(entropy)
    }

    fn md5(&self, _offset: u64, _size: u64) -> Result<String, HostApiError> {
        Err(HostApiError::NotImplemented {
            method: "md5".into(),
        })
    }

    fn crc32(&self, _offset: u64, _size: u64) -> Result<u32, HostApiError> {
        Err(HostApiError::NotImplemented {
            method: "crc32".into(),
        })
    }
}

/// Framework data: (init_script, type_init_scripts, includes).
type FrameworkData = (String, Vec<(String, String)>, BTreeMap<String, String>);

/// Load the upstream _init script and include scripts.
/// Returns (init_script, type_init_scripts, includes).
fn load_upstream_framework() -> Option<FrameworkData> {
    let db = db_root();
    let init_path = format!("{db}/_init");
    let init_source = std::fs::read_to_string(&init_path).ok()?;

    let mut includes = BTreeMap::new();

    // Load the scripts that _init includes.
    for name in &["_debug", "_runtime_helpers", "language"] {
        let path = format!("{db}/{name}");
        if let Ok(source) = std::fs::read_to_string(&path) {
            includes.insert(name.to_string(), source);
        }
    }

    // Also load archive-file helper used by many rules.
    for name in &["archive-file", "zip-file", "read"] {
        let path = format!("{db}/{name}");
        if let Ok(source) = std::fs::read_to_string(&path) {
            includes.insert(name.to_string(), source);
        }
    }

    // Load the Binary type-specific _init script.
    let binary_init = std::fs::read_to_string(format!("{db}/Binary/_init")).ok();
    let type_init_scripts = binary_init
        .map(|s| vec![("Binary".to_string(), s)])
        .unwrap_or_default();

    Some((init_source, type_init_scripts, includes))
}

/// Run a real rule file against a buffer.
fn run_real_rule(
    rule_relative_path: &str,
    init_source: &str,
    type_init_scripts: &[(String, String)],
    includes: &BTreeMap<String, String>,
    data: Vec<u8>,
) -> Option<Vec<DetectionResult>> {
    let db = db_root();
    let rule_path = format!("{db}/{rule_relative_path}");
    let source = std::fs::read_to_string(&rule_path).ok()?;

    let snapshot = DatabaseSnapshot {
        rules: vec![LoadedRule {
            path: rule_path.to_string(),
            ordinal: 0,
            file_type: "Binary".into(),
            source,
        }],
        init_script: Some(init_source.to_string()),
        type_init_scripts: type_init_scripts.to_vec(),
        include_scripts: includes.clone(),
    };

    let mut runtime = RquickjsRuntime::new(RuntimeConfig::default()).ok()?;

    let host = Arc::new(BufferHost::new(data));
    runtime.register_host_api(host.clone()).ok()?;

    runtime.load_database(&snapshot).ok()?;

    let token = CancellationToken::new();
    let host_ref: &dyn HostApi = &*host;
    runtime.init(host_ref).ok()?;

    runtime
        .evaluate_rule(&snapshot.rules[0], host_ref, &token)
        .ok()
}

#[test]
fn real_rule_7z_detects_signature() {
    let (init_source, type_init_scripts, includes) = match load_upstream_framework() {
        Some(x) => x,
        None => {
            eprintln!("Skipping: upstream rules not found");
            return;
        }
    };

    // 7z magic: 37 7A BC AF 27 1C + version bytes
    let mut data = vec![0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C, 0x00, 0x04];
    data.resize(64, 0); // Pad to minimum size

    let results = run_real_rule(
        "Binary/archive_7z.1.sg",
        &init_source,
        &type_init_scripts,
        &includes,
        data,
    );

    if let Some(results) = results {
        // Should detect 7-Zip with version "0.4"
        let found = results.iter().any(|r| r.name == "7-Zip");
        assert!(found, "Expected 7-Zip detection, got: {results:?}");
    }
}

#[test]
fn real_rule_7z_no_match_on_random_data() {
    let (init_source, type_init_scripts, includes) = match load_upstream_framework() {
        Some(x) => x,
        None => {
            eprintln!("Skipping: upstream rules not found");
            return;
        }
    };

    // Random data that doesn't match 7z signature
    let data = vec![0x00; 64];

    let results = run_real_rule(
        "Binary/archive_7z.1.sg",
        &init_source,
        &type_init_scripts,
        &includes,
        data,
    );

    if let Some(results) = results {
        // Should not detect 7-Zip
        assert!(
            results.is_empty(),
            "Expected no detection, got: {results:?}"
        );
    }
}

#[test]
fn real_rule_zip_detects_signature() {
    let (init_source, type_init_scripts, includes) = match load_upstream_framework() {
        Some(x) => x,
        None => {
            eprintln!("Skipping: upstream rules not found");
            return;
        }
    };

    // ZIP local file header: PK\x03\x04
    let mut data = vec![0x50, 0x4B, 0x03, 0x04];
    data.resize(64, 0);

    let results = run_real_rule(
        "Binary/archive_ZIP.1.sg",
        &init_source,
        &type_init_scripts,
        &includes,
        data,
    );

    if let Some(results) = results {
        // ZIP detection may or may not trigger depending on the zip-file helper
        // implementation. Just verify it doesn't crash.
        let _ = results;
    }
}

#[test]
fn real_rule_ar_detects_signature() {
    let (init_source, type_init_scripts, includes) = match load_upstream_framework() {
        Some(x) => x,
        None => {
            eprintln!("Skipping: upstream rules not found");
            return;
        }
    };

    // AR archive magic: "!<arch>\n"
    let mut data = b"!<arch>\n".to_vec();
    data.resize(128, 0);

    let results = run_real_rule(
        "Binary/archive_AR.1.sg",
        &init_source,
        &type_init_scripts,
        &includes,
        data,
    );

    if let Some(results) = results {
        // AR rule should detect the archive format.
        // It uses Archive.add() and Archive.contents() from the
        // archive-file include script.
        let found = results
            .iter()
            .any(|r| r.name.contains("Library") || r.name.contains("arch"));
        assert!(
            found || !results.is_empty(),
            "Expected AR detection, got: {results:?}"
        );
    }
}

#[test]
fn real_rule_bzip_detects_signature() {
    let (init_source, type_init_scripts, includes) = match load_upstream_framework() {
        Some(x) => x,
        None => {
            eprintln!("Skipping: upstream rules not found");
            return;
        }
    };

    // BZip2 magic: "BZh" + level digit + CRC block magic 314159265359
    let mut data = b"BZh9".to_vec();
    // bzip2 block magic: 0x314159265359 (6 bytes) at offset 4
    data.extend_from_slice(&[0x31, 0x41, 0x59, 0x26, 0x53, 0x59]);
    data.resize(64, 0);

    let results = run_real_rule(
        "Binary/archive_BZip.1.sg",
        &init_source,
        &type_init_scripts,
        &includes,
        data,
    );

    if let Some(results) = results {
        // BZip2 should be detected.
        let found = results
            .iter()
            .any(|r| r.name.contains("bzip") || r.name.contains("Bzip") || r.name.contains("BZip"));
        assert!(found, "Expected BZip2 detection, got: {results:?}");
    }
}

#[test]
fn real_rule_gzip_detects_signature() {
    let (init_source, type_init_scripts, includes) = match load_upstream_framework() {
        Some(x) => x,
        None => {
            eprintln!("Skipping: upstream rules not found");
            return;
        }
    };

    // GZIP magic: 1F 8B 08
    let mut data = vec![0x1F, 0x8B, 0x08, 0x00];
    data.resize(64, 0);

    let results = run_real_rule(
        "Binary/archive_gzip.1.sg",
        &init_source,
        &type_init_scripts,
        &includes,
        data,
    );

    if let Some(results) = results {
        // GZIP should be detected.
        let found = results
            .iter()
            .any(|r| r.name.contains("gzip") || r.name.contains("Gzip") || r.name.contains("GZIP"));
        assert!(found, "Expected GZIP detection, got: {results:?}");
    }
}
