"""Generate expanded corpus samples for differential testing.

Creates additional PE/ELF/Mach-O samples with richer structures:
- PE with resources (version info + manifest)
- PE with .NET CLR header
- ELF with DT_NEEDED entries
- Mach-O with LC_LOAD_DYLIB entries

All samples are deterministic and benign.
"""
from __future__ import annotations

import os
import struct
import sys


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


# ---------------------------------------------------------------------------
# PE with resources: version info + manifest
# ---------------------------------------------------------------------------

def make_pe_with_resources() -> bytes:
    """Build a PE32 with .rsrc section containing version info and manifest."""
    FILE_ALIGNMENT = 0x200
    SECTION_ALIGNMENT = 0x1000

    # DOS header (64 bytes) + minimal stub
    dos_header = bytearray(64)
    dos_header[0:2] = b"MZ"
    e_lfanew = 64
    struct.pack_into("<I", dos_header, 0x3C, e_lfanew)

    pe_sig = b"PE\x00\x00"

    # COFF header (20 bytes)
    coff = bytearray(20)
    struct.pack_into("<H", coff, 0, 0x014C)   # Machine: I386
    struct.pack_into("<H", coff, 2, 2)        # NumberOfSections: .text + .rsrc
    struct.pack_into("<H", coff, 16, 224)     # SizeOfOptionalHeader
    struct.pack_into("<H", coff, 18, 0x0102)  # Characteristics

    # Optional header PE32 (224 bytes)
    opt = bytearray(224)
    struct.pack_into("<H", opt, 0, 0x010B)    # Magic: PE32
    opt[2] = 14  # MajorLinkerVersion
    struct.pack_into("<I", opt, 16, 0x1000)   # AddressOfEntryPoint
    struct.pack_into("<I", opt, 20, 0x1000)   # BaseOfCode
    struct.pack_into("<I", opt, 28, 0x400000) # ImageBase
    struct.pack_into("<I", opt, 32, SECTION_ALIGNMENT)
    struct.pack_into("<I", opt, 36, FILE_ALIGNMENT)
    struct.pack_into("<I", opt, 56, 0x4000)   # SizeOfImage
    struct.pack_into("<I", opt, 60, 0x200)    # SizeOfHeaders
    struct.pack_into("<H", opt, 68, 3)        # Subsystem: CONSOLE
    struct.pack_into("<I", opt, 92, 16)       # NumberOfRvaAndSizes

    # Section headers
    text_hdr = bytearray(40)
    text_hdr[0:6] = b".text\x00"
    struct.pack_into("<I", text_hdr, 8, 0x100)
    struct.pack_into("<I", text_hdr, 12, 0x1000)
    struct.pack_into("<I", text_hdr, 16, 0x200)
    struct.pack_into("<I", text_hdr, 20, 0x200)
    struct.pack_into("<I", text_hdr, 36, 0x60000020)

    rsrc_hdr = bytearray(40)
    rsrc_hdr[0:6] = b".rsrc\x00"
    struct.pack_into("<I", rsrc_hdr, 8, 0x400)
    struct.pack_into("<I", rsrc_hdr, 12, 0x2000)
    struct.pack_into("<I", rsrc_hdr, 16, 0x200)
    struct.pack_into("<I", rsrc_hdr, 20, 0x400)
    struct.pack_into("<I", rsrc_hdr, 36, 0x40000040)

    headers = dos_header + pe_sig + coff + opt + text_hdr + rsrc_hdr
    headers_padded = headers + b"\x00" * (0x200 - len(headers))

    # .text section: RET
    text_section = b"\xC3" + b"\x00" * (0x200 - 1)

    # .rsrc section: resource directory
    # Layout:
    #   Root directory
    #     -> RT_VERSION (type 16) -> directory -> entry (id=1) -> data entry -> VS_VERSION_INFO
    #     -> RT_MANIFEST (type 24) -> directory -> entry (id=1) -> data entry -> manifest XML
    rsrc = bytearray(0x200)
    rsrc_rva = 0x2000

    # Root directory at offset 0
    root_off = 0
    # 2 named/id entries: RT_VERSION (id=16), RT_MANIFEST (id=24)
    struct.pack_into("<I", rsrc, root_off + 12, 0)      # TimeDateStamp
    struct.pack_into("<H", rsrc, root_off + 14, 0)      # MajorVersion
    struct.pack_into("<H", rsrc, root_off + 16, 0)      # MinorVersion
    struct.pack_into("<H", rsrc, root_off + 18, 0)      # NumberOfNamedEntries
    struct.pack_into("<H", rsrc, root_off + 20, 2)      # NumberOfIdEntries

    # Root entries (16 bytes each): ID + OffsetToData/Dir
    entry_off = root_off + 24
    # RT_VERSION (id=16) -> subdirectory
    struct.pack_into("<I", rsrc, entry_off, 16)
    version_subdir_off = 0x100  # offset within rsrc
    struct.pack_into("<I", rsrc, entry_off + 4, version_subdir_off | 0x80000000)

    # RT_MANIFEST (id=24) -> subdirectory
    struct.pack_into("<I", rsrc, entry_off + 8, 24)
    manifest_subdir_off = 0x140
    struct.pack_into("<I", rsrc, entry_off + 12, manifest_subdir_off | 0x80000000)

    # Version subdirectory (offset 0x100)
    struct.pack_into("<H", rsrc, version_subdir_off + 18, 0)  # NumberOfNamedEntries
    struct.pack_into("<H", rsrc, version_subdir_off + 20, 1)  # NumberOfIdEntries
    # Entry: id=1 -> data
    struct.pack_into("<I", rsrc, version_subdir_off + 24, 1)
    version_data_off = 0x110
    struct.pack_into("<I", rsrc, version_subdir_off + 28, version_data_off)

    # Version data entry (IMAGE_RESOURCE_DATA_ENTRY, 16 bytes at 0x110)
    version_info_off = 0x120  # offset within rsrc for VS_VERSIONINFO
    struct.pack_into("<I", rsrc, version_data_off, rsrc_rva + version_info_off)  # OffsetToData (RVA)
    struct.pack_into("<I", rsrc, version_data_off + 4, 0x60)  # Size

    # VS_VERSION_INFO at offset 0x120 (simplified)
    # Header: wLength, wValueLength, wType, szKey ("VS_VERSION_INFO")
    vi = bytearray(0x60)
    struct.pack_into("<H", vi, 0, 0x60)   # wLength
    struct.pack_into("<H", vi, 2, 0x34)   # wValueLength (size of VS_FIXEDFILEINFO)
    struct.pack_into("<H", vi, 4, 0)      # wType (binary)
    # szKey: "VS_VERSION_INFO" in UTF-16LE
    key = "VS_VERSION_INFO".encode("utf-16-le") + b"\x00\x00"
    vi[6:6+len(key)] = key
    # VS_FIXEDFILEINFO at offset 6+len(key) padded to 4-byte boundary
    ffi_off = align(6 + len(key), 4)
    struct.pack_into("<I", vi, ffi_off, 0xFEEF04BD)  # dwSignature
    struct.pack_into("<I", vi, ffi_off + 4, 0x00010000)  # dwStrucVersion
    # dwFileVersion: 1.2.3.4
    struct.pack_into("<HHHH", vi, ffi_off + 8, 2, 1, 4, 3)
    # dwProductVersion: 1.2.3.4
    struct.pack_into("<HHHH", vi, ffi_off + 16, 2, 1, 4, 3)
    struct.pack_into("<I", vi, ffi_off + 24, 0x3F)  # dwFileFlagsMask
    struct.pack_into("<I", vi, ffi_off + 28, 0)     # dwFileFlags
    struct.pack_into("<I", vi, ffi_off + 32, 0x40004)  # dwFileOS (NT_WINDOWS32)
    struct.pack_into("<I", vi, ffi_off + 36, 1)     # dwFileType (VFT_APP)
    rsrc[version_info_off:version_info_off+len(vi)] = vi

    # Manifest subdirectory (offset 0x140)
    struct.pack_into("<H", rsrc, manifest_subdir_off + 18, 0)
    struct.pack_into("<H", rsrc, manifest_subdir_off + 20, 1)
    struct.pack_into("<I", rsrc, manifest_subdir_off + 24, 1)
    manifest_data_off = 0x150
    struct.pack_into("<I", rsrc, manifest_subdir_off + 28, manifest_data_off)

    # Manifest data entry (16 bytes at 0x150)
    manifest_xml_off = 0x160
    manifest_xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"></assembly>\r\n'
    struct.pack_into("<I", rsrc, manifest_data_off, rsrc_rva + manifest_xml_off)
    struct.pack_into("<I", rsrc, manifest_data_off + 4, len(manifest_xml))

    # Manifest XML at offset 0x160
    if manifest_xml_off + len(manifest_xml) > len(rsrc):
        rsrc.extend(b"\x00" * (manifest_xml_off + len(manifest_xml) - len(rsrc)))
    rsrc[manifest_xml_off:manifest_xml_off+len(manifest_xml)] = manifest_xml

    # Set resource data directory (index 2)
    struct.pack_into("<I", opt, 96 + 2*8, rsrc_rva)      # VirtualAddress
    struct.pack_into("<I", opt, 96 + 2*8 + 4, len(rsrc))  # Size

    # Pad rsrc to FILE_ALIGNMENT
    rsrc_padded = bytes(rsrc) + b"\x00" * (align(len(rsrc), FILE_ALIGNMENT) - len(rsrc))

    return headers_padded + text_section + rsrc_padded


