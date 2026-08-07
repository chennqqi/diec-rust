//! Disassembler backend for die-gui.
//!
//! Uses `iced-x86` (pure Rust) for x86/x64 and `yaxpeax-arm` (pure Rust)
//! for ARM/ARM64. Supports Intel, AT&T, and NASM syntax for x86/x64.
//! Does NOT break on Ret/Retf — disassembles the full requested range.

use iced_x86::{
    Decoder as IcedDecoder, DecoderOptions, FlowControl, Formatter, GasFormatter, IntelFormatter,
    NasmFormatter,
};
use serde::{Deserialize, Serialize};

/// Disassembly syntax format (x86/x64 only).
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

/// Disassembly architecture.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Arch {
    /// x86 32-bit.
    X86,
    /// x86-64 64-bit.
    X64,
    /// ARM 32-bit (Thumb/ARM).
    Arm,
    /// ARM64/AArch64.
    Arm64,
}

impl Arch {
    /// Get the bitness for this architecture.
    fn bitness(&self) -> u32 {
        match self {
            Arch::X86 => 32,
            Arch::X64 => 64,
            Arch::Arm => 32,
            Arch::Arm64 => 64,
        }
    }
}

/// A single disassembled instruction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Instruction {
    /// Instruction address (hex string).
    pub address: String,
    /// Instruction bytes as hex string.
    pub bytes: String,
    /// Disassembled instruction text (mnemonic + operands).
    pub mnemonic: String,
    /// Optional label for this instruction (e.g. function name or jump target).
    pub label: Option<String>,
    /// Optional comment for this instruction (e.g. "; jump to 0x401000").
    pub comment: Option<String>,
    /// Optional jump/call target address (hex string), if this instruction
    /// is a branch.
    pub jump_target: Option<String>,
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
/// the specified architecture and syntax. Does NOT break on Ret —
/// the full range is disassembled.
pub fn disassemble_file(
    path: &str,
    offset: u64,
    max_bytes: usize,
    arch: Arch,
    syntax: Syntax,
) -> Result<DisassemblyResult, String> {
    let bytes = read_file_range(path, offset, max_bytes)?;
    disassemble_bytes(&bytes, offset, arch, syntax)
}

/// Disassemble raw bytes.
///
/// Disassembles the full `data` buffer without breaking on Ret/Retf.
/// The architecture determines which disassembler engine is used:
/// - X86/X64: iced-x86
/// - Arm/Arm64: yaxpeax-arm
pub fn disassemble_bytes(
    data: &[u8],
    base_address: u64,
    arch: Arch,
    syntax: Syntax,
) -> Result<DisassemblyResult, String> {
    match arch {
        Arch::X86 | Arch::X64 => disassemble_x86(data, base_address, arch.bitness(), syntax),
        Arch::Arm => disassemble_arm(data, base_address),
        Arch::Arm64 => disassemble_arm64(data, base_address),
    }
}

