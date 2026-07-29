#!/usr/bin/env python3
"""Observe Linux cache-control boundaries without changing cache state."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Any


CAP_SYS_ADMIN = 21
DROP_CACHES = Path("/proc/sys/vm/drop_caches")
RELEVANT_MOUNTS = ("/", "/proc/sys", "/sys/fs/cgroup")
VOLATILE_SUPER_OPTIONS = {"lowerdir", "upperdir", "workdir"}


class ObservationError(ValueError):
    """The cache environment cannot be observed safely."""


def parse_mountinfo(raw: str) -> dict[str, dict[str, Any]]:
    result = {}
    for line in raw.splitlines():
        before, separator, after = line.partition(" - ")
        if not separator:
            raise ObservationError("mountinfo line has no separator")
        fields = before.split()
        trailing = after.split()
        if len(fields) < 6 or len(trailing) < 3:
            raise ObservationError("mountinfo line is truncated")
        mount_point = fields[4].replace("\\040", " ")
        if mount_point not in RELEVANT_MOUNTS:
            continue
        super_options = trailing[2].split(",")
        volatile = {
            option.split("=", 1)[0]: True
            for option in super_options
            if option.split("=", 1)[0] in VOLATILE_SUPER_OPTIONS
        }
        stable_super = sorted(
            option
            for option in super_options
            if option.split("=", 1)[0] not in VOLATILE_SUPER_OPTIONS
        )
        result[mount_point] = {
            "filesystem_type": trailing[0],
            "source": trailing[1],
            "mount_options": sorted(fields[5].split(",")),
            "super_options": stable_super,
            "volatile_super_option_presence": {
                name: volatile.get(name, False)
                for name in sorted(VOLATILE_SUPER_OPTIONS)
            },
        }
    if set(result) != set(RELEVANT_MOUNTS):
        raise ObservationError("required mountinfo entries are missing")
    return result


def parse_status(raw: str) -> dict[str, str]:
    wanted = {"CapEff", "NoNewPrivs", "Seccomp"}
    result = {}
    for line in raw.splitlines():
        name, separator, value = line.partition(":")
        if separator and name in wanted:
            result[name] = value.strip()
    if set(result) != wanted:
        raise ObservationError("required process status fields are missing")
    return result


def observe_drop_caches() -> dict[str, Any]:
    status = DROP_CACHES.stat()
    opened = False
    open_errno = None
    open_error = None
    try:
        descriptor = os.open(
            DROP_CACHES,
            os.O_WRONLY | os.O_CLOEXEC,
        )
    except OSError as error:
        open_errno = error.errno
        open_error = errno.errorcode.get(error.errno, "UNKNOWN")
    else:
        opened = True
        os.close(descriptor)
    return {
        "path": str(DROP_CACHES),
        "is_regular_file": stat.S_ISREG(status.st_mode),
        "permission_bits_octal": f"{stat.S_IMODE(status.st_mode):04o}",
        "uid": status.st_uid,
        "gid": status.st_gid,
        "os_access_read": os.access(DROP_CACHES, os.R_OK),
        "os_access_write": os.access(DROP_CACHES, os.W_OK),
        "open_write_without_write_succeeded": opened,
        "open_write_errno": open_errno,
        "open_write_error": open_error,
        "write_attempted": False,
        "sync_executed": False,
        "drop_caches_executed": False,
    }


def observe() -> dict[str, Any]:
    if sys.platform != "linux":
        raise ObservationError("observer requires Linux")
    uname = platform.uname()
    status = parse_status(
        Path("/proc/self/status").read_text(encoding="utf-8")
    )
    effective = int(status["CapEff"], 16)
    namespace_types = sorted(
        path.name
        for path in Path("/proc/self/ns").iterdir()
        if path.is_symlink()
    )
    uid_map = (
        Path("/proc/self/uid_map")
        .read_text(encoding="utf-8")
        .strip()
        .split()
    )
    return {
        "schema_version": 1,
        "kernel": {
            "system": uname.system,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
        },
        "process": {
            "effective_capabilities_hex": (
                f"{effective:016x}"
            ),
            "cap_sys_admin_bit": CAP_SYS_ADMIN,
            "cap_sys_admin_effective": bool(
                effective & (1 << CAP_SYS_ADMIN)
            ),
            "no_new_privileges": int(status["NoNewPrivs"]),
            "seccomp_mode": int(status["Seccomp"]),
            "namespace_types": namespace_types,
            "page_cache_namespace_exposed": False,
            "initial_user_namespace_uid_map": (
                uid_map == ["0", "0", "4294967295"]
            ),
        },
        "mounts": parse_mountinfo(
            Path("/proc/self/mountinfo").read_text(
                encoding="utf-8"
            )
        ),
        "vm": {
            "drop_caches": observe_drop_caches(),
            "vfs_cache_pressure": int(
                Path("/proc/sys/vm/vfs_cache_pressure")
                .read_text(encoding="utf-8")
                .strip()
            ),
        },
        "scope": {
            "read_only_observation": True,
            "cache_state_changed": False,
        },
    }


def main() -> int:
    try:
        report = observe()
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
        print(f"cache environment observation error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
