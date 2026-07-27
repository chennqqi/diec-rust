import base64
import hashlib
import json
import pathlib
import unittest
import xml.etree.ElementTree as element_tree


ROOT = pathlib.Path(__file__).parents[2]
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-output-boundaries-linux-qt5.json"
)
OUTPUT_FIXTURE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "output-boundary-fixture.json"
)
NESTED_FIXTURE_PATH = (
    ROOT / "docs" / "research" / "data" / "nested-corpus.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "cli-output-boundaries.md"
)


class CliOutputBoundaryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(
            OUTPUT_FIXTURE_PATH.read_text(encoding="utf-8")
        )
        cls.cases = {
            case["id"]: case for case in cls.report["cases"]
        }

    def raw_stream(self, case_id, side, stream):
        record = self.cases[case_id][side]
        data = base64.b64decode(record[f"{stream}_base64"])
        self.assertEqual(len(data), record[f"{stream}_bytes"])
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            record[f"{stream}_sha256"],
        )
        return data

    def test_report_is_bound_to_fixed_images_binaries_and_revision(self):
        revision = "74eaf505c250ab47e709024e9dc41657cd8f2254"
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["generator"],
            "tools/upstream/probe_cli_output_boundaries.py",
        )
        self.assertEqual(report["expected_revision"], revision)
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])

        expected = {
            "left": {
                "image_id": (
                    "sha256:"
                    "cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e4710"
                    "17d3c3988bac964ab"
                ),
                "image_revision": revision,
                "binary_sha256": (
                    "721ec846507a8567aae07e91dcd1f576182481ae0dc1595b"
                    "1f19e4a3e859b79d"
                ),
            },
            "right": {
                "image_id": (
                    "sha256:"
                    "466102628c3a94b7ab1048f0c24261b1920e61a40029b12"
                    "8763cf79370255040"
                ),
                "image_revision": revision,
                "binary_sha256": (
                    "da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd809720"
                    "7e7b3c30f08236cf"
                ),
            },
        }
        for side, values in expected.items():
            for field, value in values.items():
                with self.subTest(side=side, field=field):
                    self.assertEqual(report[side][field], value)

    def test_report_binds_local_and_upstream_sources(self):
        report = self.report
        local_paths = {
            "probe": (
                ROOT
                / "tools"
                / "upstream"
                / "probe_cli_output_boundaries.py"
            ),
            "fixture_generator": (
                ROOT
                / "tools"
                / "corpus"
                / "generate_output_boundary_fixture.py"
            ),
            "nested_generator": (
                ROOT / "tools" / "corpus" / "generate_nested_corpus.py"
            ),
            "shared_helper": (
                ROOT / "tools" / "upstream" / "compare_cli_oracles.py"
            ),
        }
        generator = ROOT / report["generator"]
        self.assertEqual(
            hashlib.sha256(generator.read_bytes()).hexdigest(),
            report["generator_sha256"],
        )
        for name, path in local_paths.items():
            with self.subTest(source=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    report["local_source_hashes"][name],
                )
        self.assertEqual(
            report["upstream_source_hashes"],
            {
                (
                    "/opt/die-source/XScanEngine/"
                    "scanitemmodel.cpp"
                ): (
                    "53299fa3811510ab9dd791ed2d9ac51e82289f9fbbed303e"
                    "abf991d642ac6037"
                ),
                (
                    "/opt/die-source/XScanEngine/"
                    "scanitemmodel.h"
                ): (
                    "3150ab7ad6e75b522a853e774bf349f83ba551ab6cbe7f54"
                    "7068bcf4d8255676"
                ),
                (
                    "/opt/die-source/die_script/"
                    "die_scriptengine.cpp"
                ): (
                    "f9b9d69a17dc930556c7308fce46d3287d18dd9f927c91d6"
                    "733ce994594fcb72"
                ),
                (
                    "/opt/die-source/src/console/"
                    "main_console.cpp"
                ): (
                    "ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030d"
                    "ae6a85e7a9d7e8f"
                ),
            },
        )

    def test_fixture_hashes_and_resource_limits_are_exact(self):
        report = self.report
        self.assertEqual(
            report["output_fixture_manifest_sha256"],
            hashlib.sha256(OUTPUT_FIXTURE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["nested_fixture_manifest_sha256"],
            hashlib.sha256(NESTED_FIXTURE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["nested_fixture_sample_count"], 8)
        self.assertEqual(
            report["resource_limits"],
            {
                "network": "none",
                "cpus": 1,
                "memory_bytes": 536870912,
                "pids": 128,
                "fixtures": ["/outfx", "/nested"],
                "mount_mode": "read-only",
            },
        )

    def test_case_inventory_and_dual_oracle_raw_streams_are_exact(self):
        expected_ids = [
            f"{scope}_{format_name}"
            for scope in ("escaping", "nested")
            for format_name in (
                "json",
                "xml",
                "csv",
                "tsv",
                "plaintext",
            )
        ]
        self.assertEqual(list(self.cases), expected_ids)
        self.assertEqual(len(self.report["cases"]), 10)
        for case_id in expected_ids:
            with self.subTest(case=case_id):
                case = self.cases[case_id]
                self.assertTrue(case["oracles_equal"])
                self.assertEqual(case["left"]["exit_code"], 0)
                self.assertEqual(case["right"]["exit_code"], 0)
                left_stdout = self.raw_stream(
                    case_id,
                    "left",
                    "stdout",
                )
                right_stdout = self.raw_stream(
                    case_id,
                    "right",
                    "stdout",
                )
                self.assertEqual(left_stdout, right_stdout)
                self.assertEqual(
                    self.raw_stream(case_id, "left", "stderr"),
                    b"",
                )
                self.assertEqual(
                    self.raw_stream(case_id, "right", "stderr"),
                    b"",
                )

    def test_escaping_outputs_preserve_exact_fields_and_known_breakage(self):
        expected = self.fixture["expected_records"]
        json_raw = self.raw_stream("escaping_json", "left", "stdout")
        document = json.loads(json_raw)
        records = document["detects"][0]["values"]
        self.assertEqual(
            [
                {
                    field: record[field]
                    for field in ("type", "name", "version", "info")
                }
                for record in records
            ],
            expected,
        )

        xml_raw = self.raw_stream("escaping_xml", "left", "stdout")
        xml_root = element_tree.fromstring(xml_raw)
        self.assertEqual(
            [
                {
                    field: element.attrib[field]
                    for field in ("type", "name", "version", "info")
                }
                for element in xml_root.findall("./Binary/detect")
            ],
            expected,
        )

        csv_raw = self.raw_stream("escaping_csv", "left", "stdout")
        tsv_raw = self.raw_stream("escaping_tsv", "left", "stdout")
        self.assertGreater(len(csv_raw.splitlines()), len(expected))
        self.assertGreater(len(tsv_raw.splitlines()), len(expected))
        self.assertTrue(csv_raw.startswith(b'format;Quote"'))
        self.assertTrue(tsv_raw.startswith(b'format\tQuote"'))

    def test_nested_formatter_order_and_invalid_xml_are_fixed(self):
        json_document = json.loads(
            self.raw_stream("nested_json", "left", "stdout")
        )
        root = json_document["detects"][0]
        self.assertEqual(root["values"][0]["string"], "Unknown: Unknown")
        child = root["values"][1]
        self.assertEqual(
            (
                child["filetype"],
                child["parentfilepart"],
                child["offset"],
                child["size"],
            ),
            ("PDF", "Resource", "608", "331"),
        )
        self.assertEqual(
            [record["string"] for record in child["values"]],
            [
                "Format: PDF(1.4)",
                "Complier: HeaderComment(e2e3cfd3)",
            ],
        )

        xml_raw = self.raw_stream("nested_xml", "left", "stdout")
        with self.assertRaises(element_tree.ParseError):
            element_tree.fromstring(xml_raw)
        self.assertIn(b"<Resource: PDF[", xml_raw)

        expected_leaf_names = [
            "Unknown: Unknown",
            "Format: PDF(1.4)",
            "Complier: HeaderComment(e2e3cfd3)",
        ]
        for format_name, delimiter in (("csv", ";"), ("tsv", "\t")):
            lines = self.raw_stream(
                f"nested_{format_name}",
                "left",
                "stdout",
            ).decode("utf-8").strip().splitlines()
            self.assertEqual(
                [line.split(delimiter)[-1] for line in lines],
                expected_leaf_names,
            )

    def test_all_derived_facts_are_true_and_documented(self):
        self.assertEqual(
            set(self.report["facts"]),
            {
                "csv_flattens_depth_first_and_omits_parent_nodes",
                "csv_is_unquoted_and_delimiter_ambiguous",
                "json_preserves_parent_child_and_leaf_order",
                "json_record_fields_exact",
                "json_uses_valid_escaping",
                "plaintext_preserves_depth_first_indentation",
                "plaintext_preserves_raw_field_controls",
                "record_order_is_format_compiler_tool",
                "tsv_flattens_depth_first_and_omits_parent_nodes",
                "tsv_is_unquoted_and_delimiter_ambiguous",
                "xml_dynamic_nested_element_is_not_well_formed",
                "xml_record_attributes_exact",
                "xml_uses_entities_for_attribute_boundaries",
            },
        )
        self.assertTrue(all(self.report["facts"].values()))
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        index = (
            ROOT / "docs" / "research" / "README.md"
        ).read_text(encoding="utf-8")
        for token in (
            REPORT_PATH.name,
            "xml_dynamic_nested_element_is_not_well_formed",
            "csv_is_unquoted_and_delimiter_ambiguous",
        ):
            self.assertIn(token, document)
        self.assertIn(REPORT_PATH.name, index)


if __name__ == "__main__":
    unittest.main()
