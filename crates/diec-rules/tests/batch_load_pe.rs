//! Batch load test for PE rules.
//!
//! PE rules require a PE-specific host API (PE_Script) which is not
//! yet implemented. This test verifies that PE rules can be loaded
//! (parsed) without the PE-specific methods, identifying which rules
//! have syntax errors or use unsupported features.

#![cfg(test)]

use diec_core::format::FileType;
use diec_core::input::ByteView;
use diec_rules::backend_rquickjs::RquickjsRuntime;
use diec_rules::host_api::{HostApi, HostApiError};
use diec_rules::runtime::{DatabaseSnapshot, LoadedRule, RuleRuntime, RuntimeConfig};
use std::collections::BTreeMap;
use std::sync::Arc;

/// Dummy host that returns empty/zero values for all methods.
struct DummyHost {
    file_type: FileType,
}

impl DummyHost {
    fn new() -> Self {
        Self {
            file_type: FileType::new("PE"),
        }
    }
}

impl HostApi for DummyHost {
    fn file_type(&self) -> &FileType {
        &self.file_type
    }
    fn view(&self) -> &ByteView<'_> {
        unimplemented!()
    }
    fn read_u8(&self, _o: u64) -> Result<u8, HostApiError> {
        Ok(0)
    }
    fn read_u16_le(&self, _o: u64) -> Result<u16, HostApiError> {
        Ok(0)
    }
    fn read_u16_be(&self, _o: u64) -> Result<u16, HostApiError> {
        Ok(0)
    }
    fn read_u24_le(&self, _o: u64) -> Result<u32, HostApiError> {
        Ok(0)
    }
    fn read_u24_be(&self, _o: u64) -> Result<u32, HostApiError> {
        Ok(0)
    }
    fn read_u32_le(&self, _o: u64) -> Result<u32, HostApiError> {
        Ok(0)
    }
    fn read_u32_be(&self, _o: u64) -> Result<u32, HostApiError> {
        Ok(0)
    }
    fn read_u64_le(&self, _o: u64) -> Result<u64, HostApiError> {
        Ok(0)
    }
    fn read_u64_be(&self, _o: u64) -> Result<u64, HostApiError> {
        Ok(0)
    }
    fn read_i8(&self, o: u64) -> Result<i8, HostApiError> {
        self.read_u8(o).map(|v| v as i8)
    }
    fn read_i16_le(&self, o: u64) -> Result<i16, HostApiError> {
        self.read_u16_le(o).map(|v| v as i16)
    }
    fn read_i32_le(&self, o: u64) -> Result<i32, HostApiError> {
        self.read_u32_le(o).map(|v| v as i32)
    }
    fn read_i64_le(&self, o: u64) -> Result<i64, HostApiError> {
        self.read_u64_le(o).map(|v| v as i64)
    }
    fn file_size(&self) -> u64 {
        0
    }
    fn check_signature(&self, _o: u64, _s: &str) -> Result<bool, HostApiError> {
        Ok(false)
    }
    fn find_signature(&self, _o: u64, _s: &str) -> Result<Option<u64>, HostApiError> {
        Ok(None)
    }
    fn read_string(&self, _o: u64, _m: u64) -> Result<String, HostApiError> {
        Ok(String::new())
    }
    fn file_name(&self) -> &str {
        "dummy.exe"
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
    fn entropy(&self, _o: u64, _s: u64) -> Result<f64, HostApiError> {
        Ok(0.0)
    }
    fn md5(&self, _o: u64, _s: u64) -> Result<String, HostApiError> {
        Err(HostApiError::NotImplemented {
            method: "md5".into(),
        })
    }
    fn crc32(&self, _o: u64, _s: u64) -> Result<u32, HostApiError> {
        Err(HostApiError::NotImplemented {
            method: "crc32".into(),
        })
    }
}

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