# ---------------------------------------------------------------------------
# PE with .NET CLR header
# ---------------------------------------------------------------------------

def make_pe_dotnet() -> bytes:
    """Build a PE32 with a .NET CLR header (data directory index 14)."""
    FILE_ALIGNMENT = 0x200
    SECTION_ALIGNMENT = 0x1000

    dos_header = bytearray(64)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, 64)

    pe_sig = b"PE\x00\x00"
    coff = bytearray(20)
    struct.pack_into("<H", coff, 0, 0x014C)
    struct.pack_into("<H", coff, 2, 1)  # 1 section
    struct.pack_into("<H", coff, 16, 224)
    struct.pack_into("<H", coff, 18, 0x0102)

    opt = bytearray(224)
    struct.pack_into("<H", opt, 0, 0x010B)
    struct.pack_into("<I", opt, 16, 0x1000)
    struct.pack_into("<I", opt, 20, 0x1000)
    struct.pack_into("<I", opt, 28, 0x400000)
    struct.pack_into("<I", opt, 32, SECTION_ALIGNMENT)
    struct.pack_into("<I", opt, 36, FILE_ALIGNMENT)
    struct.pack_into("<I", opt, 56, 0x3000)
    struct.pack_into("<I", opt, 60, 0x200)
    struct.pack_into("<H", opt, 68, 3)
    struct.pack_into("<I", opt, 92, 16)

    # .text section with CLR header
    text_hdr = bytearray(40)
    text_hdr[0:6] = b".text\x00"
    struct.pack_into("<I", text_hdr, 8, 0x200)
    struct.pack_into("<I", text_hdr, 12, 0x1000)
    struct.pack_into("<I", text_hdr, 16, 0x200)
    struct.pack_into("<I", text_hdr, 20, 0x200)
    struct.pack_into("<I", text_hdr, 36, 0x60000020)

    headers = dos_header + pe_sig + coff + opt + text_hdr
    headers_padded = headers + b"\x00" * (0x200 - len(headers))

    # .text section: RET + CLR header at offset 0x1000 (RVA)
    text = bytearray(0x200)
    text[0] = 0xC3  # RET

    # CLR header at RVA 0x1010 (offset 0x10 in section)
    clr_off = 0x10
    clr_rva = 0x1010
    clr_size = 72
    # IMAGE_COR20_HEADER (72 bytes)
    struct.pack_into("<I", text, clr_off, 0x48)     # cb (size)
    struct.pack_into("<H", text, clr_off + 4, 2)    # MajorRuntimeVersion
    struct.pack_into("<H", text, clr_off + 6, 5)    # MinorRuntimeVersion
    # MetaData directory entry (rva, size)
    struct.pack_into("<I", text, clr_off + 8, 0x1050)   # MetaData RVA
    struct.pack_into("<I", text, clr_off + 12, 0x40)    # MetaData Size

    # Set CLR data directory (index 14)
    struct.pack_into("<I", opt, 96 + 14*8, clr_rva)
    struct.pack_into("<I", opt, 96 + 14*8 + 4, clr_size)

    # Re-build headers with updated opt
    headers = dos_header + pe_sig + coff + opt + text_hdr
    headers_padded = headers + b"\x00" * (0x200 - len(headers))

    return headers_padded + bytes(text)


