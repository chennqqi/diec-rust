import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools/upstream/probe_rar_compressed_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_rar_compressed_harness", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def document(children=()):
    values = [
        {
            "info": "",
            "name": "Unknown",
            "string": "Unknown: Unknown",
            "type": "Unknown",
            "version": "",
        }
    ]
    values.extend(
        {
            "filetype": filetype,
            "offset": "0",
            "parentfilepart": "Stream",
            "size": str(size),
            "values": [],
        }
        for filetype, size in children
    )
    return {
        "detects": [
            {
                "filetype": "RAR",
                "offset": "0",
                "parentfilepart": "Header",
                "size": "410",
                "values": values,
            }
        ]
    }


class ProbeRarCompressedHarnessUnitTests(unittest.TestCase):
    def test_projection_preserves_child_order_and_size(self):
        self.assertEqual(
            MODULE.result_projection(
                document((("JPEG", 220), ("PNG", 87)))
            ),
            {
                "root_filetype": "RAR",
                "root_size": 410,
                "children": [
                    {"filetype": "JPEG", "size": 220},
                    {"filetype": "PNG", "size": 87},
                ],
            },
        )

    def test_projection_rejects_non_rar_root(self):
        value = document()
        value["detects"][0]["filetype"] = "ZIP"
        with self.assertRaisesRegex(
            MODULE.RarProbeError, "not RAR"
        ):
            MODULE.result_projection(value)

    def test_projection_rejects_non_stream_child(self):
        value = document((("PNG", 87),))
        value["detects"][0]["values"][1]["parentfilepart"] = "Overlay"
        with self.assertRaisesRegex(
            MODULE.RarProbeError, "not a stream"
        ):
            MODULE.result_projection(value)

    def test_expected_matrix_covers_four_unique_fixtures(self):
        self.assertEqual(len(MODULE.EXPECTED_CASES), 4)
        self.assertEqual(
            len(
                {
                    case["fixture"]
                    for case in MODULE.EXPECTED_CASES.values()
                }
            ),
            4,
        )
        self.assertEqual(
            sum(
                len(case["aggressive_children"])
                for case in MODULE.EXPECTED_CASES.values()
            ),
            7,
        )


if __name__ == "__main__":
    unittest.main()
