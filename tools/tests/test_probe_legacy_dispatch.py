import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "upstream" / "probe_legacy_dispatch.py"
GENERATOR_PATH = (
    ROOT / "tools" / "corpus" / "generate_legacy_dispatch_corpus.py"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("probe_legacy_dispatch", MODULE_PATH)
GENERATOR = load_module(
    "generate_legacy_dispatch_corpus_for_probe", GENERATOR_PATH
)


def scan_stdout(filetype):
    return json.dumps(
        {
            "detects": [
                {
                    "parentfilepart": "",
                    "filetype": filetype,
                    "offset": 0,
                    "size": 1,
                    "values": [],
                }
            ]
        },
        sort_keys=True,
    ).encode()


class ProbeLegacyDispatchTests(unittest.TestCase):
    def test_observed_filetypes_walks_nested_projection(self):
        tree = [
            {
                "filetype": "Amiga Hunk",
                "values": [
                    {"filetype": "Binary"},
                    {"values": [{"filetype": "Atari ST"}]},
                ],
            }
        ]
        self.assertEqual(
            MODULE.observed_filetypes(tree),
            {"Amiga Hunk", "Binary", "Atari ST"},
        )

    def test_expectation_reports_missing_and_borrowed_dispatch(self):
        expectation = {
            "present_filetypes": ["Amiga Hunk"],
            "absent_filetypes": ["Atari ST"],
        }
        failures = MODULE.expectation_failures(
            "case",
            [{"filetype": "Atari ST"}],
            expectation,
        )
        self.assertEqual(
            failures,
            [
                "case.missing_filetype.Amiga Hunk",
                "case.unexpected_filetype.Atari ST",
            ],
        )

    def test_fixture_requires_exact_committed_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = pathlib.Path(temporary)
            GENERATOR.generate(corpus)
            manifest, samples, raw = MODULE.load_fixture(ROOT, corpus)
            self.assertEqual(manifest["capability"], "CAP-DISPATCH-003")
            self.assertEqual(len(samples), 8)
            self.assertEqual(
                raw,
                (
                    ROOT
                    / "docs"
                    / "research"
                    / "data"
                    / "legacy-dispatch-corpus.json"
                ).read_bytes(),
            )
            (corpus / "manifest.json").write_text(
                "{}\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "differs"):
                MODULE.load_fixture(ROOT, corpus)

    def test_build_report_accepts_expected_dispatch_on_both_oracles(self):
        with tempfile.TemporaryDirectory() as corpus_temp:
            with tempfile.TemporaryDirectory() as raw_temp:
                corpus = pathlib.Path(corpus_temp)
                raw = pathlib.Path(raw_temp)
                manifest = GENERATOR.generate(corpus)
                target_by_name = {
                    sample["name"]: (
                        sample["target_filetype"]
                        if sample["case_kind"] == "positive"
                        else "Binary"
                    )
                    for sample in manifest["samples"]
                }

                def observe(_image, _binary, arguments, _corpus):
                    name = pathlib.PurePosixPath(arguments[-1]).name
                    return MODULE.SHARED.Observation(
                        0,
                        scan_stdout(target_by_name[name]),
                        b"",
                    )

                with mock.patch.object(
                    MODULE,
                    "inspect_image",
                    return_value=("sha256:image", MODULE.UPSTREAM_COMMIT),
                ):
                    with mock.patch.object(
                        MODULE.SHARED,
                        "observe",
                        side_effect=observe,
                    ):
                        report = MODULE.build_report(ROOT, corpus, raw)
                stdout_count = len(list(raw.glob("*.stdout")))
                stderr_count = len(list(raw.glob("*.stderr")))

        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["failures"], [])
        self.assertEqual(len(report["cases"]), 8)
        self.assertEqual(stdout_count, 16)
        self.assertEqual(stderr_count, 16)
        for case in report["cases"].values():
            self.assertEqual(len(case["oracles"]), 2)

    def test_build_report_fails_when_control_borrows_target_dispatch(self):
        with tempfile.TemporaryDirectory() as corpus_temp:
            with tempfile.TemporaryDirectory() as raw_temp:
                corpus = pathlib.Path(corpus_temp)
                GENERATOR.generate(corpus)

                def observe(_image, _binary, arguments, _corpus):
                    name = pathlib.PurePosixPath(arguments[-1]).name
                    filetype = (
                        "Amiga Hunk"
                        if name == "amiga-hunk-near-magic.bin"
                        else "Binary"
                    )
                    return MODULE.SHARED.Observation(
                        0, scan_stdout(filetype), b""
                    )

                with mock.patch.object(
                    MODULE,
                    "inspect_image",
                    return_value=("sha256:image", MODULE.UPSTREAM_COMMIT),
                ):
                    with mock.patch.object(
                        MODULE.SHARED,
                        "observe",
                        side_effect=observe,
                    ):
                        report = MODULE.build_report(
                            ROOT,
                            corpus,
                            pathlib.Path(raw_temp),
                        )

        self.assertEqual(report["result"], "fail")
        self.assertIn(
            (
                "cases.amiga-hunk-near-magic.bin."
                "linux-qt5-qmake.unexpected_filetype.Amiga Hunk"
            ),
            report["failures"],
        )


if __name__ == "__main__":
    unittest.main()
