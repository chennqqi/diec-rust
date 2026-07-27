import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "compat" / "verify_raw_execution.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_raw_execution",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

STDOUT_BYTES = b'{"detects":[]}\n'
STDERR_BYTES = b"synthetic diagnostic\n"
STDOUT_SHA256 = hashlib.sha256(STDOUT_BYTES).hexdigest()
STDERR_SHA256 = hashlib.sha256(STDERR_BYTES).hexdigest()


def base_execution():
    return {
        "execution_schema": 1,
        "run_identity": {
            "case_id": "synthetic.raw-execution",
            "side": "upstream",
            "platform": "linux-x86_64",
            "producer_profile": "cmake-qt5",
            "producer_revision": (
                "74eaf505c250ab47e709024e9dc41657cd8f2254"
            ),
            "case_manifest_sha256": "0" * 64,
            "executable_sha256": "1" * 64,
        },
        "argv": ["diec", "--json", "/corpus/synthetic.bin"],
        "environment": {"LC_ALL": "C", "TZ": "UTC"},
        "logical_cwd": "/work",
        "termination": {"kind": "exit", "code": 0},
        "wall_time_ns": 1234567,
        "resource_usage": {
            "cpu_time_ns": 1000000,
            "peak_memory_bytes": 4096,
            "budget_counters": {"records": 1},
        },
        "artifacts": {
            "stdout": {
                "sha256": STDOUT_SHA256,
                "size": len(STDOUT_BYTES),
            },
            "stderr": {
                "sha256": STDERR_SHA256,
                "size": len(STDERR_BYTES),
            },
        },
    }


def write_artifact(root, digest, data):
    path = root / "sha256" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_case(directory, execution=None):
    execution = execution or base_execution()
    manifest_path = directory / "execution.json"
    artifact_root = directory / "artifacts"
    artifact_root.mkdir()
    write_artifact(artifact_root, STDOUT_SHA256, STDOUT_BYTES)
    write_artifact(artifact_root, STDERR_SHA256, STDERR_BYTES)
    manifest_path.write_text(
        json.dumps(execution),
        encoding="utf-8",
    )
    return manifest_path, artifact_root


