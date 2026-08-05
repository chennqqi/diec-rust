//! Managed application state for the die-gui Tauri backend.
//!
//! `AppState` holds the scan engine `Database` (loaded once, reused
//! across scans via `Arc`) and the current `CancellationToken` for
//! cooperative scan cancellation.

use diec_core::cancel::CancellationToken;
use diec_engine::{Database, DatabaseBuilder};
use std::sync::{Arc, Mutex};

/// The managed state shared across all Tauri IPC commands.
pub struct AppState {
    /// The rule database, loaded lazily on first scan.
    /// Stored behind `Arc` for cheap cloning into scan tasks.
    database: Mutex<Option<Arc<Database>>>,
    /// The current scan's cancellation token, if a scan is running.
    cancel_token: Mutex<Option<CancellationToken>>,
    /// The database path configured by the user (defaults to `./db`).
    db_path: Mutex<String>,
}

impl AppState {
    /// Create a new `AppState` with no loaded database.
    pub fn new() -> Self {
        Self {
            database: Mutex::new(None),
            cancel_token: Mutex::new(None),
            db_path: Mutex::new(String::new()),
        }
    }

    /// Get or load the database, returning an `Arc` clone.
    ///
    /// The database is loaded on first call and cached for subsequent
    /// scans. If the `db_path` changes, the cached database is discarded
    /// and reloaded.
    pub fn database(&self, db_path: &str) -> Result<Arc<Database>, String> {
        let mut guard = self.database.lock().expect("database mutex poisoned");
        let mut cached_path = self.db_path.lock().expect("db_path mutex poisoned");
        if let Some(ref db) = *guard
            && *cached_path == db_path
        {
            return Ok(Arc::clone(db));
        }

        let builder = DatabaseBuilder::new(db_path);
        let db = builder.build().map_err(|e| e.to_string())?;
        let arc = Arc::new(db);
        *guard = Some(Arc::clone(&arc));
        *cached_path = db_path.to_string();
        Ok(arc)
    }

    /// Start a new scan, returning a `CancellationToken` that the
    /// frontend can trigger via `stop_scan`.
    pub fn start_scan(&self) -> CancellationToken {
        let token = CancellationToken::new();
        *self
            .cancel_token
            .lock()
            .expect("cancel_token mutex poisoned") = Some(token.clone());
        token
    }

    /// Cancel the current scan, if any.
    pub fn stop_scan(&self) {
        if let Some(token) = self
            .cancel_token
            .lock()
            .expect("cancel_token mutex poisoned")
            .take()
        {
            token.cancel();
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}
