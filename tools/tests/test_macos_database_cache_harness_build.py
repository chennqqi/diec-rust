import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = (
    ROOT / "tools/upstream/build_macos_database_cache_harness.py"
)
VALIDATOR_PATH = (
    ROOT
    / "tools/upstream/validate_macos_database_cache_harness_build.py"
)
BOOTSTRAP_PATH = (
    ROOT / "tools/tests/test_macos_qt5_oracle_bootstrap.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("macos_cache_harness_builder_test", BUILDER_PATH)
VALIDATOR = load_module(
    "macos_cache_harness_build_validator_test", VALIDATOR_PATH
)
BOOTSTRAP = load_module(
    "macos_bootstrap_for_cache_harness_build_test", BOOTSTRAP_PATH
)


MAKEFILE = b"""\
CXX = clang++
OBJECTS = consoleoutput.o main_console.o helper.o
DESTDIR_TARGET = /private/tmp/source/build/release/diec

$(DESTDIR_TARGET): $(OBJECTS)
\t$(LINK) -o $(DESTDIR_TARGET) $(OBJECTS) $(LIBS)

main_console.o: ../../source/console_source/main_console.cpp die_script.h
\t$(CXX) -c $(CXXFLAGS) $(INCPATH) $(DEFINES) -o main_console.o ../../source/console_source/main_console.cpp
"""


def write_record(bundle: Path, relative: str, raw: bytes):
    path = bundle / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": relative,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def write_candidate(bundle: Path):
    oracle = BOOTSTRAP.candidate_report()
    oracle_path = bundle / "oracle-candidate.json"
    oracle_path.write_text(
        json.dumps(oracle, sort_keys=True), encoding="utf-8"
    )
    build_dir = PurePosixPath(oracle["local_paths"]["build_dir"])
    console = build_dir / "console_source"
    local_artifact = console / BUILDER.BINARY_NAME
    patched, replacements = BUILDER.patch_qmake_makefile(
        MAKEFILE, target=local_artifact
    )
    inputs = {
        "console_makefile": write_record(
            bundle,
            "build-input/database-cache-console.Makefile",
            MAKEFILE,
        ),
        "patched_makefile": write_record(
            bundle,
            "build-input/database-cache-harness.Makefile",
            patched,
        ),
        "shared_harness": write_record(
            bundle,
            "build-input/database_cache_harness_main.cpp",
            (ROOT / BUILDER.SHARED_HARNESS).read_bytes(),
        ),
        "macos_adapter": write_record(
            bundle,
            (
                "build-input/"
                "database_cache_harness_macos_adapter.cpp"
            ),
            (ROOT / BUILDER.MACOS_ADAPTER).read_bytes(),
        ),
    }
    stdout = write_record(
        bundle,
        "raw/database-cache-harness-build.stdout",
        b"clang++ -c adapter\nclang++ -o harness\n",
    )
    stderr = write_record(
        bundle,
        "raw/database-cache-harness-build.stderr",
        b"",
    )
    artifact_path = bundle / BUILDER.BINARY_NAME
    artifact_raw = (
        b"\xcf\xfa\xed\xfe"
        + (0x01000007).to_bytes(4, "little")
        + (3).to_bytes(4, "little")
        + (2).to_bytes(4, "little")
        + b"\0" * 16
        + b"synthetic cache harness"
    )
    artifact_path.write_bytes(artifact_raw)
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": BUILDER.PLATFORM,
        "generator": BUILDER.generator_bindings(ROOT),
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": hashlib.sha256(
                oracle_path.read_bytes()
            ).hexdigest(),
        },
        "source": oracle["source"],
        "qt": {
            field: oracle["qt"][field]
            for field in (
                "version",
                "qmake_spec",
                "qmake_sha256",
                "qtcore_sha256",
                "qtscript_sha256",
            )
        },
        "cli": {
            "relative_path": "build/release/diec",
            "size": oracle["artifact"]["size"],
            "sha256": oracle["artifact"]["sha256"],
        },
        "build": {
            "system": "patched-qmake-makefile",
            "tool": "make",
            "jobs": 2,
            "elapsed_milliseconds": 100,
            "console_makefile_sha256": hashlib.sha256(
                MAKEFILE
            ).hexdigest(),
            "patched_makefile_sha256": hashlib.sha256(
                patched
            ).hexdigest(),
            "replacements": replacements,
            "inputs": inputs,
            "exit_code": 0,
            "stdout": stdout,
            "stderr": stderr,
        },
        "artifact": {
            "path": BUILDER.BINARY_NAME,
            "size": len(artifact_raw),
            "sha256": hashlib.sha256(artifact_raw).hexdigest(),
            "architectures": ["x86_64"],
            "file_description": (
                "Mach-O 64-bit executable x86_64"
            ),
            "otool_l": [
                f"{BUILDER.BINARY_NAME}:",
                "\tQtCore.framework/Versions/5/QtCore",
                "\tQtScript.framework/Versions/5/QtScript",
            ],
        },
        "local_paths": {
            "source_dir": oracle["local_paths"]["source_dir"],
            "qt_dir": oracle["local_paths"]["qt_dir"],
            "build_dir": str(build_dir),
            "console_build_dir": str(console),
            "original_makefile": str(console / "Makefile"),
            "patched_makefile": str(
                console / BUILDER.PATCHED_MAKEFILE_NAME
            ),
            "local_artifact": str(local_artifact),
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": BUILDER.ADMISSION_REASON,
        },
        "limitations": BUILDER.LIMITATIONS,
    }
    report_path = bundle / BUILDER.REPORT_NAME
    report_path.write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )
    return report_path, oracle_path, artifact_path, report


