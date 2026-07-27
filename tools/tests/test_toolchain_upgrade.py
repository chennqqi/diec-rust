import hashlib
import json
import pathlib
import re
import tomllib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rust-toolchain-upgrade-1.97.1.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "rust-toolchain-upgrade-1.97.1.md"
)
ADR_0007_PATH = (
    ROOT
    / "docs"
    / "design"
    / "decisions"
    / "0007-rust-toolchain-baseline.md"
)
ADR_0011_PATH = (
    ROOT
    / "docs"
    / "design"
    / "decisions"
    / "0011-rust-1.97.1-default-toolchain.md"
)


class ToolchainUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_toolchain_identity_and_msrv_are_separate(self):
        self.assertEqual(self.report["schema_version"], 1)
        default = self.report["toolchains"]["default"]
        msrv = self.report["toolchains"]["msrv"]
        self.assertEqual(default["channel"], "1.97.1")
        self.assertEqual(msrv["channel"], "1.88.0")
        self.assertEqual(msrv["package_rust_version"], "1.88")
        self.assertNotEqual(default["channel"], msrv["channel"])

        toolchain = tomllib.loads(
            (ROOT / "rust-toolchain.toml").read_text(encoding="utf-8")
        )["toolchain"]
        self.assertEqual(toolchain["channel"], default["channel"])
        self.assertEqual(toolchain["profile"], "minimal")
        self.assertEqual(set(toolchain["components"]), {"clippy", "rustfmt"})

    def test_input_hashes_match_current_files(self):
        for relative, expected_hash in self.report["input_hashes"].items():
            with self.subTest(path=relative):
                path = ROOT / relative
                self.assertTrue(path.is_file())
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected_hash,
                )

    def test_all_spikes_pass_default_gates_and_keep_msrv(self):
        gates = {
            gate["spike"]: gate for gate in self.report["rust_gates"]
        }
        self.assertEqual(
            set(gates),
            {
                "boa-rule-runtime",
                "c-static-link",
                "rquickjs-rule-runtime",
                "rquickjs-static-link",
                "signature-parser",
            },
        )
        expected_test_counts = {
            "boa-rule-runtime": 2,
            "c-static-link": 3,
            "rquickjs-rule-runtime": 32,
            "rquickjs-static-link": 2,
            "signature-parser": 15,
        }
        for name, gate in gates.items():
            with self.subTest(spike=name):
                result = gate["default"]
                self.assertEqual(result["fmt"], "pass")
                self.assertEqual(result["clippy"], "pass")
                self.assertEqual(
                    result["unit_tests"],
                    expected_test_counts[name],
                )
                self.assertEqual(result["doc_tests"], 0)
                manifest = tomllib.loads(
                    (ROOT / gate["manifest"]).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    manifest["package"]["rust-version"],
                    "1.88",
                )

        msrv = gates["signature-parser"]["msrv"]
        self.assertEqual(
            msrv,
            {
                "fmt": "pass",
                "clippy": "pass",
                "unit_tests": 15,
                "doc_tests": 0,
            },
        )
        self.assertEqual(
            gates["rquickjs-rule-runtime"]["msrv"],
            {
                "fmt": "pass",
                "clippy": "pass",
                "unit_tests": 32,
                "doc_tests": 0,
            },
        )

    def test_clippy_remediation_is_exact_and_msrv_preserving(self):
        remediation = self.report["clippy_remediation"]
        self.assertEqual(remediation["diagnostic_count"], 5)
        self.assertEqual(
            remediation["diagnostics"],
            {
                "collapsible_if": 3,
                "manual_saturating_arithmetic": 1,
                "manual_is_multiple_of": 1,
            },
        )
        self.assertFalse(remediation["public_api_changed"])
        self.assertFalse(remediation["msrv_raised"])

    def test_six_native_consumers_pass_with_fixed_dependencies(self):
        linux = self.report["linux_gnu"]
        windows = self.report["windows_msvc"]
        self.assertEqual(
            linux["container_digest"],
            (
                "sha256:"
                "99e09cb2284e2ddbb73a995deee3e91783fd04d177602"
                "ccf6eab326d778ee777"
            ),
        )
        self.assertEqual(linux["network"], "none")
        self.assertEqual(linux["source_mount"], "read-only")
        self.assertEqual(linux["registry_cache_mount"], "read-only")
        self.assertEqual(linux["cargo_mode"], "offline")
        self.assertEqual(
            linux["native_static_libs"],
            [
                "-lgcc_s",
                "-lutil",
                "-lrt",
                "-lpthread",
                "-lm",
                "-ldl",
                "-lc",
            ],
        )

        consumers = [
            *linux["consumers"],
            *windows["consumers"],
        ]
        self.assertEqual(len(consumers), 6)
        self.assertEqual(
            {(item["spike"], item.get("crt")) for item in consumers},
            {
                ("c-static-link", None),
                ("rquickjs-static-link", None),
                ("c-static-link", "dynamic"),
                ("c-static-link", "static"),
                ("rquickjs-static-link", "dynamic"),
                ("rquickjs-static-link", "static"),
            },
        )
        for consumer in consumers:
            with self.subTest(
                spike=consumer["spike"],
                crt=consumer.get("crt"),
            ):
                self.assertEqual(consumer["smoke_exit_code"], 0)
                self.assertTrue(consumer["panic_contained"])
                self.assertTrue(consumer["panic_hook_stderr_observed"])
                archive_bytes = consumer.get(
                    "archive_bytes",
                    consumer.get("staticlib_bytes"),
                )
                archive_hash = consumer.get(
                    "archive_sha256",
                    consumer.get("staticlib_sha256"),
                )
                self.assertGreater(archive_bytes, 0)
                self.assertGreater(consumer["executable_bytes"], 0)
                self.assertRegex(archive_hash, r"^[0-9a-f]{64}$")
                self.assertRegex(
                    consumer["executable_sha256"],
                    r"^[0-9a-f]{64}$",
                )
                self.assertFalse(
                    any(
                        "quickjs" in dependency.lower()
                        for dependency in consumer["dynamic_dependencies"]
                    )
                )

        linux_dependencies = {
            item["spike"]: set(item["dynamic_dependencies"])
            for item in linux["consumers"]
        }
        self.assertEqual(
            linux_dependencies["c-static-link"],
            {
                "libgcc_s.so.1",
                "libc.so.6",
                "ld-linux-x86-64.so.2",
            },
        )
        self.assertEqual(
            linux_dependencies["rquickjs-static-link"],
            {
                "libgcc_s.so.1",
                "libm.so.6",
                "libc.so.6",
                "ld-linux-x86-64.so.2",
            },
        )
        static_windows = [
            item for item in windows["consumers"] if item["crt"] == "static"
        ]
        for item in static_windows:
            self.assertNotIn(
                "VCRUNTIME140.dll",
                item["dynamic_dependencies"],
            )
            self.assertEqual(item["defaultlib"], "/defaultlib:libcmt")

    def test_security_sources_and_documentation_are_connected(self):
        expected_urls = {
            "https://blog.rust-lang.org/2026/03/21/cve-2026-33056/",
            "https://blog.rust-lang.org/2026/05/25/cve-2026-5222/",
            "https://blog.rust-lang.org/2026/05/25/cve-2026-5223/",
            "https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/",
        }
        self.assertEqual(
            {
                advisory["url"]
                for advisory in self.report["security_advisories"]
            },
            expected_urls,
        )

        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        adr_0007 = ADR_0007_PATH.read_text(encoding="utf-8")
        adr_0011 = ADR_0011_PATH.read_text(encoding="utf-8")
        research_index = (
            ROOT / "docs" / "research" / "README.md"
        ).read_text(encoding="utf-8")
        testing = (ROOT / "docs" / "design" / "testing.md").read_text(
            encoding="utf-8"
        )
        risks = (ROOT / "docs" / "design" / "risks.md").read_text(
            encoding="utf-8"
        )

        self.assertRegex(adr_0007, r"(?m)^Status: Superseded$")
        self.assertRegex(adr_0011, r"(?m)^Status: Proposed$")
        self.assertIn(REPORT_PATH.name, adr_0011)
        self.assertIn(DOCUMENT_PATH.name, adr_0011)
        self.assertIn(REPORT_PATH.name, document)
        self.assertIn(REPORT_PATH.name, research_index)
        self.assertIn(DOCUMENT_PATH.name, research_index)
        self.assertIn(REPORT_PATH.name, risks)
        self.assertIn("fixed default + MSRV", testing)
        self.assertNotRegex(
            testing,
            re.compile(r"\| (?:Linux|Windows|macOS) .*\| stable"),
        )
        for url in expected_urls:
            self.assertIn(url, document)
            self.assertIn(url, adr_0011)

    def test_relationships_are_all_explicitly_true(self):
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertGreaterEqual(len(self.report["limitations"]), 6)


if __name__ == "__main__":
    unittest.main()
