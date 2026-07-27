# SCANSTRUCT ID 与父子关系

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

本页固定 `CAP-RESULT-004` 的 `SCANSTRUCT.id`、`parentId` 字段以及 resource
child 的层级关系。组件身份：

- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`
- die_script：`5d82316c110abf0eb863b50bc679d330e05067b6`

## 数据结构与创建路径

`SCANID` 在 `XScanEngine/xscanengine.h:995-1005` 定义八个字段：

- `sUuid`
- `fileType`
- `filePart`
- `sVersion`
- `sInfo`
- `nSize`
- `nOffset`
- `sOriginalName`

每个 `SCANSTRUCT` 同时保存 `id` 与 `parentId`
（`xscanengine.h:1007-1012`）。

`XScanEngine::createResultId` 每次 detection context：

1. 生成新 UUID；
2. 写入当前 file type；
3. 从设备取 init location 与 size；
4. 从 parent 继承 file part。

源码位置为 `XScanEngine/xscanengine.cpp:2503-2513`。规则结果和 Unknown fallback
都复制同一个 context `resultId` 与调用方 `parentId`
（`die_script/die_script.cpp:109-176`、
`die_script/die_scriptengine.cpp:662-678`）。

## Resource edge 的非直觉语义

resource/overlay 调度不是把 root ID 原样传给 child。scanner 先复制
`scanIdMain`，随后把副本的：

- `filePart`
- `nOffset`
- `nSize`

改写为 file-part edge 的值，再把该副本作为 child `scanProcess` 的 parent ID
（`XScanEngine/xscanengine.cpp:2978-2999`）。

因此 child parent 与 root ID：

- UUID 相等，用于锚定实际父节点；
- file type 相等；
- file part/offset/size 不相等，parent 上保存的是 child edge 元数据。

Rust 结果模型如果用完整 `SCANID` 相等寻找父节点会失败；关系键必须至少区分
UUID identity 与 edge metadata。

## Fixture 与 harness

复用项目生成的
[`nested-corpus.json`](data/nested-corpus.json) 中
`pe-manifest-resource.exe`：

- 1,024-byte PE32；
- offset 608、size 20 的 RT_MANIFEST resource；
- SHA-256
  `0a973cbde2f520bdbd6e1b75304e4a412462113d4de9a8139cdf997af16641ee`。

[`result_ids_harness_main.cpp`](../../tools/upstream/result_ids_harness_main.cpp)
使用无规则的 `DiE_Script`，开启 recursive/resource/aggressive scan，使 root
和 resource child 各产生一条 Unknown。harness 对 `id`、`parentId` 均原样
导出全部八个字段，并同时保留 file type/file part 的数值和字符串投影。

UUID 每次运行随机生成，报告保存原始值，但兼容断言不硬编码 UUID。

## Runtime 观察

固定 Linux amd64 Qt5 报告为
[`result-ids-engine-qt5.json`](data/result-ids-engine-qt5.json)：

| record | ID | Parent ID |
| --- | --- | --- |
| root | PE32 / Header / 0 / 1024 / UUID A | Unknown / Header / 0 / 0 / empty UUID |
| child | Binary / Resource / 608 / 20 / UUID B | PE32 / Resource / 608 / 20 / UUID A |

八项关系断言验证：

1. 两个 record 的 id/parentId 都保留完整字段集合；
2. 两条记录均为明确 Unknown；
3. UUID A/B 非空且不同；
4. root ID 描述完整 PE；
5. child ID 描述 resource Binary；
6. child parent UUID/file type 锚定 root；
7. child parent 携带 Resource edge，且明确不等于 root ID；
8. 扫描无错误且未取消。

原始 stdout 为 2,384 bytes，SHA-256
`8284bdafbb5ba866a0ee28b9a30e523891c905972c87a57e82dfbd662b65fe85`；
stderr 为空。报告绑定 nested manifest、generator、image、binary 和全部组件
commit/hash。

## 复现

```sh
python tools/corpus/generate_nested_corpus.py /tmp/diec-nested-corpus

docker build \
  -f tools/upstream/Dockerfile.result-ids-harness-qt5 \
  -t diec-rust/result-ids-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_result_ids_harness.py \
  --corpus-dir /tmp/diec-nested-corpus \
  --raw-dir /outside/repository/result-ids-raw \
  --output docs/research/data/result-ids-engine-qt5.json
```

构建从固定 CMake Qt5 oracle 派生且不下载依赖；运行使用 `--network=none`。
原始 stdout/stderr 保存在仓库外。

`CAP-RESULT-004` 的 Linux Qt5 状态可提升为 runtime-observed。