# ---------------------------------------------------------------------------
# ELF with DT_NEEDED entries
# ---------------------------------------------------------------------------

def make_elf_with_deps() -> bytes:
    """Build an ELF64 with DT_NEEDED dynamic entries."""
    # ELF64 header (64 bytes)
    ident = b"\x7fELF" + bytes((2, 1, 1, 0, 0)) + bytes(7)
    ehdr = bytearray(ident + b"\x00" * (64 - len(ident)))
    struct.pack_into("<H", ehdr, 16, 3)    # e_type: ET_DYN
    struct.pack_into("<H", ehdr, 18, 62)   # e_machine: EM_X86_64
    struct.pack_into("<I", ehdr, 20, 1)    # e_version
    struct.pack_into("<Q", ehdr, 24, 0)    # e_entry
    struct.pack_into("<Q", ehdr, 32, 0)    # e_phoff
    struct.pack_into("<Q", ehdr, 40, 64)   # e_shoff (section headers right after)
    struct.pack_into("<I", ehdr, 48, 0)    # e_flags
    struct.pack_into("<H", ehdr, 52, 64)   # e_ehsize
    struct.pack_into("<H", ehdr, 54, 0)    # e_phentsize
    struct.pack_into("<H", ehdr, 56, 0)    # e_phnum
    struct.pack_into("<H", ehdr, 58, 64)   # e_shentsize
    struct.pack_into("<H", ehdr, 60, 3)    # e_shnum: .dynstr, .dynsym, .dynamic
    struct.pack_into("<H", ehdr, 62, 0)    # e_shstrndx

    # Section data follows at offset 64 + 3*64 = 256
    shdr_off = 64
    data_off = shdr_off + 3 * 64  # 256

    # .dynstr: string table with lib names
    dynstr = b"\x00libtest.so\x00libc.so.6\x00"
    dynstr_off = data_off
    libtest_name_off = 1  # offset of "libtest.so" in dynstr
    libc_name_off = 11    # offset of "libc.so.6" in dynstr

    # .dynsym: minimal (just null entry)
    dynsym = b"\x00" * 24  # one null Elf64_Sym
    dynsym_off = dynstr_off + len(dynstr)

    # .dynamic: DT_NEEDED entries + DT_NULL
    dynamic = bytearray()
    # DT_NEEDED for libtest.so
    dynamic += struct.pack("<qQ", 1, libtest_name_off)   # DT_NEEDED=1
    # DT_NEEDED for libc.so.6
    dynamic += struct.pack("<qQ", 1, libc_name_off)      # DT_NEEDED=1
    # DT_STRTAB
    dynamic += struct.pack("<qQ", 5, dynstr_off)          # DT_STRTAB=5
    # DT_SYMTAB
    dynamic += struct.pack("<qQ", 6, dynsym_off)          # DT_SYMTAB=6
    # DT_NULL (terminator)
    dynamic += struct.pack("<qQ", 0, 0)
    dynamic_off = dynsym_off + len(dynsym)

    total_size = dynamic_off + len(dynamic)

    # Section headers (3 * 64 bytes)
    # .dynstr (section 0)
    sh0 = bytearray(64)
    sh0[0:8] = b"\x00" * 8  # sh_name (unnamed)
    struct.pack_into("<I", sh0, 4, 3)     # sh_type: SHT_STRTAB
    struct.pack_into("<Q", sh0, 24, dynstr_off)  # sh_offset
    struct.pack_into("<Q", sh0, 32, len(dynstr)) # sh_size

    # .dynsym (section 1)
    sh1 = bytearray(64)
    struct.pack_into("<I", sh1, 4, 11)    # sh_type: SHT_DYNSYM
    struct.pack_into("<Q", sh1, 24, dynsym_off)
    struct.pack_into("<Q", sh1, 32, len(dynsym))
    struct.pack_into("<I", sh1, 40, 24)   # sh_entsize

    # .dynamic (section 2)
    sh2 = bytearray(64)
    struct.pack_into("<I", sh2, 4, 6)     # sh_type: SHT_DYNAMIC
    struct.pack_into("<Q", sh2, 24, dynamic_off)
    struct.pack_into("<Q", sh2, 32, len(dynamic))
    struct.pack_into("<I", sh2, 40, 16)   # sh_entsize

    result = bytes(ehdr) + bytes(sh0) + bytes(sh1) + bytes(sh2)
    result += dynstr + dynsym + bytes(dynamic)

    return result


