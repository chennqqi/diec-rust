//! Tauri IPC commands for diec-gui.
//!
//! These commands are the bridge between the React frontend and the
//! `diec-engine` Rust backend. The frontend calls them via
//! `invoke('command_name', { args })`.

use crate::settings::AppSettings;
use crate::state::AppState;
use diec_engine::{ScanDetection, ScanError, ScanFlags, ScanResult, scan_bytes, scan_once};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Instant;

/// Structured error DTO for all IPC commands.
///
/// Replaces bare `String` errors to enable frontend error
/// classification, i18n, and logging. See `docs/design/phase8-gui.md`
/// section "IPC Error Model".
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuiError {
    /// Machine-readable error code (e.g. "DATABASE_LOAD_FAILED").
    pub code: String,
    /// Human-readable message (English, frontend i18n translates).
    pub message: String,
}

impl GuiError {
    /// Create a new `GuiError` with the given code and message.
    pub fn new(code: &str, message: impl Into<String>) -> Self {
        Self {
            code: code.to_string(),
            message: message.into(),
        }
    }
}

impl From<ScanError> for GuiError {
    fn from(e: ScanError) -> Self {
        let (code, message) = match &e {
            ScanError::DatabaseInit { detail } => ("DATABASE_INIT_FAILED", detail.clone()),
            ScanError::HostApi { detail } => ("HOST_API_FAILED", detail.clone()),
            ScanError::RuleEval { path, detail } => {
                ("RULE_EVAL_FAILED", format!("{}: {}", path, detail))
            }
            ScanError::Input { path, detail } => ("INPUT_ERROR", format!("{}: {}", path, detail)),
            ScanError::Cancelled => ("CANCELLED", "Scan cancelled".to_string()),
        };
        Self::new(code, message)
    }
}

/// Scan flags mirroring upstream `XScanEngine::SF_*` and `comboBoxFlags`.
///
/// Field mapping to `diec-engine::ScanFlags`:
/// - `deep`/`heuristic`/`verbose`/`aggressive`/`alltypes`/`hide_unknown`
///   map directly to `ScanFlags` struct fields.
/// - `recursive`/`overlay`/`resources`/`archives`/`first_wrapper_only`
///   control nested-scan behavior in the engine's work-queue; they are
///   passed as scan-options metadata rather than `ScanFlags` struct fields.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanFlagsDto {
    /// Recursive scan (resource/overlay).
    pub recursive: bool,
    /// Deep scan mode.
    pub deep: bool,
    /// Heuristic scan mode.
    pub heuristic: bool,
    /// Verbose output.
    pub verbose: bool,
    /// Aggressive scan mode.
    pub aggressive: bool,
    /// All types scan mode.
    pub alltypes: bool,
    /// Overlay scan.
    pub overlay: bool,
    /// Resources scan.
    pub resources: bool,
    /// Archives scan.
    pub archives: bool,
    /// First wrapper only.
    pub first_wrapper_only: bool,
    /// Hide unknown detections.
    pub hide_unknown: bool,
}

impl From<ScanFlagsDto> for ScanFlags {
    fn from(dto: ScanFlagsDto) -> Self {
        ScanFlags {
            deep: dto.deep,
            heuristic: dto.heuristic,
            verbose: dto.verbose,
            aggressive: dto.aggressive,
            all_types: dto.alltypes,
            hide_unknown: dto.hide_unknown,
        }
    }
}

/// A single detection result, serializable for the frontend.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanDetectionDto {
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

impl From<ScanDetection> for ScanDetectionDto {
    fn from(d: ScanDetection) -> Self {
        Self {
            file_type: d.file_type,
            type_name: d.type_name,
            name: d.name,
            version: d.version,
            options: d.options,
        }
    }
}

/// The result of scanning a single file, serializable for the frontend.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanResultDto {
    /// The file path that was scanned.
    pub path: String,
    /// All detections found.
    pub detections: Vec<ScanDetectionDto>,
    /// Diagnostics (errors, warnings) encountered during scanning.
    pub diagnostics: Vec<String>,
    /// Scan time in milliseconds.
    pub scan_time_ms: u64,
}

impl From<ScanResult> for ScanResultDto {
    fn from(r: ScanResult) -> Self {
        let detections = r.detections.into_iter().map(Into::into).collect();
        Self {
            path: r.path,
            detections,
            diagnostics: r.diagnostics,
            scan_time_ms: 0,
        }
    }
}

