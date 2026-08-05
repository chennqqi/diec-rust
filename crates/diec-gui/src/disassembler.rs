//! Disassembler backend for diec-gui.
//!
//! Uses `iced-x86` (pure Rust, no C dependency) to disassemble
//! x86/x64 code. Supports Intel, AT&T, and NASM syntax.

use iced_x86::{
    Decoder, DecoderOptions, Formatter, GasFormatter, IntelFormatter, Mnemonic, NasmFormatter,
};
use serde::{Deserialize, Serialize};

/// Disassembly syntax format.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Syntax {
    /// Intel syntax (default).
    Intel,
    /// AT&T syntax (GNU assembler).
    Gas,
    /// NASM syntax.
    Nasm,
}

/// A single disassembled instruction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Instruction {
    /// Instruction address (hex string).
    pub address: String,
    /// Instruction bytes as hex string.
    pub bytes: String,
    /// Disassembled instruction text.
    pub mnemonic: String,
}

/// Disassembly response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisassemblyResult {
    /// Starting address.
    pub start_address: u64,
    /// Number of instructions decoded.
    pub instruction_count: usize,
    /// Disassembled instructions.
    pub instructions: Vec<Instruction>,
}

/// Disassemble a byte range from a file.
///
/// Reads `max_bytes` bytes at `offset` and disassembles them using
/// the specified syntax. The bitness is auto-detected from the file
/// format (PE32=32, PE64=64, ELF64=64, etc.) or defaults to 64.
pub fn disassemble_file(
    path: &str,
    offset: u64,
    max_bytes: usize,
    bitness: u32,
    syntax: Syntax,
) -> Result<DisassemblyResult, String> {
    let bytes = read_file_range(path, offset, max_bytes)?;
    disassemble_bytes(&bytes, offset, bitness, syntax)
}

/// Disassemble raw bytes.
pub fn disassemble_bytes(
    data: &[u8],
    base_address: u64,
    bitness: u32,
    syntax: Syntax,
) -> Result<DisassemblyResult, String> {
    let options = DecoderOptions::NONE;
    let mut decoder = Decoder::with_ip(bitness, data, base_address, options);

    let mut instructions = Vec::new();
    let mut intel_buf = String::new();
    let mut gas_buf = String::new();
    let mut nasm_buf = String::new();

    for instr in decoder.iter() {
        let address = format!("{:016X}", instr.ip());
        let byte_len = instr.len();
        let byte_start = (instr.ip() - base_address) as usize;
        let bytes = &data[byte_start..byte_start + byte_len];
        let bytes_hex: Vec<String> = bytes.iter().map(|b| format!("{:02X}", b)).collect();

        let mnemonic = match syntax {
            Syntax::Intel => {
                let mut fmt = IntelFormatter::new();
                fmt.format(&instr, &mut intel_buf);
                intel_buf.clone()
            }
            Syntax::Gas => {
                let mut fmt = GasFormatter::new();
                fmt.format(&instr, &mut gas_buf);
                gas_buf.clone()
            }
            Syntax::Nasm => {
                let mut fmt = NasmFormatter::new();
                fmt.format(&instr, &mut nasm_buf);
                nasm_buf.clone()
            }
        };

        instructions.push(Instruction {
            address,
            bytes: bytes_hex.join(" "),
            mnemonic,
        });

        // Stop if we hit a return or unconditional jump (basic block end).
        let m = instr.mnemonic();
        if m == Mnemonic::Ret || m == Mnemonic::Retf || m == Mnemonic::Ud0 {
            break;
        }
    }

    let count = instructions.len();
    Ok(DisassemblyResult {
        start_address: base_address,
        instruction_count: count,
        instructions,
    })
}

/// Read a range of bytes from a file.
fn read_file_range(path: &str, offset: u64, max_bytes: usize) -> Result<Vec<u8>, String> {
    use std::io::{Read, Seek, SeekFrom};
    let mut file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    let metadata = file.metadata().map_err(|e| e.to_string())?;
    let file_size = metadata.len();
    let bytes_to_read = std::cmp::min(max_bytes as u64, file_size.saturating_sub(offset)) as usize;
    let mut buf = vec![0u8; bytes_to_read];
    file.seek(SeekFrom::Start(offset))
        .map_err(|e| e.to_string())?;
    file.read_exact(&mut buf).map_err(|e| e.to_string())?;
    Ok(buf)
}
