//! Demangle backend for die-gui.
//!
//! Demangles C++ (Itanium ABI) and Rust mangled symbols using
//! `cpp_demangle` and `rustc-demangle` crates.

/// Demangle a mangled symbol string.
///
/// Tries Rust demangling first (rustc-demangle), then C++
/// (Itanium ABI via cpp_demangle). Returns the original
/// string if neither can demangle it.
pub fn demangle_symbol(symbol: &str, compiler: &str) -> String {
    // Try Rust first if compiler is "rust" or auto-detect.
    if (compiler == "rust" || compiler == "auto")
        && let Ok(demangled) = rustc_demangle::try_demangle(symbol)
    {
        return format!("{}", demangled);
    }

    // Try C++ Itanium ABI (GCC/Clang).
    if (compiler == "cpp" || compiler == "auto")
        && let Ok(sym) = cpp_demangle::Symbol::new(symbol)
    {
        let options = cpp_demangle::DemangleOptions::default();
        if let Ok(demangled) = sym.demangle(&options) {
            return demangled;
        }
    }

    // Return original if no demangler succeeded.
    symbol.to_string()
}
