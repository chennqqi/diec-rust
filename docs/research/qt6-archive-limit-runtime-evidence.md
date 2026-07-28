# Linux Qt6 archive 深度与累计展开量差分证据

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

`CAP-NEST-009` 在固定 Linux Qt6 oracle 上达到逐行完整证据：

- Qt5 与 Qt6 使用相同的 14 个 hash-bound store-only ZIP 样本；
- 两侧均到达最大测试深度 64，产生 64 个 Stream node，最深 PDF depth 为 64；
- 两侧均在 depth 2 到达最大测试累计展开量 33,554,546 bytes；
- 第一次 progress callback 取消在两侧产生相同的非空严格前缀；
- 14 个正常 case 和 1 个取消 case 的确定性 harness 字段完全相同；
- 固定 `xscanengine.cpp` archive block 在两侧相同，仍没有独立 depth 或全 scan
  cumulative extraction token。

这关闭 Linux Qt6 `CAP-NEST-009`，并使
[`qt6-capability-closure-plan.json`](data/qt6-capability-closure-plan.json)
的 68 行全部成为 `evidence_complete`。结论仍是有界观察，不证明任意深度或
展开量都能成功，也不要求 Rust 复制上游的无界资源风险。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| XScanEngine | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| Qt5 报告 SHA-256 | `e4786dcc578fb0714c86f71955161f981a06be26aefe663281d74202f5372ecd` |
| Qt6 harness image ID | `sha256:1a264871bcffab7b2c222d79c2f9800ac272df053166a91c3cdf36c6941b08e2` |
| Qt6 harness binary SHA-256 | `31c38b40ee7a0afa0d0e482789b75f7ab151448bb2ee0c0150011f51a596dcc9` |
| `xscanengine.cpp` SHA-256 | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| corpus manifest SHA-256 | `09e31c8373cd151c68d41aab18fefd7e18fff54c29b8d56c16196276660c5cd5` |
| stable projection SHA-256 | `b10e21874a95cf675d521ae04ff8a1297fbb9bb054cdbe29b6757f5277503848` |

机器报告：
[`archive-limit-engine-qt5-qt6.json`](data/archive-limit-engine-qt5-qt6.json)，
SHA-256 为
`2dec18c44faa7580294e6da5f5ff07c8734ebe031fed53af8a03031cc406460e`。
报告内嵌 Qt6 每次执行的原始 stdout/stderr、stream hash、退出码、timeout/OOM
标志、完整 harness JSON、image/binary/source 身份，并对 Qt5 原始报告作哈希引用。

## 方法

Qt6 Dockerfile 只把固定 CMake console target 的 `main_console.cpp.o` 替换为与
Qt5 相同的
[`archive_limits_harness_main.cpp`](../../tools/upstream/archive_limits_harness_main.cpp)；
engine、formats、archive backend 和 rule runtime objects 均来自固定 Qt6
基础镜像。构建定义、harness 和基础探针各自以 SHA-256 写入机器报告。

配对驱动
[`probe_qt6_archive_limits.py`](../../tools/upstream/probe_qt6_archive_limits.py)
复用原
[`probe_archive_limits_harness.py`](../../tools/upstream/probe_archive_limits_harness.py)
协议，在以下限制内逐 case 启动独立容器：

```text
network: none
cpus: 1
memory: 256m
pids: 128
wall timeout: 30 seconds
```

跨版本相等投影包含 callback/cancellation、record/list count、parent-depth 汇总、
Stream/PDF node、error/debug/handler count、stop 状态、exit/timeout/OOM 和原始
stderr。`elapsed_ms`、`scan_result_time_ms` 与 `ru_maxrss` 是环境相关描述值，
完整保留但不用于伪造逐字节相等结论。

## 支撑边界

本报告还哈希绑定已由独立严格 validator 接纳的 Qt6 证据：

- CLI recursion 与 internal archive recursion gate；
- resource context、subdevice propagation 和 21/2001 record count；
- archive option 跨层传播；
- 99999/100000/100001 archive iteration；
- public/private archive family dispatch；
- Qt5 五类 engine extraction 闭集与 depth/total 源码结论。

因此本次实验只补齐最后缺失的 depth、cumulative expanded bytes 和 cooperative
cancellation 对照，不用小样本替代其他已完成边界。

## 复现

```powershell
$corpusDir = Join-Path $env:TEMP diec-archive-limit-corpus-qt6
python tools\corpus\generate_archive_limit_fixture.py $corpusDir
docker build `
  -f tools\upstream\Dockerfile.archive-limits-harness-qt6 `
  -t diec-rust/upstream-archive-limits-harness-qt6:74eaf505 `
  tools\upstream
python tools\upstream\probe_qt6_archive_limits.py `
  --corpus-dir $corpusDir `
  --output docs\research\data\archive-limit-engine-qt5-qt6.json
python tools\research\build_qt6_closure_plan.py
```

重复执行时 wall time、scan time、RSS 和由其影响的 raw stdout hash 可以变化；
稳定 behavior projection、case catalog、source/image/binary/corpus identity 和
语义断言必须保持不变。

## 限制

- 只验证 Linux x86_64、Qt 5/6 固定构建、ZIP store method、depth 64 和约
  32 MiB 累计展开量。
- 没有执行真实 OOM、超过 30 秒后的 engine cleanup、欺骗声明长度或任意深度。
- Qt6 与 Qt5 相等不改变 ADR 0012 的安全结论：Rust 默认必须有独立 depth、
  entry、single-object、cumulative expanded、node、allocation 和 deadline
  预算。
- Windows 与 macOS 仍没有完整能力基线。
