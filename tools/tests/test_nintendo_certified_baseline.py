import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
CORPUS_PATH = (
    ROOT / "docs" / "research" / "data" / "nintendo-certified-corpus.json"
)
BASELINE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "nintendo-certified-baseline.json"
)


class NintendoCertifiedBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        cls.baseline = json.loads(
            BASELINE_PATH.read_text(encoding="utf-8")
        )

    def test_pins_upstream_rules_and_two_oracles(self):
        self.assertEqual(
            self.baseline["expected_revision"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.baseline["rules_commit"],
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
        )
        self.assertEqual(len(self.baseline["oracles"]), 2)

    def test_baseline_exactly_covers_corpus(self):
        corpus_names = {
            sample["name"] for sample in self.corpus["samples"]
        }
        self.assertEqual(
            corpus_names, set(self.baseline["samples"])
        )
        self.assertEqual(len(corpus_names), 14)

    def test_each_sample_has_valid_raw_hash_and_nintendo_detection(self):
        for name, sample in self.baseline["samples"].items():
            with self.subTest(name=name):
                stdout_hash = sample["stdout_sha256"]
                self.assertEqual(len(stdout_hash), 64)
                self.assertTrue(
                    all(character in "0123456789abcdef" for character in stdout_hash)
                )
                primary = sample["detections"][0]
                self.assertEqual(primary[0], "format")
                self.assertTrue(primary[1].startswith("Nintend\u014d signed"))
                self.assertEqual(
                    primary[2], "PS3" if name.startswith("ps3-") else "PSVita"
                )

    def test_vita_extra_detection_is_preserved_in_order(self):
        for name, sample in self.baseline["samples"].items():
            detections = sample["detections"]
            if name.startswith("vita-"):
                self.assertEqual(len(detections), 2)
                self.assertEqual(detections[1][0], "audio")
                self.assertEqual(
                    detections[1][1],
                    "Electronic Arts' EA-XA stream (.EXA)",
                )
            else:
                self.assertEqual(len(detections), 1)

    def test_empty_stderr_hash_is_fixed(self):
        self.assertEqual(
            self.baseline["stderr_sha256"],
            "e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855",
        )


if __name__ == "__main__":
    unittest.main()
