# SCANSTRUCT 类型与名称表示

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

本页固定 `CAP-RESULT-005` 的原始 type/name 字符串、数值枚举及规范字符串之间
的关系。组件身份：

- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- die_script：`5d82316c110abf0eb863b50bc679d330e05067b6`

## 源码事实

`SCANSTRUCT` 同时保存 `sType`、`sName` 和 `RECORD_TYPE type`、
`RECORD_NAME name`（`XScanEngine/xscanengine.h:996-1012`）。
`DiE_ScriptEngine::_setResult` 原样写入两个字符串，再分别调用
`recordTypeStringToId` 和 `recordNameStringToId`
（`die_script/die_scriptengine.cpp:668-678`）。

type 反向查表前会转大写、删除空格与连字符，并剥离开头的 `~` 或 `!`；
name 会转大写并删除空格与连字符。表项比较还会忽略 `/` 和 `\`。
对应实现位于 `XScanEngine/xscanengine.cpp:3837-3903`，type/name 表分别始于
`:194` 和 `:254`。未识别字符串返回数值 0；越界数值投影为 `Unknown`。

`RECORD_NAME_UNKNOWN0` 至 `RECORD_NAME_UNKNOWN9` 是十个连续且不同的保留
数值槽位，字符串都投影为 `_Unknown`
（`XScanEngine/xscanengine.cpp:1042-1051`）。因此 Rust 模型不能仅按显示字符串
合并这些枚举，也不能把 enum 0 自动等同于 `bIsUnknown=true`。

## Fixture

[`generate_result_enum_fixture.py`](../../tools/corpus/generate_result_enum_fixture.py)
生成 37-byte 安全 Binary 输入、空数据库和三条隔离规则：

| case | 原始 type | 原始 name | 用途 |
| --- | --- | --- | --- |
| known alias | `PE-Tool` | `7 ZIP` | 非规范拼写映射到已知枚举 |
| heuristic prefix | `~format` | `7-Zip` | 保留前缀，同时映射 Format |
| custom raw | `Vendor-Custom` | `Project/Custom` | 保留未知原文及 enum 0 |
| unknown fallback | `Unknown` | `Unknown` | 空数据库产生真实 unknown |

逐文件大小和 SHA-256 见
[`result-enum-fixture.json`](data/result-enum-fixture.json)。所有输入和规则均由
本项目生成。

## Runtime 观察

固定 Linux amd64 Qt5 报告为
[`result-enums-engine-qt5.json`](data/result-enums-engine-qt5.json)：

| case | type 原文 → 数值/规范值 | name 原文 → 数值/规范值 | unknown |
| --- | --- | --- | ---: |
| known alias | `PE-Tool` → 29 / `PE Tool` | `7 ZIP` → 4 / `7-Zip` | false |
| heuristic prefix | `~format` → 13 / `Format` | `7-Zip` → 4 / `7-Zip` | false |
| custom raw | `Vendor-Custom` → 0 / `Unknown` | `Project/Custom` → 0 / `Unknown` | false |
| unknown fallback | `Unknown` → 0 / `Unknown` | `Unknown` → 0 / `Unknown` | true |

直接映射对照进一步确认 `PE Tool`、`pe-tool`、`PETOOL`、`~PE Tool`、
`!pe-tool` 均映射 type 29，`7-Zip`、`7 ZIP`、`7zip` 均映射 name 4。
十个 `_Unknown` 保留槽位为 800–809，字符串反向映射 `_Unknown` 只返回 800。
越界 type 74 和 name 826 均投影 `Unknown`。

四次扫描均成功加载且错误数为 0。原始 stdout 为 5,882 bytes，SHA-256
`77e9292c24ddd890f704339a3b3b4dfa9fc0fc210c93925563ed064fbaf14bad`；
stderr 为空。结构化报告绑定 fixture manifest、generator、image、binary 和
全部组件 commit/hash。

## 兼容约束

Rust 内部结果模型至少需要同时表达：

- 原始 type/name 字符串；
- 数值 type/name 枚举或等价的稳定表示；
- 由固定表产生的规范字符串；
- 与 enum 0 独立的 unknown 布尔标记。

规范化输出不得把 custom raw 与 unknown fallback 合并，也不得把十个
`_Unknown` 数值槽位折叠为同一 identity。未知或越界 enum 的策略若偏离上游，
必须通过 ADR 和显式回归用例记录。

## 复现

```sh
python tools/corpus/generate_result_enum_fixture.py \
  /tmp/diec-result-enum-fixture

docker build \
  -f tools/upstream/Dockerfile.result-enums-harness-qt5 \
  -t diec-rust/result-enums-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_result_enums_harness.py \
  --fixture-dir /tmp/diec-result-enum-fixture \
  --raw-dir /outside/repository/result-enums-raw \
  --output docs/research/data/result-enums-engine-qt5.json
```

构建从固定 CMake Qt5 oracle 派生且不下载依赖；运行使用 `--network=none`。
原始 stdout/stderr 保存在仓库外。九项关系断言全部通过，
`CAP-RESULT-005` 的 Linux Qt5 状态可提升为 runtime-observed。
