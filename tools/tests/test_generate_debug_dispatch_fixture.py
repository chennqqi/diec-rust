import hashlib
import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_debug_dispatch_fixture.py"
)
MANIFEST = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "debug-dispatch-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_debug_dispatch_fixture",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenerateDebugDispatchFixtureTests(unittest.TestCase):
    def test_committed_manifest_is_exact_generator_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            generated = MODULE.generate(root)
            self.assertEqual(
                (root / "manifest.json").read_bytes(),
                MANIFEST.read_bytes(),
            )
            self.assertEqual(
                generated,
                json.loads(MANIFEST.read_text(encoding="utf-8")),
            )

    def test_sample_and_parts_match_all_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = MODULE.generate(root)
            sample = manifest["sample"]
            data = (root / sample["name"]).read_bytes()
            self.assertEqual(len(data), sample["size"])
            self.assertEqual(
                hashlib.sha256(data).hexdigest(),
                sample["sha256"],
            )
            for part_name in ("resource", "debug_data"):
                part = sample[part_name]
                payload = data[
                    part["offset"] : part["offset"] + part["size"]
                ]
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    part["sha256"],
                )

    def test_pe_declares_resource_and_debug_directories(self):
        data = MODULE.make_pe_resource_debug()
        optional = 0x98
        resource = struct.unpack_from(
            "<II",
            data,
            optional + 96 + 2 * 8,
        )
        debug = struct.unpack_from(
            "<II",
            data,
            optional + 96 + 6 * 8,
        )
        self.assertEqual(resource[0], MODULE.RESOURCE_RVA)
        self.assertGreater(resource[1], 0)
        self.assertEqual(debug, (MODULE.DEBUG_RVA, 28))
        self.assertEqual(data[0x178:0x180], b".rsrc\0\0\0")
        self.assertEqual(data[0x1A0:0x1A8], b".debug\0\0")

    def test_debug_directory_points_to_rsds_payload(self):
        data = MODULE.make_pe_resource_debug()
        record = struct.unpack_from("<IIHHIIII", data, MODULE.DEBUG_RAW)
        (
            _characteristics,
            _timestamp,
            _major,
            _minor,
            debug_type,
            size,
            address,
            offset,
        ) = record
        self.assertEqual(debug_type, 2)
        self.assertEqual(size, len(MODULE.RSDS_PAYLOAD))
        self.assertEqual(
            address,
            MODULE.DEBUG_RVA + MODULE.DEBUG_PAYLOAD_RELATIVE,
        )
        self.assertEqual(
            offset,
            MODULE.DEBUG_RAW + MODULE.DEBUG_PAYLOAD_RELATIVE,
        )
        self.assertEqual(data[offset : offset + 4], b"RSDS")

    def test_resource_tree_uses_manifest_type_id(self):
        data = MODULE.make_pe_resource_debug()
        resource_type = struct.unpack_from(
            "<I",
            data,
            MODULE.RESOURCE_RAW + 0x10,
        )[0]
        self.assertEqual(resource_type, 24)
        offset = (
            MODULE.RESOURCE_RAW + MODULE.RESOURCE_PAYLOAD_RELATIVE
        )
        self.assertEqual(
            data[offset : offset + len(MODULE.MANIFEST_PAYLOAD)],
            MODULE.MANIFEST_PAYLOAD,
        )


if __name__ == "__main__":
    unittest.main()
