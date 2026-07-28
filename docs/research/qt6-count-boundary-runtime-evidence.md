# Linux Qt6 archive/resource 计数边界运行证据

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

`CAP-NEST-004` 已达到 Linux Qt6 `evidence_complete`：

- resource 默认模式在 22 个可扫描 PDF resource 中产生 21 个 child；
- resource aggressive 模式在 2002 个不可分类 resource 中产生 2001 个
  child，且 offset 严格递增；
- 两轮 Qt6 的 8 个 scan-option case 原始 stdout/stderr 逐字节相同，规范化
  摘要与固定 Qt5 CMake oracle 逐项相同；
- archive 99999/100000/100001 三点实验在 Qt6 下到达第 99999 条 PDF，而
  第 100000、100001 条
  PDF 均不可达；这与 Qt5 的第 100000 条仍可达不同；
- archive 差异不是源码 revision 漂移。Qt6 保留 ISO9660 `.` record 的单个
  NUL code unit，Qt5 将同一 `QByteArray` 转为空 `QString`，使固定 dot filter
  的比较结果不同。Qt6 因而在真实 record 前多扫描一个 Stream，并把硬循环
  边界提前一条。

该差异已保留为平台事实，不能在 Rust 差分规范化中静默删除。最终 Rust legacy
profile 以 Qt5 还是 Qt6 的 ISO 边界为目标，仍需兼容性评审或 ADR；本实验只
证明两个固定上游运行时各自的可观察行为。

## 固定证据

| 报告 | Bytes | SHA-256 |
| --- | ---: | --- |
| [`archive-iteration-boundary-engine-qt5.json`](data/archive-iteration-boundary-engine-qt5.json) | 6787 | `57a78308860d6842bf2b33367451d696a7c3252d1411de2ed5c32d9659c29533` |
| [`archive-iteration-boundary-engine-qt6.json`](data/archive-iteration-boundary-engine-qt6.json) | 7472 | `50b23210a24620561c19c9bf902f165030e4dbb10b8ecda9ebe5bc996670ba65` |
| [`qt-null-filename-semantics-qt5-qt6.json`](data/qt-null-filename-semantics-qt5-qt6.json) | 2618 | `0a62837f0a32b4147a379f1fdba3a4c286f658734bbcefc2c2b0e2e22493f8c2` |
| [`scan-option-boundaries-linux-qt5.json`](data/scan-option-boundaries-linux-qt5.json) | 168346 | `f193a9f308b04a89dd7ceeda52a658eda2ef13eb82b9c0662c66215248bbf49d` |
| [`scan-option-boundaries-linux-qt6.json`](data/scan-option-boundaries-linux-qt6.json) | 95314 | `4f9f4e1c249ebc7b8b6277544ba4c5790bbab3a5ed2158580b79dd6356b6841f` |

共同 `xscanengine.cpp` SHA-256 为
`e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498`；
共同 `xpe.cpp` 和 `main_console.cpp` SHA-256 分别为
`bfad885df2569b03bc33c040852a884bfe40d781a58bef5f6d8c53c16b488a0c`
和
`ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f`。
ISO parser `xiso9660.cpp` SHA-256 为
`d6e97c4ff2395b812b65da5ab480e937c6b365e6e6e8b0288ddf48b8fd398fb1`。

Qt6 release oracle 固定为：

- image ID
  `sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b`；
- binary SHA-256
  `e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e`。

Qt6 archive iteration harness image ID 为
`sha256:a51310e8e03ada9fb907d6ea3d3d3b0a5d0c1917a3aaef971f3a07683486508f`，
binary SHA-256 为
`d13b381bc5353f8e261a741c235a825e65461d8ab38cf9f9ba71c16fb94dfbcb`。

## Archive 三点结果与根因

| PDF ordinal | Qt5 node/PDF/record/Stream | Qt6 node/PDF/record/Stream |
| ---: | --- | --- |
| 99999 | `2 / 1 / 3 / 1` | `3 / 1 / 4 / 2` |
| 100000 | `2 / 1 / 3 / 1` | `2 / 0 / 2 / 1` |
| 100001 | `1 / 0 / 1 / 0` | `2 / 0 / 2 / 1` |

两侧使用同三个 100001-record ISO、相同受控 `TMPDIR=/proc` 分配失败、相同
`i < 100000` engine 硬循环 guard。额外 direct Qt probe 得到：

| Runtime | `QString::fromLatin1(one-NUL QByteArray)` | 与 NUL C string 相等 |
| --- | --- | --- |
| Qt 5.15.13 | size 0，首 code unit 不存在 | true |
| Qt 6.4.2 | size 1，首 code unit 0 | false |

固定 `xiso9660.cpp:546` 用
`sFileName == "\x00" || sFileName == "\x01"` 过滤 dot entries。由此可直接解释
Qt5 跳过 `.`、Qt6 保留 `.` 的一条 Stream 差异；两边源码 SHA 和 revision
完全相同。

## Resource 21/2001 结果

Qt6 probe 在相同 fixture 上执行 8 个 case × 2 repetitions，共 16 次受限
容器调用。关键结果为：

| Fixture / flags | Qt5 child | Qt6 child |
| --- | ---: | ---: |
| 22 × PDF / recursive | 21 | 21 |
| 22 × PDF / recursive+aggressive | 22 | 22 |
| 2002 × unclassified / recursive+aggressive | 2001 | 2001 |

所有 Qt6 case 的两轮 raw streams 相同；所有 stderr 为空，因此本组未触发其他
PE 规则语料中已知的四行 `Unimplemented code.`。报告仍固定并接受该 80-byte
诊断的 SHA-256
`b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b`，
但 affected case 清单必须为空，防止未知 stderr 被误分类。

## 重现

```text
python tools/corpus/generate_archive_iteration_boundary_fixture.py <iso-fixture>
python tools/upstream/probe_archive_iteration_boundary_harness.py \
  --platform qt6 \
  --image diec-rust/archive-iteration-boundary-harness-qt6:74eaf505 \
  --corpus-dir <iso-fixture> \
  --output docs/research/data/archive-iteration-boundary-engine-qt6.json

python tools/upstream/probe_qt_null_filename_semantics.py \
  --output docs/research/data/qt-null-filename-semantics-qt5-qt6.json

python tools/corpus/generate_scan_option_boundary_fixture.py <resource-fixture>
python tools/upstream/probe_qt6_scan_option_boundaries.py \
  --fixture-dir <resource-fixture> \
  --output docs/research/data/scan-option-boundaries-linux-qt6.json

python tools/research/build_qt6_closure_plan.py
```

边界探针使用无网络、1 CPU、512 MiB、128 PIDs、只读容器 root/fixture mount；
scan-option 每次 timeout 为 180 秒，archive iteration 每次为 30 秒。

## 限制

- 只验证 Linux x86_64 的 Qt 5.15.13/Qt 6.4.2 固定镜像；
- archive 大计数只用 ISO9660 和一个 PDF 哨兵，不外推到所有 adapter；
- 受控临时文件失败隔离的是 record reachability，不是 10 万成功 child 的性能；
- 本报告闭合 count-boundary 能力，不闭合独立 depth/total extraction limit 或
  cancellation；这些仍属于 `CAP-NEST-009`。
