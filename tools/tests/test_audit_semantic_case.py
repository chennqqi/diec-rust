import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPAT = ROOT / "tools" / "compat"
MODULE_PATH = COMPAT / "audit_semantic_case.py"
COMPARATOR_TEST_PATH = (
    ROOT / "tools" / "tests" / "test_compare_semantic_results.py"
)
sys.path.insert(0, str(COMPAT))

SPEC = importlib.util.spec_from_file_location(
    "audit_semantic_case",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HELPER_SPEC = importlib.util.spec_from_file_location(
    "semantic_comparison_test_support",
    COMPARATOR_TEST_PATH,
)
assert HELPER_SPEC is not None and HELPER_SPEC.loader is not None
HELPERS = importlib.util.module_from_spec(HELPER_SPEC)
HELPER_SPEC.loader.exec_module(HELPERS)


def empty_registry():
    return {
        "schema_version": 1,
        "registry_identity": {
            "platform": "linux-x86_64",
            "upstream_commit": HELPERS.UPSTREAM,
            "rust_schema": 1,
        },
        "waivers": [],
    }


def write_registry(path, registry):
    path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def audit_prepared(prepared, registry=None, as_of="2026-07-27"):
    directory = prepared["comparison_contract"].parent
    registry_path = directory / "waiver-registry.json"
    write_registry(
        registry_path,
        empty_registry() if registry is None else registry,
    )
    outputs = prepared["outputs"]
    waiver_audit = directory / "waiver-audit.json"
    case_audit = directory / "case-audit.json"
    result = MODULE.audit_files(
        comparison_contract_path=prepared["comparison_contract"],
        projection_contract_path=prepared["projection_contract"],
        upstream_manifest_path=prepared["upstream_manifest"],
        upstream_artifact_root=prepared["upstream_root"],
        rust_manifest_path=prepared["rust_manifest"],
        rust_artifact_root=prepared["rust_root"],
        upstream_projection_output=outputs["upstream_projection"],
        rust_projection_output=outputs["rust_projection"],
        normalization_policy_path=prepared["policy"],
        upstream_normalization_output=outputs[
            "upstream_normalization"
        ],
        rust_normalization_output=outputs["rust_normalization"],
        comparison_output=outputs["comparison"],
        difference_report_output=outputs["differences"],
        waiver_registry_path=registry_path,
        waiver_audit_output=waiver_audit,
        case_audit_output=case_audit,
        as_of_text=as_of,
        max_artifact_bytes=4096,
        repo_root=ROOT,
    )
    return result, registry_path, waiver_audit, case_audit


def matching_registry(difference_report):
    registry = empty_registry()
    for index, difference in enumerate(
        difference_report["differences"],
        start=1,
    ):
        waiver = {
            "id": f"DIFF-{9000 + index}",
            "status": "approved",
            "case_id": difference["case_id"],
            "json_pointer": difference["json_pointer"],
            "classification": difference["classification"],
            "failure_kind": difference["failure_kind"],
            "left_raw_sha256": difference["left_raw_sha256"],
            "right_raw_sha256": difference["right_raw_sha256"],
            "diff_fingerprint": difference["diff_fingerprint"],
            "evidence": "docs/research/cli-option-behavior.md",
            "decision": (
                "docs/design/decisions/"
                "0004-evidence-bound-difference-waivers.md"
            ),
            "owner": "compatibility-owner",
            "reviewed_by": "independent-reviewer",
            "reviewed_on": "2026-07-27",
            "expires": "2026-08-27",
            "removal_condition": "Rust behavior matches the pinned oracle.",
        }
        registry["waivers"].append(waiver)
    return registry


class SemanticCaseAuditTests(unittest.TestCase):
    def test_exact_result_and_empty_registry_pass(self):
        stdout = b'{"detects":[]}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(temporary, stdout, stdout)
            audit, registry_path, waiver_path, case_path = (
                audit_prepared(prepared)
            )
            self.assertEqual(audit["result"], "pass")
            self.assertEqual(
                audit["reason"],
                "required_equivalence_met",
            )
            self.assertEqual(audit["comparison"]["result"], "exact")
            self.assertEqual(audit["waiver_audit"]["result"], "pass")
            self.assertEqual(
                json.loads(case_path.read_text(encoding="utf-8")),
                audit,
            )
            for field, path in (
                ("waiver_registry", registry_path),
                ("waiver_audit", waiver_path),
                ("comparison", prepared["outputs"]["comparison"]),
                (
                    "difference_report",
                    prepared["outputs"]["differences"],
                ),
            ):
                self.assertEqual(
                    audit["artifacts"][field]["sha256"],
                    MODULE.waivers.sha256_bytes(path.read_bytes()),
                )

    def test_raw_only_exact_mismatch_is_not_waivable(self):
        upstream = b'{"detects":[]}'
        rust = b'{\n  "detects": []\n}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(
                temporary,
                upstream,
                rust,
            )
            audit, _, _, _ = audit_prepared(prepared)
            self.assertEqual(audit["result"], "fail")
            self.assertEqual(
                audit["reason"],
                "raw_only_mismatch_unwaivable",
            )
            self.assertEqual(
                audit["comparison"]["result"],
                "semantic_equal",
            )
            self.assertEqual(audit["waiver_audit"]["result"], "pass")

    def test_semantic_differences_require_exact_current_waivers(self):
        upstream = (
            b'{"detects":[{"filetype":"Binary","info":"",'
            b'"offset":"0","parentfilepart":"Header","size":"1",'
            b'"values":[{"info":"","name":"A","string":"Format: A",'
            b'"type":"format","version":""}]}]}'
        )
        rust = upstream.replace(b'"name":"A"', b'"name":"B"').replace(
            b'"string":"Format: A"',
            b'"string":"Format: B"',
        )
        with tempfile.TemporaryDirectory() as temporary:
            (pathlib.Path(temporary) / "unwaived").mkdir()
            prepared = HELPERS.prepare_case(
                pathlib.Path(temporary) / "unwaived",
                upstream,
                rust,
            )
            audit, _, _, _ = audit_prepared(prepared)
            self.assertEqual(audit["result"], "fail")
            self.assertEqual(audit["reason"], "waiver_audit_failed")
            self.assertEqual(
                audit["waiver_audit"]["unmatched_differences"],
                ["D-0001", "D-0002"],
            )

            approved_root = pathlib.Path(temporary) / "approved"
            approved_root.mkdir()
            approved = HELPERS.prepare_case(
                approved_root,
                upstream,
                rust,
            )
            _, difference_report = HELPERS.compare_prepared(approved)
            registry = matching_registry(difference_report)
            audit, _, _, _ = audit_prepared(approved, registry)
            self.assertEqual(audit["result"], "pass")
            self.assertEqual(
                audit["reason"],
                "approved_semantic_differences",
            )
            self.assertEqual(
                len(audit["waiver_audit"]["applied"]),
                2,
            )

    def test_stale_waiver_fails_an_executed_equal_case(self):
        stdout = b'{"detects":[]}'
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "mismatch").mkdir()
            mismatch = HELPERS.prepare_case(
                root / "mismatch",
                b'{"detects":[]}',
                b'{"detects":[{"filetype":"Binary","info":"",'
                b'"offset":"0","parentfilepart":"Header","size":"1",'
                b'"values":[]}]}',
            )
            _, difference_report = HELPERS.compare_prepared(mismatch)
            registry = matching_registry(difference_report)
            (root / "equal").mkdir()
            equal = HELPERS.prepare_case(
                root / "equal",
                stdout,
                stdout,
            )
            audit, _, _, _ = audit_prepared(equal, registry)
            self.assertEqual(audit["result"], "fail")
            self.assertEqual(
                audit["waiver_audit"]["stale_waivers"],
                ["DIFF-9001", "DIFF-9002"],
            )

    def test_projection_failure_blocks_and_overwrites_stale_audit(self):
        invalid = b'{"unexpected":true}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(
                temporary,
                invalid,
                invalid,
            )
            stale = prepared["comparison_contract"].parent / (
                "waiver-audit.json"
            )
            stale.write_text('{"result":"pass"}', encoding="utf-8")
            audit, _, waiver_path, _ = audit_prepared(prepared)
            self.assertEqual(
                audit["result"],
                "infrastructure_error",
            )
            self.assertEqual(audit["reason"], "comparison_blocked")
            self.assertEqual(
                audit["comparison"]["result"],
                "projection_failure",
            )
            self.assertEqual(
                audit["waiver_audit"]["result"],
                "infrastructure_error",
            )
            self.assertNotEqual(
                waiver_path.read_text(encoding="utf-8"),
                '{"result":"pass"}',
            )
            blocked = json.loads(
                prepared["outputs"]["differences"].read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(blocked["result"], "blocked")

    def test_invalid_date_emits_schema_representable_infrastructure(self):
        stdout = b'{"detects":[]}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(temporary, stdout, stdout)
            audit, _, waiver_path, case_path = audit_prepared(
                prepared,
                as_of="not-a-date",
            )
            self.assertEqual(
                audit["result"],
                "infrastructure_error",
            )
            self.assertIsNone(audit["as_of"])
            self.assertIsNone(audit["comparison"])
            waiver = json.loads(
                waiver_path.read_text(encoding="utf-8")
            )
            self.assertIsNone(waiver["as_of"])
            self.assertEqual(
                json.loads(case_path.read_text(encoding="utf-8")),
                audit,
            )

    def test_invalid_registry_stops_before_comparison(self):
        stdout = b'{"detects":[]}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(temporary, stdout, stdout)
            invalid = empty_registry()
            invalid["unexpected"] = True
            with mock.patch.object(
                MODULE.comparator,
                "compare_files",
                wraps=MODULE.comparator.compare_files,
            ) as compare:
                audit, _, _, _ = audit_prepared(prepared, invalid)
            self.assertEqual(
                audit["result"],
                "infrastructure_error",
            )
            self.assertIn(
                "unknown fields",
                audit["errors"][0],
            )
            self.assertEqual(compare.call_count, 0)

    def test_registry_mutation_during_comparison_is_infrastructure_error(
        self,
    ):
        stdout = b'{"detects":[]}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(temporary, stdout, stdout)
            registry_path = pathlib.Path(temporary) / (
                "waiver-registry.json"
            )
            original_compare = MODULE.comparator.compare_files

            def compare_then_mutate(*args, **kwargs):
                result = original_compare(*args, **kwargs)
                registry_path.write_bytes(
                    registry_path.read_bytes() + b" "
                )
                return result

            with mock.patch.object(
                MODULE.comparator,
                "compare_files",
                side_effect=compare_then_mutate,
            ):
                audit, _, _, _ = audit_prepared(prepared)
            self.assertEqual(
                audit["result"],
                "infrastructure_error",
            )
            self.assertIn(
                "registry changed",
                audit["errors"][0],
            )

    def test_output_collisions_are_rejected_before_writing(self):
        stdout = b'{"detects":[]}'
        with tempfile.TemporaryDirectory() as temporary:
            prepared = HELPERS.prepare_case(temporary, stdout, stdout)
            registry_path = pathlib.Path(temporary) / "registry.json"
            write_registry(registry_path, empty_registry())
            outputs = prepared["outputs"]
            with self.assertRaisesRegex(
                MODULE.comparator.ComparisonError,
                "distinct",
            ):
                MODULE.audit_files(
                    comparison_contract_path=prepared[
                        "comparison_contract"
                    ],
                    projection_contract_path=prepared[
                        "projection_contract"
                    ],
                    upstream_manifest_path=prepared[
                        "upstream_manifest"
                    ],
                    upstream_artifact_root=prepared["upstream_root"],
                    rust_manifest_path=prepared["rust_manifest"],
                    rust_artifact_root=prepared["rust_root"],
                    upstream_projection_output=outputs[
                        "upstream_projection"
                    ],
                    rust_projection_output=outputs["rust_projection"],
                    normalization_policy_path=None,
                    upstream_normalization_output=None,
                    rust_normalization_output=None,
                    comparison_output=outputs["comparison"],
                    difference_report_output=outputs["differences"],
                    waiver_registry_path=registry_path,
                    waiver_audit_output=outputs["comparison"],
                    case_audit_output=pathlib.Path(temporary)
                    / "case.json",
                    as_of_text="2026-07-27",
                    max_artifact_bytes=4096,
                    repo_root=ROOT,
                )

    def test_schema_is_closed_versioned_and_has_strict_result_branches(self):
        schema_path = (
            ROOT
            / "docs"
            / "design"
            / "schemas"
            / "semantic-case-audit-v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["properties"]["result"]["enum"]),
            {"pass", "fail", "infrastructure_error"},
        )
        self.assertIn(
            "approved_semantic_differences",
            schema["properties"]["reason"]["enum"],
        )

    def test_synthetic_example_reproduces_case_audit_golden(self):
        examples = ROOT / "docs" / "design" / "schemas" / "examples"
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary)
            case_audit = MODULE.audit_files(
                comparison_contract_path=examples
                / "semantic-comparison-contract-v1.example.json",
                projection_contract_path=examples
                / "semantic-projection-contract-v1.example.json",
                upstream_manifest_path=examples
                / "raw-framing-execution-v1.example.json",
                upstream_artifact_root=examples / "raw-artifacts",
                rust_manifest_path=examples
                / "semantic-comparison-rust-execution-v1.example.json",
                rust_artifact_root=examples / "raw-artifacts",
                upstream_projection_output=output
                / "upstream-projection.json",
                rust_projection_output=output / "rust-projection.json",
                normalization_policy_path=None,
                upstream_normalization_output=None,
                rust_normalization_output=None,
                comparison_output=output / "comparison.json",
                difference_report_output=output / "differences.json",
                waiver_registry_path=examples
                / "semantic-case-waiver-registry-v1.example.json",
                waiver_audit_output=output / "waiver-audit.json",
                case_audit_output=output / "case-audit.json",
                as_of_text="2026-07-27",
                max_artifact_bytes=1024,
                repo_root=ROOT,
            )
            self.assertEqual(
                MODULE.serialize_json(case_audit),
                (
                    examples / "semantic-case-audit-v1.example.json"
                ).read_bytes(),
            )
            self.assertEqual(
                (output / "waiver-audit.json").read_bytes(),
                (
                    examples
                    / "semantic-case-waiver-audit-v1.example.json"
                ).read_bytes(),
            )

    def test_main_exit_codes_are_stable(self):
        args = mock.Mock(
            comparison_contract=pathlib.Path("a"),
            projection_contract=pathlib.Path("b"),
            upstream_manifest=pathlib.Path("c"),
            upstream_artifact_root=pathlib.Path("d"),
            rust_manifest=pathlib.Path("e"),
            rust_artifact_root=pathlib.Path("f"),
            upstream_projection_output=pathlib.Path("g"),
            rust_projection_output=pathlib.Path("h"),
            normalization_policy=None,
            upstream_normalization_output=None,
            rust_normalization_output=None,
            comparison_output=pathlib.Path("i"),
            difference_report_output=pathlib.Path("j"),
            waiver_registry=pathlib.Path("k"),
            waiver_audit_output=pathlib.Path("l"),
            case_audit_output=pathlib.Path("m"),
            as_of="2026-07-27",
            max_artifact_bytes=4096,
            repo_root=ROOT,
        )
        for result, expected in (
            ("pass", 0),
            ("fail", 1),
            ("infrastructure_error", 2),
        ):
            with self.subTest(result=result), mock.patch.object(
                MODULE,
                "audit_files",
                return_value={"result": result},
            ), mock.patch.object(
                MODULE,
                "parse_args",
                return_value=args,
            ):
                self.assertEqual(MODULE.main([]), expected)


if __name__ == "__main__":
    unittest.main()
