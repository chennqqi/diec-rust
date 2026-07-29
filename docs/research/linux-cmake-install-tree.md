# 固定 Linux Qt5 CMake 安装树审计

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定上游的默认 CMake install 不是 `diec` CLI 发布物定义。完整默认构建执行
`cmake --install` 后会同时安装 GUI `die`、CLI `diec`、lite `diel`，以及 GUI
桌面集成、翻译、样式、图片、info、JavaScript rules 和 YARA 数据。安装树共有
4,916 个 regular file、60,881,050 bytes，tree SHA-256 为
`c5860284e27d6048f69f065d494ac7e919da263a8be43833a755df2d6e8806b4`。

只构建 `diec` 后直接执行同一 install 脚本并不能得到 CLI-only tree：CMake 会先
复制 2,434 个文件、11,178,908 bytes，随后因为缺少 `src/gui/die` 以 code 1
失败。固定构建只生成 `Unspecified` install component；上游没有可选择的 CLI
install component。

因此 Rust 项目不能把该安装树当作目标发布布局。正式 CLI 发布物应显式定义为：

- 一个 Rust CLI 薄适配器及其核心运行闭包；
- 一份原样、hash-bound 的 `db`/`db_extra`/`db_custom` runtime rules；
- 必需的 LICENSE/NOTICE/SBOM；
- 不含 GUI、lite、Qt、桌面文件、图标或 CLI 不可达的 YARA/PEiD/signature 数据。

最后一项是当前范围与可达性约束，不是许可证豁免。凡实际分发的数据仍须按自身来源
和条款审计。

机器证据为
[`data/linux-cmake-install-tree.json`](data/linux-cmake-install-tree.json)。
报告的 `scope.kind` 明确是
`cmake-install-staging-tree-not-compressed-package`，并保持
`legal_review_complete=false`、`release_approved=false`。

## 上游安装定义

固定源码的
[`src/CMakeLists.txt`](../../upstream/DIE-engine/src/CMakeLists.txt)
无条件加入 `gui`、`console` 和 `lite` 三个目录：

- [`src/gui/CMakeLists.txt`](../../upstream/DIE-engine/src/gui/CMakeLists.txt)
  安装 `die`，并安装 desktop/metainfo/icons、QSS、info、`db`、YARA、images、
  translations、LICENSE 等内容；
- [`src/console/CMakeLists.txt`](../../upstream/DIE-engine/src/console/CMakeLists.txt)
  安装 `diec`；
- [`src/lite/CMakeLists.txt`](../../upstream/DIE-engine/src/lite/CMakeLists.txt)
  安装 `diel`。

这些 `install()` 调用都没有声明 `COMPONENT`。固定 build tree 的 16 个生成
`cmake_install.cmake` 脚本因而只暴露 `Unspecified`，无法通过
`cmake --install --component ...` 选择 CLI 闭包。

## 完整 staging tree

审计在 `--network=none` 下把完整构建安装到临时 `DESTDIR` 和 `/usr` prefix。
安装结果没有 symlink，也没有超出固定 source/build tree 的未匹配文件。

| Route | Files | Bytes |
| --- | ---: | ---: |
| `usr/bin` | 3 | 40,550,912 |
| `usr/lang` | 22 | 3,430 |
| `usr/lib/DetectItEasy` | 2,412 | 11,175,478 |
| `usr/lib/die` | 2,469 | 9,114,843 |
| `usr/share/applications` | 1 | 267 |
| `usr/share/doc` | 2 | 2,114 |
| `usr/share/icons` | 6 | 31,561 |
| `usr/share/metainfo` | 1 | 2,445 |
| **Total** | **4,916** | **60,881,050** |

来源匹配把 4,890 个文件、20,326,441 bytes 归到固定 source tree，把 26 个文件、
40,554,609 bytes 归到固定 build tree；未匹配数为零。完整逐文件来源记录没有直接
塞入仓库，而以
`b89d8ac4d6f901ec5bf91d5be1e07bc8f18aa363a4a1f8ca11850ca60ddd4906`
绑定。

三个安装程序均为 mode `0755`：

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `usr/bin/die` | 25,293,840 | `28a28aabeb6e942060e5bf9333b09374c96944aed4d5e2c99a8a78fa958be2d3` |
| `usr/bin/diec` | 8,248,008 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| `usr/bin/diel` | 7,009,064 | `69facb4d8de1b61856ed749f469c2956623e6c6f9663c1b66be43470de4253da` |

## 重复安装与重复内容

生成的 `install_manifest.txt` 有 7,364 条记录，但只有 4,916 个唯一目标路径：
2,448 条是重复记录，涉及 2,278 个路径。十个
`usr/lib/DetectItEasy/yara_rules/*` 文件各出现 19 次，其余高基数重复主要来自
`db` 和 `db_extra`。manifest 的唯一集合与实际 staging tree 精确相等，所以这不是
漏记文件，而是同一路径被多个 install rule 重复覆盖。

最终 tree 中有 2,247 个重复内容组、共 4,509 个路径；除每组保留一份外的冗余为
6,857,345 bytes。以下三个 subtree 在两个 prefix 下逐路径、长度、mode 和内容完全
相同：

