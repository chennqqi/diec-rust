# PE debug-data 枚举与 scanner 分派边界

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 结论

`CAP-NEST-007` 已由同一 PE 输入上的成对运行时实验关闭：

- Formats 层从父 PE 同时枚举出 offset 608 的 Manifest resource 和 offset
  1088 的 CodeView/RSDS debug-data file part；
- 发布 engine 的 recursive+aggressive scanner 对 resource 建立 Binary child，
  原样 `win_resources.1.sg` 产生 `Manifest[Resources]`；
- 同一次公共扫描不建立 `FILEPART_DEBUGDATA` child，也不产生 `PDB file link`；
- 把刚才枚举出的同一组 38-byte RSDS 字节以
  `FILEPART_DEBUGDATA` context 直接交给原样
  `debug_data_debugData.1.sg`，会产生
  `debug data / PDB file link / 7.0`。

因此，上游契约不是“无法识别 debug data”，而是“格式层可表示、规则层可检测，
普通 recursive scanner 不调度该 file part”。Rust legacy-compatible scanner
若默认增加 debug-data child 和 PDB detection，会产生上游没有的可观察结果。

## 2. 固定身份与源码边界

| 组件 | Commit |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Formats | `1151e7254fdee3c0294ff7095edbdd7bfccf8201` |
| XScanEngine | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| die_script | `5d82316c110abf0eb863b50bc679d330e05067b6` |
| Detect-It-Easy rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |

