import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/upstream/build_windows_database_cache_harness.ps1"
)
ADAPTER = (
    ROOT / "tools/upstream/database_cache_harness_windows_adapter.cpp"
)
SHARED_HARNESS = (
    ROOT / "tools/upstream/database_cache_harness_main.cpp"
)
COMPAT = (
    ROOT
    / "tools/upstream/windows_database_cache_compat/unistd.h"
)


class BuildWindowsDatabaseCacheHarnessTests(unittest.TestCase):
    def test_adapter_reuses_shared_harness(self):
        adapter = ADAPTER.read_text(encoding="utf-8")
        self.assertIn('#include "database_cache_harness_main.cpp"', adapter)
        self.assertIn("QStandardPaths::setTestModeEnabled(true)", adapter)
        self.assertIn(
            "diecSharedDatabaseCacheHarnessMain(argc, argv)",
            adapter,
        )

    def test_compat_layer_uses_real_windows_acl_and_file_time_apis(self):
        compat = COMPAT.read_text(encoding="utf-8")
        for token in (
            "SetEntriesInAclW",
            "SetNamedSecurityInfoW",
            "GetNamedSecurityInfoW",
            "QFileDevice::FileModificationTime",
            "FILE_LIST_DIRECTORY",
            "FILE_ADD_FILE",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compat)
        self.assertNotIn("QFile::setPermissions", compat)

    def test_builder_replaces_only_the_console_main_object(self):
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"release\\main_console.obj"', builder)
        self.assertIn(
            '"release\\database_cache_harness_windows_adapter.obj"',
            builder,
        )
        self.assertIn("original_main_object_sha256", builder)
        self.assertIn("original_makefile_sha256", builder)
        self.assertNotIn("git checkout", builder)

    def test_shared_case_inventory_is_not_copied(self):
        shared = SHARED_HARNESS.read_text(encoding="utf-8")
        adapter = ADAPTER.read_text(encoding="utf-8")
        self.assertEqual(shared.count("cases.append(observeLoad("), 14)
        self.assertIn("for (int index = 0; index < 5; ++index)", shared)
        self.assertEqual(
            shared.count("observeConcurrentWriters("),
            2,
        )
        self.assertNotIn("initial_miss", adapter)

    def test_all_inputs_have_stable_hashes(self):
        for path in (BUILDER, ADAPTER, SHARED_HARNESS, COMPAT):
            with self.subTest(path=path.name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
