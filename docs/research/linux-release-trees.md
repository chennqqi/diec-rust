# 固定 Linux Qt5 发布树复演

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux 打包脚本没有定义适合当前 Rust 项目的 CLI-only 发布物：

- `create_appimage.sh` 在 `linuxdeploy` 前只放入 GUI `die`，但同时复制完整
  `db`/`db_extra`/`db_custom`、YARA、PEiD、signature、GUI assets 和三个 Qt
  plugin；前置 AppDir 为 2,640 个文件、38,920,508 bytes；
- `build_linux_portable.sh` 同时放入 `die`、`diec`、`diel`，但只带主 `db`，
  遗漏 142-file `db_extra` 和 2-file `db_custom`；它又带入 CLI 不可达的 YARA
  与 `crypto.db`，未带 PEiD；未压缩 tree 为 2,476 个文件、52,751,519 bytes；
- 两棵树按标准文件名都没有任何 LICENSE、COPYING、NOTICE 或 COPYRIGHT；
- portable 默认不捆绑 Qt。即使传入固定环境的真实 qmake prefix `/usr`，脚本也
  因 Debian multiarch 布局查错目录而复制零个 Qt 文件，得到逐字节相同的 tree；
- 两次隔离 portable tree 内容和 2,522 条 tar 成员语义完全相同，但普通
  `tar -czf` 保留八个新建路径的不同 mtime，导致未压缩 tar 与最终 tar.gz
  均逐字节不同；上游压缩包已被实验证明不可重复。

这些事实进一步说明 Rust CLI 必须有自己的显式 artifact manifest：只包含一个 CLI、
一个核心运行闭包、完整且原样的三层 runtime rules、必需归属/SBOM，不继承 GUI、
lite、Qt、YARA、PEiD 或 signature 数据。

机器报告为
[`data/linux-release-trees.json`](data/linux-release-trees.json)。它的 scope 是
`post-build-release-tree-replay`，并明确保持：

- `original_scripts_executed_end_to_end=false`；
- `final_appimage_available=false`；
- `compressed_portable_archive_generated=true`；
- `portable_archive_byte_reproducible=false`；
- `legal_review_complete=false`；
- `release_approved=false`。

因此本报告关闭的是固定脚本的复制/布局技术清单和原始 portable tar 命令的
非确定性复演，不是最终 AppImage、规范化 tar.gz、动态依赖或法律评审。

## 固定脚本身份

| 输入 | 固定身份 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| release version | `4.0.0` |
| `create_appimage.sh` | 2,415 bytes；`3b4cfc5b8118eda8bfbbe199001520bc022858955667d0ed8f851f82a2646075` |
| `build_linux_portable.sh` | 3,218 bytes；`91fb88e2f7841362b927b3471bbcb473c663ea9421859f2ec8ceae9d2b35052a` |
| build_tools | `5dd5bcc8abf3b178d9ed47100f6f37ebecceb23e` |
| `build_tools/linux.sh` | 5,272 bytes；`81d8c06a40b94ac73951a92a94c6db7d1da87bd20ca7e3dd937ee019794850a3` |
| CMake install report | `148439d4c6b2c5dd011a58e0baf82c70667e6dacfd75714786873e7bcc021c54` |

主仓库 subtree 不物化 `build_tools` gitlink；审计器从固定完整源码镜像读取
`build_tools@5dd5bcc...`，验证 commit 与组件锁一致，再绑定 `linux.sh` 内容。

## 范围与方法

本实验不是运行原脚本后声称拿到了官方发布包，而是 post-build replay：

1. 从固定完整 CMake build image 取得 `die`、`diec`、`diel`；
2. 在临时目录执行真实 `cmake --install --prefix <STAGE>`；
3. 逐条复演两个脚本的 mkdir/cp/fallback/launcher 布局语义；
4. 对每个 regular file 保存 path、mode、bytes、SHA-256 和
   source/build/system/generated 来源，再只提交摘要及完整 records hash；
5. 不运行缺失的 `linuxdeploy`；在两个隔离 package root 上执行原脚本相同的
   `tar -czf <ARCHIVE> die_4.0.0_portable`，比较 tree、tar 语义、mtime 和字节。

