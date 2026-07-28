# Deep、aggressive 与 resource count 边界

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 目的

本实验闭合 `CAP-GAP-005`，回答此前普通语料无法回答的四个问题：

1. `--deepscan` 是否产生实际增量，以及 `DS`/`EP` 的执行顺序；
2. `--aggressivecscan` 是否会自行开启 resource 扫描；
3. recursive 下不可识别 resource 与可识别 resource 的过滤差异；
4. 默认 `20`、aggressive `2000` 在上游 inclusive 判断下的精确可观察计数。

完整机器报告为
[`scan-option-boundaries-linux-qt5.json`](data/scan-option-boundaries-linux-qt5.json)，
SHA-256 为
`f193a9f308b04a89dd7ceeda52a658eda2ef13eb82b9c0662c66215248bbf49d`。
它保存 8 个 case × 2 个 Qt5 oracle 的退出码、原始 stdout/stderr
content-addressed bytes（`zlib+base64` 可逆存储）、结构摘要、容器/二进制/
源码身份和派生事实。

## 2. 固定身份与资源边界

| 项目 | 固定值 |
| --- | --- |
| qmake image ID | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| qmake binary SHA-256 | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| CMake image ID | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| CMake binary SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| `xscanengine.cpp` SHA-256 | `e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498` |
| `xpe.cpp` SHA-256 | `bfad885df2569b03bc33c040852a884bfe40d781a58bef5f6d8c53c16b488a0c` |
| `main_console.cpp` SHA-256 | `ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f` |
| fixture manifest | [`scan-option-boundary-fixture.json`](data/scan-option-boundary-fixture.json) |

每次容器执行固定为无网络、1 CPU、512 MiB、128 PIDs、180 秒 timeout、
只读 root filesystem 和只读 fixture mount。所有规则和二进制均由
[`generate_scan_option_boundary_fixture.py`](../../tools/corpus/generate_scan_option_boundary_fixture.py)
确定性生成，不包含第三方样本字节。

## 3. 源码契约

`main_console.cpp` 将三个 CLI 开关分别映射到
`bIsDeepScan`、`bIsAggressiveScan` 和 `bIsRecursiveScan`，没有把 aggressive
隐式映射为 recursive。

固定 `XScanEngine::scanProcess()` resource 分支：

- 请求最多 `10000` 个 `FILEPART_RESOURCE`；
- 默认 `nLimit = 20`，aggressive 改为 `2000`；
- 判断是 `nCurrentIndex <= nLimit`，因此实际扫描上限分别为 21 和 2001；
- overlay 无条件扫描；resource 在 aggressive 下直接扫描，否则只有
  `isScanable()` 为真时扫描；
- `nCurrentIndex` 只在 child 实际扫描后增加。

还有一层容易遗漏的 parser 限制：`XPE::getResources()` 要求 resource tree 的
root/type/language 每个 directory 各自不超过 1000 个 entry。单一 type 下放置
2002 个资源会被整体视为损坏，不能用来验证 engine 的 2001 上限。本实验因此
使用三个合法 type directory，分别包含 668、667、667 项，总数为 2002。

机器报告逐项固定以下源码关系和出现次数，避免相邻代码变化被实验结果掩盖：

- `deep_adds_ds_and_ep_in_rule_order`
- `aggressive_alone_does_not_enable_resource_scan`
- `recursive_skips_unclassified_resource_without_aggressive`
- `recursive_aggressive_scans_unclassified_resource`
- `default_scanable_resource_limit_is_inclusive_21`
- `aggressive_resource_limit_is_inclusive_2001`
- `resource_children_preserve_enumeration_order`
- `grouped_fixture_respects_pe_per_directory_limit`
- `qmake_and_cmake_raw_outputs_are_equal`

## 4. Deep 实际增量

最小 Binary database 依 priority 顺序包含普通规则、`DS` 和 `EP`：

| Case | detection names |
| --- | --- |
| default | `Binary normal` |
| `--deepscan` | `Binary normal`, `Binary deep`, `Binary entrypoint` |

因此 `DS` 和 `EP` 都只在 deep 下放行，且输出保持规则执行顺序。这与既有
rule-orchestration harness 的过滤结论一致，本实验进一步固定了发布 CLI 的实际
JSON 增量。

## 5. Aggressive gate

项目生成的单 resource PE 使用一个无法被格式探测器识别的 1-byte payload：

| Flags | Resource child count | 结论 |
| --- | ---: | --- |
| `--aggressivecscan` | 0 | aggressive 本身不打开 resource 枚举 |
| `--recursivescan` | 0 | 非 aggressive 会跳过 unscanable resource |
| `--recursivescan --aggressivecscan` | 1 | aggressive 越过 scanable gate |

这分别固定 CLI option 映射和 engine resource filter，不能把“aggressive 单独无
变化”误写成该开关无效。

## 6. Count 边界与顺序

| Fixture / flags | 枚举数 | 实际 Resource child | 结果 |
| --- | ---: | ---: | --- |
| 22 × PDF / recursive | 22 | 21 | 默认 inclusive off-by-one |
| 22 × PDF / recursive+aggressive | 22 | 22 | aggressive 未达到上限 |
| 2002 × unclassified / recursive+aggressive | 2002 | 2001 | aggressive inclusive off-by-one |

2001-child case 的第一个 offset 为 `96704`，最后一个为 `98704`；所有 child
offset 严格递增，size 均为 `1`。因此第 2002 项确实被 limit 跳过，而不是 parser
只枚举出 2001 项或 formatter 重排结果。两个 Qt5 构建的所有原始 streams
逐字节相同。

## 7. 兼容与安全含义

legacy-compatible 模式必须保留：

- deep 对 `DS`/`EP` 的独立 gate；
- aggressive 不隐式开启 recursive；
- non-aggressive resource 的 scanable filter；
- 默认 21、aggressive 2001 的可观察 child 上限和枚举顺序。

这些上游上限不是 Rust 的安全上限。Rust hard limits 必须先于兼容策略执行，
aggressive 只能在调用方允许的 hard budget 内提高 legacy policy threshold。
`CAP-GAP-006` 仍保持开放：五种 7Z 单 coder、x86/ARM64-BL BCJ+LZMA2
filter 链、RAR4 store、CAB Store/MSZIP 与 ISO9660 正例虽已由
[`archive-format-behavior.md`](archive-format-behavior.md) 固定，archive
100000 精确边界已由
[`archive-iteration-boundary.md`](archive-iteration-boundary.md) 固定；
ZIP 1 MiB/843.58:1 和首轮畸形由
[`archive-adversarial-behavior.md`](archive-adversarial-behavior.md) 固定；
其他格式/算法、更高展开量、最大深度、累计解压量和资源耗尽仍不能由本实验
外推为闭合。

## 8. 复现

```text
python tools/corpus/generate_scan_option_boundary_fixture.py <fixture-dir>

python tools/upstream/probe_scan_option_boundaries.py \
  --fixture-dir <fixture-dir> \
  --output docs/research/data/scan-option-boundaries-linux-qt5.json

python tools/tests/test_generate_scan_option_boundary_fixture.py
python tools/tests/test_probe_scan_option_boundaries.py
```

probe 会先校验 manifest 的封闭目录/文件集合、每个文件的 size/SHA-256、两个
image revision、二进制和三份固定源码，再执行 oracle。未知字段、输入漂移、
非零退出、stderr、无效 JSON、计数/顺序差异或两构建 raw bytes 差异都会失败。
