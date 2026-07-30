#!/usr/bin/env python3
"""Generate a non-admitted macOS long-path filesystem fixture."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import sys
from typing import Any


SCHEMA_VERSION = 1
PLATFORM = "macos-x86_64"
GENERATOR = "tools/corpus/generate_macos_long_path_fixture.py"
VALIDATOR = "tools/corpus/validate_macos_long_path_fixture.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
SOURCE_NAME = "minimal.pdf"
XNU_COMMIT = "f6217f891ac0bb64f3d375211650a4c1ff8ca1ea"
XNU_SOURCE = "bsd/sys/syslimits.h"
XNU_SOURCE_URL = (
    "https://github.com/apple-oss-distributions/xnu/blob/"
    f"{XNU_COMMIT}/{XNU_SOURCE}"
)
XNU_SOURCE_SHA256 = (
    "c82fe60eac5d7864220e1468e6b75740"
    "b07d2ad6d18fe923b495059e48c2f100"
)
XNU_NAME_MAX = 255
XNU_PATH_MAX = 1024
XNU_MAXLONGPATHLEN = 8192
FULL_PATH_DELTAS = (-1, 0, 1)
COMPONENT_DELTAS = (-1, 0, 1)
ADMISSION_REASON = (
    "filesystem fixture candidate only; macOS runtime evidence has not "
    "been reviewed or admitted"
)
LIMITATIONS = [
    (
        "ASCII names isolate byte length from Unicode normalization and "
        "multi-byte component accounting"
    ),
    (
        "full paths are materialized with dir_fd-relative operations so "
        "fixture creation does not pre-decide whether path-string APIs "
        "can consume the same absolute path"
    ),
    (
        "pathconf and fixed XNU constants are references; actual create "
        "success or errno is retained for every boundary attempt"
    ),
    (
        "APFS volume format, mount options, case sensitivity, ACLs, and "
        "network filesystems remain separate environment dimensions"
    ),
]


class FixtureError(ValueError):
    """The macOS long-path fixture cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def generator_binding(root: Path) -> dict[str, str]:
    paths = {
        "path": GENERATOR,
        "validator_path": VALIDATOR,
    }
    result = dict(paths)
    for field, relative in paths.items():
        digest_field = (
            "sha256"
            if field == "path"
            else field.removesuffix("_path") + "_sha256"
        )
        result[digest_field] = sha256((root / relative).read_bytes())
    return result


def load_payload(root: Path, baseline_dir: Path) -> tuple[bytes, bytes]:
    committed = (root / BASELINE_MANIFEST).read_bytes()
    generated = (baseline_dir / "manifest.json").read_bytes()
    if generated != committed:
        raise FixtureError("baseline corpus manifest differs")
    manifest = json.loads(committed)
    matches = [
        sample
        for sample in manifest["samples"]
        if sample["name"] == SOURCE_NAME
    ]
    if len(matches) != 1:
        raise FixtureError("minimal PDF manifest entry differs")
    payload = (baseline_dir / SOURCE_NAME).read_bytes()
    if (
        len(payload) != matches[0]["size"]
        or sha256(payload) != matches[0]["sha256"]
    ):
        raise FixtureError("minimal PDF payload differs")
    return payload, committed


