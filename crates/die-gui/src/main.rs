//! `die-gui` is the Tauri v2 GUI adapter binary for diec.
//!
//! It owns the Tauri application lifecycle, IPC command registration,
//! and managed state. It depends on `diec-engine` for scan logic and
//! never duplicates detection branches. See `docs/design/phase8-gui.md`.

// Hide the console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#![forbid(unsafe_code)]

mod commands;
mod demangle;
mod disassembler;
mod file_info;
mod hex_viewer;
mod peid_scanner;
mod settings;
mod state;
mod yara_scanner;

use state::AppState;
use tauri::Manager;

/// Entry point for the die-gui Tauri application.
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // Focus the existing window when a second instance is launched.
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_store::Builder::default().build())
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            commands::scan_file,
            commands::scan_bytes_cmd,
            commands::stop_scan,
            commands::list_signatures,
            commands::get_signature_source,
            commands::scan_directory,
            commands::demangle,
            commands::read_hex,
            commands::disassemble,
            commands::get_settings,
            commands::save_settings,
            commands::get_database_info,
            commands::yara_scan,
            commands::peid_scan,
            commands::get_file_info,
            commands::get_entropy_graph,
            commands::write_text_file,
            commands::save_signature_source,
            commands::run_signature,
            commands::list_archive,
        ])
        .run(tauri::generate_context!())
        .expect("error while running DIE application");
}
