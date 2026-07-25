import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "upstream"
    / "probe_archive_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_archive_harness", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeArchiveHarnessTests(unittest.TestCase):
    def test_matrix_crosses_archive_recursive_and_aggressive_flags(self):
        self.assertEqual(
            [case.name for case in MODULE.HARNESS_MATRIX],
            [
                "default",
                "archive",
                "aggressive",
                "archive_aggressive",
                "recursive",
                "recursive_aggressive",
                "archive_recursive",
                "archive_recursive_aggressive",
            ],
        )

    def test_release_equivalents_exclude_archive_cases(self):
        self.assertEqual(
            set(MODULE.RELEASE_EQUIVALENTS),
            {
                "default",
                "aggressive",
                "recursive",
                "recursive_aggressive",
            },
        )

    def test_counts_file_parts_recursively(self):
        tree = [
            {
                "parentfilepart": "Header",
                "values": [
                    {
                        "parentfilepart": "Overlay",
                        "values": [
                            {"parentfilepart": "Stream"},
                            {"parentfilepart": "Stream"},
                        ],
                    },
                    {"name": "leaf"},
                ],
            }
        ]

        self.assertEqual(MODULE.count_file_parts(tree, "Header"), 1)
        self.assertEqual(MODULE.count_file_parts(tree, "Overlay"), 1)
        self.assertEqual(MODULE.count_file_parts(tree, "Stream"), 2)
        self.assertEqual(MODULE.count_file_parts(tree, "Resource"), 0)

    def test_boundary_expectations_capture_observed_off_by_one(self):
        self.assertEqual(
            MODULE.EXPECTED_BOUNDARY_COUNTS[
                ("many-pdf-members.zip", "archive", "Stream")
            ],
            21,
        )
        self.assertEqual(
            MODULE.EXPECTED_BOUNDARY_COUNTS[
                (
                    "pe-many-pdf-resources.exe",
                    "recursive_aggressive",
                    "Resource",
                )
            ],
            22,
        )


if __name__ == "__main__":
    unittest.main()
