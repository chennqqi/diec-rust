from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_upstream.py"
SPEC = importlib.util.spec_from_file_location("verify_upstream", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
VERIFY_UPSTREAM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY_UPSTREAM
SPEC.loader.exec_module(VERIFY_UPSTREAM)


class ParseSubtreeRecordsTests(unittest.TestCase):
    def test_parses_complete_records(self) -> None:
        output = (
            "a" * 40
            + "\x00Squashed content\n"
            + "git-subtree-dir: upstream/example\n"
            + "git-subtree-split: "
            + "b" * 40
            + "\n\x1e"
        )

        records = VERIFY_UPSTREAM.parse_subtree_records(output)

        self.assertEqual(
            records,
            [
                VERIFY_UPSTREAM.SubtreeRecord(
                    commit="a" * 40,
                    directory="upstream/example",
                    split="b" * 40,
                )
            ],
        )

    def test_ignores_incomplete_records(self) -> None:
        output = "a" * 40 + "\x00git-subtree-dir: upstream/example\n\x1e"
        self.assertEqual(VERIFY_UPSTREAM.parse_subtree_records(output), [])


class ValidateLockTests(unittest.TestCase):
    def valid_lock(self) -> dict:
        return {
            "schema": 1,
            "baseline": {
                "name": "parent",
                "repository": "https://example.invalid/parent.git",
                "commit": "a" * 40,
                "local_path": "upstream/parent",
                "materialization": "subtree-squash",
            },
            "component": [
                {
                    "name": "child",
                    "repository": "https://example.invalid/child.git",
                    "commit": "b" * 40,
                    "gitlink_path": "child",
                    "local_path": "upstream/child",
                    "materialization": "subtree-squash",
                }
            ],
        }

    def test_accepts_valid_lock(self) -> None:
        self.assertEqual(
            VERIFY_UPSTREAM.validate_lock_data(self.valid_lock()),
            [],
        )

    def test_rejects_invalid_sha_and_missing_subtree_path(self) -> None:
        data = self.valid_lock()
        data["component"][0]["commit"] = "not-a-sha"
        del data["component"][0]["local_path"]

        errors = VERIFY_UPSTREAM.validate_lock_data(data)

        self.assertIn(
            "component[0].commit must be a lowercase 40-character SHA-1",
            errors,
        )
        self.assertIn(
            "component[0].local_path is required for subtree-squash",
            errors,
        )

    def test_rejects_duplicate_component_names_and_paths(self) -> None:
        data = self.valid_lock()
        data["component"].append(dict(data["component"][0]))

        errors = VERIFY_UPSTREAM.validate_lock_data(data)

        self.assertIn("duplicate component name: child", errors)
        self.assertIn("duplicate component local_path: upstream/child", errors)


if __name__ == "__main__":
    unittest.main()
