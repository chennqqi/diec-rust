//! `diec` is the thin CLI adapter binary.
//!
//! It owns arguments, file input, exit codes and terminal output. It depends
//! on `diec-engine` and `diec-output` and never copies core scan logic. Phase
//! 1 only establishes the binary target; the real CLI surface lands in
//! Phase 4.

#![forbid(unsafe_code)]

fn main() {
    // Skeleton entry point: print a stable marker and exit successfully.
    // Real argument parsing and scan dispatch arrive in Phase 4.
    println!("diec skeleton");
}
