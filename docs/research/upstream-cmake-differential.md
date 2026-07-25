# 上游 CMake CLI 基线与 qmake 差分

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-25

## 结论

固定上游的官方 Ubuntu 发布脚本使用 CMake Release。实验在 Linux amd64 和
Qt 5.15.13 环境中不修改源码地构建了 CMake `diec` 目标，并与先前的 qmake
产物执行六组逐字节 CLI 差分。

两个产物的文件哈希、大小、Build ID 和优化参数不同，但下列可观察结果完全相同：

- 退出码；
- stdout 原始字节；
- stderr 原始字节；
- `--version` 和 `--help`；
- 固定三个规则目录的 `--showdatabase`；
- 固定 `/usr/bin/true` 输入的 JSON 扫描；
- 无参数行为；
- 不存在路径的错误行为。

这支持将 CMake 产物作为 Linux 上游 oracle 的首选候选，并把 qmake 产物作为
交叉检查。当前语料过小且构建环境仍非 hermetic，因此文档保持 Draft。

## 上游发布路径

固定版本的
[`builder.yml`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/.github/workflows/builder.yml#L20-L36)
在 Ubuntu 24.04 上递归 checkout submodule、安装 Qt5 依赖并执行
`build_dpkg.sh`。

[`build_dpkg.sh`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_dpkg.sh#L14-L26)
使用：

```text
cmake -S <source> -B <build> -DCMAKE_BUILD_TYPE=Release
cmake --build <build> --parallel <nproc>
cmake --install <build> --prefix <stage>
```

本轮运行相同的 configure 参数，但只执行 `--target diec`，避免为 CLI 行为
基线编译 GUI 和 lite。`src/CMakeLists.txt` 在配置阶段仍无条件解析完整 Qt
组件和所有子项目，因此环境补充了 `libqt5opengl5-dev`；这不是源码修改。

## 固定环境与复现

新增构建入口：

[`tools/upstream/Dockerfile.oracle-cmake-qt5`](../../tools/upstream/Dockerfile.oracle-cmake-qt5)

| 输入 | 值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 直接 submodule | 58；全部与 gitlink 一致 |
| Base image | `ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90` |
| Platform | `linux/amd64` |
| Dockerfile SHA-256 | `DD96BEE2452FE4737659756E8CDA6E177931D4201ED6139BF59B56458F9D6C38` |
| CMake | `3.28.3-1build7` |
| GCC/G++ | `13.3.0` |
| Qt | `5.15.13` |
| Build type | `Release` |
| Release flags | `-O3 -DNDEBUG` |

构建命令：

```sh
docker build \
  --provenance=false \
  --file tools/upstream/Dockerfile.oracle-cmake-qt5 \
  --tag diec-rust/upstream-oracle-cmake:74eaf505 \
  tools/upstream
```

Dockerfile 还保存 package versions、CMake cache、最终 `link.txt`、submodule
状态、`file`、`sha256sum`、`ldd` 和 `readelf --dynamic` 输出。首次实验的
`diec` target 构建步骤耗时约 308 秒；此前的 APT 和 Git 层时间不包含在此数字中。

## CMake 产物

| 属性 | CMake 产物 | qmake 产物 |
| --- | --- | --- |
| Version | `die 4.0.0` | `die 4.0.0` |
| Format | ELF64 PIE, dynamically linked, not stripped | 相同 |
| Size | `8,248,008` bytes | `7,684,384` bytes |
| Build ID | `0c24995d5a42083a22381de7d0c6bb65f1012c37` | `7cb9e22c2f5d23642d6d0a0ed7f29bc55fe2b464` |
| SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| Language mode | C++17 | C++11 |
| Optimization | `-O3 -DNDEBUG` | qmake Release、最终 linker flag `-Wl,-O1` |

两个产物的直接 `DT_NEEDED` 集合完全相同：

```text
libQt5Script.so.5
libQt5Core.so.5
libstdc++.so.6
libm.so.6
libgcc_s.so.1
libc.so.6
```

CMake `link.txt` 和 qmake `Makefile` 均链接同一组 8 个 bundled archives：

```text
xsimd
xsimd_sse2
xsimd_avx2
zlib
bzip2
lzma
ppmd
capstone_x86
```

XYara 和 XCppfilt 仍未进入 `diec` 最终链接闭包。

## 自动差分

差分工具：

[`tools/upstream/compare_cli_oracles.py`](../../tools/upstream/compare_cli_oracles.py)

复现命令：

```sh
python3 tools/upstream/compare_cli_oracles.py \
  --left-image diec-rust/upstream-oracle:74eaf505 \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254
```

工具先验证两个镜像的 OCI revision label，再验证共同输入
`/usr/bin/true` 的 SHA-256：

```text
4b5a5694e3c0e8b1d58fc52ac6ef076e55e72c2f53195243ac86d5ff517cc2f6
```

为消除两个 build-tree 路径在 Usage 行中的无语义差异，工具通过同一个
`/tmp/diec` symlink 启动两个程序；除此之外不规范化输出。

| Case | Exit | stdout SHA-256 | stderr SHA-256 | Result |
| --- | ---: | --- | --- | --- |
| `--version` | 0 | `641f88fbece5c6334703787fb6801826745620bd4189f0c0cc036e63d9e1d758` | empty | equal |
| `--help` | 0 | `65a944c5841645c637313b371d47e04498441b5338faeacfd00a740ba85c8844` | empty | equal |
| `--showdatabase` | 0 | `41a888720b1a6ff610f9e1ac2adfa23eabe6eca201e1fdd540d2969b3eea6ed0` | empty | equal |
| `/usr/bin/true --json` | 0 | `e5385540a7d8984a84f1183a1fbf061db24118f934d5a25023ae508b885e9213` | empty | equal |
| no arguments | 0 | same as `--help` | empty | equal |
| missing path | 1 | `fbcbf1ccccbbaf046c131187d687ec8722683f1daa35d735a2105e86a5f4022c` | empty | equal |

共同样本 JSON 将 `/usr/bin/true` 识别为 `ELF64`，size 为 `26936`，唯一 value
为 `Library: GLIBC(2.4)[DYN AMD64-64]`。不存在路径时，错误文本写到 stdout：

```text
Cannot find: /does-not-exist
```

两个产物各自扫描自身时，都按相同顺序报告 GCC、GLIBC、Qt、FLEXlm 和 UPX；
JSON 中只有输入二进制的 `size` 不同。

## 限制与下一步

- 当前只有一个固定 ELF 样本，尚不能证明所有格式、规则和扫描模式等价。
- `build_dpkg.sh` 的全目标 build、install 和 Debian staging 尚未完整执行。
- APT repository 未固定 snapshot，clean build 尚未证明 bit-for-bit reproducible。
- GitHub TLS 中断曾触发 submodule 自身重试；构建入口尚未提供显式、有界重试。
- Windows 和 macOS oracle 尚未建立。
- 自动差分目前比较原始 stdout/stderr/exit code，但尚未保存带 provenance 的
  版本化 baseline 文件。

下一步应把差分工具扩展到可重复生成的 PE、ELF、Mach-O、DEX 和 archive
安全语料，保存原始输出与输入哈希，并覆盖全部输出格式和扫描开关。

## 源码证据

- [`src/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/CMakeLists.txt)
- [`src/console/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/CMakeLists.txt)
- [`build_dpkg.sh`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_dpkg.sh)
- [Ubuntu build workflow](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/.github/workflows/builder.yml)
