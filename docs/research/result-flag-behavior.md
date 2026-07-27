# SCANSTRUCT 结果标记行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

本页固定 `CAP-RESULT-003` 的 `bIsHeuristic`、`bIsAHeuristic` 和
`bIsUnknown` 三个独立布尔标记。组件身份：

- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- die_script：`5d82316c110abf0eb863b50bc679d330e05067b6`

## 源码事实

三个 flag 是 `SCANSTRUCT` 的独立字段
（`XScanEngine/xscanengine.h:1007-1010`），不能从 CLI display string 或
格式化后的 type 反推。

`DiE_ScriptEngine::_setResult` 保留原始 `sType`，并分别调用：

- `XScanEngine::isHeurType`：仅当 type 长度大于 1 且首字符为 `~` 时为 true；
- `XScanEngine::isAHeurType`：仅当 type 长度大于 1 且首字符为 `!` 时为 true。

赋值位于 `die_script/die_scriptengine.cpp:668-678`，前缀判断位于
`XScanEngine/xscanengine.cpp:2274-2299`。两个判断互不包含，因此 `!format`
不会同时设置普通 heuristic。

Unknown 不使用 type 前缀：当执行后没有 detection 且允许 fallback 时，
`DiE_Script::processDetect` 创建 `type/name == "Unknown"` 的记录并单独设置
`bIsUnknown=true`（`die_script/die_script.cpp:169-176`）。

规则文件名的 `HEUR` 分类只参与 `_shouldExecuteSignature`：
`bIsHeuristicScan=false` 时不执行该规则
（`die_script/die_script.cpp:227-234`）。它不是结果 flag 的来源。兼容测试必须
同时控制“规则是否执行”和“执行后结果 type 前缀”。

## Fixture 与四行真值表

[`generate_result_flag_fixture.py`](../../tools/corpus/generate_result_flag_fixture.py)
生成 37-byte 安全 Binary 输入、一个空数据库和三条规则：

| case | signature | heuristic scan | 原始 type |
| --- | --- | --- | --- |
| normal | `normal.1.sg` | false | `format` |
| heuristic | `HEUR.heuristic.2.sg` | true | `~format` |
| advanced | `HEUR.advanced.3.sg` | true | `!format` |
| unknown | 空数据库 | false | fallback `Unknown` |

逐文件大小和 SHA-256 见
[`result-flag-fixture.json`](data/result-flag-fixture.json)。所有输入和规则均由
本项目生成。

[`result_flags_harness_main.cpp`](../../tools/upstream/result_flags_harness_main.cpp)
每个 case 使用 signature filter 隔离到一条结果，同时导出原始 type/name、
signature 和三个 bool，避免 serializer 根据文本自行重建 flag。

## Runtime 观察

固定 Linux amd64 Qt5 报告为
[`result-flags-engine-qt5.json`](data/result-flags-engine-qt5.json)：

| case | heuristic | advanced heuristic | unknown |
| --- | ---: | ---: | ---: |
| normal | false | false | false |
| heuristic | true | false | false |
| advanced | false | true | false |
| unknown | false | false | true |

每个 case 恰有一条 record，数据库加载和扫描均未取消，错误数为 0。三个正 flag
互斥；normal 提供全部 false 控制。原始 `format`、`~format`、`!format` 和
`Unknown` 字符串也同时保留，但不作为 bool 的替代证据。

原始 stdout 为 2,976 bytes，SHA-256
`37ea3403ba7067bbb633574c248ae750b3ed0f78501a140ce85c4b44137722f7`；
stderr 为空。结构化报告绑定 fixture manifest、generator、image、binary 和
全部组件 commit/hash。

## 复现

```sh
python tools/corpus/generate_result_flag_fixture.py \
  /tmp/diec-result-flag-fixture

docker build \
  -f tools/upstream/Dockerfile.result-flags-harness-qt5 \
  -t diec-rust/result-flags-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_result_flags_harness.py \
  --fixture-dir /tmp/diec-result-flag-fixture \
  --raw-dir /outside/repository/result-flags-raw \
  --output docs/research/data/result-flags-engine-qt5.json
```

构建从固定 CMake Qt5 oracle 派生且不下载依赖；运行使用 `--network=none`。
原始 stdout/stderr 保存在仓库外。

六项关系断言全部通过，`CAP-RESULT-003` 的 Linux Qt5 状态可提升为
runtime-observed。
