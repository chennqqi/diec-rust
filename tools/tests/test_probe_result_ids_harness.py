import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_result_ids_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_result_ids_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


ROOT_UUID = "11111111-1111-4111-8111-111111111111"
CHILD_UUID = "22222222-2222-4222-8222-222222222222"


def scan_id(
    *,
    uuid,
    filetype,
    filetype_string,
    filepart,
    filepart_string,
    size,
    offset,
):
    return {
        "uuid": uuid,
        "filetype": filetype,
        "filetype_string": filetype_string,
        "filepart": filepart,
        "filepart_string": filepart_string,
        "version": "",
        "info": "",
        "size": size,
        "offset": offset,
        "original_name": "",
    }


def valid_document():
    root_id = scan_id(
        uuid=ROOT_UUID,
        filetype=16,
        filetype_string="PE32",
        filepart=16,
        filepart_string="Header",
        size=MODULE.SAMPLE_SIZE,
        offset=0,
    )
    root_parent = scan_id(
        uuid="",
        filetype=0,
        filetype_string="Unknown",
        filepart=16,
        filepart_string="Header",
        size=0,
        offset=0,
    )
    child_id = scan_id(
        uuid=CHILD_UUID,
        filetype=4,
        filetype_string="Binary",
        filepart=64,
        filepart_string="Resource",
        size=MODULE.RESOURCE_SIZE,
        offset=MODULE.RESOURCE_OFFSET,
    )
    child_parent = scan_id(
        uuid=ROOT_UUID,
        filetype=16,
        filetype_string="PE32",
        filepart=64,
        filepart_string="Resource",
        size=MODULE.RESOURCE_SIZE,
        offset=MODULE.RESOURCE_OFFSET,
    )
    records = [
        {
            "type": "Unknown",
            "name": "Unknown",
            "unknown": True,
            "id": root_id,
            "parent_id": root_parent,
        },
        {
            "type": "Unknown",
            "name": "Unknown",
            "unknown": True,
            "id": child_id,
            "parent_id": child_parent,
        },
    ]
    return {
        "schema_version": 1,
        "upstream_commit": MODULE.UPSTREAM_COMMIT,
        "formats_commit": MODULE.FORMATS_COMMIT,
        "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
        "die_script_commit": MODULE.DIE_SCRIPT_COMMIT,
        "sample_name": MODULE.SAMPLE_NAME,
        "sample_size": MODULE.SAMPLE_SIZE,
        "sample_sha256": MODULE.SAMPLE_SHA256,
        "record_count": len(records),
        "error_count": 0,
        "scan_not_canceled": True,
        "records": records,
    }


class ProbeResultIdsHarnessTests(unittest.TestCase):
    def test_validates_uuid_anchor_and_edge_metadata(self):
        relationships = MODULE.validate(valid_document())
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 8)

    def test_rejects_child_parent_with_different_root_uuid(self):
        document = valid_document()
        document["records"][1]["parent_id"]["uuid"] = CHILD_UUID
        with self.assertRaisesRegex(ValueError, "parent_uuid"):
            MODULE.validate(document)

    def test_rejects_parent_collapsed_to_root_id(self):
        document = valid_document()
        document["records"][1]["parent_id"] = dict(
            document["records"][0]["id"]
        )
        with self.assertRaisesRegex(ValueError, "edge_metadata"):
            MODULE.validate(document)

    def test_rejects_uuid_reuse_for_child_id(self):
        document = valid_document()
        document["records"][1]["id"]["uuid"] = ROOT_UUID
        with self.assertRaisesRegex(ValueError, "nonempty_and_distinct"):
            MODULE.validate(document)

    def test_rejects_missing_scanid_field(self):
        document = valid_document()
        del document["records"][1]["id"]["original_name"]
        with self.assertRaisesRegex(ValueError, "full_id_shape"):
            MODULE.validate(document)

    def test_cpp_harness_serializes_both_complete_ids(self):
        source = (
            ROOT
            / "tools"
            / "upstream"
            / "result_ids_harness_main.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('item.insert("id", serializeId(record.id))', source)
        self.assertIn(
            'item.insert("parent_id", serializeId(record.parentId))',
            source,
        )
        for field in (
            "sUuid",
            "fileType",
            "filePart",
            "sVersion",
            "sInfo",
            "nSize",
            "nOffset",
            "sOriginalName",
        ):
            self.assertIn(f"id.{field}", source)


if __name__ == "__main__":
    unittest.main()
