//! XML renderer for scan results.
//!
//! Produces a simple XML document matching the upstream DIE-engine
//! XML output structure. No external XML library is used.

use diec_engine::ScanResult;

/// Escape a string for XML output.
fn escape_xml(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '&' => out.push_str("&amp;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            c if (c as u32) < 0x20 && c != '\t' && c != '\n' && c != '\r' => {
                out.push_str(&format!("&#x{:x};", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

/// Render a scan result as XML.
pub fn render_xml(result: &ScanResult) -> String {
    let mut out = String::new();
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    out.push_str("<Result>\n");
    out.push_str("  <Path>");
    out.push_str(&escape_xml(&result.path));
    out.push_str("</Path>\n");

    out.push_str("  <Detections>\n");
    for det in &result.detections {
        out.push_str("    <Detection>\n");
        out.push_str("      <FileType>");
        out.push_str(&escape_xml(&det.file_type));
        out.push_str("</FileType>\n");
        out.push_str("      <Type>");
        out.push_str(&escape_xml(&det.type_name));
        out.push_str("</Type>\n");
        out.push_str("      <Name>");
        out.push_str(&escape_xml(&det.name));
        out.push_str("</Name>\n");
        if let Some(v) = &det.version {
            out.push_str("      <Version>");
            out.push_str(&escape_xml(v));
            out.push_str("</Version>\n");
        }
        if let Some(o) = &det.options {
            out.push_str("      <Options>");
            out.push_str(&escape_xml(o));
            out.push_str("</Options>\n");
        }
        out.push_str("    </Detection>\n");
    }
    out.push_str("  </Detections>\n");

    if !result.diagnostics.is_empty() {
        out.push_str("  <Diagnostics>\n");
        for diag in &result.diagnostics {
            out.push_str("    <Diagnostic>");
            out.push_str(&escape_xml(diag));
            out.push_str("</Diagnostic>\n");
        }
        out.push_str("  </Diagnostics>\n");
    }

    out.push_str("</Result>\n");
    out
}
