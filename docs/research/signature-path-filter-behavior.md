# Signature file path 过滤行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 结论与范围

`CAP-RULE-007` 的路径比较器已在固定 Linux Qt5、Linux Qt6 和原生 Windows
Qt5 engine 上运行观察，不再只是源码推断；Linux Qt6 对照见
[`qt6-signature-path-runtime-evidence.md`](qt6-signature-path-runtime-evidence.md)：

- 规则数据库把磁盘规则保存为绝对文件路径；
- 非空 filter 使用严格 `QString` 相等比较，不按 basename 匹配；
- 比较区分大小写，且不会先清理 `..` path segment；
- main/extra 中 basename 都为 `shared.1.sg` 的两条规则不会混淆，精确绝对路径
  只执行对应层的规则；
- 空 filter 执行两层普通规则；不存在路径、大小写变化路径、含 `..` 的等价
  文件系统路径和 basename-only filter 都不执行任何规则。

该参数不是公共扫描契约。固定版本的 protected `_processDetect()` 唯一转发点
始终传入空字符串，`SCAN_OPTIONS` 也没有 signature-file-path 字段。因此本实验
证明的是上游私有 comparator 的兼容语义和公共不可达边界，不表示 CLI 存在
按文件路径扫描规则的选项。

## 2. 固定源码事实

组件身份：

| 组件 | Commit |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Formats | `1151e7254fdee3c0294ff7095edbdd7bfccf8201` |
| XScanEngine | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` |
| die_script | `5d82316c110abf0eb863b50bc679d330e05067b6` |

固定
[`die_script.h`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.h)
把带 `sSignatureFilePath` 的 `processDetect()` 声明为 private。固定
[`die_script.cpp`](https://github.com/horsicq/die_script/blob/5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp#L109)
中的调用链为：

1. `processDetect()` 遍历已加载 `SIGNATURE_RECORD`；
2. `_shouldExecuteSignature()` 先检查 file type、signature name、deep 和
   heuristic gate；
3. 非空路径与 `signatureRecord.sFilePath` 直接比较，不相等就返回 `false`；
4. 随后才检查 main/extra/custom database gate；
5. protected `_processDetect()` 调用 private overload 时固定传 `""`。

固定
[`XScanEngine::_loadDatabaseFromPath()`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp)
使用目录项的 `absoluteFilePath()` 读取规则，并把同一值传给
`getSignaturesFromData()`。固定 `DiE_ScriptEngine::_setResult()` 又把当前规则
文件名写入 `SCANSTRUCT.varInfo2`，因此 harness 可直接导出实际执行规则的完整
路径，而不是从结果名反推。

## 3. 实验设计

### 3.1 安全夹具

[`generate_signature_path_fixture.py`](../../tools/corpus/generate_signature_path_fixture.py)
生成一个 38-byte 良性 Binary 输入，以及：

| 数据库层 | 路径 | 结果名 |
| --- | --- | --- |
| main | `main/Binary/shared.1.sg` | `main-path` |
| extra | `extra/Binary/shared.1.sg` | `extra-path` |

两条项目生成规则只有 `_setResult()`，basename 完全相同，内容和输出名不同。
逐文件大小与 SHA-256 固定在
[`signature-path-fixture.json`](data/signature-path-fixture.json)，不含第三方
样本或上游规则字节。

### 3.2 私有入口 harness

[`signature_path_harness_main.cpp`](../../tools/upstream/signature_path_harness_main.cpp)
先正常 include `die_scriptengine.h` 及依赖，再仅在 include `die_script.h` 时用
一次 `#define private public` 绕过 C++ access check。它不修改固定 engine
源码或对象文件，也不复制 comparator；随后直接调用真正的 private
`DiE_Script::processDetect()`。

[`Dockerfile.signature-path-harness-qt5`](../../tools/upstream/Dockerfile.signature-path-harness-qt5)
从已有固定 CMake oracle 镜像取编译和链接 flags，只替换 console main object。
运行时禁用网络，夹具只读挂载到固定 `/fixture`，`bAddUnknown=false`，所以
“零规则执行”不会被 Unknown fallback 掩盖。

## 4. 运行结果

Linux Qt5 机器报告：
[`signature-path-engine-qt5.json`](data/signature-path-engine-qt5.json)。

| Case | Filter | 结果 |
| --- | --- | --- |
| `empty_filter` | 空 | `main-path`、`extra-path` |
| `exact_main` | main 规则绝对路径 | 仅 `main-path` |
| `exact_extra` | extra 规则绝对路径 | 仅 `extra-path` |
| `missing` | 不存在的绝对路径 | 0 records |
| `case_mismatch` | `SHARED.1.SG` | 0 records |
| `dot_segment` | `Binary/../Binary/shared.1.sg` | 0 records |
| `basename_only` | `shared.1.sg` | 0 records |

七次执行均无 script error、未取消；数据库成功加载两条规则。空 filter 的两个
record 都导出 signature `shared.1.sg`，但 `signature_path` 分别为
`/fixture/main/Binary/shared.1.sg` 和
`/fixture/extra/Binary/shared.1.sg`。这组控制证明选择依据是保存的完整路径，
不是 basename 或结果名。

