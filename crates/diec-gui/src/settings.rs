//! Settings persistence for diec-gui.
//!
//! Settings are stored as JSON in the Tauri app config directory.
//! This module defines the settings structure and provides
//! load/save helpers using `tauri-plugin-store`.

use serde::{Deserialize, Serialize};

/// Application settings mirroring upstream `XOptions` categories.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    /// View settings (theme, language, fonts, stay-on-top, advanced).
    pub view: ViewSettings,
    /// File settings (last directory, recent files, backup).
    pub file: FileSettings,
    /// Scan settings (flags, hide unknown, sort, profiling).
    pub scan: ScanSettings,
    /// Database paths (main, extra, custom).
    pub database: DatabaseSettings,
    /// Engine enable flags (DIE, NFD, PEID, YARA).
    pub engine: EngineSettings,
}

/// View-related settings (upstream `XOptions::ID_VIEW_*`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ViewSettings {
    /// Theme name: "light", "dark", "system", or custom CSS name.
    pub theme: String,
    /// Language code: "en", "zh-CN", "ru", etc.
    pub language: String,
    /// Stay on top of other windows.
    pub stay_on_top: bool,
    /// Advanced mode (shows Demangle button, advanced scan widget).
    pub advanced: bool,
}

/// File-related settings (upstream `XOptions::ID_FILE_*`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSettings {
    /// Last opened directory.
    pub last_directory: String,
    /// Recent files list (most recent first).
    pub recent_files: Vec<String>,
    /// Save backup of edited signatures.
    pub save_backup: bool,
}

/// Scan-related settings (upstream `XOptions::ID_SCAN_*`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanSettings {
    /// Scan after opening a file.
    pub scan_after_open: bool,
    /// Hide unknown detections.
    pub hide_unknown: bool,
    /// Sort results.
    pub sort: bool,
    /// Log profiling data.
    pub log_profiling: bool,
    /// Default scan flags.
    pub flags: ScanFlagDefaults,
}

/// Default scan flag values (upstream `XOptions::ID_SCAN_FLAG_*`).
///
/// Field names match `ScanFlagsDto` in `commands.rs` for direct
/// frontend-to-backend round-trip without renaming.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanFlagDefaults {
    pub recursive: bool,
    pub deep: bool,
    pub heuristic: bool,
    pub verbose: bool,
    pub aggressive: bool,
    pub alltypes: bool,
    pub overlay: bool,
    pub resources: bool,
    pub archives: bool,
    pub first_wrapper_only: bool,
    pub hide_unknown: bool,
}

/// Database path settings (upstream `XOptions::ID_SCAN_DIE_DATABASE_*`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseSettings {
    /// Main database path.
    pub main_path: String,
    /// Extra database path.
    pub extra_path: String,
    /// Custom database path.
    pub custom_path: String,
    /// Enable extra database.
    pub extra_enabled: bool,
    /// Enable custom database.
    pub custom_enabled: bool,
}

/// Engine enable flags (upstream `XOptions::ID_SCAN_ENGINE_*`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineSettings {
    /// DIE engine enabled.
    pub die_enabled: bool,
    /// NFD engine enabled.
    pub nfd_enabled: bool,
    /// PEID engine enabled.
    pub peid_enabled: bool,
    /// YARA engine enabled.
    pub yara_enabled: bool,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            view: ViewSettings {
                theme: "system".to_string(),
                language: "en".to_string(),
                stay_on_top: false,
                advanced: false,
            },
            file: FileSettings {
                last_directory: String::new(),
                recent_files: Vec::new(),
                save_backup: true,
            },
            scan: ScanSettings {
                scan_after_open: true,
                hide_unknown: false,
                sort: false,
                log_profiling: false,
                flags: ScanFlagDefaults {
                    recursive: true,
                    deep: false,
                    heuristic: false,
                    verbose: false,
                    aggressive: false,
                    alltypes: false,
                    overlay: true,
                    resources: true,
                    archives: true,
                    first_wrapper_only: false,
                    hide_unknown: false,
                },
            },
            database: DatabaseSettings {
                main_path: "./db".to_string(),
                extra_path: String::new(),
                custom_path: String::new(),
                extra_enabled: false,
                custom_enabled: false,
            },
            engine: EngineSettings {
                die_enabled: true,
                nfd_enabled: false,
                peid_enabled: false,
                yara_enabled: false,
            },
        }
    }
}
