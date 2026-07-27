import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPAT = ROOT / "tools" / "compat"
MODULE_PATH = COMPAT / "run_compatibility_suite.py"
COMPARATOR_TEST_PATH = (
    ROOT / "tools" / "tests" / "test_compare_semantic_results.py"
)
sys.path.insert(0, str(COMPAT))

SPEC = importlib.util.spec_from_file_location(
    "run_compatibility_suite",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HELPER_SPEC = importlib.util.spec_from_file_location(
    "suite_semantic_comparison_support",
    COMPARATOR_TEST_PATH,
)
assert HELPER_SPEC is not None and HELPER_SPEC.loader is not None
HELPERS = importlib.util.module_from_spec(HELPER_SPEC)
HELPER_SPEC.loader.exec_module(HELPERS)


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def artifact(path, root):
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": MODULE.RAW.sha256_bytes(path.read_bytes()),
    }


def set_case_id(prepared, case_id):
    projection = json.loads(
        prepared["projection_contract"].read_text(encoding="utf-8")
    )
    projection["case_id"] = case_id
    write_json(prepared["projection_contract"], projection)

    comparison = json.loads(
        prepared["comparison_contract"].read_text(encoding="utf-8")
    )
    comparison["projection_contract_sha256"] = (
        MODULE.RAW.sha256_bytes(
            prepared["projection_contract"].read_bytes()
        )
    )
    write_json(prepared["comparison_contract"], comparison)

    for name in ("upstream_manifest", "rust_manifest"):
        manifest = json.loads(
            prepared[name].read_text(encoding="utf-8")
        )
        manifest["run_identity"]["case_id"] = case_id
        write_json(prepared[name], manifest)


def prepare_suite_case(
    root,
    directory_name,
    case_id,
    capability,
    upstream,
    rust,
    *,
    required="exact",
    approve_differences=False,
):
    case_root = root / directory_name
    case_root.mkdir()
    prepared = HELPERS.prepare_case(
        case_root,
        upstream,
        rust,
        required=required,
    )
    set_case_id(prepared, case_id)
    waivers = []
    if approve_differences:
        _, difference_report = HELPERS.compare_prepared(prepared)
        for index, difference in enumerate(
            difference_report["differences"],
            start=1,
        ):
            waivers.append(
                {
                    "id": f"DIFF-{9500 + index}",
                    "status": "approved",
                    "case_id": difference["case_id"],
                    "json_pointer": difference["json_pointer"],
                    "classification": difference["classification"],
                    "failure_kind": difference["failure_kind"],
                    "left_raw_sha256": difference["left_raw_sha256"],
                    "right_raw_sha256": difference[
                        "right_raw_sha256"
                    ],
                    "diff_fingerprint": difference[
                        "diff_fingerprint"
                    ],
                    "evidence": (
                        "docs/research/cli-option-behavior.md"
                    ),
                    "decision": (
                        "docs/design/decisions/"
                        "0004-evidence-bound-difference-waivers.md"
                    ),
                    "owner": "compatibility-owner",
                    "reviewed_by": "independent-reviewer",
                    "reviewed_on": "2026-07-27",
                    "expires": "2026-08-27",
                    "removal_condition": (
                        "Rust behavior matches the pinned oracle."
                    ),
                }
            )
    registry_path = case_root / "waiver-registry.json"
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "registry_identity": {
                "platform": "linux-x86_64",
                "upstream_commit": HELPERS.UPSTREAM,
                "rust_schema": 1,
            },
            "waivers": waivers,
        },
    )
    return {
        "case_id": case_id,
        "capability": capability,
        "platform": "linux-x86_64",
        "oracle_profile": "cmake-qt5",
        "comparison_contract": artifact(
            prepared["comparison_contract"],
            root,
        ),
        "projection_contract": artifact(
            prepared["projection_contract"],
            root,
        ),
        "upstream_manifest": artifact(
            prepared["upstream_manifest"],
            root,
        ),
        "upstream_artifact_root": prepared[
            "upstream_root"
        ].relative_to(root).as_posix(),
        "rust_manifest": artifact(
            prepared["rust_manifest"],
            root,
        ),
        "rust_artifact_root": prepared["rust_root"].relative_to(
            root
        ).as_posix(),
        "normalization_policy": None,
        "waiver_registry": artifact(registry_path, root),
    }