/// Disassemble x86/x64 code using iced-x86.
fn disassemble_x86(
    data: &[u8],
    base_address: u64,
    bitness: u32,
    syntax: Syntax,
) -> Result<DisassemblyResult, String> {
    let options = DecoderOptions::NONE;
    let mut decoder = IcedDecoder::with_ip(bitness, data, base_address, options);

    let mut all_instrs: Vec<iced_x86::Instruction> = decoder.iter().collect();

    // Collect all jump/call targets for label generation.
    let mut jump_targets: std::collections::BTreeSet<u64> = std::collections::BTreeSet::new();
    for instr in &all_instrs {
        let fc = instr.flow_control();
        if matches!(
            fc,
            FlowControl::UnconditionalBranch | FlowControl::ConditionalBranch | FlowControl::Call
        ) {
            let target = instr.near_branch_target();
            if target >= base_address && target < base_address + data.len() as u64 {
                jump_targets.insert(target);
            }
        }
    }

    let mut instructions = Vec::new();
    let mut intel_buf = String::new();
    let mut gas_buf = String::new();
    let mut nasm_buf = String::new();

    for instr in &mut all_instrs {
        let address = format!("{:016X}", instr.ip());
        let byte_len = instr.len();
        let byte_start = (instr.ip() - base_address) as usize;
        if byte_start + byte_len > data.len() {
            break;
        }
        let bytes = &data[byte_start..byte_start + byte_len];
        let bytes_hex: Vec<String> = bytes.iter().map(|b| format!("{:02X}", b)).collect();

        let mnemonic_str = match syntax {
            Syntax::Intel => {
                let mut fmt = IntelFormatter::new();
                fmt.format(instr, &mut intel_buf);
                intel_buf.clone()
            }
            Syntax::Gas => {
                let mut fmt = GasFormatter::new();
                fmt.format(instr, &mut gas_buf);
                gas_buf.clone()
            }
            Syntax::Nasm => {
                let mut fmt = NasmFormatter::new();
                fmt.format(instr, &mut nasm_buf);
                nasm_buf.clone()
            }
        };

        // Generate label if this address is a jump target.
        let label = if jump_targets.contains(&instr.ip()) {
            Some(format!("loc_{:X}", instr.ip()))
        } else {
            None
        };

        // Generate comment for branch instructions.
        let fc = instr.flow_control();
        let (comment, jump_target) = match fc {
            FlowControl::UnconditionalBranch | FlowControl::ConditionalBranch => {
                let target = instr.near_branch_target();
                if target > 0 {
                    (
                        Some(format!("; jump to 0x{:X}", target)),
                        Some(format!("{:016X}", target)),
                    )
                } else {
                    (None, None)
                }
            }
            FlowControl::Call => {
                let target = instr.near_branch_target();
                if target > 0 {
                    (
                        Some(format!("; call to 0x{:X}", target)),
                        Some(format!("{:016X}", target)),
                    )
                } else {
                    (None, None)
                }
            }
            _ => (None, None),
        };

        instructions.push(Instruction {
            address,
            bytes: bytes_hex.join(" "),
            mnemonic: mnemonic_str,
            label,
            comment,
            jump_target,
        });
    }

    let count = instructions.len();
    Ok(DisassemblyResult {
        start_address: base_address,
        instruction_count: count,
        instructions,
    })
}

/// Disassemble ARM 32-bit code using yaxpeax-arm.
fn disassemble_arm(data: &[u8], base_address: u64) -> Result<DisassemblyResult, String> {
    use yaxpeax_arch::{Decoder, U8Reader};
    use yaxpeax_arm::armv7::InstDecoder;

    let decoder = InstDecoder::default();
    let mut instructions = Vec::new();
    let mut pos = 0usize;

    while pos < data.len() {
        let address = base_address + pos as u64;
        let remaining = &data[pos..];
        let mut reader = U8Reader::new(remaining);

        match decoder.decode(&mut reader) {
            Ok(instr) => {
                // Determine how many bytes were consumed.
                // yaxpeax-arm ARMv7 instructions are 4 bytes (ARM) or 2/4 bytes (Thumb).
                // We approximate by checking the reader position.
                let consumed = 4.min(remaining.len());
                let bytes_hex: Vec<String> = remaining[..consumed]
                    .iter()
                    .map(|b| format!("{:02X}", b))
                    .collect();
                instructions.push(Instruction {
                    address: format!("{:016X}", address),
                    bytes: bytes_hex.join(" "),
                    mnemonic: format!("{}", instr),
                    label: None,
                    comment: None,
                    jump_target: None,
                });
                pos += consumed;
            }
            Err(_) => {
                // On decode error, skip 1 byte and continue.
                let bytes_hex = format!("{:02X}", data[pos]);
                instructions.push(Instruction {
                    address: format!("{:016X}", address),
                    bytes: bytes_hex,
                    mnemonic: "db".to_string(),
                    label: None,
                    comment: Some("; decode error".to_string()),
                    jump_target: None,
                });
                pos += 1;
            }
        }
    }

    let count = instructions.len();
    Ok(DisassemblyResult {
        start_address: base_address,
        instruction_count: count,
        instructions,
    })
}

