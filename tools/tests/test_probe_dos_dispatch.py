import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "upstream" / "probe_dos_dispatch.py"
GENERATOR_PATH = (
    ROOT / "tools" / "corpus" / "generate_dos_dispatch_corpus.py"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("probe_dos_dispatch", MODULE_PATH)
GENERATOR = load_module(
    "generate_dos_dispatch_corpus_for_probe", GENERATOR_PATH
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


class ProbeDosDispatchTests(unittest.TestCase):
    def test_fixture_requires_exact_public_set_and_committed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = pathlib.Path(temporary)
            GENERATOR.generate(corpus)
            manifest, samples, raw = MODULE.load_fixture(ROOT, corpus)
            self.assertEqual(
                set(manifest["public_filetypes"]),
                MODULE.EXPECTED_FILETYPES,
            )
            self.assertEqual(len(samples), 19)
            self.assertEqual(
                raw,
                (
                    ROOT
                    / "docs"
                    / "research"
                    / "data"
                    / "dos-dispatch-corpus.json"
                ).read_bytes(),
            )

    def test_build_report_runs_all_cases_on_both_oracles(self):
        with tempfile.TemporaryDirectory() as corpus_temp:
            with tempfile.TemporaryDirectory() as raw_temp:
                corpus = pathlib.Path(corpus_temp)
                raw = pathlib.Path(raw_temp)
                manifest = GENERATOR.generate(corpus)
                expected_by_name = {
                    sample["name"]: (
                        sample["expected_dispatch"]["present_filetypes"][0]
                        if sample["expected_dispatch"]["present_filetypes"]
                        else "Binary"
                    )
                    for sample in manifest["samples"]
                }

                def observe(_image, _binary, arguments, _corpus):
                    name = pathlib.PurePosixPath(arguments[-1]).name
                    return MODULE.SHARED.SHARED.Observation(
                        0,
                        scan_stdout(expected_by_name[name]),
                        b"",
                    )

                with mock.patch.object(
                    MODULE.SHARED,
                    "inspect_image",
                    return_value=("sha256:image", MODULE.UPSTREAM_COMMIT),
                ):
                    with mock.patch.object(
                        MODULE.SHARED.SHARED,
                        "observe",
                        side_effect=observe,
                    ):
                        report = MODULE.build_report(ROOT, corpus, raw)
                stdout_count = len(list(raw.glob("*.stdout")))
                stderr_count = len(list(raw.glob("*.stderr")))

        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["failures"], [])
        self.assertEqual(len(report["cases"]), 19)
        self.assertEqual(stdout_count, 38)
        self.assertEqual(stderr_count, 38)
        self.assertEqual(
            set(report["scope"]["public_filetypes"]),
            MODULE.EXPECTED_FILETYPES,
        )
        self.assertEqual(
            report["scope"]["excluded_member"], "BW DOS16M"
        )

    def test_build_report_rejects_adjacent_dos4g_dispatch(self):
        with tempfile.TemporaryDirectory() as corpus_temp:
            with tempfile.TemporaryDirectory() as raw_temp:
                corpus = pathlib.Path(corpus_temp)
                GENERATOR.generate(corpus)

                def observe(_image, _binary, arguments, _corpus):
                    name = pathlib.PurePosixPath(arguments[-1]).name
                    filetype = (
                        "DOS4G"
                        if name == "dos4g-near-nested-magic.exe"
                        else "Binary"
                    )
                    return MODULE.SHARED.SHARED.Observation(
                        0, scan_stdout(filetype), b""
                    )

                with mock.patch.object(
                    MODULE.SHARED,
                    "inspect_image",
                    return_value=("sha256:image", MODULE.UPSTREAM_COMMIT),
                ):
                    with mock.patch.object(
                        MODULE.SHARED.SHARED,
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
                "cases.dos4g-near-nested-magic.exe."
                "linux-qt5-qmake.unexpected_filetype.DOS4G"
            ),
            report["failures"],
        )


if __name__ == "__main__":
    unittest.main()