def _directory_lengths(total: int) -> list[int]:
    if total < 1:
        raise FixtureError("directory path budget is too small")
    count = max(1, (total + 121) // 121)
    character_total = total - (count - 1)
    if character_total < 4 * count:
        raise FixtureError("directory path budget cannot be partitioned")
    lengths = []
    remaining = character_total
    for index in range(count):
        remaining_items = count - index - 1
        length = min(120, remaining - 4 * remaining_items)
        lengths.append(length)
        remaining -= length
    if remaining != 0:
        raise FixtureError("directory path partition drift")
    return lengths


def build_full_relative_path(
    base: PurePosixPath, target_absolute_bytes: int
) -> str:
    base_bytes = len(str(base).encode("ascii"))
    relative_bytes = target_absolute_bytes - base_bytes - 1
    filename = "target.pdf"
    directory_bytes = relative_bytes - len(filename) - 1
    lengths = _directory_lengths(directory_bytes)
    components = []
    for index, length in enumerate(lengths):
        prefix = (
            f"p{target_absolute_bytes:08d}"
            if index == 0
            else f"d{index:03d}"
        )
        if length < len(prefix):
            raise FixtureError("directory component prefix is too long")
        components.append(prefix + "x" * (length - len(prefix)))
    relative = "/".join([*components, filename])
    absolute = f"{base}/{relative}"
    if len(absolute.encode("ascii")) != target_absolute_bytes:
        raise FixtureError("full path byte-length construction drift")
    return relative


def build_component_name(target_bytes: int) -> str:
    suffix = ".pdf"
    if target_bytes <= len(suffix):
        raise FixtureError("component byte budget is too small")
    value = "n" * (target_bytes - len(suffix)) + suffix
    if len(value.encode("ascii")) != target_bytes:
        raise FixtureError("component byte-length construction drift")
    return value


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError(errno.EIO, "short write")
        offset += written


def create_relative_file(
    root_fd: int, relative: str, payload: bytes
) -> dict[str, Any]:
    components = relative.split("/")
    current = os.dup(root_fd)
    try:
        for component in components[:-1]:
            try:
                os.mkdir(component, mode=0o755, dir_fd=current)
            except FileExistsError:
                pass
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY,
                dir_fd=current,
            )
            os.close(current)
            current = next_fd
        fd = os.open(
            components[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
            dir_fd=current,
        )
        try:
            _write_all(fd, payload)
        finally:
            os.close(fd)
    finally:
        os.close(current)
    return {"created": True, "errno": None, "errno_name": None}


def attempt_create(
    root_fd: int, relative: str, payload: bytes
) -> dict[str, Any]:
    try:
        return create_relative_file(root_fd, relative, payload)
    except OSError as error:
        number = error.errno
        return {
            "created": False,
            "errno": number,
            "errno_name": errno.errorcode.get(number, "UNKNOWN"),
        }


def read_relative_file(root_fd: int, relative: str) -> bytes:
    components = relative.split("/")
    current = os.dup(root_fd)
    try:
        for component in components[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY,
                dir_fd=current,
            )
            os.close(current)
            current = next_fd
        fd = os.open(components[-1], os.O_RDONLY, dir_fd=current)
        try:
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        finally:
            os.close(fd)
    finally:
        os.close(current)


def validate_live(
    report: dict[str, Any], fixture_dir: Path
) -> None:
    expected = Path(report["fixture"]["local_path"])
    if fixture_dir.resolve(strict=True) != expected:
        raise FixtureError("live fixture path differs from report")
    payload_size = report["baseline"]["payload_size"]
    payload_sha256 = report["baseline"]["payload_sha256"]
    root_fd = os.open(fixture_dir, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for case in report["fixture"]["cases"]:
            if not case["attempt"]["created"]:
                continue
            raw = read_relative_file(root_fd, case["relative_path"])
            if (
                len(raw) != payload_size
                or sha256(raw) != payload_sha256
            ):
                raise FixtureError(
                    f"live fixture payload differs: {case['id']}"
                )
    finally:
        os.close(root_fd)


def _case_record(
    *,
    case_id: str,
    kind: str,
    fixture_dir: PurePosixPath,
    relative: str,
    attempt: dict[str, Any],
    payload: bytes,
    target_boundary: str,
    target_bytes: int,
) -> dict[str, Any]:
    absolute = f"{fixture_dir}/{relative}"
    return {
        "id": case_id,
        "kind": kind,
        "relative_path": relative,
        "relative_bytes": len(relative.encode("ascii")),
        "absolute_path": absolute,
        "absolute_bytes": len(absolute.encode("ascii")),
        "basename_bytes": len(
            relative.rsplit("/", 1)[-1].encode("ascii")
        ),
        "target_boundary": target_boundary,
        "target_bytes": target_bytes,
        "attempt": attempt,
        "payload_size": len(payload) if attempt["created"] else None,
        "payload_sha256": (
            sha256(payload) if attempt["created"] else None
        ),
    }


def generate(
    *,
    root: Path,
    baseline_dir: Path,
    fixture_dir: Path,
    output: Path,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise FixtureError("fixture requires native Darwin x86_64")
    fixture_dir = fixture_dir.resolve()
    if fixture_dir.exists():
        if fixture_dir.is_symlink() or not fixture_dir.is_dir():
            raise FixtureError("fixture path is not a real directory")
        if any(fixture_dir.iterdir()):
            raise FixtureError("fixture directory must be empty")
    else:
        fixture_dir.mkdir(parents=True)
    fixture_text = str(fixture_dir)
    try:
        fixture_text.encode("ascii")
    except UnicodeEncodeError as error:
        raise FixtureError("fixture path must be ASCII") from error
    if not PurePosixPath(fixture_text).is_absolute():
        raise FixtureError("fixture path must be absolute POSIX")

    payload, baseline_manifest_raw = load_payload(root, baseline_dir)
    name_max = os.pathconf(fixture_dir, "PC_NAME_MAX")
    path_max = os.pathconf(fixture_dir, "PC_PATH_MAX")
    if name_max != XNU_NAME_MAX or path_max != XNU_PATH_MAX:
        raise FixtureError("runtime pathconf differs from fixed XNU limits")
    root_fd = os.open(fixture_dir, os.O_RDONLY | os.O_DIRECTORY)
    cases = []
    try:
        control_relative = "control/target.pdf"
        control_attempt = attempt_create(
            root_fd, control_relative, payload
        )
        if not control_attempt["created"]:
            raise FixtureError("control fixture could not be created")
        cases.append(
            _case_record(
                case_id="control",
                kind="control",
                fixture_dir=PurePosixPath(fixture_text),
                relative=control_relative,
                attempt=control_attempt,
                payload=payload,
                target_boundary="control",
                target_bytes=len(
                    f"{fixture_text}/{control_relative}".encode("ascii")
                ),
            )
        )
        for boundary, value in (
            ("path_max", path_max),
            ("max_long_path", XNU_MAXLONGPATHLEN),
        ):
            for delta in FULL_PATH_DELTAS:
                target = value + delta
                relative = build_full_relative_path(
                    PurePosixPath(fixture_text), target
                )
                attempt = attempt_create(root_fd, relative, payload)
                cases.append(
                    _case_record(
                        case_id=f"{boundary}_{delta:+d}",
                        kind="full_path",
                        fixture_dir=PurePosixPath(fixture_text),
                        relative=relative,
                        attempt=attempt,
                        payload=payload,
                        target_boundary=boundary,
                        target_bytes=target,
                    )
                )
        component_root = "components"
        os.mkdir(component_root, mode=0o755, dir_fd=root_fd)
        for delta in COMPONENT_DELTAS:
            target = name_max + delta
            relative = (
                f"{component_root}/{build_component_name(target)}"
            )
            attempt = attempt_create(root_fd, relative, payload)
            cases.append(
                _case_record(
                    case_id=f"name_max_{delta:+d}",
                    kind="component",
                    fixture_dir=PurePosixPath(fixture_text),
                    relative=relative,
                    attempt=attempt,
                    payload=payload,
                    target_boundary="name_max",
                    target_bytes=target,
                )
            )
        for case in cases:
            if case["attempt"]["created"]:
                raw = read_relative_file(
                    root_fd, case["relative_path"]
                )
                if raw != payload:
                    raise FixtureError(
                        f"live payload differs: {case['id']}"
                    )
    finally:
        os.close(root_fd)

    report = {
        "schema_version": SCHEMA_VERSION,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": generator_binding(root),
        "xnu_reference": {
            "repository": (
                "https://github.com/apple-oss-distributions/xnu"
            ),
            "commit": XNU_COMMIT,
            "source": XNU_SOURCE,
            "source_url": XNU_SOURCE_URL,
            "source_sha256": XNU_SOURCE_SHA256,
            "name_max": XNU_NAME_MAX,
            "path_max": XNU_PATH_MAX,
            "kernel_private_max_long_path": XNU_MAXLONGPATHLEN,
        },
        "baseline": {
            "manifest": BASELINE_MANIFEST,
            "manifest_sha256": sha256(baseline_manifest_raw),
            "sample": SOURCE_NAME,
            "payload_size": len(payload),
            "payload_sha256": sha256(payload),
        },
        "filesystem_limits": {
            "pathconf_name_max": name_max,
            "pathconf_path_max": path_max,
        },
        "fixture": {
            "local_path": fixture_text,
            "local_path_bytes": len(fixture_text.encode("ascii")),
            "case_ids": [case["id"] for case in cases],
            "cases": cases,
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": ADMISSION_REASON,
        },
        "limitations": LIMITATIONS,
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output != (
        output.parent / "long-path-fixture-candidate.json"
    ):
        raise FixtureError(
            "report must be named long-path-fixture-candidate.json"
        )
    if output.exists():
        raise FixtureError("fixture report already exists")
    output.write_bytes(
        (
            json.dumps(
                report,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generate(
            root=args.root.resolve(),
            baseline_dir=args.baseline_dir.resolve(strict=True),
            fixture_dir=args.fixture_dir,
            output=args.output,
        )
    except (FixtureError, OSError, ValueError) as error:
        print(f"macOS long-path fixture error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
