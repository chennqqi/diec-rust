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
    / "probe_debug_dispatch_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "debug-dispatch-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "debug-dispatch-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_debug_dispatch_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def committed_output():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return report, copy.deepcopy(report["harness_output"])


class ProbeDebugDispatchHarnessTests(unittest.TestCase):
    def test_committed_report_binds_all_inputs_and_validates(self):
        report, output = committed_output()
        relationships = MODULE.validate(output)
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 9)
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

    def test_rejects_public_debug_data_child(self):
        _, output = committed_output()
        public = output["public_recursive_scan"]
        child = copy.deepcopy(output["direct_debug_scan"]["records"][0])
        public["records"].append(child)
        public["record_count"] += 1
        with self.assertRaisesRegex(ValueError, "omits_debug_data"):
            MODULE.validate(output)

    def test_rejects_missing_direct_debug_detection(self):
        _, output = committed_output()
        direct = output["direct_debug_scan"]
        direct["records"] = []
        direct["record_count"] = 0
        with self.assertRaisesRegex(ValueError, "detects_rsds"):
            MODULE.validate(output)

    def test_rejects_missing_recursive_resource_control(self):
        _, output = committed_output()
        public = output["public_recursive_scan"]
        public["records"] = [
            record
            for record in public["records"]
            if record["name"] != "Manifest"
        ]
        public["record_count"] = len(public["records"])
        with self.assertRaisesRegex(ValueError, "positive_control"):
            MODULE.validate(output)

    def test_rejects_debug_part_not_used_by_direct_case(self):
        _, output = committed_output()
        output["direct_debug_scan"]["source_part"]["offset"] = 1092
        with self.assertRaisesRegex(ValueError, "uses_enumerated_part"):
            MODULE.validate(output)

    def test_harness_pairs_public_scan_with_direct_private_entry(self):
        source = MODULE.HARNESS_SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "XBinary::FILEPART_RESOURCE | "
            "XBinary::FILEPART_DEBUGDATA",
            source,
        )
        self.assertIn("engine.scanFile(", source)
        self.assertIn("engine.processDetect(", source)
        self.assertIn(
            "directParent.filePart = XBinary::FILEPART_DEBUGDATA",
            source,
        )
        self.assertIn(
            "directOptions.sSignatureName = DEBUG_RULE_NAME",
            source,
        )
        self.assertEqual(source.count("#define private public"), 1)


if __name__ == "__main__":
    unittest.main()
