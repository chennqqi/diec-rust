//! `diec` is the thin CLI adapter binary.
//!
//! It owns arguments, file input, exit codes and terminal output. It depends
//! on `diec-engine` and `diec-output` and never copies core scan logic.

#![forbid(unsafe_code)]

use diec_core::cancel::CancellationToken;
use diec_engine::{DatabaseBuilder, scan_once};
use std::process::ExitCode;

/// CLI exit codes (see docs/design/api.md section 16).
const EXIT_OK: u8 = 0;
const EXIT_USAGE: u8 = 2;
const EXIT_DATABASE: u8 = 3;
const EXIT_INPUT: u8 = 4;

fn print_usage() {
    eprintln!("Usage: diec [OPTIONS] <file>...");
    eprintln!();
    eprintln!("Options:");
    eprintln!("  --db <path>       Database directory (default: ./db)");
    eprintln!("  --output <format>  Output format: text (default) or json");
    eprintln!("  --recursive, -r   Recursively scan directories");
    eprintln!("  --version         Print version and exit");
    eprintln!("  --help            Print this help and exit");
}

/// Expand a target path: if it's a directory and `recursive` is true,
/// collect all files within it recursively. Otherwise return the path
/// as-is (if it's a file) or report an error (if it's a directory and
/// recursive is false).
fn expand_target(target: &str, recursive: bool, files: &mut Vec<String>, errors: &mut Vec<String>) {
    let path = std::path::Path::new(target);
    if !path.exists() {
        errors.push(format!("path not found: {target}"));
        return;
    }
    if path.is_dir() {
        if !recursive {
            errors.push(format!("is a directory (use --recursive): {target}"));
            return;
        }
        collect_files(path, files);
    } else {
        files.push(target.to_string());
    }
}

/// Recursively collect all regular files under a directory.
fn collect_files(dir: &std::path::Path, files: &mut Vec<String>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    let mut sorted_entries: Vec<_> = entries.filter_map(|e| e.ok()).collect();
    sorted_entries.sort_by_key(|e| e.path());
    for entry in sorted_entries {
        let path = entry.path();
        if path.is_dir() {
            collect_files(&path, files);
        } else if path.is_file()
            && let Some(s) = path.to_str()
        {
            files.push(s.to_string());
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();

    let mut db_path = String::new();
    let mut output_format = "text".to_string();
    let mut recursive = false;
    let mut targets: Vec<String> = Vec::new();

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--help" | "-h" => {
                print_usage();
                return ExitCode::from(EXIT_OK);
            }
            "--version" | "-V" => {
                println!("diec {}", env!("CARGO_PKG_VERSION"));
                return ExitCode::from(EXIT_OK);
            }
            "--recursive" | "-r" => {
                recursive = true;
            }
            "--db" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("error: --db requires a path argument");
                    return ExitCode::from(EXIT_USAGE);
                }
                db_path = args[i].clone();
            }
            "--output" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("error: --output requires a format argument");
                    return ExitCode::from(EXIT_USAGE);
                }
                output_format = args[i].clone();
                if output_format != "text" && output_format != "json" {
                    eprintln!("error: unsupported output format: {output_format}");
                    return ExitCode::from(EXIT_USAGE);
                }
            }
            s if s.starts_with("--") => {
                eprintln!("error: unknown option: {s}");
                return ExitCode::from(EXIT_USAGE);
            }
            s => {
                targets.push(s.to_string());
            }
        }
        i += 1;
    }

    if targets.is_empty() {
        eprintln!("error: no input files specified");
        print_usage();
        return ExitCode::from(EXIT_USAGE);
    }

    // Expand targets: directories are recursively scanned if --recursive.
    let mut files = Vec::new();
    let mut expand_errors = Vec::new();
    for target in &targets {
        expand_target(target, recursive, &mut files, &mut expand_errors);
    }
    for err in &expand_errors {
        eprintln!("error: {err}");
    }
    if files.is_empty() {
        eprintln!("error: no files to scan");
        return ExitCode::from(EXIT_INPUT);
    }

    // Find the database directory.
    if db_path.is_empty() {
        // Try common locations.
        let candidates = [
            "upstream/Detect-It-Easy/db",
            "../upstream/Detect-It-Easy/db",
            "../../upstream/Detect-It-Easy/db",
            "db",
        ];
        for c in &candidates {
            if std::path::Path::new(c).is_dir() {
                db_path = c.to_string();
                break;
            }
        }
        if db_path.is_empty() {
            eprintln!("error: database directory not found. Use --db <path>");
            return ExitCode::from(EXIT_DATABASE);
        }
    }

    // Build the database.
    let database = match DatabaseBuilder::new(&db_path).build() {
        Ok(db) => db,
        Err(e) => {
            eprintln!("error: failed to load database from {db_path}: {e}");
            return ExitCode::from(EXIT_DATABASE);
        }
    };

    let cancel = CancellationToken::new();
    let mut had_error = !expand_errors.is_empty();
    let mut results = Vec::new();

    for file in &files {
        match scan_once(&database, file, &cancel) {
            Ok(result) => results.push(result),
            Err(e) => {
                eprintln!("error: scanning {file}: {e}");
                had_error = true;
            }
        }
    }

    // Render output.
    match output_format.as_str() {
        "json" => {
            if results.len() == 1 {
                println!("{}", diec_output::render_json(&results[0]));
            } else {
                // Batch: wrap in array.
                print!("[");
                for (i, r) in results.iter().enumerate() {
                    if i > 0 {
                        print!(",");
                    }
                    print!("{}", diec_output::render_json(r));
                }
                println!("]");
            }
        }
        _ => {
            for r in &results {
                print!("{}", diec_output::render_text(r));
            }
        }
    }

    if had_error {
        ExitCode::from(EXIT_INPUT)
    } else {
        ExitCode::from(EXIT_OK)
    }
}