本次 oracle：

- image ID：
  `sha256:85fed5d13f1b41bea36ce6d3412bdf96da17f059187e3a758377aaa8be33a523`；
- harness binary SHA-256：
  `8f0554f121dcc5858cd1b56073a07cc6381caf61a87c5e26d5c100a1a417fa01`；
- raw stdout：3837 bytes，
  SHA-256 `1ef8d0913678d60050c0e99573fa9a07781b8292ec4c961f7164a740f7a563be`；
- raw stderr：0 bytes，
  SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

原始 stdout/stderr 保存在 probe 的外部 `--raw-dir`，不提交临时扫描输出。
版本化报告绑定 generator、manifest、harness source、Dockerfile、image、
binary 和原始流哈希。

## 5. Windows Qt5 配对结果

原生 Windows x86_64、Qt 5.15.2 使用相同 fixture 和共享 harness，七个 case
连续运行两轮，共 2 次 harness 进程执行、14 次 case observation：

- 两轮 raw stdout/stderr 哈希完全相同；
- 11/11 命名关系全部成立；
- 只把已验证 fixture 根前缀替换为 `/fixture` 后，完整结构化文档与固定
  Linux Qt5 报告相同；
- 未做大小写折叠、点段清理、basename 替换、case/record 删除或重排。

机器报告为
[`signature-path-engine-windows-qt5.json`](data/signature-path-engine-windows-qt5.json)，
SHA-256 为
`54e0d24e363cf86353365ea93fffeaf03a5dfadb9f32f0c976ec3234b646ad48`。
固定 harness binary 为 3,052,032 bytes，SHA-256
`cda13af7bb82a09e7957d4014bd94d8a800cc502ddea1d6e9e04eb1f0a9476d1`。

Windows 构建复用固定 qmake Release 的未修改 engine objects，只替换 console
main object。MSVC 把 access level 编入 decorated name：研究 translation unit
经 `private` access shim 引用 public-spelled symbol，而固定 `die_script.obj`
导出 private-spelled symbol。因此
[`build_windows_signature_path_harness.ps1`](../../tools/upstream/build_windows_signature_path_harness.ps1)
在研究链接步骤使用精确 `/alternatename` 映射；清单同时绑定原始 Makefile、
`main_console.obj` 和 `die_script.obj` 哈希，未重新编译或修改 engine object。

上游加载规则时由 `QFileInfo::absoluteFilePath()` 保存 `/` 分隔形式。Windows
采集器因此把已验证的绝对 fixture argument 以 Qt 的 `/` 拼写传入 harness，
避免由命令行 `\` 加手工 `/` 形成并非已加载 identity 的混合字符串。该步骤
不改写 filter 输出；大小写变化和 `..` 仍按原字符串传入并明确不命中。

## 6. Rust 兼容约束

后续实现若保留内部 path-filter 能力，应区分两个概念：

- 数据库 materialization 时形成的规则 identity path；
- 调用方传入的 filter string。

兼容模式必须在这两个字符串之间做严格相等比较，不能静默采用
canonicalization、case folding 或 basename fallback。公共 Rust API、CLI 和
C ABI 是否暴露该私有上游能力仍属于设计决策；无论是否暴露，内部差分测试都
应保留本实验的七行矩阵，避免重构时改变上游规则选择语义。

## 7. 复现

```text
python tools/corpus/generate_signature_path_fixture.py <fixture-dir>

docker build --network=none \
  -f tools/upstream/Dockerfile.signature-path-harness-qt5 \
  -t diec-rust/signature-path-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_signature_path_harness.py \
  --fixture-dir <fixture-dir> \
  --committed-manifest docs/research/data/signature-path-fixture.json \
  --raw-dir <raw-dir> \
  --output docs/research/data/signature-path-engine-qt5.json

python -m unittest discover -s tools/tests \
  -p "test_*signature_path*.py"
```

Windows 配对采集：

```powershell
powershell -File tools\upstream\build_windows_signature_path_harness.ps1 `
  -SourceDir <fixed-clean-source> `
  -BuildDir <fixed-qmake-build> `
  -QtDir <fixed-qt-5.15.2> `
  -VsDevCmd <VsDevCmd.bat> `
  -OutputBinary <harness.exe> `
  -OutputJson <build-manifest.json>

python tools\upstream\collect_windows_signature_path_harness.py `
  --binary <harness.exe> `
  --source-dir <fixed-clean-source> `
  --qt-dir <fixed-qt-5.15.2> `
  --fixture-dir <fixture-dir> `
  --working-dir <empty-working-dir> `
  --build-manifest <build-manifest.json> `
  --raw-dir <external-raw-dir> `
  --output docs\research\data\signature-path-engine-windows-qt5.json
```

重跑必须保持固定组件 SHA、manifest 逐字节一致、镜像 revision label、只读
夹具挂载和 `--network=none`；Windows 还必须保持固定 Qt、CLI、engine object
与 build manifest identity。任一 identity、十一项行为关系或跨平台完整文档
变化都应失败，不能只比较最终 record 数量。
