import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "corpus" / "generate_path_locale_fixture.py"
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "path-locale-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_path_locale_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GeneratePathLocaleFixtureTest(unittest.TestCase):
    def test_committed_manifest_is_exact_generator_output(self) -> None:
        manifest = MODULE.build_manifest()
        self.assertEqual(MANIFEST_PATH.read_bytes(), MODULE.serialize(manifest))
        self.assertEqual(
            json.loads(MANIFEST_PATH.read_text(encoding="utf-8")),
            manifest,
        )

    def test_matrix_is_closed_and_uses_distinct_filesystems(self) -> None:
        manifest = MODULE.build_manifest()
        self.assertEqual(manifest["locales"], ["C", "C.utf8", "POSIX"])
        self.assertEqual(
            [item["expected_type"] for item in manifest["filesystems"]],
            ["tmpfs", "ext2/ext3"],
        )
        self.assertEqual(
            [item["docker_mount"] for item in manifest["filesystems"]],
            ["tmpfs", "anonymous-volume"],
        )

    def test_name_matrix_covers_locale_and_encoding_boundaries(self) -> None:
        names = MODULE.build_manifest()["names"]
        ids = {item["id"] for item in names}
        self.assertEqual(len(ids), len(names))
        for required in (
            "ascii_upper_i",
            "ascii_lower_i",
            "nfd_e_acute",
            "nfc_e_acute",
            "german_a_umlaut",
            "swedish_a_ring",
            "turkish_capital_i_dot",
            "turkish_small_dotless_i",
            "cjk",
            "emoji",
            "hidden",
            "invalid_ff",
            "invalid_overlong",
            "invalid_truncated",
        ):
            self.assertIn(required, ids)
        self.assertEqual(
            sum(item["valid_utf8"] for item in names),
            len(MODULE.NAMES),
        )
        self.assertEqual(
            sum(not item["valid_utf8"] for item in names),
            len(MODULE.RAW_NAMES),
        )
        for item in names:
            raw = bytes.fromhex(item["path_bytes_hex"])
            if item["valid_utf8"]:
                self.assertEqual(raw.decode("utf-8"), item["utf8"])
            else:
                with self.assertRaises(UnicodeDecodeError):
                    raw.decode("utf-8")

    def test_materialization_is_empty_and_adversarial(self) -> None:
        materialization = MODULE.build_manifest()["materialization"]
        self.assertEqual(materialization["creation_order"], "reverse-manifest")
        self.assertEqual(materialization["payload_size"], 0)
        self.assertEqual(
            materialization["payload_sha256"],
            hashlib.sha256(b"").hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
