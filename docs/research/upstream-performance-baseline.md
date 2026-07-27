# 固定 Linux Qt5 上游进程性能基线

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 结论

固定 Linux Qt5 CMake oracle 现在已有第一份可重复的描述性进程基线：

- benchmark runner 在受限 Linux container **内部**直接启动原始 `diec` 或只替换
  console `main` 的测量 harness；没有把 Windows `docker.exe` 的时间/RSS 误当成
  engine 数据；
- 五层 case 分离 Qt/process control、三层 database load、单 PE JSON
  end-to-end、生成语料 batch JSON end-to-end 和 16 层 archive；
- 每个 measured sample 都是新进程；warmups 和 measured runs 使用声明的 warm OS
  cache，输出必须逐次 hash 一致；
- 107 次直接进程（17 warmup、90 measured）全部 exit 0、stderr 为空、输出 hash 稳定且有
  direct-process peak RSS；
- 4 ms control 的 p95 约为 median 的 2 倍，明确标为 `high_tail_noise`，不得作为
  性能回归 case。50 ms 是后续冻结回归阈值前的最小中位时长候选。

机器报告为
[`upstream-benchmark-linux-qt5.json`](data/upstream-benchmark-linux-qt5.json)，
严格 plans 为
[`upstream-benchmark-plans.json`](data/upstream-benchmark-plans.json)。

这份报告只建立 **descriptive upstream baseline**，没有 Rust 成对数据，因此
`targets_frozen=false`，不能据此声称 Rust 更快，也没有关闭 `P0-BLOCK-006`。

## 2. 固定身份与环境

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| rules/database | `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| release `diec` SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| benchmark harness SHA-256 | `78da92e7188d717e8991f80476f40596eedd4f0f00483cafd8495623289f5ece` |
| benchmark image | `sha256:a5b33708eb148591d127041b6a54d05d68f8dd24bea7855e95ea88715d0bf8c5` |
| build | GCC 13.3.0、Qt 5.15.13、CMake 3.28.3、Release `-O3 -DNDEBUG` |
| runner | Python 3.12.3、`time.perf_counter_ns` |
| RSS | `/proc/PID/status` 的 `VmHWM/VmRSS`，2 ms polling |

本次 host observation 为 Intel Core Ultra 7 155H、Docker Desktop WSL2 kernel
6.6.87.2、overlay filesystem。container 强制：

```text
--network none --cpus 1 --memory 512m --pids-limit 128
```

机器报告进一步验证 cgroup `cpu.max=100000 100000`、
`memory.max=536870912`、`pids.max=128`。`cpuset.cpus.effective=0-3` 表示未固定
单一物理 core，只通过 quota 限制为 1 CPU；这是保留的 noise 来源。

镜像内两份生成语料 manifest 分别固定为：

- baseline：`f5adabeedeaf3bb69b8e52f8de20efd0f0b87bd4dcd247610d4e876b9266f329`；
- archive limit：`1046b80963f82412616f150ff38b1664dcd7e82a0458e2b4484ab1532f223a36`。

## 3. 测量分层

| Case | Warmup / measured | Work 定义 |
| --- | ---: | --- |
| `qt-process-control` | 5 / 30 | 一次 QCoreApplication 新进程；不解释 throughput |
| `database-load` | 3 / 15 | 一次 main/extra/custom database 完整 load |
| `cli-pe32-json` | 3 / 15 | 512-byte PE32 scan + JSON + process/database load |
| `cli-baseline-batch-json` | 3 / 15 | baseline 目录 48,065 bytes，含 manifest，scan + JSON |
| `archive-depth16` | 3 / 15 | 单成员 store-only ZIP 链累计展开 19,816 bytes |

`database-load` 和 `archive-depth16` 使用
[`upstream_benchmark_harness_main.cpp`](../../tools/upstream/upstream_benchmark_harness_main.cpp)：
Dockerfile 只用它替换固定 CMake console 的 `main_console.cpp.o`，engine/database/
archive objects 不修改；harness 只输出确定性 correctness summary，不自行计时。

单 PE 与 batch 使用原始 release `diec`。因此单 PE/batch 是真实 CLI end-to-end，
但包含每次 database load；不能用 `PE median - database median` 伪造独立 scan
latency。16 层 case 也包含 database load，且只渲染小型 harness summary，不与
CLI JSON serialization case 等价。

## 4. 本次原始统计

下表单位由机器报告的整数纳秒/bytes 换算，未改变原始值：

| Case | Median | p95 nearest-rank | MAD | Peak RSS median | Peak RSS max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qt/process control | 4.155 ms | 8.309 ms | 0.090 ms | 10.38 MiB | 13.12 MiB |
| database load | 65.008 ms | 65.430 ms | 0.120 ms | 18.46 MiB | 18.96 MiB |
| PE32 JSON end-to-end | 115.289 ms | 166.672 ms | 0.416 ms | 33.97 MiB | 34.22 MiB |
| baseline batch JSON | 1,368.636 ms | 1,420.631 ms | 48.606 ms | 76.79 MiB | 76.98 MiB |
| depth-16 archive | 64.895 ms | 66.454 ms | 0.161 ms | 23.12 MiB | 23.43 MiB |

noise ratios 也原样保存在报告中。本次 control：

- MAD / median = `0.02169364082696853`；
- p95 / median = `1.999590399956874`；
- `(max - min) / median` 可从 30 个原始 run 重算。

因此 suite verifier 只用 `MAD ≤ 0.5× median`、`p95 ≤ 3× median` 拒绝灾难性
环境噪声；这不是产品回归阈值。短进程被明确标记为不具备 regression eligibility。

## 5. 可重复执行

```powershell
python tools\benchmark\build_upstream_benchmark_plans.py
docker build -f tools\upstream\Dockerfile.upstream-benchmark-qt5 `
  -t diec-rust/upstream-benchmark-qt5:74eaf505 tools
$report = Join-Path $env:TEMP upstream-benchmark-linux-qt5.json
python tools\benchmark\probe_upstream_benchmark.py `
  --image diec-rust/upstream-benchmark-qt5:74eaf505 `
  --output $report
```

