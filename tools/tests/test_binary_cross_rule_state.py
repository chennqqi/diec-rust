import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
REFERENCE = (
    ROOT / "docs" / "research" / "data" / "binary-cross-rule-state.json"
)


class BinaryCrossRuleStateTests(unittest.TestCase):
    def setUp(self):
        self.reference = json.loads(REFERENCE.read_text(encoding="utf-8"))

    def test_reference_is_fixed_and_has_no_wrapper_loss_candidate(self):
        self.assertEqual(
            self.reference["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.reference["rules_commit"],
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
        )
        self.assertEqual(self.reference["file_count"], 292)
        self.assertEqual(self.reference["analyzed_source_bytes"], 1_122_477)
        self.assertEqual(self.reference["persistent_declaration_count"], 302)
        self.assertEqual(self.reference["lexical_declaration_count"], 2)
        self.assertEqual(self.reference["wrapper_loss_candidate_count"], 0)
        self.assertEqual(self.reference["wrapper_loss_candidates"], [])

    def test_reference_pins_order_and_parser(self):
        order_path = ROOT / self.reference["order_manifest"]
        package_path = (
            ROOT
            / "upstream"
            / "Detect-It-Easy"
            / "autotools"
            / "dbcompiler"
            / "node_modules"
            / "uglify-js"
            / "package.json"
        )
        self.assertEqual(
            hashlib.sha256(order_path.read_bytes()).hexdigest(),
            self.reference["order_manifest_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(package_path.read_bytes()).hexdigest(),
            self.reference["parser"]["package_json_sha256"],
        )
        self.assertEqual(self.reference["parser"]["version"], "3.19.3")
        self.assertEqual(self.reference["parser"]["license"], "BSD-2-Clause")

    def test_audit_is_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "report.json"
            subprocess.run(
                [
                    "node",
                    str(
                        ROOT
                        / "tools"
                        / "upstream"
                        / "audit_binary_cross_rule_state.js"
                    ),
                    str(ROOT / "upstream" / "Detect-It-Easy" / "db"),
                    str(
                        ROOT
                        / "docs"
                        / "research"
                        / "data"
                        / "binary-rule-order-linux-qt5.json"
                    ),
                    str(
                        ROOT
                        / "upstream"
                        / "Detect-It-Easy"
                        / "autotools"
                        / "dbcompiler"
                        / "node_modules"
                        / "uglify-js"
                    ),
                    str(output),
                ],
                check=True,
                capture_output=True,
            )
            self.assertEqual(output.read_bytes(), REFERENCE.read_bytes())

    def test_audit_detects_later_use_of_prior_var(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            binary = root / "db" / "Binary"
            binary.mkdir(parents=True)
            (binary / "define.1.sg").write_text(
                "var shared = 1; function detect() {}\n",
                encoding="utf-8",
            )
            (binary / "read.2.sg").write_text(
                "function detect() { return shared; }\n",
                encoding="utf-8",
            )
            order = {
                "upstream_commit": (
                    "74eaf505c250ab47e709024e9dc41657cd8f2254"
                ),
                "rules_commit": (
                    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
                ),
                "order_sha256": (
                    "27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc"
                    "26b1a9ff0e1ff3"
                ),
                "order": ["define.1.sg", "read.2.sg"],
            }
            order_path = root / "order.json"
            order_path.write_text(json.dumps(order), encoding="utf-8")
            output = root / "report.json"
            subprocess.run(
                [
                    "node",
                    str(
                        ROOT
                        / "tools"
                        / "upstream"
                        / "audit_binary_cross_rule_state.js"
                    ),
                    str(root / "db"),
                    str(order_path),
                    str(
                        ROOT
                        / "upstream"
                        / "Detect-It-Easy"
                        / "autotools"
                        / "dbcompiler"
                        / "node_modules"
                        / "uglify-js"
                    ),
                    str(output),
                ],
                check=True,
                capture_output=True,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["wrapper_loss_candidate_count"], 1)
            self.assertEqual(
                report["wrapper_loss_candidates"][0],
                {
                    "name": "shared",
                    "provider_index": 0,
                    "provider_rule": "define.1.sg",
                    "provider_kind": "var_or_function_declaration",
                    "consumer_index": 1,
                    "consumer_rule": "read.2.sg",
                    "access_kinds": ["read"],
                },
            )


if __name__ == "__main__":
    unittest.main()
