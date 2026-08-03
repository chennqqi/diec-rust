"""Generate a minimal PE32 file with real import and export tables for testing.

This PE file has:
- MZ header + DOS stub
- PE signature + COFF header + Optional header
- .text section (minimal)
- .rdata section with:
  - Import directory (1 library: "testlib.dll" with 1 function)
  - Export directory (2 exports: "ExportA" and "ExportB")
- Data directories pointing to both tables

This is used by corpus_differential.rs and pe_rule_e2e.rs to verify
that PE rules can detect imports/exports in real PE files.
"""
import struct
import os

def align(value, alignment):
    return (value + alignment - 1) & ~(alignment - 1)

def build_pe_with_tables():
    # Constants
    FILE_ALIGNMENT = 0x200
    SECTION_ALIGNMENT = 0x1000

    # We'll build:
    # 1. Headers (DOS + PE + COFF + Optional + Section headers)
    # 2. .text section (minimal, just a RET instruction)
    # 3. .rdata section (import dir + export dir + name strings)

    # DOS header (64 bytes) + DOS stub
    dos_stub = b"This program cannot be run in DOS mode.\r\r\n$"
    dos_header = bytearray(64)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, 64 + len(dos_stub) + 1)  # e_lfanew

    # PE signature
    pe_sig = b"PE\x00\x00"

    # COFF header (20 bytes)
    coff = bytearray(20)
    struct.pack_into("<H", coff, 0, 0x014C)   # Machine: I386
    struct.pack_into("<H", coff, 2, 2)        # NumberOfSections: 2 (.text + .rdata)
    struct.pack_into("<I", coff, 4, 0)        # TimeDateStamp
    struct.pack_into("<I", coff, 8, 0)        # PointerToSymbolTable
    struct.pack_into("<I", coff, 12, 0)       # NumberOfSymbols
    struct.pack_into("<H", coff, 16, 224)     # SizeOfOptionalHeader (96 + 16*8)
    struct.pack_into("<H", coff, 18, 0x0102)  # Characteristics: EXECUTABLE | 32BIT

    # Optional header PE32 (96 bytes base + 128 bytes data dirs = 224)
    opt = bytearray(224)
    struct.pack_into("<H", opt, 0, 0x010B)    # Magic: PE32
    opt[2] = 12  # MajorLinkerVersion
    opt[3] = 0   # MinorLinkerVersion
    struct.pack_into("<I", opt, 4, 0x100)     # SizeOfCode
    struct.pack_into("<I", opt, 8, 0x200)     # SizeOfInitializedData
    struct.pack_into("<I", opt, 12, 0)        # SizeOfUninitializedData
    struct.pack_into("<I", opt, 16, 0x1000)   # AddressOfEntryPoint
    struct.pack_into("<I", opt, 20, 0x1000)   # BaseOfCode
    struct.pack_into("<I", opt, 24, 0x2000)   # BaseOfData
    struct.pack_into("<I", opt, 28, 0x400000) # ImageBase
    struct.pack_into("<I", opt, 32, SECTION_ALIGNMENT)
    struct.pack_into("<I", opt, 36, FILE_ALIGNMENT)
    struct.pack_into("<H", opt, 40, 4)  # MajorOSVersion
    struct.pack_into("<H", opt, 42, 0)  # MinorOSVersion
    struct.pack_into("<I", opt, 44, 0)  # ImageVersion
    struct.pack_into("<I", opt, 48, 0)  # SubsystemVersion (4.0 = Win32 GUI)
    struct.pack_into("<I", opt, 52, 0)  # Win32VersionValue
    struct.pack_into("<I", opt, 56, 0x4000)  # SizeOfImage
    struct.pack_into("<I", opt, 60, 0x200)   # SizeOfHeaders
    struct.pack_into("<I", opt, 64, 0)       # CheckSum
    struct.pack_into("<H", opt, 68, 3)       # Subsystem: CONSOLE
    struct.pack_into("<H", opt, 70, 0)       # DllCharacteristics
    struct.pack_into("<I", opt, 72, 0x100000)  # SizeOfStackReserve
    struct.pack_into("<I", opt, 76, 0x1000)    # SizeOfStackCommit
    struct.pack_into("<I", opt, 80, 0x100000)  # SizeOfHeapReserve
    struct.pack_into("<I", opt, 84, 0x1000)    # SizeOfHeapCommit
    struct.pack_into("<I", opt, 88, 0)         # LoaderFlags
    struct.pack_into("<I", opt, 92, 16)        # NumberOfRvaAndSizes

    # Data directories (16 * 8 = 128 bytes) start at opt+96
    dd_off = 96
    # DD[0] = Export, DD[1] = Import, rest = 0
    # Will fill in after calculating offsets.

    # Section headers (2 * 40 = 80 bytes)
    # .text: VirtualAddress=0x1000, RawData at 0x200, size=0x200
    text_hdr = bytearray(40)
    text_hdr[0:6] = b".text\x00"
    struct.pack_into("<I", text_hdr, 8, 0x100)   # VirtualSize
    struct.pack_into("<I", text_hdr, 12, 0x1000)  # VirtualAddress
    struct.pack_into("<I", text_hdr, 16, 0x200)   # SizeOfRawData
    struct.pack_into("<I", text_hdr, 20, 0x200)   # PointerToRawData
    struct.pack_into("<I", text_hdr, 36, 0x60000020)  # Characteristics: CODE|EXEC|READ

    # .rdata: VirtualAddress=0x2000, RawData at 0x400, size=0x400
    rdata_hdr = bytearray(40)
    rdata_hdr[0:7] = b".rdata\x00"
    struct.pack_into("<I", rdata_hdr, 8, 0x400)   # VirtualSize
    struct.pack_into("<I", rdata_hdr, 12, 0x2000)  # VirtualAddress
    struct.pack_into("<I", rdata_hdr, 16, 0x400)   # SizeOfRawData
    struct.pack_into("<I", rdata_hdr, 20, 0x400)   # PointerToRawData
    struct.pack_into("<I", rdata_hdr, 36, 0x40000040)  # Characteristics: INITIALIZED_DATA|READ

    # Build headers
    headers = dos_header + dos_stub + b"\x00" + pe_sig + coff + opt + text_hdr + rdata_hdr
    headers_padded = headers + b"\x00" * (0x200 - len(headers))

    # .text section: just a RET instruction + padding
    text_section = b"\xC3" + b"\x00" * (0x200 - 1)  # RET

    # .rdata section: import + export tables
    # Layout within .rdata (RVA 0x2000, file offset 0x400):
    #   0x000: Export directory (40 bytes)
    #   0x028: Export name pointers (2 * 4 = 8 bytes)
    #   0x030: Export name ordinals (2 * 2 = 4 bytes)
    #   0x034: Export name strings
    #   0x0A0: Import descriptors (2 * 20 = 40 bytes, 1 + terminator)
    #   0x0C8: Import library name
    #   0x0E0: Import thunk (zero terminator)

    rdata = bytearray(0x400)
    rdata_rva = 0x2000

    # --- Export directory ---
    export_dir_off = 0x000
    export_dir_rva = rdata_rva + export_dir_off

    export_names = [b"ExportA\x00", b"ExportB\x00"]
    num_names = len(export_names)

    # AddressOfNames: points to array of name RVAs
    names_array_off = 0x028
    names_array_rva = rdata_rva + names_array_off

    # AddressOfNameOrdinals
    ordinals_off = 0x030

    # Name strings start at 0x034
    name_strings_off = 0x034
    name_rvas = []
    pos = name_strings_off
    for name in export_names:
        name_rvas.append(rdata_rva + pos)
        rdata[pos:pos+len(name)] = name
        pos += len(name)

    # Fill export directory
    struct.pack_into("<I", rdata, export_dir_off + 12, rdata_rva + 0x100)  # Name RVA (DLL name, we'll put it later)
    struct.pack_into("<I", rdata, export_dir_off + 16, 1)    # Base
    struct.pack_into("<I", rdata, export_dir_off + 20, num_names)  # NumberOfFunctions
    struct.pack_into("<I", rdata, export_dir_off + 24, num_names)  # NumberOfNames
    struct.pack_into("<I", rdata, export_dir_off + 28, names_array_rva)  # AddressOfFunctions (we reuse names array area for simplicity)
    struct.pack_into("<I", rdata, export_dir_off + 32, names_array_rva)  # AddressOfNames
    struct.pack_into("<I", rdata, export_dir_off + 36, rdata_rva + ordinals_off)  # AddressOfNameOrdinals

    # Name pointer array
    for i, rva in enumerate(name_rvas):
        struct.pack_into("<I", rdata, names_array_off + i * 4, rva)

    # Ordinals (just 0, 1)
    struct.pack_into("<H", rdata, ordinals_off, 0)
    struct.pack_into("<H", rdata, ordinals_off + 2, 1)

    # DLL name at offset 0x100
    dll_name_off = 0x100
    dll_name = b"testdll.dll\x00"
    rdata[dll_name_off:dll_name_off+len(dll_name)] = dll_name
    struct.pack_into("<I", rdata, export_dir_off + 12, rdata_rva + dll_name_off)

    # --- Import directory ---
    import_dir_off = 0x0A0
    import_dir_rva = rdata_rva + import_dir_off

    # Import library name at 0x0C8
    import_lib_name_off = 0x0C8
    import_lib_name = b"kernel32.dll\x00"
    rdata[import_lib_name_off:import_lib_name_off+len(import_lib_name)] = import_lib_name
    import_lib_name_rva = rdata_rva + import_lib_name_off

    # Import thunk (ILT) at 0x0E0 - just a zero terminator (no actual functions)
    ilt_off = 0x0E0
    ilt_rva = rdata_rva + ilt_off
    # Thunk is zero (terminator)

    # Import descriptor
    struct.pack_into("<I", rdata, import_dir_off, ilt_rva)       # OriginalFirstThunk
    struct.pack_into("<I", rdata, import_dir_off + 4, 0)         # TimeDateStamp
    struct.pack_into("<I", rdata, import_dir_off + 8, 0)         # ForwarderChain
    struct.pack_into("<I", rdata, import_dir_off + 12, import_lib_name_rva)  # Name
    struct.pack_into("<I", rdata, import_dir_off + 16, ilt_rva)  # FirstThunk

    # Terminator (all zeros, already zero)

    # Set data directories
    export_size = 40 + num_names * 4 + num_names * 2 + sum(len(n) for n in export_names)
    struct.pack_into("<I", opt, dd_off, export_dir_rva)
    struct.pack_into("<I", opt, dd_off + 4, export_size)

    import_size = 40  # 2 descriptors * 20 bytes
    struct.pack_into("<I", opt, dd_off + 8, import_dir_rva)
    struct.pack_into("<I", opt, dd_off + 12, import_size)

    # Rebuild headers with updated data directories
    headers = dos_header + dos_stub + b"\x00" + pe_sig + coff + opt + text_hdr + rdata_hdr
    headers_padded = headers + b"\x00" * (0x200 - len(headers))

    return bytes(headers_padded + text_section + rdata)

data = build_pe_with_tables()
out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "corpus", "with-tables.exe")
with open(out_path, "wb") as f:
    f.write(data)
print(f"Written {len(data)} bytes to {out_path}")

# Verify with our own parser
import struct as s
e_lfanew = s.unpack_from("<I", data, 0x3C)[0]
print(f"e_lfanew: 0x{e_lfanew:X}")
print(f"PE sig: {data[e_lfanew:e_lfanew+4]}")
coff = e_lfanew + 4
num_sections = s.unpack_from("<H", data, coff + 2)[0]
print(f"NumberOfSections: {num_sections}")
opt = coff + 20
magic = s.unpack_from("<H", data, opt)[0]
print(f"Optional header magic: 0x{magic:X} ({'PE32' if magic == 0x10B else 'PE32+' if magic == 0x20B else 'unknown'})")
dd = opt + 96
export_rva = s.unpack_from("<I", data, dd)[0]
export_size = s.unpack_from("<I", data, dd + 4)[0]
import_rva = s.unpack_from("<I", data, dd + 8)[0]
import_size = s.unpack_from("<I", data, dd + 12)[0]
print(f"Export: RVA=0x{export_rva:X}, size={export_size}")
print(f"Import: RVA=0x{import_rva:X}, size={import_size}")