固定
[`XPE::getFileParts()`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/exec/xpe.cpp#L11094)
在请求 `FILEPART_DEBUGDATA` 时读取 PE debug directory；只接纳 type 0/2、
有效 `PointerToRawData` 和有效 size，并生成带实际 offset/size 的
`FILEPART_DEBUGDATA`。

固定
[`XScanEngine::scanProcess()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp#L2932)
的普通嵌套路径只向 `XFormats::getFileParts()` 请求：

- resource：`FILEPART_RESOURCE`；
- overlay：`FILEPART_OVERLAY`。

该固定源文件没有 `FILEPART_DEBUGDATA` token。既有
[`subdevice-source-audit.json`](data/subdevice-source-audit.json) 已绑定完整
Formats/XScanEngine source SHA 和相关行；本实验在其上增加同输入运行时证据。

原样规则：

| 规则 | SHA-256 | 条件 |
| --- | --- | --- |
| `db/Binary/win_resources.1.sg` | `2fdad41d666d32467cabe83dae7d16625ade5935e3061c58dfefeb1fb7b99db7` | `Binary.isResource()` 且 scan ID `24` |
| `db/Binary/debug_data_debugData.1.sg` | `381b6259b239f2633b92fbd84fd0d99b972751e20cab12b6e09139a260f1f47d` | `Binary.isDebugData()` 且前四字节为 `RSDS` |

## 3. 同输入 paired fixture

[`generate_debug_dispatch_fixture.py`](../../tools/corpus/generate_debug_dispatch_fixture.py)
生成 1536-byte PE32：

| Part | PE 声明 | File offset / size | Payload SHA-256 |
| --- | --- | ---: | --- |
| Resource | RT_MANIFEST / ID 24 | 608 / 20 | `96f63fca235e4a359900fa17b076d2cb3d16945855b25fcb3c391eb49215428b` |
| Debug data | IMAGE_DEBUG_TYPE_CODEVIEW / type 2 | 1088 / 38 | `f4062413bf0504b8eb9b30dc76d27a576f75827f0b13822a43eea00706709e5f` |

完整样本 SHA-256 为
`58e2b8e73ba187977564e719d39022079b8fb9172c5bcdf40c495ed825b38ea1`。
内容完全由项目生成，不含第三方样本字节；PE data directory、section、
resource tree、debug directory 和 RSDS payload 的字段测试固定在
[`debug-dispatch-fixture.json`](data/debug-dispatch-fixture.json)。

选择同一父 PE、同时放置两类 file part 是实验的关键。Manifest child 是发布
scanner 确实进入嵌套分派的正控制；不能用两个无关输入分别证明 resource 与
debug-data 行为。

## 4. Paired harness

[`debug_dispatch_harness_main.cpp`](../../tools/upstream/debug_dispatch_harness_main.cpp)
按以下顺序运行：

1. 校验样本及两条原样规则 SHA-256；
2. 对父 PE 调用真实 `XFormats::getFileParts(RESOURCE | DEBUGDATA)`；
3. 对同一文件调用 public `DiE_Script::scanFile()`，开启 recursive 和
   aggressive，加载固定三层数据库；
4. 从步骤 2 的 debug part offset/size 提取实际字节；
5. 保持 `FILEPART_DEBUGDATA` parent context，并用
   `sSignatureName=debug_data_debugData.1.sg` 调用真实 private
   `processDetect()`，关闭 Unknown fallback。

private access shim 只影响 harness translation unit 的 C++ access check；
固定 engine object 和规则字节均未修改。这个直接入口是正控制，不冒充公共
scanner API。

## 5. 运行结果

机器报告：
[`debug-dispatch-engine-qt5.json`](data/debug-dispatch-engine-qt5.json)。

### Format enumeration

| File part | Enum | Offset | Size | 附加字段 |
| --- | ---: | ---: | ---: | --- |
| Resource | 64 | 608 | 20 | resource ID `24` |
| Debug data | 128 | 1088 | 38 | debug type name `2` |

### Public recursive+aggressive scan

公共扫描得到两个 record：

1. 父 PE header record：
   `debug data / Records / info=CodeView`，规则 `_debug_data.5.sg`；
2. Resource child：
   `format / Manifest / info=Resources`，规则 `win_resources.1.sg`。

第一个结果是“父 PE 包含 CodeView 目录”的 header metadata，不是 debug-data
child。两个公共 record 的 `id.filePart`/`parentId.filePart` 均不是
`Debug data`，且没有 `PDB file link`。

### Direct enumerated debug context

direct case 的 source part 与 Formats 枚举结果逐字段相等。唯一 record 为：

```text
type=debug data
name=PDB file link
version=7.0
signature=debug_data_debugData.1.sg
id.filePart=Debug data
parentId.filePart=Debug data
parentId.offset=1088
parentId.size=38
```

枚举、数据库加载、公共扫描和 direct case 均未取消且 error count 为 0。九项
关系断言全部通过。

本次 oracle：

- image ID：
  `sha256:e146f7e8941b144e326da0e092846cf1536d1b15d5047eb8e7d36058c9943a08`；
- harness binary SHA-256：
  `2e3690cc8a60ab1adcca465316ac2de75ea76fc07002094f31b6b0ec47ffde5d`；
- raw stdout：5010 bytes，
  SHA-256 `6068b2b4d1a322b2ba398546e865ba0dbdfd269da99d935fdaa2f8538c22f0cd`；
- raw stderr：0 bytes，
  SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

运行限制为无网络、1 CPU、512 MiB memory、128 PIDs；夹具只读挂载。原始
stdout/stderr 保存到外部 `--raw-dir`，版本化报告绑定 generator、manifest、
harness source、Dockerfile、image、binary、规则和原始流哈希。

## 6. Rust 兼容约束

后续 Rust 格式层应保留 debug directory 的 file-part 表示能力，但扫描策略需
与表示能力分离：

- legacy 默认 recursive 路径只调度 resource/overlay；
- 若未来提供显式 debug-data child scan，应作为新选项或扩展模式，不得静默
  改变兼容默认；
- 结果模型必须能区分父 PE 的 debug metadata record 与真正
  `FILEPART_DEBUGDATA` child；
- 差分测试使用本页同输入三段关系，而不是只检查是否出现字符串
  `debug data`。

## 7. 复现

```text
python tools/corpus/generate_debug_dispatch_fixture.py <fixture-dir>

docker build --network=none \
  -f tools/upstream/Dockerfile.debug-dispatch-harness-qt5 \
  -t diec-rust/debug-dispatch-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_debug_dispatch_harness.py \
  --fixture-dir <fixture-dir> \
  --committed-manifest docs/research/data/debug-dispatch-fixture.json \
  --raw-dir <raw-dir> \
  --output docs/research/data/debug-dispatch-engine-qt5.json

python -m unittest discover -s tools/tests \
  -p "test_*debug_dispatch*.py"
```
