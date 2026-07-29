# Windows Qt5 result-model 行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 结论

固定原生 Windows x86_64、Qt 5.15.2 qmake engine objects 上，五组
result-model harness 各连续运行两轮，共 10 次进程执行、30 次 case
observation。每组先通过原 Linux Qt5 probe 的完整关系验证，再做窄化
规范化；五份完整结构化文档均与固定 Linux Qt5 相同：

| Profile | Case/轮 | 直接边界 | Linux Qt5 |
| --- | ---: | --- | --- |
| metadata | 4 | file/memory/device/subdevice scalar fields | 相同 |
| lists | 2 | records/errors/debug/handlers、重复与顺序 | 相同 |
| flags | 4 | normal/heuristic/advanced/Unknown | 相同 |
| IDs | 1 | 两层 record/parent ID 字段与链接 | 相同 |
| enums | 4 | raw/numeric/canonical/reserved/fallback | 相同 |

结合 lists 中的非空 version/info 和已固定 Windows engine-contract 中的 rule
name/path、priority `12/30/100`，六个 result-model 能力行均有直接 Windows
runtime 证据。

正式报告为
[`result-model-engine-windows-qt5.json`](data/result-model-engine-windows-qt5.json)，
SHA-256 为
`611c111c38f85d7fbbe42fe41e5f6d922a7f168e084a1950b5bb6a70a5e3fc65`。

## 2. 固定构建

[`build_windows_result_model_harnesses.ps1`](../../tools/upstream/build_windows_result_model_harnesses.ps1)
验证固定上游、58 个递归 submodule、规则 commit、CLI、Qt 二进制和 tracked
clean 状态。它复用 qmake Release Makefile 与未修改 engine objects，对每个
profile 只替换 `release/main_console.obj`：

| Profile | Binary SHA-256 |
| --- | --- |
| metadata | `0fc28e90dfe8afd30257a7dcc63797c89e6c282f640860c6cc2eaa97deebeae9` |
| lists | `38f70046bdf1d46646d277b4fd4b5412753ff59ebdd960fbe0bf7787c822b7f1` |
| flags | `0cc938543720cb7f5f202bc371a9f088d54f70aa98cc3ec8fa46d8d344e46c5a` |
| IDs | `d1a63bd0b81a7f5ea7b18701be95e3b1857b416d4ba7085655e9308c3eaf9777` |
| enums | `8f055f1cba9142cf3f33706209befb635fd375f768b86a24e3bc4775c6edb6a1` |

外部 build manifest SHA-256 为
`92c6729d3e1accbb746f6819967f29026bf2bf8516917834affae268a06a959c`；
它绑定 builder、五个共享 harness source、原始 Makefile、
`main_console.obj`、`die_script.obj` 和五个产物。没有重编译或修改 engine
object，也没有使用 private-access ABI shim。

## 3. 输入与原始证据

lists、flags 和 enums 使用各自项目生成、逐文件 hash-bound fixture；IDs 使用
[`nested-corpus.json`](data/nested-corpus.json) 中 1,024-byte
`pe-manifest-resource.exe`。metadata 自行生成固定 128-byte MSDOS 输入。
所有 fixture 在运行前由原 probe verifier 与已提交 manifest 逐字节核对。

每轮 stdout/stderr 原样写入外部 `--raw-dir`。metadata、lists、flags 和 enums
的两轮 raw 流逐字节相同；IDs 的 UUID 每轮按上游契约随机，因此 raw stdout
不同。所有 stderr 均为空，exit code 均为 `0`。

## 4. 规范化边界

规范化只在原 probe 完整验证之后执行：

- 已验证 fixture 根前缀替换为 `/fixture`；
- 只在该前缀及固定 collection destination 内统一路径分隔符；
- 保留每轮原值后，将 `nScanTime` 和 debug `elapsed_ms` 置零；
- UUID 按首次出现映射为稳定 token，同时保留父子 equality link 和每轮原值。

没有删除或重排 case/record，没有改写 error text、type、name、flag、enum 或
其他 value，也没有改写 raw hash。Windows lists 的唯一路径表达差异是固定
handler destination 使用 `\`；规范化后完整文档与 Linux Qt5 相同。

## 5. Rust 兼容约束

后续 Rust 结果模型必须使用同一结构化核心供 CLI、JSON 和 FFI 投影：

- scalar metadata 的 filename/size/filetype 与 entry point 关系不能合并；
- records/errors/debug/handlers 是四个独立有序列表，重复项不能去重；
- heuristic、advanced heuristic 和 Unknown 是独立布尔语义；
- ID 的随机 identity 与父子 equality link 必须分开比较；
- raw type/name 与 numeric/canonical enum 必须同时保留；
- version、info、rule name/path 和 priority 不得在 adapter 层丢失。

时间与 UUID 是明确的非确定字段；差分测试应保留原值并另建语义投影，不能把
整条 record 删除来获得确定性。

## 6. 复现

```powershell
powershell -File tools\upstream\build_windows_result_model_harnesses.ps1 `
  -SourceDir <fixed-clean-source> `
  -BuildDir <fixed-qmake-build> `
  -QtDir <fixed-qt-5.15.2> `
  -VsDevCmd <VsDevCmd.bat> `
  -OutputDir <harness-dir> `
  -OutputJson <build-manifest.json>

python tools\upstream\collect_windows_result_model_harnesses.py `
  --binary-dir <harness-dir> `
  --source-dir <fixed-clean-source> `
  --qt-dir <fixed-qt-5.15.2> `
  --list-fixture <list-fixture> `
  --id-corpus <nested-corpus> `
  --flag-fixture <flag-fixture> `
  --enum-fixture <enum-fixture> `
  --working-dir <working-dir> `
  --build-manifest <build-manifest.json> `
  --raw-dir <external-raw-dir> `
  --output docs\research\data\result-model-engine-windows-qt5.json
```

重跑必须保持所有 source/object/binary/fixture/reference 哈希；任一关系失败、
规范化双轮不一致或 Linux Qt5 完整文档差异都应使采集失败。
