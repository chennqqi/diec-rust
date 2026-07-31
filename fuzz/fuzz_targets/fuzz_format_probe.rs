//! Fuzz target: format probe table on arbitrary input.
//!
//! Invariant: no panic, no hang, no unbounded allocation. Probes must return
//! Ok(Some), Ok(None) or Err(ProbeError). See testing.md section 14.

#![no_main]

use diec_core::input::{ByteRange, ByteSource, ByteView, MemorySource};
use diec_formats::{FormatProbe, ProbeTable};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let src = MemorySource::new(data);
    let range = ByteRange::new(0, src.len()).unwrap();
    let view = ByteView::new(&src, range).unwrap();

    let table = ProbeTable::default_phase2();
    let (candidates, errors) = table.probe_all(&view);

    // Invariant: no candidate has None strength.
    for c in &candidates {
        assert_ne!(
            c.strength,
            diec_core::format::FormatStrength::None,
            "candidate with None strength"
        );
    }

    // Invariant: MemorySource should not produce Io errors.
    for e in &errors {
        match e {
            diec_formats::ProbeError::Truncated { .. }
            | diec_formats::ProbeError::InvalidHeader { .. } => {}
            diec_formats::ProbeError::Io(_) => {
                panic!("MemorySource should not produce Io errors: {e:?}");
            }
        }
    }
});
