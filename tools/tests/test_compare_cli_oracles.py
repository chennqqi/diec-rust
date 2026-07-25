import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "upstream"
    / "compare_cli_oracles.py"
)
SPEC = importlib.util.spec_from_file_location("compare_cli_oracles", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CompareObservationsTests(unittest.TestCase):
    def test_accepts_identical_observations(self):
        observation = MODULE.Observation(0, b"same\n", b"")

        self.assertEqual(
            MODULE.compare_observations(observation, observation),
            [],
        )

    def test_reports_each_observable_difference(self):
        left = MODULE.Observation(0, b"left", b"left error")
        right = MODULE.Observation(1, b"right", b"right error")

        self.assertEqual(
            MODULE.compare_observations(left, right),
            ["exit_code", "stdout", "stderr"],
        )

    def test_summary_hashes_raw_bytes(self):
        observation = MODULE.Observation(1, b"output\r\n", b"error\n")

        self.assertEqual(
            observation.summary(),
            {
                "exit_code": 1,
                "stdout_sha256": (
                    "50be220f44c8a03a97b92b50debecbbdb2876205aa5d0e"
                    "ec4b69c93a17c64b48"
                ),
                "stderr_sha256": (
                    "f097b5f4f46cda2da21b954c9ff4097e1e14ae7064ecde"
                    "e2c2cec2d3c1f08e6b"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
