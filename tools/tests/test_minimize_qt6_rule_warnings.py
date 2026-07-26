import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/minimize_qt6_rule_warnings.py"
SPEC = importlib.util.spec_from_file_location(
    "minimize_qt6_rule_warnings", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class MinimizeQt6RuleWarningsTests(unittest.TestCase):
    def test_committed_report_identifies_exact_warning_source(self):
        report = json.loads(
            (
                ROOT / "docs/research/data/qt6-rule-warnings.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["candidate_scope"]["signature_count"], 834)
        self.assertEqual(report["candidate_scope"]["helper_count"], 30)
        self.assertEqual(report["init_only_warning_count"], 0)
        self.assertEqual(report["full_warning_count"], 4)
        self.assertEqual(report["combined_minimized_warning_count"], 4)
        self.assertTrue(report["independently_additive"])
        self.assertEqual(report["observations"], 22)
        self.assertEqual(
            report["oracle"]["id"],
            (
                "sha256:e015495c313d0715f0b80f395da983a"
                "113a439f2a135eb637e9f0638c225200b"
            ),
        )
        self.assertEqual(
            report["findings"],
            [
                {
                    "path": (
                        "PE/__GenericHeuristicAnalysis_By_DosX.7.sg"
                    ),
                    "sha256": (
                        "c84a375fdc66508c66ae10440ab46be2"
                        "3d345d602b2ae6d79e26e66393ebadde"
                    ),
                    "warning_count": 4,
                    "stderr_lines": ["Unimplemented code."] * 4,
                    "raw_stdout_bytes": 467,
                    "raw_stdout_sha256": (
                        "c94fa4d2fa5742c41a67681779d3fc17"
                        "9aaf0f6558d74d385c648c2dae9dddde"
                    ),
                    "raw_stderr_bytes": 80,
                    "raw_stderr_sha256": (
                        "b303e6913e76b70a6f0d6a4d3ccd389"
                        "bc342589e45e1615873a37334dea8c51b"
                    ),
                }
            ],
        )

    def test_warning_counter_is_exact(self):
        self.assertEqual(MODULE.warning_count(b""), 0)
        self.assertEqual(
            MODULE.warning_count(b"Unimplemented code.\n" * 4),
            4,
        )
        with self.assertRaisesRegex(ValueError, "unexpected"):
            MODULE.warning_count(b"Unimplemented code.\nother\n")

    def test_locates_multiple_independent_sources(self):
        candidates = tuple(pathlib.Path(str(number)) for number in range(8))
        weights = {
            pathlib.Path("1"): 1,
            pathlib.Path("6"): 3,
        }

        def observe(selected):
            return sum(weights.get(path, 0) for path in selected)

        self.assertEqual(
            MODULE.locate_independent_sources(
                candidates,
                observe(candidates),
                observe,
            ),
            [(pathlib.Path("1"), 1), (pathlib.Path("6"), 3)],
        )

    def test_rejects_interacting_sources(self):
        candidates = (pathlib.Path("left"), pathlib.Path("right"))

        def observe(selected):
            return 1 if len(selected) == 2 else 0

        with self.assertRaisesRegex(ValueError, "not independently additive"):
            MODULE.locate_independent_sources(
                candidates,
                1,
                observe,
            )


if __name__ == "__main__":
    unittest.main()
