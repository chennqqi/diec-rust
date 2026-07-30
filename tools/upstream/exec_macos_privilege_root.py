#!/usr/bin/env python3
"""Set a contained root runtime environment, then exec one binary."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Sequence


class ExecError(ValueError):
    """The requested root exec is outside the helper contract."""


def parse_invocation(
    arguments: Sequence[str],
) -> tuple[Path, Path, str, Path, list[str]]:
    if len(arguments) < 9:
        raise ExecError("incomplete root exec invocation")
    if (
        arguments[0] != "--home"
        or arguments[2] != "--tmp"
        or arguments[4] != "--path"
        or arguments[6] != "--"
    ):
        raise ExecError("root exec argument order changed")
    home = Path(arguments[1])
    temporary = Path(arguments[3])
    path_value = arguments[5]
    binary = Path(arguments[7])
    binary_arguments = list(arguments[8:])
    for path, label in (
        (home, "home"),
        (temporary, "tmp"),
        (binary, "binary"),
    ):
        if not path.is_absolute():
            raise ExecError(f"{label} path must be absolute")
    home = home.resolve(strict=True)
    temporary = temporary.resolve(strict=True)
    binary = binary.resolve(strict=True)
    if not home.is_dir() or not temporary.is_dir():
        raise ExecError("runtime home/tmp must be directories")
    if home.parent != temporary.parent:
        raise ExecError("runtime home/tmp must share one parent")
    if not binary.is_file():
        raise ExecError("binary must be a regular file")
    if not path_value or "\x00" in path_value:
        raise ExecError("PATH value is invalid")
    if not binary_arguments:
        raise ExecError("binary argument vector is empty")
    return home, temporary, path_value, binary, binary_arguments


def main() -> int:
    try:
        if sys.platform != "darwin" or os.geteuid() != 0:
            raise ExecError("helper requires native Darwin uid 0")
        home, temporary, path_value, binary, arguments = (
            parse_invocation(sys.argv[1:])
        )
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        environment["TMPDIR"] = str(temporary)
        environment["PATH"] = path_value
        os.umask(0)
        os.execve(
            str(binary),
            [binary.name, *arguments],
            environment,
        )
    except (ExecError, OSError) as error:
        print(f"macOS root exec error: {error}", file=sys.stderr)
        return 125
    return 125


if __name__ == "__main__":
    raise SystemExit(main())