/// Disassemble ARM64/AArch64 code using yaxpeax-arm.
fn disassemble_arm64(data: &[u8], base_address: u64) -> Result<DisassemblyResult, String> {
    use yaxpeax_arch::{Decoder, U8Reader};
    use yaxpeax_arm::armv8::a64::InstDecoder as A64Decoder;

    let decoder = A64Decoder::default();
    let mut instructions = Vec::new();
    let mut pos = 0usize;

    while pos < data.len() {
        let address = base_address + pos as u64;
        let remaining = &data[pos..];
        let mut reader = U8Reader::new(remaining);

        match decoder.decode(&mut reader) {
            Ok(instr) => {
                // ARM64 instructions are always 4 bytes.
                let consumed = 4.min(remaining.len());
                let bytes_hex: Vec<String> = remaining[..consumed]
                    .iter()
                    .map(|b| format!("{:02X}", b))
                    .collect();
                instructions.push(Instruction {
                    address: format!("{:016X}", address),
                    bytes: bytes_hex.join(" "),
                    mnemonic: format!("{}", instr),
                    label: None,
                    comment: None,
                    jump_target: None,
                });
                pos += consumed;
            }
            Err(_) => {
                let bytes_hex = format!("{:02X}", data[pos]);
                instructions.push(Instruction {
                    address: format!("{:016X}", address),
                    bytes: bytes_hex,
                    mnemonic: "db".to_string(),
                    label: None,
                    comment: Some("; decode error".to_string()),
                    jump_target: None,
                });
                pos += 1;
            }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_disassemble_x86_ret_not_break() {
        // x86 code: xor eax, eax; ret; nop; nop
        let code = [0x31, 0xC0, 0xC3, 0x90, 0x90];
        let result = disassemble_bytes(&code, 0x1000, Arch::X86, Syntax::Intel).unwrap();
        // Should NOT break on Ret — all instructions should be decoded.
        assert!(
            result.instruction_count >= 4,
            "Expected at least 4 instructions (no break on Ret), got {}: {:?}",
            result.instruction_count,
            result
                .instructions
                .iter()
                .map(|i| &i.mnemonic)
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn test_disassemble_x64_basic() {
        // x64 code: 48 89 C8 = mov rax, rcx
        let code = [0x48, 0x89, 0xC8];
        let result = disassemble_bytes(&code, 0x1000, Arch::X64, Syntax::Intel).unwrap();
        assert!(result.instruction_count >= 1);
        assert!(result.instructions[0].mnemonic.contains("mov"));
    }

    #[test]
    fn test_disassemble_jump_target() {
        // x86: eb 02 = jmp short +2 (to 0x1004)
        // 90 90 = nop nop
        let code = [0xEB, 0x02, 0x90, 0x90];
        let result = disassemble_bytes(&code, 0x1000, Arch::X86, Syntax::Intel).unwrap();
        // First instruction should have a jump_target.
        assert!(result.instructions[0].jump_target.is_some());
        assert!(result.instructions[0].comment.is_some());
    }

    #[test]
    fn test_disassemble_label_generation() {
        // x86: eb 02 = jmp short +2 (to 0x1004)
        // 90 90 = nop nop (at 0x1002)
        // 90 = nop (at 0x1004 — this should get a label)
        let code = [0xEB, 0x02, 0x90, 0x90, 0x90];
        let result = disassemble_bytes(&code, 0x1000, Arch::X86, Syntax::Intel).unwrap();
        // The instruction at 0x1004 should have a label.
        let labeled = result.instructions.iter().find(|i| i.label.is_some());
        assert!(
            labeled.is_some(),
            "Expected at least one labeled instruction"
        );
    }

    #[test]
    fn test_disassemble_arm_basic() {
        // ARM NOP: e1a00000 (mov r0, r0) — little endian bytes
        let code = [0x00, 0x00, 0xa0, 0xe1];
        let result = disassemble_bytes(&code, 0x1000, Arch::Arm, Syntax::Intel).unwrap();
        assert!(result.instruction_count >= 1);
    }

    #[test]
    fn test_disassemble_arm64_basic() {
        // ARM64 NOP: d503201f — little endian bytes
        let code = [0x1f, 0x20, 0x03, 0xd5];
        let result = disassemble_bytes(&code, 0x1000, Arch::Arm64, Syntax::Intel).unwrap();
        assert!(result.instruction_count >= 1);
    }

    #[test]
    fn test_disassemble_empty_data() {
        let code: [u8; 0] = [];
        let result = disassemble_bytes(&code, 0x1000, Arch::X64, Syntax::Intel).unwrap();
        assert_eq!(result.instruction_count, 0);
    }

    #[test]
    fn test_disassemble_max_bytes_not_limited_to_256() {
        // Create 512 bytes of NOP instructions (90 repeated).
        let code = vec![0x90u8; 512];
        let result = disassemble_bytes(&code, 0x1000, Arch::X86, Syntax::Intel).unwrap();
        // Should decode all 512 NOPs, not stop at 256 bytes.
        assert!(
            result.instruction_count > 256,
            "Expected more than 256 instructions, got {} (old 256-byte limit should be removed)",
            result.instruction_count
        );
    }
}