probe 验证 image revision、镜像内 corpus manifest、cgroup、每个 runner report、
raw report hash、executable hash、输入 artifacts、run 数量、输出确定性、stderr、
duration 顺序和 RSS。宿主临时路径不写入提交报告。

## 6. 解释边界与下一门禁

- warm cache 是显式声明；没有可靠 drop OS page cache，未采集 cold baseline。
- CPU quota 为 1，但没有 physical-core affinity、governor、frequency 或后台负载
  控制；host/WSL2 更新后必须新建 baseline identity，不能就地覆盖历史。
- RSS 只测直接进程，不含任意 descendant tree；这些命令不得派生持久子进程。
- throughput 对 control/database 不解释；对 512-byte PE 也没有工程意义。batch 与
  nested 的分母定义不同，不能横向比较。
- database-only harness 证明 load 总成本；当前进程 runner 不能测同一已加载
  session 内的单次 warm scan。Phase 1 需要 in-process benchmark port。
- 上游没有本项目的 C ABI，因此 staticlib C-call overhead 只能在 Rust 实现出现后
  与 Rust direct-call/control 成对测量，不能伪造 upstream exact case。
- 固定 Linux Qt5 的 ELF、动态依赖闭包和规则 size 已另行采集，见
  [`upstream-deployment-size.md`](upstream-deployment-size.md)；它不等于跨平台
  发行包口径。
- 尚缺 Linux cold/affinity 复验、Windows/macOS 基线、Rust 相同 bytes/options
  与 size 的成对报告，以及评审后的 latency/p95/RSS/size/default limit targets。

只有上述成对证据存在后，才能冻结“Rust 相对固定 upstream 的改善百分比”和发布
回归阈值。
