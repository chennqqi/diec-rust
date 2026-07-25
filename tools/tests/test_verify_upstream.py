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


class ParseGitMetadataTests(unittest.TestCase):
    def test_parses_direct_gitlinks(self) -> None:
        output = (
            "100644 blob " + "a" * 40 + "\tREADME.md\n"
            "160000 commit " + "b" * 40 + "\tchild\n"
        )
        self.assertEqual(
            VERIFY_UPSTREAM.parse_gitlink_tree(output),
            {"child": "b" * 40},
        )

    def test_parses_gitmodule_paths_and_repositories(self) -> None:
        output = (
            '[submodule "child"]\n'
            "\tpath = child\n"
            "\turl = https://example.invalid/child.git\n"
        )
        self.assertEqual(
            VERIFY_UPSTREAM.parse_gitmodules(output),
            {"child": "https://example.invalid/child.git"},
        )


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
            "gitlink": {
                "child": {
                    "repository": "https://example.invalid/child.git",
                    "commit": "b" * 40,
                }
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

    def test_rejects_missing_gitlink_inventory(self) -> None:
        data = self.valid_lock()
        del data["gitlink"]

        errors = VERIFY_UPSTREAM.validate_lock_data(data)

        self.assertIn("gitlink table is required", errors)
        self.assertIn(
            "component[0].gitlink_path is not present in gitlink table",
            errors,
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

    def test_rejects_component_that_differs_from_gitlink_inventory(self) -> None:
        data = self.valid_lock()
        data["gitlink"]["child"]["commit"] = "c" * 40

        errors = VERIFY_UPSTREAM.validate_lock_data(data)

        self.assertIn("component[0].commit differs from gitlink table", errors)

    def test_rejects_duplicate_component_names_and_paths(self) -> None:
        data = self.valid_lock()
        data["component"].append(dict(data["component"][0]))

        errors = VERIFY_UPSTREAM.validate_lock_data(data)

        self.assertIn("duplicate component name: child", errors)
        self.assertIn("duplicate component local_path: upstream/child", errors)


class ValidateCliDependencyTests(unittest.TestCase):
    def lock_data(self) -> dict:
        return {
            "baseline": {"commit": "a" * 40},
            "gitlink": {
                "parent": {"commit": "b" * 40},
                "child": {"commit": "c" * 40},
            },
        }

    def valid_data(self) -> dict:
        return {
            "schema": 1,
            "baseline_commit": "a" * 40,
            "component": [
                {
                    "name": "parent",
                    "commit": "b" * 40,
                    "dependencies": ["child"],
                    "license_blob": "d" * 40,
                },
                {
                    "name": "child",
                    "commit": "c" * 40,
                    "dependencies": [],
                    "license_blob": "e" * 40,
                },
            ],
            "bundled_code": [
                {
                    "name": "library",
                    "owner": "parent",
                    "evidence_blob": "f" * 40,
                }
            ],
        }

    def test_accepts_manifest_matching_component_lock(self) -> None:
        self.assertEqual(
            VERIFY_UPSTREAM.validate_cli_dependency_data(
                self.valid_data(),
                self.lock_data(),
            ),
            [],
        )

    def test_rejects_unknown_dependency_and_commit_mismatch(self) -> None:
        data = self.valid_data()
        data["component"][0]["commit"] = "0" * 40
        data["component"][0]["dependencies"] = ["missing"]

        errors = VERIFY_UPSTREAM.validate_cli_dependency_data(
            data,
            self.lock_data(),
        )

        self.assertIn("component[0].commit differs from component lock", errors)
        self.assertIn(
            "component[0].dependencies contains unknown component: missing",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
