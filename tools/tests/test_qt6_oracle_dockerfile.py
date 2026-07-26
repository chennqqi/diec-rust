import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "tools/upstream/Dockerfile.oracle-cmake-qt6"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
BASE_DIGEST = (
    "sha256:4fbb8e6a8395de5a7550b33509421a2b"
    "afbc0aab6c06ba2cef9ebffbc7092d90"
)


class Qt6OracleDockerfileTests(unittest.TestCase):
    def test_build_is_pinned_and_explicitly_selects_qt6(self):
        source = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn(f"FROM ubuntu@{BASE_DIGEST}", source)
        self.assertIn(f"ARG DIE_COMMIT={UPSTREAM_COMMIT}", source)
        self.assertIn("qt6-base-dev", source)
        self.assertIn("qt6-declarative-dev", source)
        self.assertIn("qt6-svg-dev", source)
        self.assertIn("-DQT_DEFAULT_MAJOR_VERSION=6", source)
        self.assertIn("--target diec", source)

    def test_image_checks_qt_runtime_and_submodule_identity(self):
        source = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("test \"$(git rev-parse HEAD)\"", source)
        self.assertIn("test \"$(git submodule status | wc -l)\" -eq 58", source)
        self.assertIn("grep -q 'libQt6Qml.so'", source)
        self.assertIn("! grep -q 'libQt5'", source)
        self.assertIn("org.opencontainers.image.revision", source)


if __name__ == "__main__":
    unittest.main()
