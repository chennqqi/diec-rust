import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_result_lists_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_result_lists_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def result_record(signature):
    return {
        "type": "format",
        "name": "Duplicate",
        "version": "1",
        "info": "same",
        "signature": signature,
        "signature_file": f"/fixture/main/Binary/{signature}",
        "unknown": False,
    }


def debug_record(script):
    return {
        "script": script,
        "type": "",
        "name": "",
        "value": "",
        "elapsed_ms": 0,
        "line": 0,
    }


def handler_record():
    return {
        "kind": 2,
        "source": "/fixture/input/probe.bin",
        "destination": (
            MODULE.COLLECTION_ROOT + "/files/duplicate.bin"
        ),
    }


def valid_document():
    default = {
        "id": "default_success",
        "signature_name": "a_first.1.sg",
        "show_scan_time": False,
        "collection": False,
        "database_loaded": True,
        "load_not_canceled": True,
        "scan_not_canceled": True,
        "records": [result_record("a_first.1.sg")],
        "errors": [],
        "debug_records": [],
        "handlers": [],
    }
    complete = {
        "id": "all_lists",
        "signature_name": "",
        "show_scan_time": True,
        "collection": True,
        "database_loaded": True,
        "load_not_canceled": True,
        "scan_not_canceled": True,
        "records": [
            result_record("a_first.1.sg"),
            result_record("b_second.1.sg"),
        ],
        "errors": [
            {"script": script, "message": "non-empty"}
            for script in MODULE.EXPECTED_SCRIPTS[2:]
        ],
        "debug_records": [
            debug_record(script) for script in MODULE.EXPECTED_SCRIPTS
        ],
        "handlers": [handler_record(), handler_record()],
    }
    return {
        "schema_version": 1,
        "upstream_commit": MODULE.UPSTREAM_COMMIT,
        "formats_commit": MODULE.FORMATS_COMMIT,
        "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
        "die_script_commit": MODULE.DIE_SCRIPT_COMMIT,
        "input_sha256": MODULE.INPUT_SHA256,
        "collection_root": MODULE.COLLECTION_ROOT,
        "case_count": 2,
        "cases": [default, complete],
    }


class ProbeResultListsHarnessTests(unittest.TestCase):
    def test_validates_independent_ordered_lists(self):
        relationships = MODULE.validate(valid_document())
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 7)

    def test_rejects_reordered_duplicate_results(self):
        document = valid_document()
        document["cases"][1]["records"].reverse()
        with self.assertRaisesRegex(ValueError, "duplicate_records"):
            MODULE.validate(document)

    def test_rejects_missing_error_message(self):
        document = valid_document()
        document["cases"][1]["errors"][0]["message"] = ""
        with self.assertRaisesRegex(ValueError, "errors_preserved"):
            MODULE.validate(document)

    def test_rejects_float_debug_elapsed_time(self):
        document = valid_document()
        document["cases"][1]["debug_records"][0]["elapsed_ms"] = 0.0
        with self.assertRaisesRegex(ValueError, "debug_records"):
            MODULE.validate(document)

    def test_rejects_handler_deduplication(self):
        document = valid_document()
        document["cases"][1]["handlers"].pop()
        with self.assertRaisesRegex(ValueError, "duplicate_handlers"):
            MODULE.validate(document)

    def test_cpp_harness_does_not_process_handler_records(self):
        source = (
            ROOT
            / "tools"
            / "upstream"
            / "result_lists_harness_main.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("result.listHandlers", source)
        self.assertNotIn("processRecords(", source)
        self.assertIn("bCollectionCopyFiles = collection", source)


if __name__ == "__main__":
    unittest.main()