/// Progress events streamed to the frontend via Tauri Channel.
///
/// Reserved for 7A-1 streaming scan progress; not yet wired into
/// `scan_file`/`scan_bytes_cmd`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "event", content = "data", rename_all = "snake_case")]
#[allow(dead_code)]
pub enum ScanProgress {
    /// Scan started.
    Started {
        /// File name being scanned.
        file_name: String,
        /// File size in bytes.
        file_size: u64,
    },
    /// Scan progress update.
    Progress {
        /// Current progress (0..=total).
        current: u64,
        /// Total work units.
        total: u64,
        /// Human-readable progress message.
        message: String,
    },
    /// Scan finished successfully.
    Finished {
        /// The scan result.
        result: ScanResultDto,
    },
    /// Scan failed.
    Error {
        /// Error message.
        message: String,
    },
}

/// Signature group for the signature browser tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureGroupDto {
    /// File type name (e.g. "PE", "ELF", "MACH").
    pub file_type: String,
    /// Signatures in this group.
    pub signatures: Vec<SignatureInfoDto>,
}

/// Individual signature info.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureInfoDto {
    /// Signature name.
    pub name: String,
    /// Signature file path relative to database root.
    pub file_path: String,
}

/// Signature source code response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureSourceDto {
    /// Signature source code.
    pub source: String,
    /// Signature file path.
    pub file_path: String,
}

/// Directory scan progress events.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "event", content = "data", rename_all = "snake_case")]
pub enum DirectoryScanProgress {
    /// Directory scan started.
    Started {
        /// Number of files to scan.
        total_files: usize,
    },
    /// A file scan completed.
    FileScanned {
        /// File index (0-based).
        index: usize,
        /// File path.
        file_path: String,
        /// Scan result.
        result: ScanResultDto,
    },
    /// Directory scan finished.
    Finished {
        /// Total number of files scanned.
        total: usize,
    },
    /// Directory scan error.
    Error {
        /// Error message.
        message: String,
    },
}

/// Database info response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseInfoDto {
    /// Database path.
    pub path: String,
    /// Number of loaded rules.
    pub rule_count: usize,
    /// Database version commit SHA.
    pub commit: String,
    /// Database version sync timestamp.
    pub synced_at: String,
}

// ---------------------------------------------------------------------------
// IPC Commands
// ---------------------------------------------------------------------------

/// Resolve the database directory by checking candidate paths in order.
///
/// Candidates: user-configured path (TODO: from settings), then
/// `./db`, then `upstream/Detect-It-Easy/db` (development layout).
fn resolve_db_path() -> String {
    let candidates = ["./db", "upstream/Detect-It-Easy/db"];
    for c in &candidates {
        if std::path::Path::new(c).is_dir() {
            return c.to_string();
        }
    }
    "./db".to_string()
}

/// Scan a file by path.
#[tauri::command]
pub async fn scan_file(
    state: tauri::State<'_, AppState>,
    path: String,
    flags: ScanFlagsDto,
) -> Result<ScanResultDto, GuiError> {
    let db_path = resolve_db_path();
    let db = state
        .database(&db_path)
        .map_err(|e| GuiError::new("DATABASE_LOAD_FAILED", e))?;
    let cancel = state.start_scan();
    let engine_flags: ScanFlags = flags.into();

    let start = Instant::now();
    let result = tokio::task::spawn_blocking({
        let path = path.clone();
        let db = Arc::clone(&db);
        move || scan_once(&db, &path, engine_flags, &cancel)
    })
    .await
    .map_err(|e| GuiError::new("TASK_JOIN_FAILED", e.to_string()))?
    .map_err(GuiError::from)?;

    let mut dto: ScanResultDto = result.into();
    dto.scan_time_ms = start.elapsed().as_millis() as u64;
    Ok(dto)
}

/// Scan a byte buffer (for drag-and-drop or remote content).
#[tauri::command]
pub async fn scan_bytes_cmd(
    state: tauri::State<'_, AppState>,
    file_name: String,
    data: Vec<u8>,
    flags: ScanFlagsDto,
) -> Result<ScanResultDto, GuiError> {
    let db_path = resolve_db_path();
    let db = state
        .database(&db_path)
        .map_err(|e| GuiError::new("DATABASE_LOAD_FAILED", e))?;
    let cancel = state.start_scan();
    let engine_flags: ScanFlags = flags.into();

    let start = Instant::now();
    let result = tokio::task::spawn_blocking({
        let file_name = file_name.clone();
        let db = Arc::clone(&db);
        move || scan_bytes(&db, &file_name, data, engine_flags, &cancel)
    })
    .await
    .map_err(|e| GuiError::new("TASK_JOIN_FAILED", e.to_string()))?
    .map_err(GuiError::from)?;

    let mut dto: ScanResultDto = result.into();
    dto.scan_time_ms = start.elapsed().as_millis() as u64;
    Ok(dto)
}

