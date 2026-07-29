import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "tools/upstream/build_macos_qt5_oracle.sh"
VALIDATOR_PATH = (
    ROOT / "tools/upstream/validate_macos_qt5_oracle_report.py"
)
PLAN_SCRIPT = ROOT / "tools/research/build_macos_qt5_oracle_plan.py"
PLAN_PATH = ROOT / "docs/research/data/macos-qt5-oracle-plan.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("validate_macos_qt5_oracle_report", VALIDATOR_PATH)
PLAN = load_module("build_macos_qt5_oracle_plan", PLAN_SCRIPT)


def candidate_report() -> dict:
    digest = "0" * 64
    return {
        "schema_version": 1,
        "result": "candidate",
        "platform": "macos-x86_64-qt5",
        "source": {
            "repository": "https://github.com/horsicq/DIE-engine",
            "commit": VALIDATOR.UPSTREAM_COMMIT,
            "rules_commit": VALIDATOR.RULES_COMMIT,
            "recursive_submodule_count": 58,
            "tracked_files_clean_before_and_after": True,
        },
        "source_files": {
            path: digest for path in VALIDATOR.EXPECTED_SOURCE_FILES
        },
        "host": {
            "sw_vers": ["ProductName:\tmacOS", "ProductVersion:\t15.0"],
            "uname": "Darwin host 24.0.0 x86_64",
            "cpu_brand": "Intel test CPU",
            "logical_cpu_count": 4,
            "xcode_version": ["Xcode 16.0", "Build version 16A1"],
            "clang_version": ["Apple clang version 16.0.0"],
            "cmake_version": "cmake version 3.30.0",
        },
        "qt": {
            "version": "5.15.2",
            "qmake_spec": "macx-clang",
            "qmake_version": [
                "QMake version 3.1",
                "Using Qt version 5.15.2",
            ],
            "qmake_sha256": digest,
            "qtcore_sha256": digest,
            "qtscript_sha256": digest,
        },
        "build": {
            "system": "qmake",
            "configuration": "release",
            "jobs": 4,
            "targets": [
                "sub-build_libs-make_first",
                "sub-console_source-make_first",
            ],
            "elapsed_seconds": 60,
        },
        "artifact": {
            "size": 1,
            "sha256": digest,
            "architectures": ["x86_64"],
            "file_description": "Mach-O 64-bit executable x86_64",
            "otool_l": [
                "diec:",
                "\tQtCore.framework/Versions/5/QtCore",
            ],
            "version_stdout": "die 4.0.0",
            "version_exit_code": 0,
        },
        "admission": {
            "platform_admitted": False,
            "reason": "runtime capability evidence is missing",
        },
        "local_paths": {
            "source_dir": "/private/tmp/source",
            "qt_dir": "/Users/runner/Qt/5.15.2/clang_64",
            "build_dir": "/private/tmp/build",
            "artifact": "/private/tmp/source/build/release/diec",
        },
    }


class MacosQt5OracleBootstrapTests(unittest.TestCase):
    def test_plan_is_exact_generator_output_and_source_bound(self):
        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        expected = PLAN.build_plan(ROOT)
        self.assertEqual(report, expected)
        self.assertEqual(PLAN_PATH.read_bytes(), PLAN.serialize(expected))
        for relative, digest in report["sources"].items():
            with self.subTest(path=relative):
                self.assertEqual(
                    hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                    digest,
                )

    def test_plan_keeps_runtime_and_platform_admission_open(self):
        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            report["result"],
            "infrastructure_ready_runtime_missing",
        )
        self.assertFalse(report["admission"]["platform_admitted"])
        self.assertEqual(
            report["admission"]["coverage_status"],
            "platform_missing",
        )
        self.assertEqual(
            report["runtime_closure"]["required_capability_count"],
            68,
        )
        self.assertEqual(
            report["runtime_closure"]["minimum_repetitions_per_case"],
            2,
        )

    def test_shell_builder_is_fail_closed_and_cli_only(self):
        text = BUILD_SCRIPT.read_text(encoding="utf-8")
        for required in (
            VALIDATOR.UPSTREAM_COMMIT,
            VALIDATOR.RULES_COMMIT,
            'EXPECTED_SUBMODULE_COUNT=58',
            'EXPECTED_QT_VERSION="5.15.2"',
            'EXPECTED_QMAKE_SPEC="macx-clang"',
            'EXPECTED_ARCH="x86_64"',
            'git -C "$source_dir" submodule status --recursive',
            'build directory must be empty',
            'sub-build_libs-make_first',
            'sub-console_source-make_first',
            'tracked_files_clean_before_and_after',
            'platform_admitted": False',
            'validate_macos_qt5_oracle_report.py',
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("rm -rf", text)
        self.assertNotIn("gui_source", text)
        self.assertNotIn("lite_source", text)

    def test_candidate_validator_accepts_complete_report(self):
        VALIDATOR.validate_report(candidate_report())

    def test_candidate_validator_rejects_identity_and_admission_drift(self):
        changed = candidate_report()
        changed["source"]["commit"] = "f" * 40
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "source identity",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["admission"]["platform_admitted"] = True
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "must not admit",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["artifact"]["architectures"] = ["arm64"]
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "artifact identity",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["qt"] = []
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "expected object: qt",
        ):
            VALIDATOR.validate_report(changed)

    def test_loader_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(
                VALIDATOR.ReportError,
                "duplicate JSON key",
            ):
                VALIDATOR.load_report(path)


if __name__ == "__main__":
    unittest.main()
