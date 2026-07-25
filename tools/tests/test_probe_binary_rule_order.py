import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "upstream" / "probe_binary_rule_order.py"
SPEC = importlib.util.spec_from_file_location(
    "probe_binary_rule_order", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeBinaryRuleOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "binary-rule-order-linux-qt5.json"
            ).read_text(encoding="utf-8")
        )

    def test_extracts_only_exact_signature_announcement_lines(self):
        expected = {"alpha.1.sg", "beta.2.sg"}
        output = (
            b"debug\n"
            b"alpha.1.sg\n"
            b"alpha.1.sg: [3 ms]\n"
            b"beta.2.sg\r\n"
            b'{\"name\":\"alpha.1.sg\"}\n'
        )
        self.assertEqual(
            MODULE.extract_order(output, expected),
            ["alpha.1.sg", "beta.2.sg"],
        )

    def test_validation_rejects_missing_and_duplicate_records(self):
        expected = {"alpha.1.sg", "beta.2.sg"}
        MODULE.validate_order(["alpha.1.sg", "beta.2.sg"], expected)
        with self.assertRaisesRegex(ValueError, "duplicates"):
            MODULE.validate_order(
                ["alpha.1.sg", "alpha.1.sg"], expected
            )
        with self.assertRaisesRegex(ValueError, "missing"):
            MODULE.validate_order(["alpha.1.sg"], expected)

    def test_order_hash_uses_utf8_lf_with_trailing_newline(self):
        self.assertEqual(
            MODULE.canonical_order_bytes(["alpha.1.sg", "βeta.2.sg"]),
            "alpha.1.sg\nβeta.2.sg\n".encode(),
        )

    def test_fixed_lifecycle_manifest_has_292_unique_names(self):
        names, digest = MODULE.load_expected_names(
            ROOT
            / "docs"
            / "research"
            / "data"
            / "binary-rule-lifecycle.json"
        )
        self.assertEqual(len(names), 292)
        self.assertEqual(len(digest), 64)

    def test_reference_pins_two_oracles_and_complete_order(self):
        self.assertEqual(
            self.reference["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            self.reference["rules_commit"], MODULE.RULES_COMMIT
        )
        self.assertEqual(self.reference["platform"], "linux-amd64-qt5")
        self.assertTrue(self.reference["orders_equal"])
        self.assertEqual(self.reference["order_count"], 292)
        self.assertEqual(len(set(self.reference["order"])), 292)
        self.assertEqual(
            self.reference["order_sha256"],
            MODULE.sha256(
                MODULE.canonical_order_bytes(self.reference["order"])
            ),
        )
        self.assertEqual(
            [oracle["name"] for oracle in self.reference["oracles"]],
            ["linux-qt5-qmake", "linux-qt5-cmake"],
        )
        for oracle in self.reference["oracles"]:
            with self.subTest(oracle=oracle["name"]):
                self.assertEqual(oracle["revision"], MODULE.UPSTREAM_COMMIT)
                self.assertEqual(oracle["exit_code"], 0)
                self.assertEqual(oracle["raw_stderr_bytes"], 0)
                self.assertEqual(
                    oracle["raw_stderr_sha256"], MODULE.EMPTY_SHA256
                )
                self.assertEqual(
                    oracle["order_sha256"],
                    self.reference["order_sha256"],
                )

    def test_reference_order_exactly_covers_lifecycle_inventory(self):
        names, digest = MODULE.load_expected_names(
            ROOT
            / "docs"
            / "research"
            / "data"
            / "binary-rule-lifecycle.json"
        )
        self.assertEqual(set(self.reference["order"]), names)
        self.assertEqual(
            self.reference["lifecycle_manifest"]["sha256"], digest
        )
        irregular = [
            (index, name)
            for index, name in enumerate(self.reference["order"])
            if name.count(".") <= 1
        ]
        self.assertEqual(
            irregular,
            [
                (1, "ROM_1.sg"),
                (20, "archive_DotBundle.sg"),
                (41, "archive_PC_Secure.sg"),
                (148, "format_MS-PST.sg"),
                (150, "format_MS-VHDX.sg"),
                (248, "image_ICNS.sg"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
