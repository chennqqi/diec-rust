import pathlib
import tomllib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
EXPECTED_CHANNEL = "1.97.1"
EXPECTED_MSRV = "1.88"


class RustToolchainPolicyTests(unittest.TestCase):
    def test_repository_toolchain_is_exact_and_minimal(self):
        toolchain = tomllib.loads(
            (ROOT / "rust-toolchain.toml").read_text(encoding="utf-8")
        )["toolchain"]

        self.assertEqual(toolchain["channel"], EXPECTED_CHANNEL)
        self.assertEqual(toolchain["profile"], "minimal")
        self.assertEqual(
            set(toolchain["components"]),
            {"clippy", "rustfmt"},
        )

    def test_every_spike_declares_the_repository_msrv(self):
        manifests = sorted((ROOT / "spikes").glob("*/Cargo.toml"))
        self.assertTrue(manifests)

        for manifest in manifests:
            with self.subTest(manifest=manifest.relative_to(ROOT)):
                package = tomllib.loads(
                    manifest.read_text(encoding="utf-8")
                )["package"]
                self.assertEqual(
                    package.get("rust-version"),
                    EXPECTED_MSRV,
                )

    def test_default_toolchain_and_msrv_are_independent(self):
        self.assertNotEqual(
            EXPECTED_CHANNEL.removesuffix(".0"),
            EXPECTED_MSRV,
        )


if __name__ == "__main__":
    unittest.main()
