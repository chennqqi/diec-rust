# Linux 大目录枚举与取消接线边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 qmake/CMake 两个 Oracle 对 5 个 case、共 10 次执行给出
逐字节一致结果：

- empty directory 仍是 exit `0`、空 stdout/stderr；
- 单文件目录产生一个 entropy JSON document，不打印 filename prefix；
- flat 256、flat 4096 和 16×256 nested 4096 三个目录的所有文件都被处理，没有
  在 256/4096 处截断；
- 文件按 `QDir::entryInfoList()` name order 输出，与 fixture 故意采用的
  descending creation order 无关；
- 两种 4096-file layout 都输出 4096 个 filename prefix 和 4096 个 entropy
  document，exit `0`、stderr 为空。

该结果只证明固定环境在 4096 项以内没有观察到 entry cap；不能从有限样本声称
上游对任意规模“无上限”。机器报告：
[`large-path-engine-qt5.json`](data/large-path-engine-qt5.json)，SHA-256 为
`100562d79fa661055fd79e0efe6ce8f58a31b8e4faebedf410f80f51e817883b`。

源码审计同时修正了“`findFiles` 完全没有取消检查”的过宽表述：

- `XBinary::findFiles(..., PDSTRUCT *pPdStruct = nullptr)` 的 overload 在每个
  directory entry 前调用 `isPdStructNotCanceled(pPdStruct)`；
- `isPdStructNotCanceled(nullptr)` 返回 true，因此可选 `PDSTRUCT` 为 null 时不会
  停止；
- 发布 CLI 使用两参数
  `XBinary::findFiles(sFileName, &listFileNames)`，通过默认参数传入 `nullptr`；
- 所以 Formats API 存在 cooperative cancellation 接线点，但发布 CLI 的 target
  expansion 没有把自身 `PDSTRUCT` 传进去，用户也没有可达的 cooperative cancel
  channel。

这一区分必须保留：Rust modern `TargetExpander` 需要真实 cancellation token，
legacy CLI differential 则要记录固定上游入口未接线的行为。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| qmake image | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| CMake image | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| qmake binary | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| CMake binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| fixture manifest | `67a29846d009f10b6448021f651d6b7e8bed0c16124f16c2b07f55085e2dd26a` |
| `Formats/xbinary.cpp` | `d82bd21326bb7ba07eb343020d50af0ae2cf7e8e534d8e08d07ffa8129913c34` |
| `Formats/xbinary.h` | `c0e92d317ca9d0c54edaeeaf2846e13c50abaf9d32b987a9454bb8b4d63b5838` |
| `main_console.cpp` | `ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f` |

报告绑定 source file 的完整 SHA-256，并为以下精确 pattern 保存 occurrence count
与 1-based line number：

```text
findFiles(..., PDSTRUCT *pPdStruct = nullptr)
isPdStructNotCanceled(pPdStruct)
if (pPdStruct) / pPdStruct->bIsStop
XBinary::findFiles(sFileName, &listFileNames)
```

运行结论来自双 Oracle；取消可达性来自固定源码。两者不能互相替代。

## 确定性 fixture plan

[`generate_large_path_fixture.py`](../../tools/corpus/generate_large_path_fixture.py)
只生成
[`large-path-fixture.json`](data/large-path-fixture.json)，不提交 8,449 个 materialized
文件。每个 case 在全新 read-only-root container 的 64 MiB tmpfs 中生成：

| Case | Layout | 文件数 | 创建顺序 |
| --- | --- | ---: | --- |
| `empty_0` | flat | 0 | n/a |
| `single_1` | flat | 1 | descending |
| `flat_256` | flat | 256 | descending |
| `flat_4096` | flat | 4,096 | descending |
| `nested_4096` | 16 buckets × 256 | 4,096 | bucket/file 均 descending |

