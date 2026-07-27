import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    ROOT / "tools" / "corpus" / "generate_image_dispatch_fixture.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module(
    "generate_image_dispatch_fixture_for_test",
    GENERATOR_PATH,
)


class GenerateImageDispatchFixtureTests(unittest.TestCase):
    def test_manifest_and_files_are_exact_and_reproducible(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first_root = Path(first_directory)
                second_root = Path(second_directory)
                first = GENERATOR.generate(first_root)
                second = GENERATOR.generate(second_root)
                self.assertEqual(first, second)
                self.assertEqual(
                    (first_root / "manifest.json").read_bytes(),
                    (second_root / "manifest.json").read_bytes(),
                )
                self.assertEqual(first["capability"], "CAP-DISPATCH-007")
                self.assertEqual(first["coverage_gap"], "CAP-GAP-012")
                self.assertEqual(len(first["samples"]), 7)
                for sample in first["samples"]:
                    data = (first_root / sample["name"]).read_bytes()
                    self.assertEqual(len(data), sample["size"])
                    self.assertEqual(
                        hashlib.sha256(data).hexdigest(),
                        sample["sha256"],
                    )

    def test_samples_cover_every_non_jpeg_png_image_variant(self):
        expected = {
            "BMP",
            "GIF",
            "TIFF",
            "ICO",
            "CUR",
            "ICC",
            "WebP",
        }
        self.assertEqual(
            {item[1] for item in GENERATOR.GENERATORS},
            expected,
        )

    def test_headers_satisfy_pinned_validator_boundaries(self):
        bmp = GENERATOR.make_bmp()
        self.assertEqual(bmp[:2], b"BM")
        self.assertEqual(struct.unpack_from("<I", bmp, 2)[0], len(bmp))
        self.assertEqual(struct.unpack_from("<I", bmp, 14)[0], 40)

        gif = GENERATOR.make_gif()
        self.assertGreater(len(gif), 0x320)
        self.assertEqual(gif[:6], b"GIF89a")
        self.assertEqual(set(gif[13:0x320]), {0xFF})
        self.assertEqual(gif[0x320:], b"\0\x3b")

        tiff = GENERATOR.make_tiff()
        self.assertEqual(tiff[:4], b"II\x2a\0")
        self.assertEqual(struct.unpack_from("<I", tiff, 4)[0], 8)

        for icon_type in (1, 2):
            icon = GENERATOR.make_icon(icon_type)
            self.assertGreater(len(icon), 22)
            self.assertEqual(
                struct.unpack_from("<HHH", icon, 0),
                (0, icon_type, 1),
            )
            self.assertEqual(struct.unpack_from("<I", icon, 14)[0], 1)

        icc = GENERATOR.make_icc()
        self.assertEqual(struct.unpack_from(">I", icc, 0)[0], len(icc))
        self.assertEqual(icc[12:16], b"mntr")
        self.assertEqual(icc[36:40], b"acsp")

        webp = GENERATOR.make_webp()
        self.assertGreater(len(webp), 0x20)
        self.assertEqual(webp[:4], b"RIFF")
        self.assertEqual(webp[8:12], b"WEBP")
        self.assertEqual(struct.unpack_from("<I", webp, 4)[0], len(webp) - 8)


if __name__ == "__main__":
    unittest.main()
