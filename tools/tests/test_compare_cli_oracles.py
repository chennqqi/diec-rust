import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "upstream"
    / "compare_cli_oracles.py"
)
SPEC = importlib.util.spec_from_file_location("compare_cli_oracles", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CompareObservationsTests(unittest.TestCase):
    def test_accepts_identical_observations(self):
        observation = MODULE.Observation(0, b"same\n", b"")

        self.assertEqual(
            MODULE.compare_observations(observation, observation),
            [],
        )

    def test_reports_each_observable_difference(self):
        left = MODULE.Observation(0, b"left", b"left error")
        right = MODULE.Observation(1, b"right", b"right error")

        self.assertEqual(
            MODULE.compare_observations(left, right),
            ["exit_code", "stdout", "stderr"],
        )

    def test_summary_hashes_raw_bytes(self):
        observation = MODULE.Observation(1, b"output\r\n", b"error\n")

        self.assertEqual(
            observation.summary(),
            {
                "exit_code": 1,
                "stdout_sha256": (
                    "50be220f44c8a03a97b92b50debecbbdb2876205aa5d0e"
                    "ec4b69c93a17c64b48"
                ),
                "stderr_sha256": (
                    "f097b5f4f46cda2da21b954c9ff4097e1e14ae7064ecde"
                    "e2c2cec2d3c1f08e6b"
                ),
            },
        )


class LoadCorpusTests(unittest.TestCase):
    def test_loads_and_verifies_manifest(self):
        data = b"sample"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sample.bin").write_bytes(data)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "samples": [
                            {
                                "name": "sample.bin",
                                "size": len(data),
                                "sha256": (
                                    "af2bdbe1aa9b6ec1e2ade1d694f41fc71a831d02"
                                    "68e9891562113d8a62add1bf"
                                ),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            samples = MODULE.load_corpus(root)

        self.assertEqual(samples[0]["name"], "sample.bin")

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "samples": [
                            {
                                "name": "../escape",
                                "size": 0,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unsafe"):
                MODULE.load_corpus(root)

    def test_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sample.bin").write_bytes(b"sample")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "samples": [
                            {
                                "name": "sample.bin",
                                "size": 6,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match"):
                MODULE.load_corpus(root)


if __name__ == "__main__":
    unittest.main()