/// Stop the current scan.
#[tauri::command]
pub async fn stop_scan(state: tauri::State<'_, AppState>) -> Result<(), GuiError> {
    state.stop_scan();
    Ok(())
}

/// List all signatures grouped by file type.
#[tauri::command]
pub async fn list_signatures(
    _state: tauri::State<'_, AppState>,
) -> Result<Vec<SignatureGroupDto>, GuiError> {
    let db_path = resolve_db_path();
    let db_dir = std::path::Path::new(&db_path);
    let mut groups = Vec::new();

    let Ok(entries) = std::fs::read_dir(db_dir) else {
        return Ok(groups);
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let file_type = entry.file_name().to_string_lossy().to_string();
        // Skip non-signature directories (e.g. _icons, .vscode).
        if file_type.starts_with('_') || file_type.starts_with('.') {
            continue;
        }

        let mut sigs = Vec::new();
        if let Ok(sig_entries) = std::fs::read_dir(&path) {
            for sig_entry in sig_entries.flatten() {
                let sig_path = sig_entry.path();
                if !sig_path.is_file() {
                    continue;
                }
                let ext = sig_path
                    .extension()
                    .map(|e| e.to_string_lossy().to_string())
                    .unwrap_or_default();
                if ext != "sg" {
                    continue;
                }
                let name = sig_entry.file_name().to_string_lossy().to_string();
                let rel_path = format!("{}/{}", file_type, name);
                sigs.push(SignatureInfoDto {
                    name,
                    file_path: rel_path,
                });
            }
        }

        if !sigs.is_empty() {
            sigs.sort_by(|a, b| a.name.cmp(&b.name));
            groups.push(SignatureGroupDto {
                file_type,
                signatures: sigs,
            });
        }
    }

    groups.sort_by(|a, b| a.file_type.cmp(&b.file_type));
    Ok(groups)
}

/// Get the source code of a specific signature.
#[tauri::command]
pub async fn get_signature_source(
    _state: tauri::State<'_, AppState>,
    file_type: String,
    name: String,
) -> Result<SignatureSourceDto, GuiError> {
    let db_path = resolve_db_path();
    let file_path = format!("{}/{}/{}", db_path, file_type, name);
    let source = std::fs::read_to_string(&file_path)
        .map_err(|e| GuiError::new("SIGNATURE_READ_ERROR", e.to_string()))?;
    Ok(SignatureSourceDto {
        source,
        file_path: format!("{}/{}", file_type, name),
    })
}

/// Run a single signature against a file (for signature browser).
#[tauri::command]
pub async fn run_signature(
    _state: tauri::State<'_, AppState>,
    _file_path: String,
    _file_type: String,
    _signature_name: String,
    _debug: bool,
) -> Result<ScanResultDto, GuiError> {
    // TODO: implement single-signature execution
    Err(GuiError::new(
        "NOT_IMPLEMENTED",
        "run_signature is not yet implemented",
    ))
}

/// Scan a directory recursively.
#[tauri::command]
pub async fn scan_directory(
    state: tauri::State<'_, AppState>,
    dir: String,
    flags: ScanFlagsDto,
    subdirectories: bool,
    on_progress: tauri::ipc::Channel<DirectoryScanProgress>,
) -> Result<Vec<ScanResultDto>, GuiError> {
    let db_path = resolve_db_path();
    let db = state
        .database(&db_path)
        .map_err(|e| GuiError::new("DATABASE_LOAD_FAILED", e))?;
    let cancel = state.start_scan();
    let engine_flags: ScanFlags = flags.into();

    // Collect files to scan.
    let files = collect_files(&dir, subdirectories);
    let total = files.len();
    let _ = on_progress.send(DirectoryScanProgress::Started { total_files: total });

    let mut results = Vec::with_capacity(total);
    for (index, file_path) in files.into_iter().enumerate() {
        if cancel.is_cancelled() {
            let _ = on_progress.send(DirectoryScanProgress::Error {
                message: "Cancelled".to_string(),
            });
            break;
        }

        let db = Arc::clone(&db);
        let cancel = cancel.clone();
        let path_str = file_path.to_string_lossy().to_string();
        let scan_result =
            tokio::task::spawn_blocking(move || scan_once(&db, &path_str, engine_flags, &cancel))
                .await
                .map_err(|e| GuiError::new("TASK_JOIN_FAILED", e.to_string()))?;

        match scan_result {
            Ok(r) => {
                let dto: ScanResultDto = r.into();
                let _ = on_progress.send(DirectoryScanProgress::FileScanned {
                    index,
                    file_path: dto.path.clone(),
                    result: dto.clone(),
                });
                results.push(dto);
            }
            Err(e) => {
                let err_msg = e.to_string();
                let _ = on_progress.send(DirectoryScanProgress::Error {
                    message: format!("{}: {}", file_path.display(), err_msg),
                });
            }
        }
    }

    let _ = on_progress.send(DirectoryScanProgress::Finished {
        total: results.len(),
    });
    Ok(results)
}