文件名固定为 `item-{index:06d}.empty`，bucket 为
`bucket-{index:03d}`，payload 是 0 byte（SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`）。
probe 在启动 Oracle 前递归复验 file/root-entry count 及 first/last path。

选择 empty file 的目的，是减少规则/格式解析成本，让本实验主要观察 target
expansion 与 formatter framing；它不代表普通扫描性能。

## 精确结果

| Case | Documents | Prefixes | stdout bytes | stdout SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `empty_0` | 0 | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `single_1` | 1 | 0 | 228 | `dfffd893cea0ad3d9d925824f634b5ceaae92cb12bbbadad904e2e329cc9dc87` |
| `flat_256` | 256 | 256 | 66,048 | `ecfda4bbb2774c5a9a4d8b053b89a265374c9dc994c0f308f7a48b1564fbd901` |
| `flat_4096` | 4,096 | 4,096 | 1,056,768 | `0f4ca62f93978f859199b45bb5177cb16da46b26332f52470b44f434613e838a` |
| `nested_4096` | 4,096 | 4,096 | 1,101,824 | `13dd85e56d883e96c46a386b9aa7663ea93b20e0db26c57f9e38aadd65d77072` |

flat 4096 的 first/last prefix：

```text
/work/case/item-000000.empty
/work/case/item-004095.empty
```

nested 4096 的 first/last prefix：

```text
/work/case/bucket-000/item-000000.empty
/work/case/bucket-015/item-000255.empty
```

probe 不只比较 first/last；它构造全部期望路径并与 4096 项序列逐项相等比较，
随后保存 prefix sequence SHA-256。

## 描述性资源数据

每个 case 在全新 container 中由 Python wrapper 使用 `RUSAGE_CHILDREN` 记录单个
`diec --entropy --json` child 的 wall time、user/system CPU、major faults 和
peak RSS。报告中的单次观测为：

| Case | qmake wall / RSS | CMake wall / RSS |
| --- | ---: | ---: |
| `empty_0` | 49.60 ms / 19,392 KiB | 56.75 ms / 19,720 KiB |
| `single_1` | 49.40 ms / 20,836 KiB | 52.91 ms / 21,224 KiB |
| `flat_256` | 63.29 ms / 21,096 KiB | 67.44 ms / 20,848 KiB |
| `flat_4096` | 210.73 ms / 23,656 KiB | 212.66 ms / 23,528 KiB |
| `nested_4096` | 207.17 ms / 21,480 KiB | 203.98 ms / 21,608 KiB |

这些数值包含进程启动、数据库加载、目录展开、逐文件 entropy 和输出构造，只是
本轮身份绑定的描述性观测。它们没有 warmup/repetition/noise analysis，不能作为
性能目标，也不能据此声称 flat/nested 的稳定相对性能。

## 受限执行

每个 case/Oracle 使用全新 container：

```text
network=none
cpus=1
memory=512 MiB
pids=128
root filesystem=read-only
work tmpfs=64 MiB
core size=0
child timeout=60 seconds
host safety timeout=90 seconds
```

所有 stdout/stderr 先由 wrapper 有界捕获，再以 `zlib+base64` 返回；版本化报告
按原始 SHA-256 content address 去重。probe 重新解压并核对 size/hash，qmake 与
CMake 的 exit/stdout/stderr 任何一项不同都会失败。

复现：

```powershell
python tools\corpus\generate_large_path_fixture.py `
  --output docs\research\data\large-path-fixture.json
python tools\upstream\probe_large_path_behavior.py `
  --output docs\research\data\large-path-engine-qt5.json
```

`--explore` 只用于首次调查；版本化报告必须在内置 stdout hash 集合完整时用严格
模式生成。

## 兼容与设计含义

- legacy-compatible 枚举在预算允许时必须保留完整 prefix 顺序，不能把 4096 当作
  上游 entry cap 或静默截断。
- “Formats API 有取消参数”不等于“发布 CLI 路径展开可取消”。Rust CLI 必须把
  shared cancellation token 真正传入 `TargetExpander`，并用大目录 system test
  验证有界响应。
- 上游先构造完整 `QList<QString>` 再开始逐文件扫描；Rust modern streaming
  expansion 若改变错误/输出时序，必须由 API/ADR 明确并单独差分。
- 4096 项的成功不能成为 Rust 无界默认。depth、considered/emitted entry、
  path bytes、deadline/cancellation hard budget 仍按
  [`ADR 0014`](../design/decisions/0014-bounded-path-expansion.md) 处理。
- 本轮没有制造枚举后、打开前 target replacement，因此不证明 TOCTOU 行为安全
  或兼容。

## 剩余缺口

- 可控 rename/symlink target swap 的枚举—打开 TOCTOU harness；
- locale 改变、case/normalization 不同的 filesystem 排序；
- Windows junction/reparse point 与 macOS volume 行为；
- Linux Qt6 完整平台基线；
- Rust `TargetExpander` 实现后的 `limit-1/exact/+1`、取消 latency 和 streaming
  prefix 差分。

本页继续缩小 `CAP-GAP-003`，但 TOCTOU 与剩余 Linux locale/filesystem 行为仍
使该 gap 保持开放；`CAP-GAP-007`/`CAP-GAP-008` 的平台缺口不变。
