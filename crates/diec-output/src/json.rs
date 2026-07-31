//! Canonical JSON renderer for scan results.
//!
//! Produces a stable, single-document JSON object with deterministic
//! field ordering. No external JSON library is used to avoid adding
//! a workspace dependency.

use diec_engine::ScanResult;

/// Escape a string for JSON output.
fn escape_json(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

/// Render a scan result as canonical JSON.
pub fn render_json(result: &ScanResult) -> String {
    let mut out = String::new();
    out.push('{');
    out.push_str("\"path\":\"");
    out.push_str(&escape_json(&result.path));
    out.push_str("\",");

    out.push_str("\"detections\":[");
    for (i, det) in result.detections.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str("\"file_type\":\"");
        out.push_str(&escape_json(&det.file_type));
        out.push_str("\",");
        out.push_str("\"type\":\"");
        out.push_str(&escape_json(&det.type_name));
        out.push_str("\",");
        out.push_str("\"name\":\"");
        out.push_str(&escape_json(&det.name));
        out.push('"');
        if let Some(v) = &det.version {
            out.push_str(",\"version\":\"");
            out.push_str(&escape_json(v));
            out.push('"');
        }
        if let Some(o) = &det.options {
            out.push_str(",\"options\":\"");
            out.push_str(&escape_json(o));
            out.push('"');
        }
        out.push('}');
    }
    out.push(']');

    if !result.diagnostics.is_empty() {
        out.push_str(",\"diagnostics\":[");
        for (i, diag) in result.diagnostics.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            out.push('"');
            out.push_str(&escape_json(diag));
            out.push('"');
        }
        out.push(']');
    }

    out.push('}');
    out
}
