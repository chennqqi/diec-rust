# Formats/xsimd 最终 ELF 源码与许可证闭包

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux x86_64、Qt 5、CMake Release oracle 的最终 `diec` 链接行包含
`Formats/xsimd` 产生的三个静态 archive：

| Archive | 唯一 member | 最终 ELF 全局符号见证 |
| --- | --- | ---: |
| `libxsimd.a` | `xsimd.c.o` | 41 |
| `libxsimd_avx2.a` | `xsimd_avx2.c.o` | 24 |
| `libxsimd_sse2.a` | `xsimd_sse2.c.o` | 24 |

三个 member 均实际进入最终非 stripped ELF，不只是被写在 link line。对应三个
编译源及 `.o.d` 的 Formats 内依赖并集恰为六个文件：

```text
xsimd/src/xsimd.c
xsimd/src/xsimd.h
xsimd/src/xsimd_avx2.c
xsimd/src/xsimd_avx2.h
xsimd/src/xsimd_sse2.c
xsimd/src/xsimd_sse2.h
```

六个文件都包含同一 horsicq copyright 与完整 MIT permission marker。组件根
`Formats/LICENSE` 也保留相同 copyright/MIT 文本，但它不是编译器 dependency；
发布归属不能仅靠 `.o.d` 自动发现。其 SHA-256 为：

```text
5f1133d595966880a5c4af69f448d5cc6ebbad6989033bb2f8c2c874e861c5ca
```

`xsimd_cuda.cu` 与 `xsimd_cuda.h` 不在本次 Linux Qt5 闭包。这里的 xsimd 是
Formats 内的 horsicq C 实现，不应与同名第三方 C++ xsimd 项目混同。

机器证据位于
[`data/xsimd-license-closure-linux.json`](data/xsimd-license-closure-linux.json)。
这是技术来源/许可证据，不是法律批准；`P0-BLOCK-004` 继续保持 Open。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Formats | `1151e7254fdee3c0294ff7095edbdd7bfccf8201` |
| source image | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| image revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| component lock SHA-256 | `9fabcaf6a0062fcae7007ea5af13a98876e8a6e08b3e2e4727fdff06d974c63c` |
| link line SHA-256 | `b2a4c7953997137d45f06eb3541d5da2efe127e85905c62311f5e03e5a500afb` |
| final ELF SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |

报告同时 hash-bind 三个 archive：

| Archive | SHA-256 |
| --- | --- |
| `libxsimd.a` | `191e4d13d5b522459f77df9f492d7d9a6a146c603d7a5c3acc97e8e117e1a77b` |
| `libxsimd_avx2.a` | `03b5de490217c929903691b545d13922aba4903c7b5491d46bf29f884d572e9e` |
| `libxsimd_sse2.a` | `eab901e6c823ab49dc86ad4d744348cf5a92f1732e084eee102bde897e273a15` |

## 方法

[`audit_xsimd_license_closure.py`](../../tools/upstream/audit_xsimd_license_closure.py)
先检查本地 OCI image revision，再以 `--network=none` 和只读 repository mount
进入固定 image：

1. 校验 DIE-engine、Formats 与 `components.lock.toml` 的 commit；
2. 解析 `src/console/CMakeFiles/diec.dir/link.txt`，要求三个 archive 各出现一次；
3. 用 `ar t` 要求每个 archive 恰含预期的一个 member；
4. 用 `nm -g --defined-only` 比较 member 与最终 ELF 的全局 defined symbols；
5. 仅接纳具有符号交集的 member，并解析其 `.o.d`；
6. 将 Formats 内依赖规范化、去重、逐文件记录大小、SHA-256 和 marker；
7. 单独保留不在编译依赖中的根 LICENSE。

复现：

```powershell
python tools\upstream\audit_xsimd_license_closure.py `
  --output docs\research\data\xsimd-license-closure-linux.json

python -m unittest discover -s tools\tests `
  -p test_xsimd_license_closure.py
```

审计器对 commit、image revision、link token、archive member、符号见证、依赖
文件数、marker 和 CUDA 排除关系 fail closed。报告不保存本机或 `/opt` 路径。

## 对 Rust 设计的约束

- Rust 可以采用不同 SIMD 实现，但必须以固定行为差分证明 byte/pattern/string
  搜索结果及边界一致，不能因替换 backend 缩小兼容范围。
- 若复用或翻译这六个上游文件，必须保留 Formats MIT/copyright 归属；若采用
  Rust crate，则对最终 feature/target dependency graph 独立生成 SBOM/NOTICE。
- Linux scalar/SSE2/AVX2 闭包不能外推到 Windows、macOS、Qt6、qmake 或 CUDA。
- archive 出现在 link line 不足以证明贡献；后续闭包应继续保留 member 级符号
  见证或等价 link-map 证据。

## 尚未完成

- Windows、macOS、Qt6 与 qmake 的 XSIMD build/member 闭包；
- 不同 CPU feature/topology 下 scalar、SSE2、AVX2 的选择与性能基线；
- 最终 Rust SIMD backend、feature 组合及发布 SBOM/NOTICE；
- 发布/法律责任人的书面组合评审。