# ---------------------------------------------------------------------------
# Mach-O with LC_LOAD_DYLIB
# ---------------------------------------------------------------------------

def make_macho_with_dylib() -> bytes:
    """Build a Mach-O 64 with LC_LOAD_DYLIB load command."""
    # Mach-O 64 header (32 bytes)
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,   # magic
        0x01000007,   # cputype: CPU_TYPE_X86_64
        3,            # cpusubtype
        2,            # filetype: MH_EXECUTE
        2,            # ncmds: LC_SEGMENT + LC_LOAD_DYLIB
        0,            # sizeofcmds (fill later)
        0,            # flags
        0,            # reserved
    )

    # LC_SEGMENT_64 (72 bytes)
    seg_name = b"__TEXT" + b"\x00" * 10
    segment = struct.pack(
        "<II16sQQQQiiII",
        0x19,         # cmd: LC_SEGMENT_64
        72,           # cmdsize
        seg_name,     # segname
        0,            # vmaddr
        0x1000,       # vmsize
        0,            # fileoff
        0,            # filesize
        7,            # maxprot
        5,            # initprot
        0,            # nsects
        0,            # flags
    )

    # LC_LOAD_DYLIB (cmd=12)
    dylib_name = b"/usr/lib/libSystem.B.dylib\x00"
    # Align to 8 bytes
    dylib_name_padded = dylib_name + b"\x00" * (align(len(dylib_name), 8) - len(dylib_name))
    cmdsize = 24 + len(dylib_name_padded)  # 24 = cmd(4) + cmdsize(4) + offset(4) + size(4) + timestamp(4) + current_version(4)

    load_dylib = struct.pack(
        "<IIIIII",
        12,           # cmd: LC_LOAD_DYLIB
        cmdsize,      # cmdsize
        24,           # name offset (after the 24-byte header)
        len(dylib_name),  # name size (without padding)
        0,            # timestamp
        0x10000,      # current_version (1.0.0)
    ) + dylib_name_padded

    sizeofcmds = len(segment) + len(load_dylib)

    # Re-build header with sizeofcmds
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x01000007,
        3,
        2,
        2,
        sizeofcmds,
        0,
        0,
    )

    return header + segment + load_dylib


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "corpus")
    out_dir = os.path.abspath(out_dir)

    samples = [
        ("pe-with-resources.exe", make_pe_with_resources()),
        ("pe-dotnet.exe", make_pe_dotnet()),
        ("elf-with-deps.elf", make_elf_with_deps()),
        ("macho-with-dylib.macho", make_macho_with_dylib()),
    ]

    for name, data in samples:
        path = os.path.join(out_dir, name)
        with open(path, "wb") as f:
            f.write(data)
        print(f"Generated {name}: {len(data)} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
