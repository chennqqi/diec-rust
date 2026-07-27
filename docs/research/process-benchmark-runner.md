# 进程级 benchmark runner

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 1. 目的与结论

[`tools/benchmark/run_process_benchmark.py`](../../tools/benchmark/run_process_benchmark.py)
建立了 Phase 0 可重复性能证据的第一层：用严格 JSON plan 运行一个直接进程，
记录 wall time、peak RSS、输入/可执行文件身份、输出 hash、宿主身份和统计摘要。

该工具只证明测量契约可以执行，**尚未形成 DIE-engine 上游性能基线，也没有冻结
Rust 实现的回归阈值或默认资源限制**。因此 `P0-BLOCK-006` 仍为 Open，当前证据
不得用于“Rust 更快”之类结论。

## 2. Plan 契约

plan schema 版本固定为 `1`，未知字段、重复 JSON key、`NaN`/`Infinity`、非法路径、
不匹配的大小或 SHA-256 均显式失败。关键字段包括：

- `producer`：实现名、源码 commit、规则 commit、profile 和 toolchain；
- `input_artifacts`：仓库内相对路径、字节数和 SHA-256；
- `command`/`working_directory`：直接进程 argv 和仓库内工作目录；
- `cache_state`：v1 只接受声明的 `warm`；
- `warmup_runs`/`measured_runs`：最多 20 次预热，测量至少 3 次、最多 100 次；
- `work_bytes`/`work_definition`：throughput 分母及其明确语义；
- timeout、stdout/stderr 上限、输出确定性和 peak RSS 要求。

环境可使用 `explicit_only`，也可继承 runner 环境后覆盖。报告只记录环境变量名和
override 对象的 hash，不复制值；plan 本身仍可能含敏感值，因此不得把凭据放进
plan、argv 或提交的 artifact。

## 3. 执行与报告

runner 在执行前后重新验证全部输入和可执行文件身份。stdout/stderr 由两个线程
以 64 KiB 块持续 drain、计数和 hash，不把完整输出保存在内存或报告中；超过
配置上限时终止直接进程并失败。

每个 measured run 记录：

- `time.perf_counter_ns` wall time；
- Windows `PeakWorkingSetSize`、Linux `VmHWM/VmRSS` 或 macOS
  `proc_pid_rusage` 采样所得 direct-process peak RSS；
- exit code、stdout/stderr 字节数和 SHA-256。

摘要记录 duration min/median/p95 nearest-rank/max/MAD、median throughput、
peak RSS median/max，以及输出 hash 的唯一值集合。要求确定性时，measured runs
的 stdout/stderr hash 必须各自唯一。

CLI 用法：

```text
python tools/benchmark/run_process_benchmark.py \
  --plan <plan.json> \
  --output <report.json> \
  --repo-root <checkout>
```

## 4. 安全边界和已知限制

- 工作目录和输入必须在 repo root 内，且路径组件不能是 symlink/reparse point。
- v1 只支持期望退出码 `0` 的直接进程。
- warm cache 是声明值；runner 不强制刷新或预热 OS cache。
- RSS 不聚合任意 descendant tree；timeout 也只终止直接进程。benchmark 命令
  不得留下持久子进程。
- CPU affinity、power governor、worker count、调度和后台负载尚未控制。
- 当前是 process-level benchmark，不替代 allocation profiler 或 component trace。

## 5. 验证证据

[`test_run_process_benchmark.py`](../../tools/tests/test_run_process_benchmark.py)
使用项目内 `README.md` 作为 hash-bound 安全输入，覆盖：

- 三次 measured run、统计量、peak RSS、可执行文件和输入身份；
- strict plan、重复 key、非有限 JSON、cold cache 和少于三次测量的拒绝；
- 输入 hash 漂移、输出上限和 timeout 的显式失败；
- CLI report 写入和环境值不进入 host identity。

这组测试是 runner contract test，不是产品性能样本。

## 6. 关闭 `P0-BLOCK-006` 尚需

1. 固定可重建的 upstream release command、数据库、语料和 host 环境；
2. 采集并提交 upstream 原始 plan/report，完成 runner noise calibration；
3. 为 database load、单文件、batch、nested、serialization 和 C ABI 分层；
4. 评审并冻结 latency、throughput、peak memory、产物大小和默认资源限制；
5. 在支持的平台重复验证，并明确无法等价的 case。
