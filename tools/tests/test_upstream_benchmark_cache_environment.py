import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OBSERVER_PATH = (
    ROOT / "tools/benchmark/observe_linux_cache_environment.py"
)
PROBE_PATH = (
    ROOT
    / "tools/benchmark/"
    "probe_upstream_benchmark_cache_environment.py"
)
REPORT_PATH = (
    ROOT
    / "docs/research/data/"
    "upstream-benchmark-linux-qt5-cache-environment.json"
)
DOCUMENT_PATH = (
    ROOT
    / "docs/research/"
    "upstream-benchmark-cache-environment.md"
)
ADR_PATH = (
    ROOT
    / "docs/design/decisions/"
    "0015-benchmark-cache-state-model.md"
)
RUNNER_PATH = (
    ROOT / "tools/benchmark/run_process_benchmark.py"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OBSERVER = load_module(
    "observe_linux_cache_environment_test",
    OBSERVER_PATH,
)
PROBE = load_module(
    "probe_upstream_benchmark_cache_environment_test",
    PROBE_PATH,
)


class UpstreamBenchmarkCacheEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_raw)

    def test_report_binds_image_page_cache_and_generators(self):
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["upstream_commit"],
            PROBE.EXPECTED_REVISION,
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["observer"]["sha256"],
            hashlib.sha256(OBSERVER_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["observer"]["repetitions"], 2)
        self.assertEqual(
            report["environment"]["image_identity"]["id"],
            PROBE.EXPECTED_IMAGE_ID,
        )
        self.assertEqual(
            report["page_cache_evidence"]["sha256"],
            PROBE.EXPECTED_PAGE_CACHE_SHA256,
        )
        self.assertEqual(
            report["environment"]["cgroup"]["cpuset_effective"],
            "0",
        )

    def test_observation_is_exact_and_read_only(self):
        observation = self.report["observation"]
        self.assertEqual(
            observation["kernel"],
            {
                "machine": "x86_64",
                "release": "6.6.87.2-microsoft-standard-WSL2",
                "system": "Linux",
                "version": (
                    "#1 SMP PREEMPT_DYNAMIC Thu Jun  5 "
                    "18:30:46 UTC 2025"
                ),
            },
        )
        process = observation["process"]
        self.assertEqual(
            process["effective_capabilities_hex"],
            "00000000a80425fb",
        )
        self.assertFalse(process["cap_sys_admin_effective"])
        self.assertFalse(process["page_cache_namespace_exposed"])
        self.assertTrue(process["initial_user_namespace_uid_map"])
        self.assertEqual(process["seccomp_mode"], 2)
        mounts = observation["mounts"]
        self.assertEqual(mounts["/"]["filesystem_type"], "overlay")
        self.assertIn("rw", mounts["/"]["mount_options"])
        self.assertEqual(
            mounts["/proc/sys"]["filesystem_type"],
            "proc",
        )
        self.assertIn("ro", mounts["/proc/sys"]["mount_options"])
        drop = observation["vm"]["drop_caches"]
        self.assertEqual(drop["permission_bits_octal"], "0200")
        self.assertEqual(drop["open_write_errno"], 30)
        self.assertEqual(drop["open_write_error"], "EROFS")
        self.assertFalse(drop["open_write_without_write_succeeded"])
        self.assertFalse(drop["write_attempted"])
        self.assertFalse(drop["sync_executed"])
        self.assertFalse(drop["drop_caches_executed"])
        self.assertEqual(
            observation["scope"],
            {
                "cache_state_changed": False,
                "read_only_observation": True,
            },
        )

    def test_relationships_and_scope_reject_global_cold_claim(self):
        self.assertTrue(all(self.report["relationships"].values()))
        scope = self.report["scope"]
        self.assertTrue(scope["read_only_probe"])
        for field in (
            "host_global_drop_caches_executed",
            "privileged_container_started",
            "cap_sys_admin_added",
            "container_page_cache_isolation_proven",
            "directory_dentry_inode_eviction_proven",
            "system_cold_cache_controlled",
        ):
            self.assertFalse(scope[field])
        self.assertEqual(
            set(self.report["decision_inputs"]),
            {
                "warm",
                "file_content_nonresident_metadata_warm",
                "system_cold",
                "generic_cold",
            },
        )

    def test_official_contract_sources_are_exact(self):
        sources = self.report["kernel_contract_sources"]
        self.assertEqual(len(sources), 4)
        urls = {source["url"] for source in sources}
        self.assertEqual(
            urls,
            {
                (
                    "https://docs.kernel.org/6.6/"
                    "admin-guide/sysctl/vm.html#drop-caches"
                ),
                (
                    "https://man7.org/linux/man-pages/man2/"
                    "posix_fadvise.2.html"
                ),
                (
                    "https://man7.org/linux/man-pages/man7/"
                    "namespaces.7.html"
                ),
                (
                    "https://docs.docker.com/engine/storage/"
                    "drivers/overlayfs-driver/#page-caching"
                ),
            },
        )
        self.assertTrue(all(source["claim"] for source in sources))

    def test_observer_parsers_normalize_volatile_mount_paths(self):
        raw = (
            "1 0 0:1 / / rw,relatime - overlay overlay "
            "rw,lowerdir=/volatile,upperdir=/u,workdir=/w\n"
            "2 1 0:2 / /proc/sys ro,nodev - proc proc rw\n"
            "3 1 0:3 / /sys/fs/cgroup ro,nodev - cgroup2 cgroup rw\n"
        )
        mounts = OBSERVER.parse_mountinfo(raw)
        self.assertEqual(
            mounts["/"]["super_options"],
            ["rw"],
        )
        self.assertEqual(
            mounts["/"]["volatile_super_option_presence"],
            {
                "lowerdir": True,
                "upperdir": True,
                "workdir": True,
            },
        )
        self.assertNotIn("/volatile", json.dumps(mounts))
        with self.assertRaisesRegex(
            OBSERVER.ObservationError,
            "required mountinfo entries",
        ):
            OBSERVER.parse_mountinfo(raw.splitlines()[0] + "\n")
        self.assertEqual(
            OBSERVER.parse_status(
                "CapEff:\t1\nNoNewPrivs:\t0\nSeccomp:\t2\n"
            ),
            {"CapEff": "1", "NoNewPrivs": "0", "Seccomp": "2"},
        )

    def test_adr_taxonomy_and_runner_fail_closed_are_aligned(self):
        adr = ADR_PATH.read_text(encoding="utf-8")
        for value in (
            "`warm`",
            "`file-content-nonresident-metadata-warm`",
            "`system-cold`",
            "通用字符串 `cold` 永久禁止",
            "不得自动启动 privileged container",
        ):
            self.assertIn(value, adr)
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'if cache_state != "warm":',
            runner,
        )
        self.assertIn(
            "only explicit warm cache_state is supported",
            runner,
        )

    def test_document_and_report_are_hash_bound_and_portable(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for text in (
            "00000000a80425fb",
            "`CAP_SYS_ADMIN`",
            "`EROFS`",
            "`file-content-nonresident-metadata-warm`",
            "privileged container",
        ):
            self.assertIn(text, document)
        self.assertIn(
            hashlib.sha256(self.report_raw).hexdigest(),
            document,
        )
        for local in (
            b"I:\\\\",
            b"C:\\\\",
            b"Users\\\\worker",
            b"github.com\\\\chennqqi",
            b"lowerdir=/",
            b"upperdir=/",
            b"workdir=/",
        ):
            self.assertNotIn(local, self.report_raw)


if __name__ == "__main__":
    unittest.main()
