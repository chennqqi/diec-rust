# 上游 Linux CLI 构建基线

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-25

## 结论

固定上游源码可以在 Linux amd64、Qt 5.15.13 环境中不修改源码地构建并运行
`diec 4.0.0`。本仓库用
[`tools/upstream/Dockerfile.oracle-qt5`](../../tools/upstream/Dockerfile.oracle-qt5)
保存该环境，并在镜像内保留包版本、submodule 状态、qmake 配置、链接参数、
ELF 动态段和二进制哈希等证据。

本次产物是 **qmake CLI 候选 oracle**。固定版本的 Ubuntu workflow 调用
`build_dpkg.sh`，该脚本使用 CMake Release 和 C++17；本次实验使用上游仍维护的
qmake 工程、Release 和 C++11。CMake 产物及两条路径的首轮原始输出差分已记录在
[`upstream-cmake-differential.md`](upstream-cmake-differential.md)。

## 固定输入

| 输入 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 直接 submodule | 58；全部 checkout 到主仓库 gitlink |
| Base image | `ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90` |
| Target platform | `linux/amd64` |
| Docker client/server | `29.6.1` / `29.6.1` |
| Dockerfile SHA-256 | `9B067C5C489E1D252D5864B54D1BD302F4EC4C4A30768C28D6C10B46D288C330` |

首次联网构建时实际解析到的关键包版本如下。它们是实验记录，不是当前
Dockerfile 中可长期获取的 package lock。

| Package | Version |
| --- | --- |
| `build-essential` | `12.10ubuntu1` |
| `ca-certificates` | `20260601~24.04.1` |
| `file` | `1:5.45-3build1` |
| `git` | `1:2.43.0-1ubuntu7.3` |
| `libqt5svg5-dev:amd64` | `5.15.13-1` |
| `qt5-qmake:amd64` | `5.15.13+dfsg-1ubuntu1` |
| `qtbase5-dev:amd64` | `5.15.13+dfsg-1ubuntu1` |
| `qtscript5-dev:amd64` | `5.15.13+dfsg-1` |
| `qttools5-dev:amd64` | `5.15.13-1` |
| `qttools5-dev-tools` | `5.15.13-1` |

工具链为 GCC/G++ `13.3.0`、GNU ld `2.42`、qmake `3.1` 和 Qt
`5.15.13`。

## 构建方式

从仓库根目录执行：

```sh
docker build \
  --provenance=false \
  --file tools/upstream/Dockerfile.oracle-qt5 \
  --tag diec-rust/upstream-oracle:74eaf505 \
  tools/upstream
```

`--provenance=false` 去除每次可能变化的 BuildKit attestation manifest。它不能
解决下文列出的 APT 和 Git 元数据问题，因此不得据此宣称 clean build 已达到
bit-for-bit reproducible。

Dockerfile 执行以下门禁：

1. 只 fetch 确切的 DIE-engine commit。
2. 初始化 recursive submodule，验证 58 个直接 submodule，拒绝缺失、修改或
   merge-conflict 状态。
3. 执行顶层 qmake，但只依次构建 `sub-build_libs-make_first` 和
   `sub-console_source-make_first`。
4. 保存构建环境和链接证据。
5. 对 `diec` 执行 `file`、`sha256sum`、`ldd` 和 `readelf --dynamic`。

