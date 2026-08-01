//! `diec-output` renders scan results into canonical JSON and
//! human-readable text output.
//!
//! It only performs presentation conversion and never duplicates detection,
//! nesting, ordering or diagnostic logic. Canonical JSON is the stable data
//! plane shared by the library, FFI and modern CLI.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

mod delimited;
mod json;
mod text;
mod xml;

pub use delimited::{render_csv, render_tsv};
pub use json::render_json;
pub use text::{render_text, render_text_formatted};
pub use xml::render_xml;

#[cfg(test)]
mod tests {
    use super::*;
    use diec_engine::ScanDetection;

    fn sample_result() -> diec_engine::ScanResult {
        diec_engine::ScanResult {
            path: "test.7z".into(),
            detections: vec![ScanDetection {
                file_type: "Binary".into(),
                type_name: "archive".into(),
                name: "7-Zip".into(),
                version: Some("0.4".into()),
                options: None,
            }],
            diagnostics: vec![],
        }
    }

    #[test]
    fn json_contains_detection() {
        let result = sample_result();
        let json = render_json(&result);
        assert!(json.contains("7-Zip"));
        assert!(json.contains("archive"));
        assert!(json.contains("0.4"));
        assert!(json.contains("test.7z"));
    }

    #[test]
    fn text_contains_detection() {
        let result = sample_result();
        let text = render_text(&result);
        assert!(text.contains("7-Zip"));
        assert!(text.contains("test.7z"));
    }

    #[test]
    fn json_is_valid_json() {
        let result = sample_result();
        let json = render_json(&result);
        // Verify it starts and ends with JSON object delimiters.
        assert!(json.trim_start().starts_with('{'));
        assert!(json.trim_end().ends_with('}'));
    }

    #[test]
    fn empty_result_renders() {
        let result = diec_engine::ScanResult {
            path: "empty.bin".into(),
            detections: vec![],
            diagnostics: vec![],
        };
        let json = render_json(&result);
        assert!(json.contains("empty.bin"));
        assert!(json.contains("\"detections\""));
        let text = render_text(&result);
        assert!(text.contains("empty.bin"));
    }
}
