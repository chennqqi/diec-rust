import copy
import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_signature_path_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-path-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-path-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_signature_path_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def committed_output():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return report, copy.deepcopy(report["harness_output"])


class ProbeSignaturePathHarnessTests(unittest.TestCase):
    def test_committed_report_binds_all_inputs_and_validates(self):
        report, output = committed_output()
        relationships = MODULE.validate(output)
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 11)
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["fixture"]["manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["harness"]["source_sha256"],
            hashlib.sha256(MODULE.HARNESS_SOURCE.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["harness"]["dockerfile_sha256"],
            hashlib.sha256(MODULE.DOCKERFILE.read_bytes()).hexdigest(),
        )

    def test_rejects_case_insensitive_match(self):
        _, output = committed_output()
        case = MODULE.case_map(output)["case_mismatch"]
        case["records"] = [
            {
                "name": "main-path",
                "signature": "shared.1.sg",
                "signature_path": "/fixture/main/Binary/shared.1.sg",
            }
        ]
        case["record_count"] = 1
        with self.assertRaisesRegex(ValueError, "case_sensitive"):
            MODULE.validate(output)

    def test_rejects_dot_segment_normalization(self):
        _, output = committed_output()
        case = MODULE.case_map(output)["dot_segment"]
        case["records"] = [
            {
                "name": "main-path",
                "signature": "shared.1.sg",
                "signature_path": "/fixture/main/Binary/shared.1.sg",
            }
        ]
        case["record_count"] = 1
        with self.assertRaisesRegex(ValueError, "dot_segments"):
            MODULE.validate(output)

    def test_rejects_basename_only_match(self):
        _, output = committed_output()
        case = MODULE.case_map(output)["basename_only"]
        case["records"] = [
            {
                "name": "main-path",
                "signature": "shared.1.sg",
                "signature_path": "/fixture/main/Binary/shared.1.sg",
            }
        ]
        case["record_count"] = 1
        with self.assertRaisesRegex(ValueError, "basename"):
            MODULE.validate(output)

    def test_rejects_noncanonical_fixture_root(self):
        _, output = committed_output()
        output["fixture_root"] = "/tmp/fixture"
        with self.assertRaisesRegex(ValueError, "fixture_root"):
            MODULE.validate(output)

    def test_harness_limits_access_shim_and_calls_private_entry(self):
        source = MODULE.HARNESS_SOURCE.read_text(encoding="utf-8")
        self.assertIn('#include "die_scriptengine.h"', source)
        self.assertIn("#define private public", source)
        self.assertIn('#include "die_script.h"', source)
        self.assertIn("#undef private", source)
        self.assertIn("engine->processDetect(", source)
        self.assertIn("        false,\n        &state", source)
        self.assertEqual(source.count("#define private public"), 1)


if __name__ == "__main__":
    unittest.main()