CLI-only 目标选择不是源码补丁。上游
[`die_source.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/die_source.pro)
同时列出 `build_libs`、`console_source`、`gui_source` 和 `lite_source`。
实验中直接执行顶层 `make` 会在 `gui_source` 配置时报
`Unknown module(s) in QT: opengl`；而 CLI 目标无需 Qt OpenGL，并能完整构建。

上游仓库自己的
[`Dockerfile`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/Dockerfile)
使用浮动的 `alpine:latest`，并在构建前用 `sed` 修改
`XOptions/xoptions.cpp`。本基线没有继承这两个行为，也没有 strip 产物，避免把
未经记录的源码修改或调试信息变化混入行为 oracle。

## 产物

| 属性 | 观测值 |
| --- | --- |
| Version output | `die 4.0.0` |
| Format | ELF 64-bit LSB PIE, x86-64, dynamically linked, not stripped |
| Size | `7,684,384` bytes |
| Build ID | `7cb9e22c2f5d23642d6d0a0ed7f29bc55fe2b464` |
| SHA-256 | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| Link flags | `-Wl,-O1` |

ELF `DT_NEEDED` 只包含：

```text
libQt5Script.so.5
libQt5Core.so.5
libstdc++.so.6
libm.so.6
libgcc_s.so.1
libc.so.6
```

`ldd` 还展开了 Qt 和 libc 的传递依赖，包括 zlib、double-conversion、ICU、
PCRE2、zstd 和 glib。它们不是 `diec` 的直接 `DT_NEEDED` 项。

qmake 生成的最终链接行包含以下 bundled static archives：

```text
Formats/xsimd/libs/libxsimd-unix-x86_64.a
Formats/xsimd/libs/libxsimd_sse2-unix-x86_64.a
Formats/xsimd/libs/libxsimd_avx2-unix-x86_64.a
XArchive/3rdparty/zlib/libs/libzlib-unix-x86_64.a
XArchive/3rdparty/bzip2/libs/libbzip2-unix-x86_64.a
XArchive/3rdparty/lzma/libs/liblzma-unix-x86_64.a
XArchive/3rdparty/ppmd/libs/libppmd-unix-x86_64.a
XCapstone/3rdparty/Capstone/libs/libcapstone_x86-unix-x86_64.a
```

`build_libs` 还构建了 XYara 和 XCppfilt，但它们没有出现在 `diec` 的最终链接
参数中。这与 [`cli-dependency-and-license.md`](cli-dependency-and-license.md)
的静态闭包结论一致。

## 无样本行为检查

以下命令都返回退出码 `0`：

```sh
docker run --rm diec-rust/upstream-oracle:74eaf505 \
  /opt/die-source/build/release/diec --version

docker run --rm diec-rust/upstream-oracle:74eaf505 \
  /opt/die-source/build/release/diec --help

docker run --rm diec-rust/upstream-oracle:74eaf505 \
  /opt/die-source/build/release/diec \
  --showdatabase \
  --database /opt/die-source/Detect-It-Easy/db \
  --extradatabase /opt/die-source/Detect-It-Easy/db_extra \
  --customdatabase /opt/die-source/Detect-It-Easy/db_custom
```

`--showdatabase` 成功加载主、extra 和 custom 数据库，共报告 27 个文件类型、
2,172 条签名：

```text
Binary 292; COM 247; MSDOS 351; NE 13; LE 3; LX 5; PE 965; ELF 47;
Mach-O 12; PDF 7; CFBF 3; Image 1; JPEG 5; PNG 1; RAR 1; ISO 9660 23;
Archive 1; ZIP 3; JAR 2; APK 52; DEX 29; NPM 4; Mach-O FAT 2;
Amiga Hunk 98; Atari ST 1; DOS/16M 2; DOS/4G 2.
```

为避免引入未知样本，本轮还让 `diec` 扫描自身。输入由上述 SHA-256 和长度唯一
标识，JSON 模式返回退出码 `0`，根检测为 `ELF64`，并依次报告：

```text
Compiler: GCC(3.X)
Library: GLIBC(2.4)[DYN AMD64-64]
Library: Qt(5.X)
Library: FLEXlm
Packer: UPX($Id:)
```

这里的 FLEXlm 和 UPX 结果只作为上游可观察行为保存，不代表本项目认可其准确性。
兼容实现默认仍须复现，除非后续通过 ADR 明确允许偏离。

## 可重复性边界

当前实验固定了上游 commit、submodule gitlink、基础镜像 digest、构建命令和已安装
包版本，并证明缓存命中时重复构建保持同一产物哈希。它还没有达到独立 clean
environment 的字节级复现：

- Ubuntu APT 仓库未固定到 snapshot；未来解析到的包可能变化或消失。
- `git fetch` 生成的 `.git` 元数据包含构建时状态，镜像层不保证跨 clean build
  相同，即使工作树内容相同。
- GCC/linker 是否对所有中间产物完全确定尚未用两个独立 clean builder 验证。
- 当前只覆盖 Linux amd64/Qt5/qmake。
- 默认顶层 qmake 全目标构建和官方 CMake 全目标/install 路径尚未完成；两个
  CLI-only 产物已完成首轮差分，但语料覆盖仍很小。

因此当前状态保持 Draft。下一步应：

1. 固定 Ubuntu snapshot 或构建依赖镜像 digest，并移除最终镜像中的 Git 元数据。
2. 扩大 qmake/CMake 差分语料和扫描模式，并采集可重复性能数据。
3. 在独立 clean builder 上重复两次并比较 `diec` 哈希；若不能相同，定位
   build-id、时间戳或生成代码中的非确定输入。
4. Windows 固定构建记录已建立；macOS 已具备 CLI-only bootstrap，但仍需在
   Darwin x86_64 主机执行、固定 toolchain lock 并完成第二次 clean build。

## 上游证据

- [Ubuntu 24.04 workflow](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/.github/workflows/builder.yml#L20-L36)
- [`build_dpkg.sh`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_dpkg.sh#L14-L26)
- [`die_source.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/die_source.pro)
- [`console_source.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/console_source/console_source.pro)
- [`src/console/CMakeLists.txt`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/src/console/CMakeLists.txt)
- [上游 Dockerfile](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/Dockerfile)