AppImage 脚本引用 `build/release/die`，它属于与固定 CMake build 不同的构建路径。
本实验用固定 CMake GUI ELF 代替该位置，只验证复制树；不声称实际 AppImage workflow
会生成相同 GUI binary。portable 原脚本会重新 configure/build，本实验同样复用固定
完整 build，避免把另一轮 GUI 非确定性混入内容布局。

## AppImage 前置 AppDir

固定镜像没有 `linuxdeploy`，所以以下结果只到调用它之前：

| 指标 | 值 |
| --- | ---: |
| regular files | 2,640 |
| directories | 83 |
| bytes | 38,920,508 |
| records SHA-256 | `795314ec3393e6e4abfcc81c3ea3de61a1e825f5c3f9402bc6873a60d191f039` |
| product binaries | 1：`usr/bin/die` |
| system Qt plugins | 3 files / 157,584 bytes |
| license candidates | 0 |
| symlinks | 0 |

`usr/lib/die` 有 2,628 个文件、13,434,852 bytes。除 GUI assets 外，它包括：

| Tree | Files | Bytes |
| --- | ---: | ---: |
| `db` | 2,124 | 2,832,469 |
| `db_extra` | 142 | 76,651 |
| `db_custom` | 2 | 196 |
| `yara_rules` | 10 | 3,900,619 |
| `peid` | 14 | 1,157,703 |
| `signatures` | 1 | 3,085,459 |
| `images` | 202 | 2,180,397 |
| `info` | 118 | 122,340 |
| `qss` | 15 | 79,018 |

三层 runtime rules 的 2,268-file/2,909,316-byte combined SHA-256 为
`20f2b74effc2bdaf069e3b2e13060432b8890d38364511f5cde56a337348bfda`，
与固定 runtime rule identity 一致。YARA、PEiD 与 signature 对 GUI/其他 engine
有意义，但不是当前 CLI runtime rules；未来 Rust CLI 包不得仅因上游 AppImage
携带它们而复制。

三个预复制 plugin 是：

- `platforms/libqxcb.so`；
- `imageformats/libqjpeg.so`；
- `printsupport/libcupsprintersupport.so`。

`linuxdeploy --plugin qt` 后还会复制或修改哪些 ELF、Qt library、plugin、AppRun 和
metadata，本环境没有证据，不能由前置树外推。

## Portable 未压缩树

默认无 Qt prefix 与传入 qmake prefix `/usr` 的两次复演结果完全相同：

| 指标 | 值 |
| --- | ---: |
| regular files | 2,476 |
| directories | 45 |
| bytes | 52,751,519 |
| records SHA-256 | `fa9938f9456d6a3b92a6e5537f9da47ec6d7f5a00d4727eaed9f3e3005ae20b5` |
| product binaries | 3：`base/die`、`base/diec`、`base/diel` |
| generated launchers | 3 files / 305 bytes |
| bundled Qt files | 0 |
| license candidates | 0 |
| symlinks | 0 |

portable 从 CMake staging 的 `lib/die` 复制 `db`、`images`、`info`、`qss` 和
`yara_rules`，然后单独复制 `signatures/crypto.db`。结果包括：

- 主 `db`：2,124 files / 2,832,469 bytes；
- YARA：10 files / 3,900,619 bytes；
- signature：1 file / 3,085,459 bytes；
- images/info/qss：335 files / 2,381,755 bytes；
- `db_extra`、`db_custom`、PEiD：全部缺失。

也就是说它对 CLI 检测数据既有缺项又有额外项：漏掉 extra/custom 共 144 files /
76,847 bytes，却携带 CLI 不加载的 YARA 与 signature 共 6,986,078 bytes。
不能把该 portable tree 当作 `diec` 能力等价的发布基线。

三个 launcher 固定为：

```sh
#!/bin/sh
CWD=$(dirname $0)
export LD_LIBRARY_PATH="$CWD/base:$LD_LIBRARY_PATH"
"$CWD/base/<product>" "$@"
```

它们只把 `base` 加入 `LD_LIBRARY_PATH`，不会补齐未捆绑的系统依赖。