class RawExecutionVerificationTests(unittest.TestCase):
    def test_verifies_exact_content_addressed_streams(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            output_path = directory / "verification.json"
            verification = MODULE.verify_files(
                manifest_path,
                artifact_root,
                output_path,
                1024,
            )
            self.assertEqual(verification["result"], "pass")
            self.assertEqual(verification["verified_total_bytes"], 36)
            self.assertEqual(
                verification["artifacts"]["stdout"],
                {
                    "relative_path": f"sha256/{STDOUT_SHA256}",
                    "sha256": STDOUT_SHA256,
                    "size": 15,
                },
            )
            self.assertEqual(
                output_path.read_bytes(),
                MODULE.serialize_verification(verification),
            )
            self.assertNotIn(b"\r\n", output_path.read_bytes())

    def test_hash_only_verification_does_not_capture_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            path = write_artifact(root, STDOUT_SHA256, STDOUT_BYTES)
            with mock.patch.object(
                MODULE,
                "_verify_artifact_content",
                wraps=MODULE._verify_artifact_content,
            ) as verifier:
                MODULE.hash_artifact(
                    path,
                    STDOUT_SHA256,
                    len(STDOUT_BYTES),
                    1024,
                )
            self.assertFalse(verifier.call_args.args[-1])

    def test_rejects_content_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            path = artifact_root / "sha256" / STDOUT_SHA256
            path.write_bytes(b'{"detects":{}}\n')
            self.assertEqual(path.stat().st_size, len(STDOUT_BYTES))
            with self.assertRaisesRegex(
                MODULE.VerificationError,
                "SHA-256 mismatch",
            ):
                MODULE.verify_files(
                    manifest_path,
                    artifact_root,
                    directory / "output.json",
                    1024,
                )

    def test_rejects_size_mismatch_and_missing_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            execution = base_execution()
            execution["artifacts"]["stdout"]["size"] += 1
            manifest_path, artifact_root = write_case(
                directory,
                execution,
            )
            with self.assertRaisesRegex(
                MODULE.VerificationError,
                "size mismatch",
            ):
                MODULE.verify_files(
                    manifest_path,
                    artifact_root,
                    directory / "output.json",
                    1024,
                )

        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            (artifact_root / "sha256" / STDERR_SHA256).unlink()
            with self.assertRaisesRegex(
                MODULE.VerificationError,
                "artifact is missing",
            ):
                MODULE.verify_files(
                    manifest_path,
                    artifact_root,
                    directory / "output.json",
                    1024,
                )

    def test_manifest_cannot_supply_an_artifact_path(self):
        execution = base_execution()
        execution["artifacts"]["stdout"]["path"] = "../../other"
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "unknown fields: path",
        ):
            MODULE.validate_execution(execution)

    def test_rejects_unknown_or_missing_artifact_roles(self):
        execution = base_execution()
        execution["artifacts"]["trace"] = {
            "sha256": "2" * 64,
            "size": 0,
        }
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "unknown roles: trace",
        ):
            MODULE.validate_execution(execution)

        execution = base_execution()
        del execution["artifacts"]["stderr"]
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "missing roles: stderr",
        ):
            MODULE.validate_execution(execution)

    def test_optional_runtime_log_is_a_separate_raw_stream(self):
        execution = base_execution()
        execution["artifacts"]["runtime_log"] = {
            "sha256": STDERR_SHA256,
            "size": len(STDERR_BYTES),
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(
                directory,
                execution,
            )
            verification = MODULE.verify_files(
                manifest_path,
                artifact_root,
                directory / "output.json",
                1024,
            )
            self.assertEqual(
                list(verification["artifacts"]),
                ["stdout", "stderr", "runtime_log"],
            )
            self.assertEqual(
                verification["verified_total_bytes"],
                57,
            )

    def test_rejects_total_budget_before_hashing(self):
        execution = MODULE.validate_execution(base_execution())
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            with mock.patch.object(
                MODULE,
                "resolve_artifact_path",
            ) as resolver:
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    "total exceeds verification budget",
                ):
                    MODULE.verify_execution(
                        execution,
                        "3" * 64,
                        root,
                        35,
                    )
                resolver.assert_not_called()

    def test_cli_path_rejects_budget_before_artifact_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            with mock.patch.object(
                MODULE,
                "resolve_artifact_path",
            ) as resolver:
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    "total exceeds verification budget",
                ):
                    MODULE.verify_files(
                        manifest_path,
                        artifact_root,
                        directory / "output.json",
                        35,
                    )
                resolver.assert_not_called()

    def test_rejects_zero_budget_and_oversized_manifest(self):
        execution = MODULE.validate_execution(base_execution())
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "positive u64",
        ):
            MODULE.verify_execution(
                execution,
                "3" * 64,
                pathlib.Path("."),
                0,
            )
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "positive u64",
        ):
            MODULE.verify_execution(
                execution,
                "3" * 64,
                pathlib.Path("."),
                MODULE.MAX_U64 + 1,
            )
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "exceeds",
        ):
            MODULE.load_json_bytes(
                b" " * (MODULE.MAX_MANIFEST_BYTES + 1),
                "manifest",
            )
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "manifest.json"
            path.write_bytes(b" " * (MODULE.MAX_MANIFEST_BYTES + 1))
            with self.assertRaisesRegex(
                MODULE.VerificationError,
                "exceeds",
            ):
                MODULE.read_stable_manifest(path)

    def test_rejects_artifact_file_mutation_during_hashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            path = write_artifact(root, STDOUT_SHA256, STDOUT_BYTES)
            stable = (1, 2, 15, 3)
            changed = (1, 2, 15, 4)
            with mock.patch.object(
                MODULE,
                "file_identity",
                side_effect=[
                    stable,
                    stable,
                    stable,
                    stable,
                    stable,
                    changed,
                ],
            ):
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    "changed while hashing",
                ):
                    MODULE.hash_artifact(
                        path,
                        STDOUT_SHA256,
                        len(STDOUT_BYTES),
                        1024,
                    )

    def test_rejects_manifest_file_mutation_during_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "manifest.json"
            path.write_bytes(b"{}\n")
            stable = (1, 2, 3, 4)
            changed = (1, 2, 3, 5)
            with mock.patch.object(
                MODULE,
                "file_identity",
                side_effect=[
                    stable,
                    stable,
                    stable,
                    stable,
                    stable,
                    changed,
                ],
            ):
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    "changed while reading",
                ):
                    MODULE.read_stable_manifest(path)

    def test_rejects_symlink_artifact_and_symlink_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            target = artifact_root / "actual"
            target.write_bytes(STDOUT_BYTES)
            link = artifact_root / "sha256" / STDOUT_SHA256
            link.unlink()
            try:
                link.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(
                MODULE.VerificationError,
                "symlink/reparse",
            ):
                MODULE.verify_files(
                    manifest_path,
                    artifact_root,
                    directory / "output.json",
                    1024,
                )

        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            root_link = directory / "artifact-link"
            try:
                root_link.symlink_to(
                    artifact_root,
                    target_is_directory=True,
                )
            except OSError as error:
                self.skipTest(f"directory symlinks unavailable: {error}")
            with self.assertRaisesRegex(
                MODULE.VerificationError,
                "artifact root must be a real directory",
            ):
                MODULE.verify_files(
                    manifest_path,
                    root_link,
                    directory / "output.json",
                    1024,
                )

    def test_validates_all_termination_variants(self):
        variants = (
            {"kind": "exit", "code": 4294967295},
            {"kind": "signal", "signal": 9},
            {"kind": "timeout", "limit_ms": 1000},
            {"kind": "spawn_error", "error_code": "NOT_FOUND"},
        )
        for termination in variants:
            with self.subTest(termination=termination):
                execution = base_execution()
                execution["termination"] = termination
                self.assertEqual(
                    MODULE.validate_execution(execution)["termination"],
                    termination,
                )

        execution = base_execution()
        execution["termination"] = {
            "kind": "exit",
            "code": 0,
            "signal": 9,
        }
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "unknown fields: signal",
        ):
            MODULE.validate_execution(execution)

    def test_rejects_identity_environment_and_argument_drift(self):
        mutations = (
            (
                lambda value: value["run_identity"].update(
                    {"side": "both"}
                ),
                "side must be",
            ),
            (
                lambda value: value["run_identity"].update(
                    {"producer_revision": "latest"}
                ),
                "40-hex SHA",
            ),
            (
                lambda value: value["environment"].update(
                    {"BAD=NAME": "value"}
                ),
                "environment key is invalid",
            ),
            (
                lambda value: value["argv"].append("bad\x00argument"),
                "must not contain NUL",
            ),
        )
        for mutate, message in mutations:
            execution = base_execution()
            mutate(execution)
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    message,
                ):
                    MODULE.validate_execution(execution)

    def test_preserves_platform_environment_names_and_nullable_metrics(self):
        execution = base_execution()
        execution["environment"] = {
            "Path": "C:\\Windows",
            "SystemRoot": "C:\\Windows",
        }
        execution["resource_usage"] = {
            "cpu_time_ns": None,
            "peak_memory_bytes": None,
            "budget_counters": {},
        }
        validated = MODULE.validate_execution(execution)
        self.assertEqual(
            validated["environment"],
            execution["environment"],
        )
        self.assertEqual(
            validated["resource_usage"],
            execution["resource_usage"],
        )

    def test_rejects_invalid_resource_usage(self):
        mutations = (
            (
                lambda value: value["resource_usage"].update(
                    {"cpu_time_ns": -1}
                ),
                "cpu_time_ns must be an integer",
            ),
            (
                lambda value: value["resource_usage"][
                    "budget_counters"
                ].update({"Bad Counter": 1}),
                "budget_counters key is invalid",
            ),
            (
                lambda value: value["resource_usage"][
                    "budget_counters"
                ].update({"records": True}),
                "records must be an integer",
            ),
        )
        for mutate, message in mutations:
            execution = base_execution()
            mutate(execution)
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    message,
                ):
                    MODULE.validate_execution(execution)

    def test_rejects_boolean_schema_version(self):
        execution = base_execution()
        execution["execution_schema"] = True
        with self.assertRaisesRegex(
            MODULE.VerificationError,
            "unsupported execution_schema",
        ):
            MODULE.validate_execution(execution)

    def test_strict_json_rejects_duplicate_nan_and_invalid_utf8(self):
        for data, message in (
            (b'{"a":1,"a":2}', "duplicate JSON key"),
            (b'{"a":NaN}', "non-finite JSON constant"),
            (b"\xff", "UTF-8 JSON"),
        ):
            with self.subTest(data=data):
                with self.assertRaisesRegex(
                    MODULE.VerificationError,
                    message,
                ):
                    MODULE.load_json_bytes(data, "manifest")

    def test_refuses_to_overwrite_manifest_or_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            stdout_path = artifact_root / "sha256" / STDOUT_SHA256
            for output in (manifest_path, stdout_path):
                with self.subTest(output=output):
                    with self.assertRaisesRegex(
                        MODULE.VerificationError,
                        "must not overwrite",
                    ):
                        MODULE.verify_files(
                            manifest_path,
                            artifact_root,
                            output,
                            1024,
                        )

    def test_cli_preserves_manifest_and_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            manifest_path, artifact_root = write_case(directory)
            output_path = directory / "verification.json"
            original_manifest = manifest_path.read_bytes()
            original_stdout = (
                artifact_root / "sha256" / STDOUT_SHA256
            ).read_bytes()
            process = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--manifest",
                    str(manifest_path),
                    "--artifact-root",
                    str(artifact_root),
                    "--output",
                    str(output_path),
                    "--max-artifact-bytes",
                    "1024",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(manifest_path.read_bytes(), original_manifest)
            self.assertEqual(
                (
                    artifact_root / "sha256" / STDOUT_SHA256
                ).read_bytes(),
                original_stdout,
            )
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8"))[
                    "result"
                ],
                "pass",
            )

    def test_schema_files_parse_and_match_closed_roles(self):
        schemas = ROOT / "docs" / "design" / "schemas"
        execution_schema = json.loads(
            (schemas / "raw-execution-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        json.loads(
            (
                schemas
                / "raw-execution-verification-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        artifact_properties = execution_schema["properties"][
            "artifacts"
        ]["properties"]
        self.assertEqual(
            tuple(artifact_properties),
            MODULE.ARTIFACT_ROLES,
        )
        self.assertEqual(
            set(
                execution_schema["properties"]["artifacts"][
                    "required"
                ]
            ),
            MODULE.REQUIRED_ARTIFACT_ROLES,
        )

    def test_documentation_example_reproduces_golden_verification(self):
        examples = ROOT / "docs" / "design" / "schemas" / "examples"
        manifest_path = examples / "raw-execution-v1.example.json"
        artifact_root = examples / "raw-artifacts"
        expected_path = (
            examples / "raw-execution-verification-v1.example.json"
        )
        manifest_bytes = manifest_path.read_bytes()
        execution = MODULE.validate_execution(
            MODULE.load_json_bytes(manifest_bytes, "manifest")
        )
        verification = MODULE.verify_execution(
            execution,
            MODULE.sha256_bytes(manifest_bytes),
            artifact_root.resolve(),
            1024,
        )
        self.assertEqual(
            MODULE.serialize_verification(verification),
            expected_path.read_bytes(),
        )

    def test_documents_link_verifier_schemas_and_remaining_scope(self):
        testing = (
            ROOT / "docs" / "design" / "testing.md"
        ).read_text(encoding="utf-8")
        risks = (
            ROOT / "docs" / "design" / "risks.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / "docs" / "design" / "schemas" / "README.md"
        ).read_text(encoding="utf-8")
        compat = (
            ROOT / "tools" / "compat" / "README.md"
        ).read_text(encoding="utf-8")
        for name in (
            MODULE_PATH.name,
            "raw-execution-v1.schema.json",
            "raw-execution-verification-v1.schema.json",
        ):
            self.assertIn(name, testing)
            self.assertIn(name, index)
            self.assertIn(name, compat)
        self.assertIn("content-addressed", risks)
        self.assertIn("full differential integration", testing)


if __name__ == "__main__":
    unittest.main()
