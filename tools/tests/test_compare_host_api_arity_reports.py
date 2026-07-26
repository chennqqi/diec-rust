import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
UPSTREAM_DIR = ROOT / "tools/upstream"
if str(UPSTREAM_DIR) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_DIR))
MODULE_PATH = UPSTREAM_DIR / "compare_host_api_arity_reports.py"
SPEC = importlib.util.spec_from_file_location(
    "compare_host_api_arity_reports", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


EXPECTED_PATHS = {
    "$.observation.binary.sc_missing.backtrace[0]",
    "$.observation.binary.sc_missing.error_message",
    "$.observation.binary.sc_missing.error_name",
    "$.observation.binary.sc_missing.string",
    "$.observation.binary.u8_missing.backtrace[0]",
    "$.observation.binary.u8_missing.error_message",
    "$.observation.binary.u8_missing.error_name",
    "$.observation.binary.u8_missing.string",
    "$.observation.binary.u8_null.backtrace",
    "$.observation.binary.u8_null.error_line",
    "$.observation.binary.u8_null.error_message",
    "$.observation.binary.u8_null.error_name",
    "$.observation.binary.u8_null.is_error",
    "$.observation.binary.u8_null.is_number",
    "$.observation.binary.u8_null.number",
    "$.observation.binary.u8_null.string",
    "$.observation.binary.u8_undefined.backtrace",
    "$.observation.binary.u8_undefined.error_line",
    "$.observation.binary.u8_undefined.error_message",
    "$.observation.binary.u8_undefined.error_name",
    "$.observation.binary.u8_undefined.is_error",
    "$.observation.binary.u8_undefined.is_number",
    "$.observation.binary.u8_undefined.number",
    "$.observation.binary.u8_undefined.string",
    "$.observation.pe.get_ep_signature_call.backtrace[0]",
    "$.observation.pe.get_ep_signature_call.error_message",
    "$.observation.pe.get_ep_signature_call.string",
    "$.observation.pe.init_evaluation.is_undefined",
    "$.observation.qt_version",
    "$.stderr.bytes",
    "$.stderr.sha256",
    *{f"$.stderr.utf8_lines[{index}]" for index in range(10)},
}


class CompareHostApiArityReportsTests(unittest.TestCase):
    def setUp(self):
        path = (
            ROOT / "docs/research/data/host-api-arity-qt5-qt6.json"
        )
        self.report = json.loads(path.read_text(encoding="utf-8"))

    def test_committed_report_has_exact_runtime_differences(self):
        self.assertFalse(self.report["equal"])
        self.assertEqual(self.report["difference_count"], 41)
        self.assertEqual(
            {item["path"] for item in self.report["differences"]},
            EXPECTED_PATHS,
        )
        self.assertEqual(
            len(self.report["differences"]),
            len(EXPECTED_PATHS),
        )

    def test_committed_input_and_source_hashes_are_current(self):
        for item in self.report["inputs"].values():
            data = (ROOT / item["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(data).hexdigest(),
                item["sha256"],
            )
        for relative, identity in self.report["sources"].items():
            data = (ROOT / relative).read_bytes()
            self.assertEqual(len(data), identity["bytes"])
            self.assertEqual(
                hashlib.sha256(data).hexdigest(),
                identity["sha256"],
            )

    def test_report_includes_stderr_and_semantic_differences(self):
        paths = {item["path"] for item in self.report["differences"]}
        self.assertIn("$.stderr.sha256", paths)
        self.assertIn(
            "$.observation.binary.u8_null.error_name",
            paths,
        )
        self.assertIn(
            "$.observation.pe.get_ep_signature_call.error_message",
            paths,
        )


if __name__ == "__main__":
    unittest.main()