### Qt prefix multiarch 边界

固定环境的 qmake 返回：

| Query | Path |
| --- | --- |
| `QT_INSTALL_PREFIX` | `/usr` |
| `QT_INSTALL_LIBS` | `/usr/lib/x86_64-linux-gnu` |
| `QT_INSTALL_PLUGINS` | `/usr/lib/x86_64-linux-gnu/qt5/plugins` |

portable 脚本却把参数机械拼成 `$QT_PREFIX_PATH/lib` 与
`$QT_PREFIX_PATH/plugins`。传入 `/usr` 后实际查找 `/usr/lib/libQt5*.so.5`、
`/usr/plugins/platforms/libqxcb.so` 和 `/usr/plugins/sqldrivers/libqsqlite.so`，
在该镜像中全部不存在。脚本不报错，最终仍生成不含 Qt 的 tree。

这不证明脚本对所有自包含 Qt SDK 都失败；它证明固定 Debian multiarch 环境下，
qmake 的真实 prefix 不能直接满足脚本假设。其他 Qt layout 必须另建固定实验。

## 许可证与可重复性

两个 replay tree 都分发多来源代码/数据，却没有一个按标准名称识别的许可证文件：

- AppImage pre-tree 含 MIT root 项目、完整 rules、YARA/PEiD/signature 数据和 Qt
  plugins；
- portable tree 含三个 ELF、主 rules、YARA/signature 数据，且运行时仍依赖系统
  Qt/C++/OS libraries。

这不是“无需许可证”的证据，而是发布脚本没有形成 LICENSE/NOTICE closure 的证据。
`P0-BLOCK-004` 必须继续 Open。

portable 最后使用普通 `tar -czf`。脚本没有：

- `--sort=name`；
- 固定 `--mtime`；
- 固定 owner/group；
- `SOURCE_DATE_EPOCH`；
- gzip header 规范化。

本实验以至少 1.1 秒间隔创建两个隔离 package root，并分别执行原始 tar 命令。
两次未压缩 tree 的 records hash 相同；各 tar 都有 2,522 个成员，排除 mtime
后的完整成员语义 hash 同为
`27d38544770412dbf8a080ad16d94d4307f4eac3a5415ba0c7a422fdcc040376`。
发生 mtime 差异的八个路径是 package root、`base`、`base/platforms`、
`base/signatures`、`base/sqldrivers` 和三个 launcher；路径集合 hash 为
`ea384a2e43e9f0d15a9d55eb68ce8c9122a27d573c2e5b4164692adcd3733c86`。
这些差异使未压缩 tar 和 tar.gz 的字节比较都为 false。

报告只提交稳定比较结果，刻意省略两次偶然 archive hash。正式 Rust 发布流程必须
从规范化 manifest 生成 archive，并以两次 clean build/extract/tree/archive hash
相同作为门禁；本次 post-build replay 证明上游原命令失败，不代替 Rust clean-build
发布验证。

## 复现

```powershell
docker build --network=none `
  -f tools\upstream\Dockerfile.upstream-release-trees-qt5 `
  -t diec-rust/upstream-release-trees-qt5:74eaf505 tools

python tools\upstream\audit_linux_release_trees.py `
  --output docs\research\data\linux-release-trees.json
```

审计镜像固定继承
`diec-rust/upstream-install-qt5:74eaf505@sha256:6f7a378e...230368`；
运行时使用 `--network=none`。生成器拒绝 image revision/ID、脚本、build_tools
commit、release version、prior report、CMake staging、规则身份、产品集合、Qt
布局、license candidate 或来源关系漂移。报告不包含临时路径与时间戳。

## 尚未完成

- 在固定 `linuxdeploy` 版本和依赖源上执行并解包最终 AppImage；
- 原脚本各自完整 configure/build 的 binary identity 和 GUI RCC 非确定性；
- 使用真实、布局兼容的独立 Qt SDK 验证 portable bundling branch；
- 规范化 tar.gz 的两次 clean-build 可重复性；
- DEB/RPM、Windows、macOS 发布树；
- 各实际 artifact 的完整 ELF dependency、LICENSE/NOTICE/SBOM 与书面发布评审。