| Subtree | Files each | Bytes each | Tree SHA-256 |
| --- | ---: | ---: | --- |
| `db` | 2,124 | 2,832,469 | `006c6789e364f2a31c2ab2a18e374c34d548c60405f9c4128d1b8ea31aca6a7a` |
| `info` | 118 | 122,340 | `42db9c7018459af1499ad8da59c612454f9f6056543a96e1df9193ea2afca843` |
| `yara_rules` | 10 | 3,900,619 | `190872d30fec728e99a3b19056ef86bb319ec6d7f17708414c3c66f95932cead` |

Rust CLI 发布布局应避免复制这些 GUI/lite 路径，也应让核心库、CLI 和 FFI 共享同一
规则定位/加载逻辑，不能各自维护一份检测数据。

## Runtime rules 与许可证边界

安装在 `usr/lib/DetectItEasy` 下的 CLI runtime 三棵规则树与既有来源报告一致：

| Tree | Files | Bytes |
| --- | ---: | ---: |
| `db` | 2,124 | 2,832,469 |
| `db_extra` | 142 | 76,651 |
| `db_custom` | 2 | 196 |
| **Total** | **2,268** | **2,909,316** |

combined tree SHA-256 为
`20f2b74effc2bdaf069e3b2e13060432b8890d38364511f5cde56a337348bfda`，
与
[`runtime-rule-assets-license.md`](runtime-rule-assets-license.md)
绑定的固定 runtime identity 相同。

按文件名查找 `LICENSE*`、`COPYING*`、`NOTICE*`、`COPYRIGHT*`，完整安装树只发现
`usr/share/doc/DetectItEasy/detect-it-easy/LICENSE`。但 tree 同时包含 YARA、
PEiD/signature 相关数据和多种来源的编译代码；单个根 MIT 文件不证明发布归属闭包
完整。该观察是 `P0-BLOCK-004` 的新增技术证据，不能关闭书面许可证评审。

## 与其他上游打包脚本的区别

本报告不代表 AppImage、DEB、RPM、portable archive 或系统包：

- 固定
  [`create_appimage.sh`](../../upstream/DIE-engine/create_appimage.sh)
  只复制 GUI `die`；复制 `diec`/`diel` 的两行被注释，然后脚本另行复制数据和
  Qt plugins 并调用 `linuxdeploy`；
- [`build_linux_portable.sh`](../../upstream/DIE-engine/build_linux_portable.sh)
  另有自己的 staging 和三程序复制逻辑；
- 系统动态库不进入本次 CMake `DESTDIR`。

因此不同发布方式必须分别做内容、依赖、许可证与体积闭包，不能从本报告外推。

## 重建确定性边界

正式报告绑定 full image ID
`sha256:6f7a378ea1c5a07745d45083c0e596430fefc6526273528366a7dc7e11230368`。
同一镜像重复执行审计可以逐字节生成相同报告；这不等于 Dockerfile 重建会得到相同
GUI ELF。

调研期间的两次完整 build 具有相同的 4,916-file path/size/mode、manifest、runtime
rules 和 `diec`/`diel` hash，但 `die` SHA-256 分别为
`f5fd721231794e33644e302e8f515488fba9eb2d9f277c15e19ff0bafdcdb54c`
与本报告值，GNU build-id 也不同。差异同时出现在 Qt RCC 生成的
`qrc_rsrc.cpp` 和 `qrc_res.cpp`。本轮没有继续把具体字节归因到 RCC timestamp
字段，所以机器报告明确保持
`image_rebuild_reproducibility_verified=false`。GUI 不在当前 Rust 交付范围，
但任何未来 GUI 基线必须先关闭这一确定性缺口。

## 复现

最终镜像从固定 CLI oracle image ID
`sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`
构建，先完成 `die`/`diec`/`diel`，再复制审计器：

```powershell
docker build --network=none `
  -f tools\upstream\Dockerfile.upstream-install-qt5 `
  -t diec-rust/upstream-install-qt5:74eaf505 tools

python tools\upstream\audit_linux_cmake_install.py `
  --output docs\research\data\linux-cmake-install-tree.json
```

生成器检查：

- base/full image 的 OCI revision 与固定 base image ID；
- image 内审计器与仓库文件逐字节相同；
- source commit、三个 build executable、完整 install 返回码和 stderr；
- manifest 唯一路径与 staging tree 相等；
- 每个 regular file 对固定 source/build tree 的 size+SHA-256 映射；
- 既有 source/rule/runtime 报告的 hash 和关系；
- CLI-only base tree 确实在复制部分文件后因缺少 GUI 程序失败。

报告不含时间戳、随机 `DESTDIR` 或本机路径；对报告绑定的确切 full image 可逐字节
复现。它不声称从 Dockerfile 独立重建该 GUI image 仍会得到相同 binary hash。

## 尚未完成

- [`linux-release-trees.md`](linux-release-trees.md) 已闭合 AppImage
  pre-linuxdeploy 与 portable post-build 复制树；仍缺最终 AppImage、
  基于获批 manifest 的 clean-build tar.gz、DEB/RPM/archive 实际内容和动态库
  closure；同一错误 portable tree 的规范化 control 只验证归档机制；
- Windows 与 macOS 发布树；
- GUI/lite 与非 CLI 数据是否发布的产品范围决定；
- XUCL、UnRAR、artwork、YARA/PEiD/signature 等书面许可证/归属结论；
- Rust CLI/staticlib 的最终 package、SBOM、NOTICE、签名和跨平台体积对照。
