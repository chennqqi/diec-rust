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
#[serde(tag = "event", content = "data")]
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
#[serde(tag = "event", content = "data")]
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

/// Scan a file by path.
#[tauri::command]
pub async fn scan_file(
    state: tauri::State<'_, AppState>,
    path: String,
    flags: ScanFlagsDto,
) -> Result<ScanResultDto, GuiError> {
    let db_path = "./db"; // TODO: read from settings
    let db = state
        .database(db_path)
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
    let db_path = "./db";
    let db = state
        .database(db_path)
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
    // TODO: implement signature listing from database
    Ok(Vec::new())
}

/// Get the source code of a specific signature.
#[tauri::command]
pub async fn get_signature_source(
    _state: tauri::State<'_, AppState>,
    _file_type: String,
    _name: String,
) -> Result<SignatureSourceDto, GuiError> {
    // TODO: implement signature source retrieval
    Ok(SignatureSourceDto {
        source: String::new(),
        file_path: String::new(),
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
    _state: tauri::State<'_, AppState>,
    _dir: String,
    _flags: ScanFlagsDto,
    _subdirectories: bool,
    _on_progress: tauri::ipc::Channel<DirectoryScanProgress>,
) -> Result<Vec<ScanResultDto>, GuiError> {
    // TODO: implement directory scanning
    Err(GuiError::new(
        "NOT_IMPLEMENTED",
        "scan_directory is not yet implemented",
    ))
}

/// Demangle a C++ or Rust symbol.
#[tauri::command]
pub async fn demangle(symbol: String, compiler: String) -> Result<String, GuiError> {
    // TODO: integrate cpp_demangle / msvc-demangle / rustc-demangle
    let _ = compiler;
    Ok(symbol)
}

/// Get application settings.
#[tauri::command]
pub async fn get_settings(_state: tauri::State<'_, AppState>) -> Result<AppSettings, GuiError> {
    Ok(AppSettings::default())
}

/// Save application settings.
#[tauri::command]
pub async fn save_settings(
    _state: tauri::State<'_, AppState>,
    _settings: AppSettings,
) -> Result<(), GuiError> {
    // TODO: persist settings via tauri-plugin-store
    Ok(())
}

/// Get database info (path, rule count, version).
#[tauri::command]
pub async fn get_database_info(
    state: tauri::State<'_, AppState>,
) -> Result<DatabaseInfoDto, GuiError> {
    let db_path = "./db";
    let db = state
        .database(db_path)
        .map_err(|e| GuiError::new("DATABASE_LOAD_FAILED", e))?;
    let version = db.version();
    Ok(DatabaseInfoDto {
        path: db_path.to_string(),
        rule_count: db.rule_count(),
        commit: version.commit,
        synced_at: version.synced_at,
    })
}
