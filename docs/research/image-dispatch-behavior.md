# 非 JPEG/PNG 图像分派行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 1. 结论

固定 Linux Qt5 engine oracle 已闭合 `CAP-GAP-012`。项目生成的 BMP、GIF、TIFF、
ICO、CUR、ICC 和 WebP 七类安全语料均被 Formats 层识别为 `Image + 具体类型`，
但上游 `scanProcess()` 没有这些具体类型的分派分支，因此自然扫描全部初始化为
`Binary`：

| 类型 | Formats filetypes | 自然分派记录 |
| --- | --- | --- |
| BMP | `BMP, Binary, Image` | Binary `Windows Bitmap` |
| GIF | `Binary, GIF, Image` | Binary `Unknown` |
| TIFF | `Binary, Image, TIFF, Text, UTF8` | Binary `Tagged Image File Format (.TIFF)` |
| ICO | `Binary, ICO, Image, Text, UTF8` | Binary `Windows Icon` |
| CUR | `Binary, CUR, Image, Text, UTF8` | Binary `Unknown` |
| ICC | `Binary, ICC, Image` | Binary `Unknown` |
| WebP | `Binary, Image, RIFF, Text, UTF8, WebP` | Binary `WebP` |

`SCAN_OPTIONS.fileType=FT_IMAGE` 会把每个集合过滤为唯一 `Image` 并到达通用 Image
分支；但 `die_script` 只为 JPEG/PNG 创建 Image adapter。七类输入的 `Image`
全局对象因此均为 null，`Image/_Image.0.sg` 第 7 行产生完全相同的 TypeError，
随后返回一个 `filetype=Image` 的 Unknown record。scan state 仍为 success。

这不是 Rust 应“修正掉”的实现细节，而是固定上游的可观察兼容行为。未来若选择
更安全或更有用的行为，必须通过 ADR、精确差分 waiver 和回归测试显式偏离。

机器报告为
[`image-dispatch-engine-qt5.json`](data/image-dispatch-engine-qt5.json)。

## 2. 固定源码证据

| 组件 | Commit | 位置 | 事实 |
| --- | --- | --- | --- |
| Formats | `1151e7254fdee3c0294ff7095edbdd7bfccf8201` | `xformats.cpp:1725-1748` | PNG/JPEG/GIF/BMP/TIFF/ICO/CUR/ICC 插入 `FT_IMAGE` 和具体类型 |
| Formats | 同上 | `xformats.cpp:1765-1770` | WebP 插入 `FT_RIFF`、`FT_IMAGE`、`FT_WEBP` |
| Formats | 同上 | `xbinary.cpp:13965-13990` | `filterFileTypes(..., FT_IMAGE)` 只保留 `FT_IMAGE` |
| XScanEngine | `dfe4a419e4f491bb23688ba03c5a5bf39e34da83` | `xscanengine.cpp:2757-2762` | 只有 JPEG/PNG 有具体 image 分支 |
| XScanEngine | 同上 | `xscanengine.cpp:2799-2801` | 通用 Image 仅在集合大小为 1 时分派 |
| die_script | `5d82316c110abf0eb863b50bc679d330e05067b6` | `die_scriptengine.cpp:147-163` | FT_IMAGE adapter 只实现 JPEG/PNG，其他类型保留 null TODO |
| rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` | `db/Image/_Image.0.sg:7` | verbose 路径调用 `Image.getFileFormatName()` |

自然检测的集合包含 `Binary`，部分极小结构也包含 `Text/UTF8`；这些附加类型原样
进入机器报告，不能在规范化时删除。最初的零填充 GIF 正例因同时命中 Text 而被
`XBinary` 后处理删除 GIF；最终生成器使用非文本 padding，明确证明固定验证器的
异常 `size > 0x320` 边界而不触发该无关路径。

## 3. 实验设计

[`generate_image_dispatch_fixture.py`](../../tools/corpus/generate_image_dispatch_fixture.py)
只用 Python 标准库生成七个小型文件，不包含第三方样本 bytes。manifest 固定：

- capability：`CAP-DISPATCH-007`；
- closure：`CAP-GAP-012`；
- 7 个文件的 path、specific filetype、size 和 SHA-256；
- manifest SHA-256：
  `77e2e743897d9c85ed7c539b1213ce1270bf43aa2cf976a3bf470bdd185a9238`。

[`image_dispatch_harness_main.cpp`](../../tools/upstream/image_dispatch_harness_main.cpp)
只替换固定 CMake console 的 `main_console.cpp.o`，链接其余未修改 engine objects。
它加载原始三层规则，对每个输入执行：

1. `XFormats::getFileTypes(..., true)`；
2. 对副本调用 `filterFileTypes(..., FT_IMAGE)`；
3. `fileType=FT_UNKNOWN` 的自然 `scanDevice`；
4. `fileType=FT_IMAGE` 的强制 `scanDevice`。

probe 严格验证七类闭集、输入 hash、detector set、自然/强制 initial filetype、
record、error 文本、scan state、镜像内 generator/harness 与仓库 bytes，以及
以下身份：

| 项目 | 值 |
| --- | --- |
| image | `sha256:41bf8553a48e84b759e09d77079e6682f08d44d9d89c38da4b3dbd12f8e5c0dd` |
| harness binary SHA-256 | `ce9ec2200afdd2531c2c42ec5e00ad1fc427e0282287524cf4b3c0f2f9fed6d3` |
| raw stdout | 14,387 bytes / `818a5121bbbbf8f26b73aa646c04f3c454064165fa00d21e97bf1e25b2c59fc7` |
| Qt | `5.15.13` |

## 4. 可重复执行

```powershell
docker build --network none `
  -f tools\upstream\Dockerfile.image-dispatch-harness-qt5 `
  -t diec-rust/image-dispatch-harness-qt5:74eaf505 tools

$raw = Join-Path $env:TEMP diec-image-dispatch-raw
$report = Join-Path $env:TEMP image-dispatch-engine-qt5.json
python tools\upstream\probe_image_dispatch_harness.py `
  --raw-dir $raw `
  --output $report

python -m unittest discover -s tools\tests `
  -p "test_*image_dispatch*.py" -v
```

Docker base 以
`diec-rust/upstream-oracle-cmake:74eaf505@sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
固定，构建和运行均断网。raw stdout/stderr 保存到调用方指定的未跟踪目录；提交的
机器报告只保存长度、hash 和已解析结构。

## 5. 覆盖范围

本实验与既有 JPEG/PNG baseline 合并后，已覆盖上游 Image 分派族的全部公开成员：

- JPEG、PNG 的专用 engine/rule adapter；
- GIF、BMP、TIFF、ICO、CUR、ICC 和 WebP 的自然 Binary fallback；
- 七类输入经 engine option 强制进入 generic Image 的 null-adapter 错误。

因此 Linux Qt5 的 `CAP-DISPATCH-007` 从 `observed_with_gaps` 提升为 `observed`，
`CAP-GAP-012` 从开放清单删除。该结论不外推到 Linux Qt6、Windows 或 macOS；
这些平台仍由 `CAP-GAP-007` 的完整平台矩阵门禁覆盖。