fn load_all_include_scripts(db: &str) -> BTreeMap<String, String> {
    let mut includes = BTreeMap::new();
    if let Ok(entries) = std::fs::read_dir(db) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file()
                && path.extension().is_none()
                && let Some(name) = path.file_name().and_then(|n| n.to_str())
                && let Ok(source) = std::fs::read_to_string(&path)
            {
                includes.insert(name.to_string(), source);
            }
        }
    }
    // Load files in subdirectories: db/<dir>/<dir>
    if let Ok(entries) = std::fs::read_dir(db) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir()
                && let Some(dir_name) = path.file_name().and_then(|n| n.to_str())
            {
                let inner = path.join(dir_name);
                if inner.is_file()
                    && !includes.contains_key(dir_name)
                    && let Ok(source) = std::fs::read_to_string(&inner)
                {
                    includes.insert(dir_name.to_string(), source);
                }
                if let Ok(sub_entries) = std::fs::read_dir(&path) {
                    for sub_entry in sub_entries.flatten() {
                        let sub_path = sub_entry.path();
                        if sub_path.is_file()
                            && sub_path.extension().is_none()
                            && let Some(name) = sub_path.file_name().and_then(|n| n.to_str())
                            && !includes.contains_key(name)
                            && let Ok(source) = std::fs::read_to_string(&sub_path)
                        {
                            includes.insert(name.to_string(), source);
                        }
                    }
                }
            }
        }
    }
    includes
}

#[test]
fn batch_load_pe_rules() {
    let db = db_root();
    let pe_dir = format!("{db}/PE");

    let init_script = std::fs::read_to_string(format!("{db}/_init")).ok();

    // PE _init requires PE-specific host API methods (getNumberOfSections, etc.)
    // which are not yet implemented. We skip it for now and only test rule parsing.
    let includes = load_all_include_scripts(&db);

    // Collect all .sg files in PE directory.
    let mut rules = Vec::new();
    let mut ordinal = 0u64;

    if let Ok(entries) = std::fs::read_dir(&pe_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("sg")
                && let Ok(source) = std::fs::read_to_string(&path)
            {
                let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("?");
                rules.push(LoadedRule {
                    path: format!("PE/{name}"),
                    ordinal,
                    file_type: "PE".into(),
                    source,
                });
                ordinal += 1;
            }
        }
    }

    if rules.is_empty() {
        eprintln!("Skipping: no PE rules found");
        return;
    }

    eprintln!("Found {} PE rules", rules.len());

    let mut success_count = 0;
    let mut fail_count = 0;
    let mut failures = Vec::new();

    for rule in &rules {
        let snapshot = DatabaseSnapshot {
            rules: vec![rule.clone()],
            init_script: init_script.clone(),
            type_init_scripts: Vec::new(), // No PE _init yet
            include_scripts: includes.clone(),
        };

        let mut runtime = match RquickjsRuntime::new(RuntimeConfig::default()) {
            Ok(rt) => rt,
            Err(e) => {
                fail_count += 1;
                failures.push((rule.path.clone(), format!("runtime create: {e}")));
                continue;
            }
        };

        // Register dummy host (provides Binary but not PE-specific methods).
        let dummy_host = Arc::new(DummyHost::new());
        if let Err(e) = runtime.register_host_api(dummy_host.clone()) {
            fail_count += 1;
            failures.push((rule.path.clone(), format!("register_host_api: {e}")));
            continue;
        }

        match runtime.load_database(&snapshot) {
            Ok(()) => {
                success_count += 1;
            }
            Err(e) => {
                fail_count += 1;
                failures.push((rule.path.clone(), format!("{e}")));
            }
        }
    }

    eprintln!("Success: {success_count}, Fail: {fail_count}");

    let show = failures.len().min(20);
    for (path, error) in failures.iter().take(show) {
        eprintln!("FAIL: {path} -> {error}");
    }

    let success_ratio = success_count as f64 / rules.len() as f64;
    eprintln!("Success ratio: {:.1}%", success_ratio * 100.0);

    // PE rules use PE-specific methods at the top level (outside detect()),
    // so many will fail. We expect at least 50% to parse successfully.
    assert!(
        success_ratio >= 0.50,
        "Expected at least 50% of PE rules to load, got {:.1}% ({}/{})",
        success_ratio * 100.0,
        success_count,
        rules.len()
    );
}
