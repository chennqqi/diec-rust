import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "upstream"
    / "probe_resource_context_chain.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_resource_context_chain",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Observation:
    def __init__(
        self,
        exit_code=0,
        stdout=b"",
        stderr=b"",
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class ResourceContextChainProbeTests(unittest.TestCase):
    def test_matrix_requires_recursive_and_aggressive_together(self):
        self.assertEqual(
            [case.name for case in MODULE.CASES],
            [
                "default",
                "recursive",
                "aggressive",
                "recursive_aggressive",
            ],
        )
        self.assertEqual(
            MODULE.EXPECTED_TREES["default"],
            MODULE.EXPECTED_TREES["recursive"],
        )
        self.assertEqual(
            MODULE.EXPECTED_TREES["default"],
            MODULE.EXPECTED_TREES["aggressive"],
        )
        self.assertNotEqual(
            MODULE.EXPECTED_TREES["default"],
            MODULE.EXPECTED_TREES["recursive_aggressive"],
        )

    def test_expected_resource_tree_preserves_context_and_detection(self):
        child = MODULE.RESOURCE_TREE[0]["values"][1]
        self.assertEqual(child["filetype"], "Binary")
        self.assertEqual(child["parentfilepart"], "Resource")
        self.assertEqual(child["offset"], "608")
        self.assertEqual(child["size"], "20")
        self.assertEqual(
            child["values"],
            [{"name": "Manifest", "type": "format", "version": ""}],
        )

    def test_validate_case_accepts_exact_tree(self):
        stdout = (
            b'{"detects":'
            + MODULE.json.dumps(
                MODULE.RESOURCE_TREE,
                separators=(",", ":"),
            ).encode()
            + b"}"
        )
        observation = Observation(stdout=stdout)
        self.assertEqual(
            MODULE.validate_case(
                "recursive_aggressive",
                observation,
            ),
            [],
        )

    def test_validate_case_rejects_missing_child(self):
        stdout = (
            b'{"detects":'
            + MODULE.json.dumps(
                MODULE.ROOT_TREE,
                separators=(",", ":"),
            ).encode()
            + b"}"
        )
        observation = Observation(stdout=stdout)
        self.assertEqual(
            MODULE.validate_case(
                "recursive_aggressive",
                observation,
            ),
            ["recursive_aggressive.detect_tree"],
        )

    def test_validate_case_rejects_process_failures(self):
        observation = Observation(exit_code=1, stderr=b"error")
        failures = MODULE.validate_case("default", observation)
        self.assertIn("default.exit_code", failures)
        self.assertIn("default.stderr", failures)
        self.assertIn("default.detect_tree", failures)


if __name__ == "__main__":
    unittest.main()
