import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_image_dispatch_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "image-dispatch-engine-qt5.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "probe_image_dispatch_harness_for_test",
    MODULE_PATH,
)


class ProbeImageDispatchHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_committed_report_binds_all_inputs(self):
        report = self.report
        self.assertTrue(all(report["relationships"].values()))
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["fixture"]["generator_sha256"],
            hashlib.sha256(PROBE.GENERATOR.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["harness"]["source_sha256"],
            hashlib.sha256(PROBE.HARNESS_SOURCE.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["harness"]["dockerfile_sha256"],
            hashlib.sha256(PROBE.DOCKERFILE.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["fixture"]["manifest_sha256"],
            PROBE.MANIFEST_SHA256,
        )

    def test_report_proves_natural_fallback_and_forced_failure(self):
        samples = PROBE.sample_map(self.report["harness_output"])
        self.assertEqual(set(samples), set(PROBE.EXPECTED_DETECTED))
        for specific, sample in samples.items():
            with self.subTest(specific=specific):
                self.assertIn("Image", sample["detected_filetypes"])
                self.assertIn(specific, sample["detected_filetypes"])
                self.assertEqual(
                    sample["image_filtered_filetypes"],
                    ["Image"],
                )
                self.assertEqual(
                    sample["automatic"]["initial_filetype"],
                    "Binary",
                )
                self.assertEqual(
                    sample["forced_image"]["initial_filetype"],
                    "Image",
                )
                self.assertEqual(
                    sample["forced_image"]["errors"][0]["message"],
                    PROBE.EXPECTED_IMAGE_ERROR,
                )
                self.assertTrue(
                    sample["forced_image"]["records"][0]["unknown"]
                )

    def test_committed_output_passes_strict_validator(self):
        relationships = PROBE.validate(
            self.report["harness_output"],
            self.report["fixture"]["manifest"],
        )
        self.assertEqual(relationships, self.report["relationships"])

    def test_validator_rejects_detector_and_error_drift(self):
        document = copy.deepcopy(self.report["harness_output"])
        document["samples"][0]["detected_filetypes"].remove("Image")
        with self.assertRaisesRegex(PROBE.ProbeError, "detector set"):
            PROBE.validate(document, self.report["fixture"]["manifest"])

        document = copy.deepcopy(self.report["harness_output"])
        document["samples"][0]["forced_image"]["errors"] = []
        with self.assertRaisesRegex(PROBE.ProbeError, "Image error"):
            PROBE.validate(document, self.report["fixture"]["manifest"])

    def test_dockerfile_and_harness_change_only_research_surface(self):
        dockerfile = PROBE.DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn(
            "upstream-oracle-cmake:74eaf505@sha256:"
            "466102628c3a94b7ab1048f0c24261b1920e61a40029b128"
            "763cf79370255040",
            dockerfile,
        )
        self.assertIn(
            "CMakeFiles/diec.dir/main_console.cpp.o",
            dockerfile,
        )
        source = PROBE.HARNESS_SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "options.fileType = (",
            source,
        )
        self.assertIn(
            "forceImage ? XBinary::FT_IMAGE : XBinary::FT_UNKNOWN",
            source,
        )
        self.assertNotIn("setProperty(\"filetypes\"", source)


if __name__ == "__main__":
    unittest.main()
