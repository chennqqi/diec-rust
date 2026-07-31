//! Database loading and snapshot management.
//!
//! The database is built from a directory of `.sg` rule files and
//! framework scripts. After building, it is immutable and can be
//! shared across scans via `Arc<Database>`.

use diec_rules::runtime::{DatabaseSnapshot, LoadedRule};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// Error type for database operations.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DatabaseError {
    /// The database directory does not exist or is not a directory.
    NotFound {
        /// The path that was not found.
        path: String,
    },
    /// An I/O error occurred while reading a file.
    IoError {
        /// The file path that could not be read.
        path: String,
        /// The I/O error detail.
        detail: String,
    },
    /// The database directory contains no rules.
    Empty,
}

impl std::fmt::Display for DatabaseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DatabaseError::NotFound { path } => {
                write!(f, "database directory not found: {path}")
            }
            DatabaseError::IoError { path, detail } => {
                write!(f, "I/O error reading {path}: {detail}")
            }
            DatabaseError::Empty => write!(f, "database directory contains no rules"),
        }
    }
}

impl std::error::Error for DatabaseError {}

/// Builder for constructing a `Database` from rule directories.
#[derive(Debug, Clone)]
pub struct DatabaseBuilder {
    db_path: PathBuf,
}

impl Default for DatabaseBuilder {
    fn default() -> Self {
        Self {
            db_path: PathBuf::new(),
        }
    }
}

impl DatabaseBuilder {
    /// Create a new builder pointing at the given database directory.
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self {
            db_path: path.into(),
        }
    }

    /// Build the immutable `Database` by reading and parsing all rules.
    pub fn build(self) -> Result<Database, DatabaseError> {
        if self.db_path.as_os_str().is_empty() {
            return Err(DatabaseError::NotFound {
                path: "(empty path)".into(),
            });
        }
        if !self.db_path.is_dir() {
            return Err(DatabaseError::NotFound {
                path: self.db_path.display().to_string(),
            });
        }

        let mut rules: Vec<LoadedRule> = Vec::new();
        let mut ordinal = 0u64;

        // Collect rules from each format-type subdirectory.
        let format_types = ["Binary", "PE", "ELF", "MACH", "MACHOFAT"];
        for ft in &format_types {
            let ft_dir = self.db_path.join(ft);
            if !ft_dir.is_dir() {
                continue;
            }
            if let Ok(entries) = std::fs::read_dir(&ft_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.extension().and_then(|e| e.to_str()) == Some("sg") {
                        let source =
                            std::fs::read_to_string(&path).map_err(|e| DatabaseError::IoError {
                                path: path.display().to_string(),
                                detail: e.to_string(),
                            })?;
                        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("?");
                        rules.push(LoadedRule {
                            path: format!("{ft}/{name}"),
                            ordinal,
                            file_type: ft.to_string(),
                            source,
                        });
                        ordinal += 1;
                    }
                }
            }
        }

        if rules.is_empty() {
            return Err(DatabaseError::Empty);
        }

        // Load the global _init script.
        let init_script = std::fs::read_to_string(self.db_path.join("_init")).ok();

        // Load all include scripts (files without extensions at the root).
        let mut include_scripts: BTreeMap<String, String> = BTreeMap::new();
        load_include_scripts(&self.db_path, &mut include_scripts);

        // Load type-specific _init scripts.
        let mut type_init_scripts: Vec<(String, String)> = Vec::new();
        for ft in &format_types {
            let init_path = self.db_path.join(ft).join("_init");
            if init_path.is_file()
                && let Ok(source) = std::fs::read_to_string(&init_path)
            {
                type_init_scripts.push((ft.to_string(), source));
            }
        }

        Ok(Database {
            snapshot: DatabaseSnapshot {
                rules,
                init_script,
                type_init_scripts,
                include_scripts,
            },
            db_path: self.db_path,
        })
    }
}

/// Recursively load include scripts from the database root.
fn load_include_scripts(db: &Path, includes: &mut BTreeMap<String, String>) {
    // Load files at the root level (no extension).
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

    // Load files in subdirectories: db/<dir>/<dir> and db/<dir>/<other>.
    if let Ok(entries) = std::fs::read_dir(db) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir()
                && let Some(dir_name) = path.file_name().and_then(|n| n.to_str())
            {
                // db/<dir>/<dir> file.
                let inner = path.join(dir_name);
                if inner.is_file()
                    && !includes.contains_key(dir_name)
                    && let Ok(source) = std::fs::read_to_string(&inner)
                {
                    includes.insert(dir_name.to_string(), source);
                }
                // Other files in the subdirectory.
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
}

/// An immutable, reusable database of rules and framework scripts.
#[derive(Debug, Clone)]
pub struct Database {
    /// The loaded database snapshot.
    pub snapshot: DatabaseSnapshot,
    /// The path the database was loaded from.
    pub db_path: PathBuf,
}

impl Database {
    /// Get a reference to the database snapshot.
    pub fn snapshot(&self) -> &DatabaseSnapshot {
        &self.snapshot
    }

    /// Get the number of rules in the database.
    pub fn rule_count(&self) -> usize {
        self.snapshot.rules.len()
    }
}
