# XArchive 聚合 Brotli/Zstandard 来源与许可证追溯

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 结论

固定 CLI 编译闭包中的两个无声明聚合文件已追溯到官方源码：

| XArchive file | 固定官方来源 | 内容证据 | 官方许可证 |
| --- | --- | --- | --- |
| `Algos/brotlideclib.cpp` | `google/brotli@028fb5a23661f123017c060daa546b55cf4bde29`，tag `v1.2.0` | 文件宏为 1.2.0；64-token 指纹覆盖 98.6036%，唯一映射到 28 个 common/decoder/public header 文件 | MIT |
| `Algos/zstddeclib.cpp` | `facebook/zstd@5c7b7bad26808e6b40ac3b3d0075466e27738a9d` | 官方 `combine.py` 生成 90,410 个去注释 token；XArchive 内容精确为 `extern "C" {` + 全部官方 token + `}` | BSD 或 GPLv2 二选一 |

机器证据见
[`data/embedded-compression-origins.json`](data/embedded-compression-origins.json)。
两个 XArchive 文件都实际进入固定 `diec`，但都不含 `copyright`、`license`、
`redistribution`、MIT permission 或 Public Domain 文本。

因此“来源不明”已经收敛为“固定来源明确、许可证声明在聚合副本中缺失”。这不是
法律结论：在发布归属清单恢复前，R-002 仍为 Open。

## Brotli 1.2.0

XArchive 文件 SHA-256 为
`42289e96819b525d3dbb74e2812c0c5043d6fdaee10da10f87149625ebae5ed3`，
内部声明：

```text
BROTLI_VERSION_MAJOR 1
BROTLI_VERSION_MINOR 2
BROTLI_VERSION_PATCH 0
```

官方 [`v1.2.0`](https://github.com/google/brotli/tree/028fb5a23661f123017c060daa546b55cf4bde29)
commit 为 `028fb5a23661f123017c060daa546b55cf4bde29`。忽略注释和空白后：

- XArchive 文件共 296,486 个 C token；
- 12-token shingle 覆盖 295,463 个 token，覆盖率 99.6549%；
- 更严格的 64-token shingle 覆盖 292,346 个 token，覆盖率 98.6036%；
- 64-token 唯一指纹来自 28 个官方文件，全部位于 `c/common/`、`c/dec/` 和
  `c/include/brotli/`，完整 path/hash/count 保存在机器报告。

这证明它是 Brotli 1.2.0 decoder/common 源码的聚合与适配，但不是逐字节副本；
剩余 token 包括聚合 wrapper、预处理展开边界和局部适配，不能用 98.6% 覆盖率
声称每个 token 都来自官方文件。

官方 [`LICENSE`](https://github.com/google/brotli/blob/028fb5a23661f123017c060daa546b55cf4bde29/LICENSE)
是 Brotli Authors MIT 文本，SHA-256 为
`3d180008e36922a4e8daec11c34c7af264fed5962d07924aea928c38e8663c94`。
XArchive tree 没有保存该文本，根 MIT 的版权主体也不同，不能用一份根许可证去重。

## Zstandard 1.6.0 development snapshot

XArchive 文件 SHA-256 为
`61e7028570039c299dad5689483d82341f558388ba06f4b2c4819e0ba489e812`，
内部声明 1.6.0。官方 tag 清单在本次调研时没有 `v1.6.0`；该版本号由
Zstandard dev 分支在 `073c7fb6eaf4d121d3757d83d2433d413fe789ef` 更新，
不能把它写成正式 1.6.0 release。

固定对照 commit
[`5c7b7bad26808e6b40ac3b3d0075466e27738a9d`](https://github.com/facebook/zstd/tree/5c7b7bad26808e6b40ac3b3d0075466e27738a9d)
的官方
[`combine.py`](https://github.com/facebook/zstd/blob/5c7b7bad26808e6b40ac3b3d0075466e27738a9d/build/single_file_libs/combine.py)
和 `zstddeclib-in.c` 生成 decoder 单文件。忽略注释与空白后，生成物的 90,410
个 token 与 XArchive wrapper 内部完全相同；XArchive 只额外增加三个前缀 token
`extern "C" {` 和一个结尾 `}`。

官方生成物保留每个源文件的版权与双许可证提示，XArchive 聚合副本则移除了全部
注释。官方：

- [`LICENSE`](https://github.com/facebook/zstd/blob/5c7b7bad26808e6b40ac3b3d0075466e27738a9d/LICENSE)
  为 BSD 条款，SHA-256
  `7055266497633c9025b777c78eb7235af13922117480ed5c674677adc381c9d8`；
- [`COPYING`](https://github.com/facebook/zstd/blob/5c7b7bad26808e6b40ac3b3d0075466e27738a9d/COPYING)
  为 GPLv2，SHA-256
  `f9c375a1be4a41f7b70301dd83c91cb89e41567478859b77eef375a52d782505`；
- 源文件声明允许接收方在 BSD 与 GPLv2 中选择其一。

对本项目静态库发布而言，官方双许可提供 BSD 选择路径；采用该路径仍必须保留
BSD copyright、条件和 disclaimer。具体组合与发布义务由发布/法律责任人确认，
本文不作法律结论。

## 可重复方法

先取得两个固定官方 checkout：

```powershell
git clone --no-checkout https://github.com/google/brotli.git brotli
git -C brotli checkout 028fb5a23661f123017c060daa546b55cf4bde29

git clone --no-checkout https://github.com/facebook/zstd.git zstd
git -C zstd checkout 5c7b7bad26808e6b40ac3b3d0075466e27738a9d
```

再运行：

```powershell
python tools\upstream\audit_embedded_compression_origins.py `
  --brotli-root <brotli-checkout> `
  --zstd-root <zstd-checkout> `
  --output docs\research\data\embedded-compression-origins.json
```

host 端拒绝错误 commit、remote 或 dirty checkout。比较在固定、禁网 Docker image
中完成，三个 source mount 均为只读；报告固定 image、生成器、官方生成脚本、输入
模板、许可证、官方来源文件和聚合文件 hash，不记录本机路径或时间。

## 对 Rust 实现和同步的约束

- 不直接复制 XArchive 的无声明聚合文件。
- 若使用 Brotli/Zstandard Rust crate 或 native backend，必须重新建立其
  feature-resolved source/license/SBOM 闭包，不能继承本报告作为许可结论。
- 若为兼容性临时复用聚合源码，必须携带两个独立的官方许可证与归属；Zstandard
  明确选择 BSD 或 GPLv2 路径，不允许留作隐含决定。
- 上游同步时重新运行 token 对照；版本宏、聚合 hash、官方来源或 wrapper 变化均
  需要 review。
- Brotli 剩余约 1.4% 的 64-token 未覆盖区仍需在“复制该源码”之前完成逐段分类；
  若 Rust 实现不复制它，可作为上游归属风险保留而不进入 Rust 发布闭包。
