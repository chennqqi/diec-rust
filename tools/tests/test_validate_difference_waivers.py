import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "compat"
    / "validate_difference_waivers.py"
)
SCHEMA_DIR = ROOT / "docs" / "design" / "schemas"
SPEC = importlib.util.spec_from_file_location(
    "validate_difference_waivers",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


IDENTITY = {
    "platform": "linux-x86_64",
    "upstream_commit": "74eaf505c250ab47e709024e9dc41657cd8f2254",
    "rust_schema": 1,
}


def make_difference() -> dict[str, object]:
    difference: dict[str, object] = {
        "id": "D-0001",
        "case_id": "cli.path.line-ending",
        "json_pointer": "/stdout/framing/line_ending",
        "classification": "Semantic",
        "failure_kind": "platform_behavior",
        "left_raw_sha256": "1" * 64,
        "right_raw_sha256": "2" * 64,
        "upstream_value": "\r\n",
        "rust_value": "\n",
    }
    difference["diff_fingerprint"] = (
        MODULE.difference_fingerprint(difference)
    )
    return difference


def make_registry(difference=None) -> dict[str, object]:
    if difference is None:
        difference = make_difference()
    return {
        "schema_version": 1,
        "registry_identity": copy.deepcopy(IDENTITY),
        "waivers": [
            {
                "id": "DIFF-0001",
                "status": "approved",
                "case_id": difference["case_id"],
                "json_pointer": difference["json_pointer"],
                "classification": difference["classification"],
                "failure_kind": difference["failure_kind"],
                "left_raw_sha256": difference["left_raw_sha256"],
                "right_raw_sha256": difference["right_raw_sha256"],
                "diff_fingerprint": difference["diff_fingerprint"],
                "evidence": "docs/research/cli-path-behavior.md",
                "decision": (
                    "docs/design/decisions/"
                    "0004-evidence-bound-difference-waivers.md"
                ),
                "owner": "compatibility",
                "reviewed_by": "compatibility-owner",
                "reviewed_on": "2026-07-27",
                "expires": "2027-07-27",
                "removal_condition": (
                    "Remove when canonical line endings are identical"
                ),
            }
        ],
    }


def make_report(difference=None) -> dict[str, object]:
    if difference is None:
        difference = make_difference()
    return {
        "report_schema": 1,
        "run_identity": copy.deepcopy(IDENTITY),
        "executed_case_ids": ["cli.path.line-ending"],
        "differences": [difference],
    }


def validate_and_audit(
    registry,
    report,
    as_of="2026-07-27",
):
    date = MODULE.dt.date.fromisoformat(as_of)
    validated_registry = MODULE.validate_registry(
        registry,
        ROOT,
        date,
    )
    validated_report = MODULE.validate_report(report)
    return MODULE.audit_waivers(
        validated_registry,
        validated_report,
        date,
        "a" * 64,
        "b" * 64,
    )


class ValidateDifferenceWaiversTests(unittest.TestCase):
    def test_exact_waiver_passes_and_is_auditable(self):
        audit = validate_and_audit(make_registry(), make_report())
        self.assertEqual(audit["result"], "pass")
        self.assertEqual(
            audit["applied"],
            [
                {
                    "waiver_id": "DIFF-0001",
                    "difference_id": "D-0001",
                }
            ],
        )
        for field in (
            "unmatched_differences",
            "expired_waivers",
            "stale_waivers",
            "unmatched_waivers",
            "forbidden_waiver_attempts",
            "failures",
        ):
            self.assertEqual(audit[field], [])
        self.assertTrue(audit["input_files_unchanged"])

    def test_difference_expansion_or_raw_hash_change_does_not_match(self):
        for mutation in ("rust_value", "right_raw_sha256"):
            with self.subTest(mutation=mutation):
                original = make_difference()
                changed = copy.deepcopy(original)
                if mutation == "rust_value":
                    changed[mutation] = "\n\n"
                else:
                    changed[mutation] = "3" * 64
                changed["diff_fingerprint"] = (
                    MODULE.difference_fingerprint(changed)
                )
                audit = validate_and_audit(
                    make_registry(original),
                    make_report(changed),
                )
                self.assertEqual(audit["result"], "fail")
                self.assertEqual(
                    audit["unmatched_differences"],
                    ["D-0001"],
                )
                self.assertEqual(audit["stale_waivers"], ["DIFF-0001"])

    def test_disappeared_difference_is_stale(self):
        report = make_report()
        report["differences"] = []
        audit = validate_and_audit(make_registry(), report)
        self.assertEqual(audit["result"], "fail")
        self.assertEqual(audit["stale_waivers"], ["DIFF-0001"])
        self.assertEqual(audit["unmatched_differences"], [])

    def test_unexecuted_waiver_case_is_unmatched(self):
        report = make_report()
        report["executed_case_ids"] = ["cli.path.other"]
        report["differences"] = []
        audit = validate_and_audit(make_registry(), report)
        self.assertEqual(audit["result"], "fail")
        self.assertEqual(audit["unmatched_waivers"], ["DIFF-0001"])

    def test_expired_waiver_fails_at_injected_audit_date(self):
        audit = validate_and_audit(
            make_registry(),
            make_report(),
            as_of="2027-07-27",
        )
        self.assertEqual(audit["result"], "fail")
        self.assertEqual(audit["expired_waivers"], ["DIFF-0001"])
        self.assertEqual(audit["unmatched_differences"], ["D-0001"])

    def test_identity_drift_is_an_infrastructure_error(self):
        for field, value in (
            ("platform", "windows-x86_64"),
            ("upstream_commit", "0" * 40),
            ("rust_schema", 2),
        ):
            with self.subTest(field=field):
                report = make_report()
                report["run_identity"][field] = value
                with self.assertRaisesRegex(
                    MODULE.ValidationError,
                    "registry_identity",
                ):
                    validate_and_audit(make_registry(), report)

    def test_wildcards_root_and_unknown_fields_are_rejected(self):
        mutations = (
            ("case_id", "cli.path.*", "wildcards"),
            ("json_pointer", "/", "non-root"),
            ("json_pointer", "/items/*/code", "wildcards"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field, value=value):
                registry = make_registry()
                registry["waivers"][0][field] = value
                with self.assertRaisesRegex(
                    MODULE.ValidationError,
                    message,
                ):
                    MODULE.validate_registry(
                        registry,
                        ROOT,
                        MODULE.dt.date(2026, 7, 27),
                    )

        registry = make_registry()
        registry["waivers"][0]["unexpected"] = True
        with self.assertRaisesRegex(
            MODULE.ValidationError,
            "unknown fields",
        ):
            MODULE.validate_registry(
                registry,
                ROOT,
                MODULE.dt.date(2026, 7, 27),
            )

    def test_forbidden_failures_can_never_enter_registry(self):
        for failure_kind in sorted(MODULE.FORBIDDEN_FAILURE_KINDS):
            with self.subTest(failure_kind=failure_kind):
                registry = make_registry()
                registry["waivers"][0]["failure_kind"] = failure_kind
                with self.assertRaisesRegex(
                    MODULE.ValidationError,
                    "forbidden",
                ):
                    MODULE.validate_registry(
                        registry,
                        ROOT,
                        MODULE.dt.date(2026, 7, 27),
                    )

    def test_report_fingerprint_is_recomputed(self):
        report = make_report()
        report["differences"][0]["rust_value"] = "expanded"
        with self.assertRaisesRegex(
            MODULE.ValidationError,
            "canonical content",
        ):
            MODULE.validate_report(report)

    def test_safety_and_unsupported_require_specific_evidence(self):
        registry = make_registry()
        registry["waivers"][0]["classification"] = "SafetyDeviation"
        registry["waivers"][0]["failure_kind"] = "safety_limit"
        with self.assertRaisesRegex(
            MODULE.ValidationError,
            "threat_analysis",
        ):
            MODULE.validate_registry(
                registry,
                ROOT,
                MODULE.dt.date(2026, 7, 27),
            )

        registry = make_registry()
        registry["waivers"][0]["classification"] = "Unsupported"
        registry["waivers"][0][
            "failure_kind"
        ] = "unsupported_feature"
        with self.assertRaisesRegex(
            MODULE.ValidationError,
            "roadmap_phase",
        ):
            MODULE.validate_registry(
                registry,
                ROOT,
                MODULE.dt.date(2026, 7, 27),
            )

    def test_duplicate_ids_and_targets_are_rejected(self):
        for mutation, message in (
            ("id", "IDs must be unique"),
            ("target", "target may have only one"),
        ):
            with self.subTest(mutation=mutation):
                registry = make_registry()
                duplicate = copy.deepcopy(registry["waivers"][0])
                if mutation == "target":
                    duplicate["id"] = "DIFF-0002"
                registry["waivers"].append(duplicate)
                with self.assertRaisesRegex(
                    MODULE.ValidationError,
                    message,
                ):
                    MODULE.validate_registry(
                        registry,
                        ROOT,
                        MODULE.dt.date(2026, 7, 27),
                    )

    def test_cli_preserves_input_bytes_and_writes_versioned_audit(self):
        registry = make_registry()
        report = make_report()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            registry_path = root / "registry.json"
            report_path = root / "report.json"
            audit_path = root / "audit.json"
            registry_path.write_text(
                json.dumps(registry, indent=2) + "\n",
                encoding="utf-8",
            )
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            registry_before = registry_path.read_bytes()
            report_before = report_path.read_bytes()

            result = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--registry",
                    str(registry_path),
                    "--report",
                    str(report_path),
                    "--as-of",
                    "2026-07-27",
                    "--repo-root",
                    str(ROOT),
                    "--output",
                    str(audit_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(audit["audit_schema"], 1)
            self.assertEqual(audit["result"], "pass")
            self.assertTrue(audit["input_files_unchanged"])
            self.assertEqual(registry_path.read_bytes(), registry_before)
            self.assertEqual(report_path.read_bytes(), report_before)

    def test_cli_distinguishes_audit_failure_and_infrastructure_error(self):
        registry = make_registry()
        changed = make_difference()
        changed["rust_value"] = "expanded"
        changed["diff_fingerprint"] = (
            MODULE.difference_fingerprint(changed)
        )
        report = make_report(changed)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            registry_path = root / "registry.json"
            report_path = root / "report.json"
            registry_path.write_text(
                json.dumps(registry),
                encoding="utf-8",
            )
            report_path.write_text(
                json.dumps(report),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(MODULE_PATH),
                "--registry",
                str(registry_path),
                "--report",
                str(report_path),
                "--as-of",
                "2026-07-27",
                "--repo-root",
                str(ROOT),
            ]
            failed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(
                json.loads(failed.stdout)["result"],
                "fail",
            )

            report["run_identity"]["rust_schema"] = 2
            report_path.write_text(
                json.dumps(report),
                encoding="utf-8",
            )
            infrastructure = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(infrastructure.returncode, 2)
            self.assertEqual(
                json.loads(infrastructure.stdout)["result"],
                "infrastructure_error",
            )

    def test_cli_invalid_date_emits_null_infrastructure_date(self):
        examples = SCHEMA_DIR / "examples"
        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--registry",
                str(
                    examples
                    / "difference-waiver-registry-v1.example.json"
                ),
                "--report",
                str(
                    examples
                    / "difference-input-report-v1.example.json"
                ),
                "--as-of",
                "not-a-date",
                "--repo-root",
                str(ROOT),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        audit = json.loads(result.stdout)
        self.assertEqual(audit["result"], "infrastructure_error")
        self.assertIsNone(audit["as_of"])

    def test_strict_json_rejects_duplicate_keys_and_non_finite_values(self):
        for content, message in (
            (b'{"schema_version":1,"schema_version":1}', "duplicate key"),
            (b'{"value":NaN}', "non-finite"),
            (b'{"value":Infinity}', "non-finite"),
        ):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as directory:
                    path = pathlib.Path(directory) / "input.json"
                    path.write_bytes(content)
                    with self.assertRaisesRegex(
                        MODULE.ValidationError,
                        message,
                    ):
                        MODULE.load_json_bytes(path, "input")

    def test_machine_schemas_are_versioned_and_closed(self):
        for filename in (
            "difference-waiver-registry-v1.schema.json",
            "difference-input-report-v1.schema.json",
            "difference-waiver-audit-v1.schema.json",
        ):
            with self.subTest(schema=filename):
                schema = json.loads(
                    (SCHEMA_DIR / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertFalse(schema["additionalProperties"])

        registry_schema = json.loads(
            (
                SCHEMA_DIR
                / "difference-waiver-registry-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        report_schema = json.loads(
            (
                SCHEMA_DIR / "difference-input-report-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(
                registry_schema["$defs"]["waiver"]["properties"][
                    "failure_kind"
                ]["enum"]
            ),
            MODULE.WAIVABLE_FAILURE_KINDS,
        )
        self.assertEqual(
            set(
                report_schema["$defs"]["difference"]["properties"][
                    "failure_kind"
                ]["enum"]
            ),
            (
                MODULE.WAIVABLE_FAILURE_KINDS
                | MODULE.FORBIDDEN_FAILURE_KINDS
            ),
        )

    def test_synthetic_examples_reproduce_versioned_audit(self):
        examples = SCHEMA_DIR / "examples"
        registry_path = (
            examples
            / "difference-waiver-registry-v1.example.json"
        )
        report_path = (
            examples / "difference-input-report-v1.example.json"
        )
        expected_path = (
            examples / "difference-waiver-audit-v1.example.json"
        )
        registry_bytes = registry_path.read_bytes()
        report_bytes = report_path.read_bytes()
        registry = MODULE.validate_registry(
            json.loads(registry_bytes),
            ROOT,
            MODULE.dt.date(2026, 7, 27),
        )
        report = MODULE.validate_report(json.loads(report_bytes))
        audit = MODULE.audit_waivers(
            registry,
            report,
            MODULE.dt.date(2026, 7, 27),
            MODULE.sha256_bytes(registry_bytes),
            MODULE.sha256_bytes(report_bytes),
        )
        self.assertEqual(
            MODULE.serialize_audit(audit),
            expected_path.read_text(encoding="utf-8"),
        )
        readme = (examples / "README.md").read_text(encoding="utf-8")
        self.assertIn("documentation-only synthetic", readme)
        self.assertIn("must not be copied", readme)

    def test_design_documents_link_validator_and_remaining_scope(self):
        testing = (
            ROOT / "docs" / "design" / "testing.md"
        ).read_text(encoding="utf-8")
        adr = (
            ROOT / "docs" / "design" / "decisions"
            / "0004-evidence-bound-difference-waivers.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / "docs" / "design" / "schemas" / "README.md"
        ).read_text(encoding="utf-8")
        for text in (
            MODULE_PATH.name,
            "difference-waiver-registry-v1.schema.json",
            "difference-input-report-v1.schema.json",
            "difference-waiver-audit-v1.schema.json",
        ):
            self.assertIn(text, testing)
            self.assertIn(text, adr)
            self.assertIn(text, index)
        self.assertIn("compare_semantic_results.py", testing)
        self.assertIn("顶层 single-case auditor", adr)
        self.assertIn("audit_semantic_case.py", adr)
        self.assertIn("仍保持 Proposed", adr)


if __name__ == "__main__":
    unittest.main()