/// Collect files in a directory, optionally recursing into subdirectories.
fn collect_files(dir: &str, recursive: bool) -> Vec<std::path::PathBuf> {
    let mut files = Vec::new();
    collect_files_inner(std::path::Path::new(dir), recursive, &mut files);
    files
}

/// Recursive helper for `collect_files`.
/// Silently skips directories with permission errors.
fn collect_files_inner(
    dir: &std::path::Path,
    recursive: bool,
    files: &mut Vec<std::path::PathBuf>,
) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        // Permission denied or other I/O error — skip this directory.
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if recursive {
                collect_files_inner(&path, recursive, files);
            }
        } else if path.is_file() {
            files.push(path);
        }
    }
}

/// Demangle a C++ or Rust symbol.
#[tauri::command]
pub async fn demangle(symbol: String, compiler: String) -> Result<String, GuiError> {
    Ok(crate::demangle::demangle_symbol(&symbol, &compiler))
}

/// Read a hex dump of a file region.
#[tauri::command]
pub async fn read_hex(
    path: String,
    offset: u64,
    max_bytes: Option<usize>,
) -> Result<crate::hex_viewer::HexDump, GuiError> {
    let max = max_bytes.unwrap_or(4096);
    crate::hex_viewer::read_hex_dump(&path, offset, max)
        .map_err(|e| GuiError::new("HEX_READ_ERROR", e))
}

/// Disassemble a byte range from a file.
#[tauri::command]
pub async fn disassemble(
    path: String,
    offset: u64,
    max_bytes: Option<usize>,
    bitness: Option<u32>,
    syntax: Option<crate::disassembler::Syntax>,
) -> Result<crate::disassembler::DisassemblyResult, GuiError> {
    let max = max_bytes.unwrap_or(256);
    let bits = bitness.unwrap_or(64);
    let syn = syntax.unwrap_or(crate::disassembler::Syntax::Intel);
    crate::disassembler::disassemble_file(&path, offset, max, bits, syn)
        .map_err(|e| GuiError::new("DISASM_ERROR", e))
}

/// Get application settings from the persistent store.
#[tauri::command]
pub async fn get_settings(app: tauri::AppHandle) -> Result<AppSettings, GuiError> {
    use tauri_plugin_store::StoreExt;
    let store = app
        .store("settings.json")
        .map_err(|e| GuiError::new("STORE_ERROR", e.to_string()))?;
    match store.get("app_settings") {
        Some(val) => serde_json::from_value::<AppSettings>(val)
            .map_err(|e| GuiError::new("SETTINGS_PARSE_ERROR", e.to_string())),
        None => Ok(AppSettings::default()),
    }
}

/// Save application settings to the persistent store.
#[tauri::command]
pub async fn save_settings(app: tauri::AppHandle, settings: AppSettings) -> Result<(), GuiError> {
    use tauri_plugin_store::StoreExt;
    let store = app
        .store("settings.json")
        .map_err(|e| GuiError::new("STORE_ERROR", e.to_string()))?;
    let val = serde_json::to_value(&settings)
        .map_err(|e| GuiError::new("SETTINGS_SERIALIZE_ERROR", e.to_string()))?;
    store.set("app_settings", val);
    store
        .save()
        .map_err(|e| GuiError::new("STORE_SAVE_ERROR", e.to_string()))?;
    Ok(())
}

/// Get database info (path, rule count, version).
#[tauri::command]
pub async fn get_database_info(
    state: tauri::State<'_, AppState>,
) -> Result<DatabaseInfoDto, GuiError> {
    let db_path = resolve_db_path();
    let db = state
        .database(&db_path)
        .map_err(|e| GuiError::new("DATABASE_LOAD_FAILED", e))?;
    let version = db.version();
    Ok(DatabaseInfoDto {
        path: db_path.to_string(),
        rule_count: db.rule_count(),
        commit: version.commit,
        synced_at: version.synced_at,
    })
}
