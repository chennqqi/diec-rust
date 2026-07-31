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
    eprintln!("  --version         Print version and exit");
    eprintln!("  --help            Print this help and exit");
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();

    let mut db_path = String::new();
    let mut output_format = "text".to_string();
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
    let mut had_error = false;
    let mut results = Vec::new();

    for target in &targets {
        match scan_once(&database, target, &cancel) {
            Ok(result) => results.push(result),
            Err(e) => {
                eprintln!("error: scanning {target}: {e}");
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