def write_plan(root, cases):
    plan = {
        "suite_plan_schema": 1,
        "suite_id": "synthetic.test-suite",
        "as_of": "2026-07-27",
        "upstream_commit": HELPERS.UPSTREAM,
        "semantic_schema": 1,
        "max_artifact_bytes": 4096,
        "cases": cases,
    }
    path = root / "suite-plan.json"
    write_json(path, plan)
    return path, plan


class CompatibilitySuiteTests(unittest.TestCase):
    def test_plan_is_closed_and_rejects_duplicate_case_identity(self):
        valid_case = {
            "case_id": "case.one",
            "capability": "normal-scan",
            "platform": "linux-x86_64",
            "oracle_profile": "cmake-qt5",
            "comparison_contract": {
                "path": "comparison.json",
                "sha256": "1" * 64,
            },
            "projection_contract": {
                "path": "projection.json",
                "sha256": "2" * 64,
            },
            "upstream_manifest": {
                "path": "upstream.json",
                "sha256": "3" * 64,
            },
            "upstream_artifact_root": "upstream-artifacts",
            "rust_manifest": {
                "path": "rust.json",
                "sha256": "4" * 64,
            },
            "rust_artifact_root": "rust-artifacts",
            "normalization_policy": None,
            "waiver_registry": {
                "path": "waivers.json",
                "sha256": "5" * 64,
            },
        }
        plan = {
            "suite_plan_schema": 1,
            "suite_id": "suite.one",
            "as_of": "2026-07-27",
            "upstream_commit": HELPERS.UPSTREAM,
            "semantic_schema": 1,
            "max_artifact_bytes": 4096,
            "cases": [valid_case],
        }
        validated = MODULE.validate_plan(plan)
        self.assertEqual(validated["suite_id"], "suite.one")
        for mutation, message in (
            ({"unknown": True}, "unknown fields"),
            ({"as_of": "today"}, "YYYY-MM-DD"),
            ({"max_artifact_bytes": True}, "integer"),
            ({"cases": []}, "1..10000"),
        ):
            changed = dict(plan)
            changed.update(mutation)
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(MODULE.SuiteError, message):
                    MODULE.validate_plan(changed)

        duplicate = dict(plan)
        duplicate["cases"] = [valid_case, valid_case]
        with self.assertRaisesRegex(
            MODULE.SuiteError,
            "identities must be unique",
        ):
            MODULE.validate_plan(duplicate)

    def test_two_case_pass_report_is_ordered_and_grouped(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            exact = prepare_suite_case(
                input_root,
                "exact",
                "case.exact",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{"detects":[]}',
            )
            semantic = prepare_suite_case(
                input_root,
                "semantic",
                "case.semantic",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{\n  "detects": []\n}',
                required="semantic",
            )
            plan_path, _ = write_plan(
                input_root,
                [exact, semantic],
            )
            report = MODULE.run_suite(
                plan_path,
                input_root,
                pathlib.Path(output_directory),
                ROOT,
            )
            self.assertEqual(report["result"], "pass")
            self.assertEqual(
                report["summary"]["case_results"],
                {
                    "total": 2,
                    "pass": 2,
                    "fail": 0,
                    "infrastructure_error": 0,
                },
            )
            self.assertEqual(
                report["summary"]["comparison_results"]["exact"],
                1,
            )
            self.assertEqual(
                report["summary"]["comparison_results"][
                    "semantic_equal"
                ],
                1,
            )
            self.assertEqual(
                [
                    item["identity"]["case_id"]
                    for item in report["cases"]
                ],
                ["case.exact", "case.semantic"],
            )
            self.assertEqual(len(report["platforms"]), 1)
            self.assertEqual(len(report["capabilities"]), 1)
            self.assertTrue(report["input_files_unchanged"])

    def test_valid_case_failure_makes_suite_fail_not_infrastructure(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            case = prepare_suite_case(
                input_root,
                "raw-mismatch",
                "case.raw-mismatch",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{\n  "detects": []\n}',
            )
            plan_path, _ = write_plan(input_root, [case])
            report = MODULE.run_suite(
                plan_path,
                input_root,
                pathlib.Path(output_directory),
                ROOT,
            )
            self.assertEqual(report["result"], "fail")
            self.assertEqual(report["errors"], [])
            self.assertEqual(
                report["cases"][0]["reason"],
                "raw_only_mismatch_unwaivable",
            )
            self.assertEqual(
                report["summary"]["case_results"]["fail"],
                1,
            )

    def test_approved_differences_are_counted_by_classification(self):
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
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            case = prepare_suite_case(
                input_root,
                "waived",
                "case.waived",
                "legacy-cli.normal-scan",
                upstream,
                rust,
                approve_differences=True,
            )
            plan_path, _ = write_plan(input_root, [case])
            report = MODULE.run_suite(
                plan_path,
                input_root,
                pathlib.Path(output_directory),
                ROOT,
            )
            self.assertEqual(report["result"], "pass")
            self.assertEqual(
                report["cases"][0]["reason"],
                "approved_semantic_differences",
            )
            self.assertEqual(
                report["summary"]["differences"],
                {
                    "total": 2,
                    "applied": 2,
                    "unmatched": 0,
                    "by_classification": {
                        "Semantic": 2,
                        "SafetyDeviation": 0,
                        "Unsupported": 0,
                    },
                },
            )
            self.assertEqual(report["summary"]["waived_cases"], 1)

    def test_one_blocked_case_makes_whole_suite_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            passing = prepare_suite_case(
                input_root,
                "passing",
                "case.passing",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{"detects":[]}',
            )
            blocked = prepare_suite_case(
                input_root,
                "blocked",
                "case.blocked",
                "legacy-cli.normal-scan",
                b'{"unexpected":true}',
                b'{"unexpected":true}',
            )
            plan_path, _ = write_plan(
                input_root,
                [passing, blocked],
            )
            report = MODULE.run_suite(
                plan_path,
                input_root,
                pathlib.Path(output_directory),
                ROOT,
            )
            self.assertEqual(
                report["result"],
                "infrastructure_error",
            )
            self.assertEqual(
                report["summary"]["case_results"],
                {
                    "total": 2,
                    "pass": 1,
                    "fail": 0,
                    "infrastructure_error": 1,
                },
            )
            self.assertEqual(
                report["cases"][1]["comparison_result"],
                "projection_failure",
            )
            self.assertTrue(report["errors"])
            self.assertTrue(
                (
                    pathlib.Path(output_directory)
                    / "cases"
                    / "000001"
                    / "case-audit.json"
                ).is_file()
            )

    def test_hash_drift_stops_before_any_case_is_run(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            case = prepare_suite_case(
                input_root,
                "case",
                "case.hash-drift",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{"detects":[]}',
            )
            case["comparison_contract"]["sha256"] = "0" * 64
            plan_path, _ = write_plan(input_root, [case])
            with mock.patch.object(
                MODULE.case_auditor,
                "audit_files",
                wraps=MODULE.case_auditor.audit_files,
            ) as audit:
                report = MODULE.run_suite(
                    plan_path,
                    input_root,
                    pathlib.Path(output_directory),
                    ROOT,
                )
            self.assertEqual(
                report["result"],
                "infrastructure_error",
            )
            self.assertIn("SHA-256 mismatch", report["errors"][0])
            self.assertEqual(audit.call_count, 0)
            self.assertEqual(report["cases"], [])

    def test_input_mutation_after_case_run_invalidates_suite(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            case = prepare_suite_case(
                input_root,
                "case",
                "case.mutated",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{"detects":[]}',
            )
            plan_path, _ = write_plan(input_root, [case])
            contract = input_root.joinpath(
                *pathlib.PurePosixPath(
                    case["comparison_contract"]["path"]
                ).parts
            )
            original_audit = MODULE.case_auditor.audit_files

            def audit_then_mutate(**kwargs):
                result = original_audit(**kwargs)
                contract.write_bytes(contract.read_bytes() + b" ")
                return result

            with mock.patch.object(
                MODULE.case_auditor,
                "audit_files",
                side_effect=audit_then_mutate,
            ):
                report = MODULE.run_suite(
                    plan_path,
                    input_root,
                    pathlib.Path(output_directory),
                    ROOT,
                )
            self.assertEqual(
                report["result"],
                "infrastructure_error",
            )
            self.assertFalse(report["input_files_unchanged"])
            self.assertTrue(
                any(
                    "input changed during suite execution" in error
                    for error in report["errors"]
                )
            )

    def test_case_identity_drift_is_not_aggregated(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            case = prepare_suite_case(
                input_root,
                "case",
                "case.identity-drift",
                "legacy-cli.normal-scan",
                b'{"detects":[]}',
                b'{"detects":[]}',
            )
            case["platform"] = "windows-x86_64"
            plan_path, _ = write_plan(input_root, [case])
            report = MODULE.run_suite(
                plan_path,
                input_root,
                pathlib.Path(output_directory),
                ROOT,
            )
            self.assertEqual(
                report["result"],
                "infrastructure_error",
            )
            self.assertEqual(
                report["cases"][0]["reason"],
                "suite_case_identity_mismatch",
            )
            self.assertTrue(
                any(
                    "run identity" in error
                    for error in report["cases"][0]["errors"]
                )
            )

    def test_output_root_must_be_disjoint_before_creation(self):
        with tempfile.TemporaryDirectory() as input_directory:
            input_root = pathlib.Path(input_directory)
            output_root = input_root / "generated"
            with self.assertRaisesRegex(
                MODULE.SuiteError,
                "must be disjoint",
            ):
                MODULE.prepare_roots(input_root, output_root)
            self.assertFalse(output_root.exists())

    def test_output_root_must_be_empty_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as input_directory, (
            tempfile.TemporaryDirectory()
        ) as output_directory:
            input_root = pathlib.Path(input_directory)
            output_root = pathlib.Path(output_directory)
            marker = output_root / "existing.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.SuiteError,
                "must be empty",
            ):
                MODULE.prepare_roots(input_root, output_root)
            self.assertEqual(
                marker.read_text(encoding="utf-8"),
                "preserve",
            )

    def test_synthetic_example_reproduces_report_golden(self):
        examples = ROOT / "docs" / "design" / "schemas" / "examples"
        plan_path = (
            examples / "compatibility-suite-plan-v1.example.json"
        )
        expected = (
            examples / "compatibility-suite-report-v1.example.json"
        ).read_bytes()
        with tempfile.TemporaryDirectory() as output_directory:
            report = MODULE.run_suite(
                plan_path,
                ROOT,
                pathlib.Path(output_directory),
                ROOT,
            )
            self.assertEqual(MODULE.serialize_json(report), expected)
            self.assertEqual(
                (
                    pathlib.Path(output_directory)
                    / "compatibility-report.json"
                ).read_bytes(),
                expected,
            )

    def test_schemas_are_closed_and_versioned(self):
        schemas = ROOT / "docs" / "design" / "schemas"
        for filename in (
            "compatibility-suite-plan-v1.schema.json",
            "compatibility-suite-report-v1.schema.json",
        ):
            with self.subTest(filename=filename):
                schema = json.loads(
                    (schemas / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertFalse(schema["additionalProperties"])
        report_schema = json.loads(
            (
                schemas
                / "compatibility-suite-report-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(report_schema["properties"]["result"]["enum"]),
            {"pass", "fail", "infrastructure_error"},
        )

    def test_main_exit_codes_are_stable(self):
        args = mock.Mock(
            plan=pathlib.Path("plan"),
            input_root=pathlib.Path("input"),
            output_root=pathlib.Path("output"),
            repo_root=ROOT,
        )
        for result, expected in (
            ("pass", 0),
            ("fail", 1),
            ("infrastructure_error", 2),
        ):
            with self.subTest(result=result), mock.patch.object(
                MODULE,
                "parse_args",
                return_value=args,
            ), mock.patch.object(
                MODULE,
                "run_suite",
                return_value={"result": result},
            ):
                self.assertEqual(MODULE.main([]), expected)


if __name__ == "__main__":
    unittest.main()
