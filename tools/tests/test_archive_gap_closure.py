import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/archive-gap-closure.json"
)
GENERATOR_PATH = (
    ROOT / "tools/research/build_archive_gap_closure.py"
)
REPORT_SHA256 = (
    "1b727c06c87a14fcb217e0fd69b3b8f935e1f2b7930461ff2a76dc3ffa8996b5"
)


class ArchiveGapClosureReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.raw)

    def test_report_and_generator_identity_are_fixed(self):
        self.assertEqual(
            hashlib.sha256(self.raw).hexdigest(),
            REPORT_SHA256,
        )
        generator = self.report["generator"]
        generator_raw = GENERATOR_PATH.read_bytes()
        self.assertEqual(
            generator,
            {
                "path": "tools/research/build_archive_gap_closure.py",
                "bytes": len(generator_raw),
                "sha256": hashlib.sha256(generator_raw).hexdigest(),
            },
        )
        self.assertEqual(
            self.report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )

    def test_engine_family_inventory_is_closed_and_runtime_bound(self):
        inventory = self.report["engine_extraction_families"]
        self.assertEqual(
            inventory["ordered_filetypes"],
            ["ZIP", "7Z", "RAR", "CAB", "ISO9660"],
        )
        self.assertEqual(inventory["count"], 5)
        self.assertEqual(
            inventory["adapters"],
            {
                "ZIP": "XZip",
                "7Z": "XSevenZip",
                "RAR": "XRar",
                "CAB": "XCab",
                "ISO9660": "XISO9660",
            },
        )
        self.assertEqual(
            [item["family"] for item in inventory["runtime_evidence"]],
            inventory["ordered_filetypes"],
        )
        for item in inventory["runtime_evidence"]:
            self.assertEqual(item["default_stream_count"], 0)
            self.assertEqual(item["archive_stream_count"], 1)
            self.assertEqual(item["archive_stream_filetypes"], ["PDF"])

    def test_count_depth_and_total_boundaries_are_precise(self):
        self.assertEqual(
            self.report["iteration_boundary"],
            {
                "aggressive_scanable_member_limit": (
                    "unreachable before hard iteration guard"
                ),
                "hard_iteration_guard": 100000,
                "record_100000_reachable": True,
                "record_100001_reachable": False,
                "record_99999_reachable": True,
            },
        )
        limits = self.report["depth_and_total_observation"]
        self.assertEqual(limits["maximum_observed_depth"], 64)
        self.assertEqual(
            limits["maximum_observed_cumulative_expanded_bytes"],
            33554546,
        )
        self.assertTrue(
            limits["source_has_no_independent_depth_or_total_token"]
        )
        self.assertTrue(limits["cancellation_retains_partial_result"])

    def test_all_four_capabilities_receive_observed_dispositions(self):
        self.assertEqual(self.report["result"], "closed")
        dispositions = self.report["capability_dispositions"]
        self.assertEqual(
            [item["id"] for item in dispositions],
            [
                "CAP-DISPATCH-004",
                "CAP-NEST-003",
                "CAP-NEST-004",
                "CAP-NEST-009",
            ],
        )
        self.assertEqual(
            {item["verification"] for item in dispositions},
            {"observed"},
        )
        self.assertTrue(
            all(self.report["closure_assertions"].values())
        )
        self.assertEqual(
            self.report["gap"]["disposition"].startswith(
                "closed by exhaustive"
            ),
            True,
        )

    def test_remaining_risks_do_not_overstate_the_observations(self):
        risks = "\n".join(self.report["remaining_risks"])
        self.assertIn("lacks an independent depth", risks)
        self.assertIn("maximum observations", risks)
        self.assertIn("RAR15/RAR20/RAR7-v1", risks)
        self.assertIn("Windows, macOS", risks)


if __name__ == "__main__":
    unittest.main()
