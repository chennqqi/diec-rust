import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "upstream" / "probe_path_toctou_behavior.py"
REPORT_PATH = (
    ROOT / "docs" / "research" / "data" / "path-toctou-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "path-toctou-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "path-toctou-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_path_toctou_behavior",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProbePathToctouBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def test_identity_generator_and_sync_tool_are_pinned(self) -> None:
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["upstream_commit"], MODULE.UPSTREAM_COMMIT)
        self.assertEqual(report["platform"], "linux-x86_64-qt5")
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(
            report["generator"],
            "tools/upstream/probe_path_toctou_behavior.py",
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["fixture"]["manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["stdbuf"]["path"], "/usr/bin/stdbuf")
        self.assertEqual(
            report["stdbuf"]["sha256"],
            "1fd37836e4a9060756fcec760b0b0f482621aad3fe13af39591a8c14b118eb5d",
        )

    def test_case_matrix_and_entropy_documents_are_exact(self) -> None:
        cases = self.report["cases"]
        self.assertEqual(
            set(cases),
            {
                "stable_old",
                "stable_new",
                "swap_old_to_new",
                "remove_old_after_enumeration",
            },
        )
        for name, case in cases.items():
            with self.subTest(case=name):
                self.assertEqual(
                    case["blocker_document"],
                    MODULE.EXPECTED_BLOCKER_DOCUMENT,
                )
                self.assertEqual(
                    case["link_document"],
                    MODULE.EXPECTED_LINK_DOCUMENTS[
                        case["expected_open_target"]
                    ],
                )
                self.assertEqual(
                    case["stdout_sha256"],
                    MODULE.EXPECTED_STDOUT_SHA256[name],
                )
                for oracle in ("qmake", "cmake"):
                    observation = case["observations"][oracle]
                    self.assertEqual(observation["exit_code"], 0)
                    self.assertEqual(observation["stderr"]["bytes"], 0)
                    self.assertEqual(
                        observation["synchronization"]["first_line"],
                        "/work/case/a-blocker.bin:",
                    )
                    self.assertTrue(
                        observation["synchronization"][
                            "mutation_while_stopped"
                        ]
                    )
                    self.assertEqual(
                        observation["synchronization"]["stop_signal"],
                        19,
                    )

    def test_atomic_swap_changes_inode_and_matches_new_control(self) -> None:
        cases = self.report["cases"]
        old = cases["stable_old"]
        new = cases["stable_new"]
        swapped = cases["swap_old_to_new"]
        self.assertNotEqual(old["link_document"], new["link_document"])
        self.assertEqual(swapped["link_document"], new["link_document"])
        self.assertEqual(swapped["stdout_sha256"], new["stdout_sha256"])
        self.assertNotEqual(swapped["stdout_sha256"], old["stdout_sha256"])
        for oracle in ("qmake", "cmake"):
            observation = swapped["observations"][oracle]
            before = observation["before"]
            after = observation["after"]
            self.assertEqual(before["link_target"], "../targets/old.bin")
            self.assertEqual(after["link_target"], "../targets/new.bin")
            self.assertNotEqual(
                before["link_identity"]["inode"],
                after["link_identity"]["inode"],
            )
            self.assertNotEqual(
                before["target_identity"]["inode"],
                after["target_identity"]["inode"],
            )

    def test_unlink_after_enumeration_keeps_prefix_but_returns_empty_error_shape(
        self,
    ) -> None:
        removed = self.report["cases"]["remove_old_after_enumeration"]
        self.assertEqual(
            removed["link_document"],
            {"records": [], "status": "", "total": 0},
        )
        self.assertNotEqual(
            removed["link_document"],
            self.report["cases"]["stable_old"]["link_document"],
        )
        for oracle in ("qmake", "cmake"):
            after = removed["observations"][oracle]["after"]
            self.assertEqual(
                after,
                {
                    "link_identity": None,
                    "link_target": None,
                    "target_identity": None,
                },
            )

    def test_facts_and_source_order_contract_are_bound(self) -> None:
        for value in self.report["facts"].values():
            self.assertTrue(value)
        source = self.report["source_contract"]
        self.assertEqual(set(source), set(MODULE.SOURCE_PATHS))
        for path, patterns in MODULE.SOURCE_PATTERNS.items():
            records = source[path]["required_patterns"]
            for pattern in patterns:
                self.assertGreaterEqual(records[pattern]["count"], 1)
                self.assertTrue(records[pattern]["lines"])

    def test_raw_artifacts_are_content_addressed_and_referenced(self) -> None:
        artifacts = self.report["raw_artifacts"]
        decoded = {}
        for digest, artifact in artifacts.items():
            compressed = base64.b64decode(
                artifact["base64"],
                validate=True,
            )
            raw = zlib.decompress(compressed)
            self.assertEqual(len(raw), artifact["bytes"])
            self.assertEqual(len(compressed), artifact["compressed_bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            decoded[digest] = raw
        referenced = set()
        for case in self.report["cases"].values():
            for observation in case["observations"].values():
                for stream in ("stdout", "stderr"):
                    reference = observation[stream]
                    digest = reference["artifact_sha256"]
                    referenced.add(digest)
                    self.assertEqual(reference["sha256"], digest)
                    self.assertEqual(reference["bytes"], len(decoded[digest]))
        self.assertEqual(referenced, set(artifacts))

    def test_fixture_loader_rejects_duplicate_keys_and_sync_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "duplicate JSON key",
            ):
                MODULE.load_fixture(duplicate)

            changed = json.loads(json.dumps(self.manifest))
            changed["synchronization"]["stop_signal"] = "SIGTERM"
            tampered = Path(directory) / "tampered.json"
            tampered.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "synchronization changed",
            ):
                MODULE.load_fixture(tampered)

    def test_document_records_scope_and_non_claims(self) -> None:
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for token in (
            "SIGSTOP",
            "SIGCONT",
            "stdbuf",
            "old → new",
            "records",
            "CAP-GAP-003",
            "ADR 0014",
            "Windows",
            "macOS",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
