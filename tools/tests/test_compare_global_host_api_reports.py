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
MODULE_PATH = UPSTREAM_DIR / "compare_global_host_api_reports.py"
SPEC = importlib.util.spec_from_file_location(
    "compare_global_host_api_reports", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


EXPECTED_PATHS = {
    "$.include.errors_after_parse[1]",
    "$.include.errors_after_runtime[1]",
    "$.include.parse_error.evaluation.backtrace",
    "$.include.parse_error.evaluation.error_line",
    "$.include.parse_error.evaluation.error_message",
    "$.include.parse_error.evaluation.error_name",
    "$.include.parse_error.evaluation.is_error",
    "$.include.parse_error.evaluation.is_undefined",
    "$.include.parse_error.evaluation.string",
    "$.include.runtime_error.evaluation.backtrace",
    "$.include.runtime_error.evaluation.error_line",
    "$.include.runtime_error.evaluation.error_message",
    "$.include.runtime_error.evaluation.error_name",
    "$.include.runtime_error.evaluation.is_error",
    "$.include.runtime_error.evaluation.is_undefined",
    "$.include.runtime_error.evaluation.string",
    "$.info.encoding_call.evaluation.boolean",
    "$.info.encoding_call.evaluation.is_boolean",
    "$.info.encoding_call.evaluation.is_undefined",
    "$.info.encoding_last",
    "$.info.encoding_message_count",
    "$.info.encoding_messages_sha256",
    "$.info.log_messages[0]",
    "$.info.log_messages[1]",
    "$.info.log_messages[2]",
    "$.info.missing.evaluation.backtrace",
    "$.info.missing.evaluation.error_line",
    "$.info.missing.evaluation.error_message",
    "$.info.missing.evaluation.error_name",
    "$.info.missing.evaluation.is_error",
    "$.info.missing.evaluation.is_undefined",
    "$.info.missing.evaluation.string",
    "$.info.pd_info_after_missing",
    "$.info.pd_info_after_null",
    "$.isolated_query_conversions.cyclic_array_count.exit_code",
    "$.isolated_query_conversions.cyclic_array_count.exit_status",
    "$.isolated_query_conversions.cyclic_array_count.observation",
    "$.isolated_query_conversions.cyclic_array_count.process_error_code",
    "$.isolated_query_conversions.cyclic_array_count.stdout.base64",
    "$.isolated_query_conversions.cyclic_array_count.stdout.bytes",
    "$.isolated_query_conversions.cyclic_array_count.stdout.sha256",
    (
        "$.isolated_query_conversions.proxy_object_count."
        "observation.evaluation.number"
    ),
    "$.isolated_query_conversions.proxy_object_count.stdout.base64",
    "$.isolated_query_conversions.proxy_object_count.stdout.bytes",
    "$.isolated_query_conversions.proxy_object_count.stdout.sha256",
    (
        "$.isolated_query_conversions.symbol_count."
        "observation.evaluation.number"
    ),
    "$.isolated_query_conversions.symbol_count.stdout.base64",
    "$.isolated_query_conversions.symbol_count.stdout.bytes",
    "$.isolated_query_conversions.symbol_count.stdout.sha256",
    "$.missing_arguments.count.evaluation.backtrace",
    "$.missing_arguments.count.evaluation.error_line",
    "$.missing_arguments.count.evaluation.error_message",
    "$.missing_arguments.count.evaluation.error_name",
    "$.missing_arguments.count.evaluation.is_error",
    "$.missing_arguments.count.evaluation.is_number",
    "$.missing_arguments.count.evaluation.number",
    "$.missing_arguments.count.evaluation.string",
    "$.missing_arguments.count.records[0]",
    "$.missing_arguments.is_present.evaluation.backtrace",
    "$.missing_arguments.is_present.evaluation.boolean",
    "$.missing_arguments.is_present.evaluation.error_line",
    "$.missing_arguments.is_present.evaluation.error_message",
    "$.missing_arguments.is_present.evaluation.error_name",
    "$.missing_arguments.is_present.evaluation.is_boolean",
    "$.missing_arguments.is_present.evaluation.is_error",
    "$.missing_arguments.is_present.evaluation.string",
    "$.missing_arguments.is_present.records[0]",
    "$.missing_arguments.set_result.evaluation.backtrace",
    "$.missing_arguments.set_result.evaluation.error_line",
    "$.missing_arguments.set_result.evaluation.error_message",
    "$.missing_arguments.set_result.evaluation.error_name",
    "$.missing_arguments.set_result.evaluation.is_error",
    "$.missing_arguments.set_result.evaluation.is_undefined",
    "$.missing_arguments.set_result.evaluation.string",
    "$.missing_arguments.set_result.records[0]",
    "$.modes.engine_version.string",
    "$.modes.qt_version",
    "$.qt_version",
    "$.query_conversions.evaluations.null_count.number",
    "$.query_conversions.evaluations.proxy_type.string",
    "$.query_conversions.evaluations.symbol_type.string",
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.backtrace"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.error_line"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.error_message"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.error_name"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.is_error"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.is_number"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.number"
    ),
    (
        "$.query_conversions.evaluations."
        "throwing_object_count.string"
    ),
    "$.query_conversions.evaluations.undefined_count.number",
    "$.surface.methods._getQtVersion.length.is_null",
    "$.surface.methods._getQtVersion.length.is_number",
    "$.surface.methods._getQtVersion.length.number",
    "$.surface.methods._getQtVersion.type.string",
}


class CompareGlobalHostApiReportsTests(unittest.TestCase):
    def test_recursive_comparison_preserves_missing_and_type_changes(self):
        differences = MODULE.compare_values(
            {"same": [1], "missing_right": True, "typed": 1},
            {"same": [1, 2], "missing_left": False, "typed": True},
        )
        self.assertEqual(
            differences,
            [
                {
                    "path": "$.missing_left",
                    "kind": "missing_left",
                    "right": False,
                },
                {
                    "path": "$.missing_right",
                    "kind": "missing_right",
                    "left": True,
                },
                {
                    "path": "$.same[1]",
                    "kind": "missing_left",
                    "right": 2,
                },
                {
                    "path": "$.typed",
                    "kind": "value",
                    "left": 1,
                    "right": True,
                },
            ],
        )

    def test_committed_report_has_exact_runtime_differences(self):
        path = (
            ROOT
            / "docs/research/data/global-host-api-qt5-qt6.json"
        )
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(report["equal"])
        self.assertEqual(report["difference_count"], 94)
        self.assertEqual(
            {item["path"] for item in report["differences"]},
            EXPECTED_PATHS,
        )
        self.assertEqual(
            len(report["differences"]),
            len(EXPECTED_PATHS),
        )

    def test_committed_input_and_source_hashes_are_current(self):
        report = json.loads(
            (
                ROOT
                / "docs/research/data/global-host-api-qt5-qt6.json"
            ).read_text(encoding="utf-8")
        )
        for item in report["inputs"].values():
            data = (ROOT / item["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(data).hexdigest(),
                item["sha256"],
            )
        source = report["source"]
        data = (ROOT / source["path"]).read_bytes()
        self.assertEqual(len(data), source["bytes"])
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            source["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
