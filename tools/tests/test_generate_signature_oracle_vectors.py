import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "corpus" / "generate_signature_oracle_vectors.py"
)
COMMITTED_VECTORS = (
    ROOT / "docs" / "research" / "data" / "signature-oracle-vectors.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_signature_oracle_vectors", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SignatureOracleVectorTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_has_unique_cases(self):
        first = MODULE.manifest()
        second = MODULE.manifest()
        self.assertEqual(first, second)
        self.assertEqual(first["case_count"], 53)
        ids = [case["id"] for case in first["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(first["generator"]["version"], 7)

    def test_serialization_round_trip_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            payload = (
                json.dumps(
                    MODULE.manifest(),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            first.write_text(
                payload,
                encoding="utf-8",
                newline="\n",
            )
            second.write_text(
                payload,
                encoding="utf-8",
                newline="\n",
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_committed_manifest_matches_generator(self):
        committed = json.loads(COMMITTED_VECTORS.read_text(encoding="utf-8"))
        self.assertEqual(committed, MODULE.manifest())


if __name__ == "__main__":
    unittest.main()
