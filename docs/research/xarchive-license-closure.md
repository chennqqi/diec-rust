# XArchive CLI 编译闭包与文件级许可证证据

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 范围与结论

本轮以固定 Linux Qt5 CMake Release 构建树为证据，把 `diec` 链接行、对象依赖
文件和 XArchive 固定源码关联起来。XArchive 固定到
`0fcd4e8d3e9933baac3b12246d82ac026557ffd0`。

`diec` 的 XArchive 构建/link-input 闭包包含：

- 84 个直接编译进 `diec` 的 XArchive C++ 单元，其中 32 个位于 `Algos/`；
- 四个 link-line archive 构建的 22 个 C 单元：bzip2 8、LZMA 2、PPMd 4、zlib 8；
- 合计 106 个唯一编译源文件；
- 展开 `.o.d` 后，合计 217 个 XArchive 源码/头文件依赖；
- 最终链接行没有 XYara/YARA。

机器报告为
[`data/xarchive-license-closure-linux.json`](data/xarchive-license-closure-linux.json)。
它逐项保存编译源、链接方式、dependency file、闭包文件 hash、许可证/来源标记，
并固定 link line、image、component lock 和生成器 hash。

后续 [`xarchive-final-link-closure.md`](xarchive-final-link-closure.md) 已通过
byte-identical 链接重放和 GNU ld map 进一步区分构建与抽取：22 个 archive
member 中仅 `liblzma.a(LzmaDec.c.o)` 进入最终 ELF。因此最终 XArchive
compile-source contribution 是 84 个直接对象加 1 个 archive member，共 85 个；
本页 106/217 仍作为构建、源码和许可证候选闭包保留。

## 文件级许可证证据

报告从 217 个闭包文件中识别以下非互斥标记：

| 标记 | 文件数 | 证据含义 |
| --- | ---: | --- |
| MIT permission text | 167 | XArchive 自有包装和 decoder 文件中的 MIT 文本 |
| Public Domain | 23 | 7-Zip/LZMA/PPMd 派生文件中的明确声明 |
| bzip2 copyright | 12 | Julian Seward/bzip2 声明 |
| zlib notice | 9 | Jean-loup Gailly/Mark Adler 声明 |

“文件数”是字符串证据计数，不是 SPDX 分类：同一聚合文件可以同时含 MIT 与第三方
声明，缺少已知字符串也不能证明没有许可证义务。

报告另固定五个代表性许可证证据：

- `LICENSE`：XArchive 根 MIT；
- `3rdparty/bzip2/src/LICENSE`：bzip2 redistribution 条款；
- `3rdparty/lzma/src/LzmaDec.c`：Igor Pavlov Public Domain；
- `3rdparty/ppmd/src/Ppmd7.c`：Igor Pavlov/Dmitry Shkarin Public Domain；
- `3rdparty/zlib/src/zlib.h`：zlib notice。

## 聚合源码归属

`Algos/brotlideclib.cpp` 和 `Algos/zstddeclib.cpp` 都实际编译进 `diec`。文件内容分别
具有明显 Brotli/Zstandard 来源标记，但全文未匹配版权、许可证、redistribution、
MIT、BSD、Apache 或 Public Domain 声明，XArchive tree 也没有与它们对应的独立
LICENSE 文件。

[`embedded-compression-origins.md`](embedded-compression-origins.md) 已进一步
固定 Brotli `v1.2.0` MIT 与 Zstandard `1.6.0-dev@5c7b7bad` BSD/GPLv2 官方
来源：Zstandard 聚合代码 token 精确一致，Brotli 64-token 覆盖率为 98.60%。
当前未关闭项不再是“来源类型未知”，而是 XArchive 剥离声明且未保存两个官方
许可证，以及 Brotli 剩余约 1.4% token 尚未逐段归类。

同一闭包中的 `Algos/xrardecoder.cpp/.h` 已由
[`rar-decoder-provenance.md`](rar-decoder-provenance.md) 单独追溯：固定
decoder 的 26,627 个 token 与 UnRAR 7.1.10 在 12-token 下覆盖 94.21%，
64-token 下仍覆盖 74.21%，跨 17 个长连续唯一来源文件。XArchive 文件只携带
horsicq MIT，没有 UnRAR 修改分发 notice。该证据禁止本项目在书面评审前直接
复制或翻译 decoder，但不构成法律结论。

`xdeflatedecoder.cpp`、`xbzip2decoder.cpp` 和 `xalgo_local.h` 也是聚合源码，但其中
保留了 MIT 包装声明及对应 zlib、bzip2 或 Public Domain 文本；它们仍需发布责任人
复核组合义务，证据强度高于上述两个无声明文件。

## 方法与复现

工具
[`audit_xarchive_license_closure.py`](../../tools/upstream/audit_xarchive_license_closure.py)
在固定 source image 中：

1. 校验 OCI revision、主仓库 commit、XArchive gitlink 和 component lock；
2. 解析 `src/console/CMakeFiles/diec.dir/link.txt`；
3. 将 84 个直接对象映射回源码；
4. 对链接的四个 XArchive archive 展开 22 个 `.o.d`；
5. 从全部 dependency files 收集 XArchive 内部源码/头文件；
6. 保存原始文件 hash 和保守的文本标记，不自动给出法律结论。

```powershell
python tools\upstream\audit_xarchive_license_closure.py `
  --output docs\research\data\xarchive-license-closure-linux.json
```

容器禁网，仓库只读挂载；报告不含时间和本机路径，可逐字节复现。

## 限制与后续

- 当前只证明固定 Linux Qt5 CMake Release CLI；qmake、Qt6、Windows、macOS 和
  GUI/all-target closure 仍需分别验证。
- `.o.d` 证明编译依赖，link line 证明对象/archive 输入；member 抽取已由后续
  GNU ld map 报告闭合，但不判断 section GC、LTO 或最终机器码 reachability。
- 文本 marker 是审计线索，不替代 SPDX/license 法律复核。
- XYara 未进入本次 CLI 产物，但默认全目标构建会生成 YARA archive，仍需独立
  文件级许可证清单。
- Rust 实现若不复制这些聚合文件，可选择来源和许可证清晰的 archive crate；
  行为兼容性仍必须通过固定语料差分证明。
