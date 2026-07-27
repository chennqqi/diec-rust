# SCAN_RESULT 列表行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

本页固定 `CAP-RESULT-002` 的 `listRecords`、`listErrors`、
`listDebugRecords` 和 `listHandlers` 四个独立结果列表。组件身份：

- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- die_script：`5d82316c110abf0eb863b50bc679d330e05067b6`

## 源码事实

四个列表在 `XScanEngine/xscanengine.h:1041-1050` 中分别声明，不共享存储或
字符串通道：

- detection 由规则执行路径写入 `listRecords`；
- `_handleError` 将 parse/runtime error 写入 `listErrors`；
- `DiE_Script::_handleElapsedTime` 仅在 `bShowScanTime` 时逐执行规则追加
  `DEBUG_RECORD`（`die_script/die_script.cpp:315-326`）；
- collection copy/move 在
  `XScanEngine/xscanengine.cpp:3121-3129` 通过 `XHandler::addRecord_Copy` 或
  `addRecord_Move` 写入 `listHandlers`。

`XHandler::RECORD` 保存命令 enum 和 source/destination option map
（`Formats/xhandler.h:29-53`）。普通 `scanFile` 只返回这些计划记录；
`XScanEngineProcess` 才会调用 `XHandler::processRecords` 执行副作用。因此
研究 harness 可以观察 handler，而不复制、移动或删除输入文件。

嵌套扫描会把 child 的 records/errors/debug records 追加回父结果
（`xscanengine.cpp:2789-2828, 2901, 2997-2999`），但 handler 不走这条追加
路径。Rust 结果模型不能把四个列表互相推导，也不能从 CLI stderr 反推
`listErrors`。

## Fixture 与 harness

[`generate_result_list_fixture.py`](../../tools/corpus/generate_result_list_fixture.py)
生成 37-byte Binary 输入及四条安全规则：

1. `a_first.1.sg` 与 `b_second.1.sg` 字节完全相同，产生完全相同的
   `format / Duplicate / 1 / same` detection；
2. `c_runtime_error.1.sg` 抛出固定 `Error`；
3. `d_parse_error.1.sg` 包含固定语法错误。

逐文件大小和 SHA-256 见
[`result-list-fixture.json`](data/result-list-fixture.json)。fixture 完全由本项目
生成，不包含第三方样本或规则字节。

[`result_lists_harness_main.cpp`](../../tools/upstream/result_lists_harness_main.cpp)
执行两个控制：

| case | signature filter | scan time | collection copy |
| --- | --- | --- | --- |
| `default_success` | 仅第一条成功规则 | off | off |
| `all_lists` | 全部四条规则 | on | on |

serializer 逐字段导出四个列表；handler 只读取，不调用 `processRecords`。
collection destination 使用固定
`/tmp/diec-result-list-collection/files/duplicate.bin`。

## Runtime 观察

固定 Linux amd64 Qt5 报告为
[`result-lists-engine-qt5.json`](data/result-lists-engine-qt5.json)。

- 默认 case：1 个 record，errors/debug/handlers 均为空。
- 综合 case：2 个完全重复 detection，signature 来源顺序为 first、second。
- errors 独立保存 runtime、parse 两条错误，顺序与规则执行顺序一致。
- debug records 覆盖全部四条规则，包括两条失败规则；本次 elapsed 均为
  0 ms。兼容断言只要求非 bool 整数且非负，不固定精确时间。
- handlers 保存两个完全相同的 `XHANDLER_COPY`（数值 2），未去重；source
  均为 `/fixture/input/probe.bin`，destination 均为固定 collection path。

原始 stdout 为 4,224 bytes，SHA-256
`40894aec1387bf0745981202f65b8e17cf0f8f9ae11d6387daae11a03641ec3f`；
stderr 为空。报告绑定 fixture manifest、generator、image、binary 和全部组件
commit/hash。

## 复现

```sh
python tools/corpus/generate_result_list_fixture.py \
  /tmp/diec-result-list-fixture

docker build \
  -f tools/upstream/Dockerfile.result-lists-harness-qt5 \
  -t diec-rust/result-lists-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_result_lists_harness.py \
  --fixture-dir /tmp/diec-result-list-fixture \
  --raw-dir /outside/repository/result-lists-raw \
  --output docs/research/data/result-lists-engine-qt5.json
```

Docker build 从已固定 CMake Qt5 oracle 派生，不下载依赖；运行使用
`--network=none`。原始 stdout/stderr 保存在仓库外，版本库只保存其大小和
SHA-256。

七项关系断言全部通过，`CAP-RESULT-002` 的 Linux Qt5 状态可提升为
runtime-observed。