class MacosDatabaseCacheHarnessBuildTest(unittest.TestCase):
    def validate(self, report_path, oracle_path, artifact_path):
        report = json.loads(report_path.read_bytes())
        VALIDATOR.validate_report(
            report,
            report_path=report_path.resolve(strict=True),
            oracle_path=oracle_path.resolve(strict=True),
            artifact_path=artifact_path.resolve(strict=True),
            root=ROOT,
        )

    def test_makefile_patch_is_minimal_and_fail_closed(self):
        target = PurePosixPath("/private/tmp/build/cache-harness")
        patched, replacements = BUILDER.patch_qmake_makefile(
            MAKEFILE, target=target
        )
        self.assertNotIn(b"main_console.cpp", patched)
        self.assertNotIn(b"main_console.o", patched)
        self.assertEqual(
            replacements["source_token_replacements"], 2
        )
        self.assertEqual(
            replacements["object_token_replacements"], 3
        )
        self.assertIn(str(target).encode(), patched)
        for changed in (
            MAKEFILE.replace(
                b"DESTDIR_TARGET", b"OTHER_TARGET"
            ),
            MAKEFILE.replace(
                b"main_console.o", b"other.o"
            ),
            MAKEFILE.replace(
                b"main_console.cpp", b"other.cpp"
            ),
        ):
            with self.assertRaises(BUILDER.BuildError):
                BUILDER.patch_qmake_makefile(changed, target=target)

    def test_validator_recomputes_patched_makefile_and_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            report_path, oracle_path, artifact_path, _ = (
                write_candidate(bundle)
            )
            self.validate(report_path, oracle_path, artifact_path)

    def test_validator_rejects_input_raw_artifact_and_admission_drift(self):
        for mutation in ("input", "raw", "artifact", "admission"):
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as temporary:
                    bundle = Path(temporary)
                    (
                        report_path,
                        oracle_path,
                        artifact_path,
                        report,
                    ) = write_candidate(bundle)
                    if mutation == "input":
                        path = (
                            bundle
                            / report["build"]["inputs"][
                                "patched_makefile"
                            ]["path"]
                        )
                        path.write_bytes(path.read_bytes() + b"x")
                    elif mutation == "raw":
                        extra = (
                            bundle
                            / "raw"
                            / "database-cache-harness-build.extra"
                        )
                        extra.write_bytes(b"x")
                    elif mutation == "artifact":
                        artifact_path.write_bytes(b"changed")
                    else:
                        changed = copy.deepcopy(report)
                        changed["admission"][
                            "platform_admitted"
                        ] = True
                        report_path.write_text(
                            json.dumps(changed), encoding="utf-8"
                        )
                    with self.assertRaises(
                        (VALIDATOR.ReportError, ValueError)
                    ):
                        self.validate(
                            report_path, oracle_path, artifact_path
                        )


if __name__ == "__main__":
    unittest.main()
