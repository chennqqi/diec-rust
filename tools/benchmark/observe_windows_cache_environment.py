#!/usr/bin/env python3
"""Observe Windows cache-control boundaries without changing cache state."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import platform
import struct
import sys
from typing import Any


TOKEN_QUERY = 0x0008
TOKEN_PRIVILEGES = 3
TOKEN_ELEVATION_TYPE = 18
TOKEN_ELEVATION = 20
SE_PRIVILEGE_ENABLED = 0x00000002
SE_INCREASE_QUOTA_NAME = "SeIncreaseQuotaPrivilege"


class ObservationError(ValueError):
    """The Windows cache environment cannot be observed safely."""


class Luid(ctypes.Structure):
    _fields_ = [
        ("low_part", wintypes.DWORD),
        ("high_part", wintypes.LONG),
    ]


class LuidAndAttributes(ctypes.Structure):
    _fields_ = [
        ("luid", Luid),
        ("attributes", wintypes.DWORD),
    ]


class SystemInfoArch(ctypes.Structure):
    _fields_ = [
        ("processor_architecture", wintypes.WORD),
        ("reserved", wintypes.WORD),
    ]


class SystemInfoUnion(ctypes.Union):
    _fields_ = [
        ("oem_id", wintypes.DWORD),
        ("arch", SystemInfoArch),
    ]


class SystemInfo(ctypes.Structure):
    _anonymous_ = ("identity",)
    _fields_ = [
        ("identity", SystemInfoUnion),
        ("page_size", wintypes.DWORD),
        ("minimum_application_address", wintypes.LPVOID),
        ("maximum_application_address", wintypes.LPVOID),
        ("active_processor_mask", ctypes.c_size_t),
        ("number_of_processors", wintypes.DWORD),
        ("processor_type", wintypes.DWORD),
        ("allocation_granularity", wintypes.DWORD),
        ("processor_level", wintypes.WORD),
        ("processor_revision", wintypes.WORD),
    ]


def require_windows() -> tuple[Any, Any]:
    if sys.platform != "win32":
        raise ObservationError("observer requires native Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL(
        "advapi32", use_last_error=True
    )
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetNativeSystemInfo.argtypes = [
        ctypes.POINTER(SystemInfo)
    ]
    kernel32.GetNativeSystemInfo.restype = None
    kernel32.GetSystemFileCacheSize.argtypes = [
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetSystemFileCacheSize.restype = wintypes.BOOL
    kernel32.GetVolumePathNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumePathNameW.restype = wintypes.BOOL
    kernel32.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeInformationW.restype = wintypes.BOOL
    kernel32.GetDiskFreeSpaceW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetDiskFreeSpaceW.restype = wintypes.BOOL
    kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetDriveTypeW.restype = wintypes.UINT
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.LookupPrivilegeValueW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.POINTER(Luid),
    ]
    advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
    return kernel32, advapi32


def checked(result: int, operation: str) -> None:
    if not result:
        raise OSError(ctypes.get_last_error(), operation)


def query_token_information(
    advapi32: Any,
    token: wintypes.HANDLE,
    information_class: int,
) -> bytes:
    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(
        token,
        information_class,
        None,
        0,
        ctypes.byref(needed),
    )
    if needed.value == 0:
        raise OSError(
            ctypes.get_last_error(),
            f"GetTokenInformation({information_class}) size",
        )
    buffer = ctypes.create_string_buffer(needed.value)
    checked(
        advapi32.GetTokenInformation(
            token,
            information_class,
            buffer,
            needed.value,
            ctypes.byref(needed),
        ),
        f"GetTokenInformation({information_class})",
    )
    return bytes(buffer.raw[: needed.value])


def query_privilege(
    advapi32: Any,
    token: wintypes.HANDLE,
    name: str,
) -> dict[str, Any]:
    target = Luid()
    checked(
        advapi32.LookupPrivilegeValueW(
            None,
            name,
            ctypes.byref(target),
        ),
        f"LookupPrivilegeValueW({name})",
    )
    raw = query_token_information(
        advapi32,
        token,
        TOKEN_PRIVILEGES,
    )
    count = struct.unpack_from("<I", raw, 0)[0]
    entry_size = ctypes.sizeof(LuidAndAttributes)
    offset = ctypes.sizeof(wintypes.DWORD)
    if count > 4096 or offset + count * entry_size > len(raw):
        raise ObservationError("TOKEN_PRIVILEGES is malformed")
    present = False
    attributes = 0
    for index in range(count):
        entry = LuidAndAttributes.from_buffer_copy(
            raw,
            offset + index * entry_size,
        )
        if (
            entry.luid.low_part == target.low_part
            and entry.luid.high_part == target.high_part
        ):
            present = True
            attributes = entry.attributes
            break
    return {
        "name": name,
        "present": present,
        "enabled": bool(attributes & SE_PRIVILEGE_ENABLED),
        "attributes": attributes if present else None,
    }


def query_process_security(
    kernel32: Any,
    advapi32: Any,
) -> dict[str, Any]:
    token = wintypes.HANDLE()
    checked(
        advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            TOKEN_QUERY,
            ctypes.byref(token),
        ),
        "OpenProcessToken",
    )
    try:
        elevation_raw = query_token_information(
            advapi32,
            token,
            TOKEN_ELEVATION,
        )
        elevation_type_raw = query_token_information(
            advapi32,
            token,
            TOKEN_ELEVATION_TYPE,
        )
        if len(elevation_raw) < 4 or len(elevation_type_raw) < 4:
            raise ObservationError("token elevation data is truncated")
        elevation_type = struct.unpack_from(
            "<I", elevation_type_raw, 0
        )[0]
        elevation_names = {
            1: "default",
            2: "full",
            3: "limited",
        }
        if elevation_type not in elevation_names:
            raise ObservationError("unknown TOKEN_ELEVATION_TYPE")
        return {
            "elevated": bool(
                struct.unpack_from("<I", elevation_raw, 0)[0]
            ),
            "elevation_type": elevation_names[elevation_type],
            "set_system_file_cache_privilege": query_privilege(
                advapi32,
                token,
                SE_INCREASE_QUOTA_NAME,
            ),
        }
    finally:
        checked(kernel32.CloseHandle(token), "CloseHandle(token)")


def query_system(kernel32: Any) -> dict[str, Any]:
    info = SystemInfo()
    kernel32.GetNativeSystemInfo(ctypes.byref(info))
    version = sys.getwindowsversion()
    minimum = ctypes.c_size_t()
    maximum = ctypes.c_size_t()
    flags = wintypes.DWORD()
    checked(
        kernel32.GetSystemFileCacheSize(
            ctypes.byref(minimum),
            ctypes.byref(maximum),
            ctypes.byref(flags),
        ),
        "GetSystemFileCacheSize",
    )
    return {
        "windows_version": {
            "major": version.major,
            "minor": version.minor,
            "build": version.build,
            "platform": version.platform,
            "service_pack": version.service_pack,
        },
        "machine": platform.machine(),
        "pointer_width_bits": ctypes.sizeof(ctypes.c_void_p) * 8,
        "page_size": info.page_size,
        "allocation_granularity": info.allocation_granularity,
        "logical_processor_count": info.number_of_processors,
        "system_file_cache_limits": {
            "minimum_bytes": minimum.value,
            "maximum_bytes": maximum.value,
            "flags": flags.value,
            "minimum_hard_enabled": bool(flags.value & 0x4),
            "maximum_hard_enabled": bool(flags.value & 0x1),
        },
    }


def query_volume(kernel32: Any, target_root: Path) -> dict[str, Any]:
    resolved = target_root.resolve(strict=True)
    volume_path = ctypes.create_unicode_buffer(32768)
    checked(
        kernel32.GetVolumePathNameW(
            str(resolved),
            volume_path,
            len(volume_path),
        ),
        "GetVolumePathNameW",
    )
    filesystem = ctypes.create_unicode_buffer(256)
    maximum_component_length = wintypes.DWORD()
    filesystem_flags = wintypes.DWORD()
    checked(
        kernel32.GetVolumeInformationW(
            volume_path.value,
            None,
            0,
            None,
            ctypes.byref(maximum_component_length),
            ctypes.byref(filesystem_flags),
            filesystem,
            len(filesystem),
        ),
        "GetVolumeInformationW",
    )
    sectors_per_cluster = wintypes.DWORD()
    bytes_per_sector = wintypes.DWORD()
    free_clusters = wintypes.DWORD()
    total_clusters = wintypes.DWORD()
    checked(
        kernel32.GetDiskFreeSpaceW(
            volume_path.value,
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters),
        ),
        "GetDiskFreeSpaceW",
    )
    drive_types = {
        0: "unknown",
        1: "no-root-directory",
        2: "removable",
        3: "fixed",
        4: "remote",
        5: "cdrom",
        6: "ramdisk",
    }
    drive_type = kernel32.GetDriveTypeW(volume_path.value)
    if drive_type not in drive_types:
        raise ObservationError("unknown Windows drive type")
    return {
        "filesystem": filesystem.value,
        "drive_type": drive_types[drive_type],
        "maximum_component_length": maximum_component_length.value,
        "filesystem_flags": filesystem_flags.value,
        "bytes_per_sector": bytes_per_sector.value,
        "sectors_per_cluster": sectors_per_cluster.value,
        "target_path_recorded": False,
        "volume_identity_recorded": False,
    }


def observe(target_root: Path) -> dict[str, Any]:
    kernel32, advapi32 = require_windows()
    return {
        "schema_version": 1,
        "platform": query_system(kernel32),
        "process": query_process_security(kernel32, advapi32),
        "target_volume": query_volume(kernel32, target_root),
        "api_availability": {
            "get_system_file_cache_size": hasattr(
                kernel32, "GetSystemFileCacheSize"
            ),
            "set_system_file_cache_size": hasattr(
                kernel32, "SetSystemFileCacheSize"
            ),
            "empty_working_set": hasattr(
                ctypes.WinDLL("psapi", use_last_error=True),
                "EmptyWorkingSet",
            ),
            "flush_file_buffers": hasattr(
                kernel32, "FlushFileBuffers"
            ),
        },
        "scope": {
            "read_only_observation": True,
            "cache_state_changed": False,
            "set_system_file_cache_size_called": False,
            "empty_working_set_called": False,
            "flush_file_buffers_called": False,
            "no_buffering_handle_opened": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-root",
        type=Path,
        default=Path.cwd(),
        help="existing path whose Windows volume is observed",
    )
    return parser.parse_args()


def main() -> int:
    try:
        report = observe(parse_args().target_root)
        print(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (ObservationError, OSError, ValueError) as error:
        print(
            f"Windows cache environment observation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
