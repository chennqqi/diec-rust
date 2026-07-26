# XYara 内嵌 YARA 构建与许可证闭包

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

## 范围与结论

本轮审计固定 Linux Qt5 CMake source image 中的 `XYara/3rdparty/yara`，显式构建
`yara` target，并用编译器依赖文件反推实际源码/头文件闭包。结论是：

- `yara` target 成功生成 51-object `libyara.a`，SHA-256 为
  `2a7db6ee2b0191a6092afe3c27640e98702d2b363d01d93e33afe7d2a29d85c9`；
- 51 个编译单元的实际 vendored dependency closure 为 109 个文件；
- 固定 `diec` link line 不含 XYara/YARA，因此该 archive 是 build-only target，
  不进入当前 CLI 二进制；
- 内嵌 132 个 YARA 文件全部映射到官方 YARA v4.5.2：
  129 个内容精确相同，3 个只有 XYara 的 MSVC compatibility patch；
- 6 个 TLSH 文件可沿官方 YARA 引入提交精确追溯到
  `avast/tlshc@bb91fef...`，其条款为
  `Apache-2.0 OR BSD-3-Clause`，并有 Trend Micro NOTICE；
- 6 个 Bison 生成 parser `.c/.h` 实际进入闭包，文件声明
  GPL-3.0-or-later 和 Bison parser-skeleton special exception；
- 10 个 Authenticode parser 文件均带 Avast MIT 文件头，但当前 Linux target
  未定义 `HAVE_LIBCRYPTO`，所以 10/10 均未进入编译或头文件闭包；
- XYara 保存了上述源码，却没有在 bundled YARA 根目录保存
  `COPYING`、`LICENSE` 或 `NOTICE`。这是 source/default-build 分发的明确归属
  缺口，不能由 XYara 根 MIT 文件代替。

机器报告为
[`data/yara-license-closure-linux.json`](data/yara-license-closure-linux.json)。
它固定镜像、组件 lock、官方源码 commit、文件哈希、对象列表、依赖闭包、许可证
标记和构建 warning，不包含扫描时间或本机路径。

## 固定身份

| 对象 | 固定身份 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| XYara | `34a733e9c733669ad8dcaf4588d51197a08545e3` |
| source image | `diec-rust/upstream-oracle-cmake:74eaf505` |
| image ID | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| VirusTotal/yara tag source | `688268d83983a0d61bb68ef3d8dfd28102b7d1b4`（v4.5.2） |
| YARA TLSH import | `19ac2efeb89b88f938fd64234791149ec7edf00f` |
| avast/tlshc source | `bb91fef822a21d480a6bee2a8d693965b5bca16e` |
| official YARA `COPYING` | SHA-256 `efdabc1c1f655528b8c3a59b03668d446746d87273fab76f8af800b6e8891bd2` |
| avast/tlshc `LICENSE` | SHA-256 `ad18f3db3225882e03535e586402699684c744115a667dbbc240ef02b16fdbfc` |
| avast/tlshc `NOTICE.txt` | SHA-256 `84a6a091e05230fd03d7d57f0423d6ac45fdc217dcf997058b255bef530d51c6` |

YARA 版本不是根据目录名推断：vendored
`src/include/yara/libyara.h` 的 `YR_MAJOR_VERSION`、`YR_MINOR_VERSION` 和
`YR_MICRO_VERSION` 分别为 4、5、2。

## 实际构建闭包

审计在一次性容器中执行：

```text
cmake --build /opt/die-build --target yara --parallel 2
```

容器使用 `--network=none --cpus=2 --memory=2g`。实际编译定义为：

```text
-DBUCKETS_128
-DCHECKSUM_1B
-DHAVE_CLOCK_GETTIME
-DHAVE_MEMMEM
-DHAVE_SCAN_PROC_IMPL
-DHAVE_STDBOOL_H
-DHAVE_TIMEGM
-DUSE_LINUX_PROC
```

编译参数为 `-O3 -DNDEBUG -std=gnu11 -fPIC`。`libyara.a`、51 个 archive
member 和 51 个 `.o.d` 在两个全新容器中生成相同机器报告；两个报告 SHA-256
均为 `90fd3a9a806ec1b505ae648c74472f18849da0ed026d0652dde43ad924c9eb57`。

固定 `src/console/CMakeFiles/diec.dir/link.txt` 没有 `XYara`、`libyara` 或
`/yara` token。因此：

- YARA C library 属于默认 CMake 构建图；
- 它不属于当前 `diec` runtime link closure；
- source distribution 或执行默认 all-target build 仍会携带/编译它，许可证审计
  不能因 CLI 未链接就删除；
- `Detect-It-Easy/yara_rules` 是独立的数据能力，不能由 native archive 是否链接
  推导其可达性。

## 与官方 YARA v4.5.2 的内容映射

XYara 的 `3rdparty/yara/src` 有 132 个文件，官方 v4.5.2 `libyara` 有 139 个。
审计对每个 vendored path 建立内容映射：

- 128 个同路径文件逐字节相同；
- `_hash.c` 与官方 `hash.c` 逐字节相同，只是文件名不同；
- 3 个文件有本地 patch：
  - `include/yara/unaligned.h`：增加 GCC strict ANSI/MSVC C `inline` compatibility；
  - `simple_str.c`：增加旧 MSVC/32-bit `va_copy` compatibility；
  - `strutils.c`：增加同一 `va_copy` compatibility；
- 官方额外保留 7 个生成器输入/设置文件：
  `grammar.y`、`hex_grammar.y`、`hex_lexer.l`、`lexer.l`、
  `re_grammar.y`、`re_lexer.l`、`stino.settings`。

这证明 bundled tree 是带三个明确补丁的 YARA v4.5.2 snapshot，而不是只凭版本宏
进行相似度推断。三个 patch 没有改变对应文件原有 YARA BSD 文件头。

## 文件级许可证分类

### YARA 主体

官方 v4.5.2 根 `COPYING` 是 BSD-3-Clause 文本。109-file 实际闭包中：

- 89 个文件含 YARA BSD redistribution marker；
- 8 个非 TLSH YARA 文件没有内联 marker，但内容映射仍固定到同一官方
  v4.5.2 distribution；
- bundled `3rdparty/yara` 根目录没有任何名称以 `LICENSE`、`COPYING`、
  `NOTICE` 或 `COPYRIGHT` 开头的文件。

因此后续若复制、发布或继续构建这份 snapshot，必须从固定官方版本恢复完整
`COPYING`，不能只保留 XYara 根 MIT。

### Bison 生成 parser

以下 6 个文件实际进入 dependency closure：

```text
src/grammar.c
src/grammar.h
src/hex_grammar.c
src/hex_grammar.h
src/re_grammar.c
src/re_grammar.h
```

每个文件同时含 GPL-3.0-or-later 文本和 Bison parser-skeleton special exception。
发布审计必须保留完整生成文件声明，不能只用 “YARA 是 BSD” 覆盖它们；是否满足
exception 的具体发布处理仍须由发布/法律责任人确认。

### TLSH/tlshc

当前闭包实际包含 6 个无内联许可证声明的 TLSH 文件：

```text
src/include/tlshc/tlsh.h
src/tlshc/tlsh.c
src/tlshc/tlsh_impl.c
src/tlshc/tlsh_impl.h
src/tlshc/tlsh_util.c
src/tlshc/tlsh_util.h
```

来源链由三段独立证据闭合：

1. XYara 6 文件逐字节等于官方 YARA v4.5.2 对应文件；
2. [YARA PR #1624](https://github.com/VirusTotal/yara/pull/1624) 的描述明确引用
   `https://github.com/avast/tlshc`，官方 merge commit 为
   `19ac2ef...`；
3. merge commit 中的 6 个新增 blob 与
   `avast/tlshc@bb91fef...` 对应 6 个 blob 逐字节相同。

YARA 后续对这些文件执行 clang-format，并在 `tlsh_impl.c/.h` 修复问题；机器报告
固定这 6 个文件到 v4.5.2 的完整 path history，而不是错误声称当前文件仍与初始
tlshc blob 完全相同。

`avast/tlshc` 的 `LICENSE` 允许在 Apache-2.0 或 BSD-3-Clause 中选择；若选择
Apache-2.0，必须处理 `NOTICE.txt` 中的 Trend Micro attribution。当前 XYara/YARA
snapshot 没有携带这两个文件，所以发布前必须恢复并书面确定所选许可分支。

### Authenticode parser

vendored tree 有 10 个路径名含 `authenticode` 的文件，全部含
`Copyright (c) 2021 Avast Software` 和完整 MIT permission header。当前 target：

- `flags.make` 不含 `HAVE_LIBCRYPTO`；
- `pe.c` 的 include 与实现调用均受该宏保护；
- CMake source list 不含 Authenticode parser `.c`；
- 10 个文件均未出现在 51 个 `.o.d` 依赖中。

所以这些文件是当前 Linux build 的 source-only 内容，不属于 `libyara.a` 闭包。
启用 OpenSSL、其他平台配置或未来 CMake 变更时必须重新生成审计，不能沿用本结论。

## 编译器 warning

`-O3` 构建成功，但 GCC 对 `src/atoms.c` 产生 12 条
`-Wstringop-overflow=` 主 warning：

| 函数位置 | 源码行 | 重复次数 |
| --- | ---: | ---: |
| `_yr_atoms_case_insensitive` | 730 | 3 |
| `_yr_atoms_case_insensitive` | 731 | 3 |
| `yr_atoms_extract_from_string` | 1396 | 3 |
| `yr_atoms_extract_from_string` | 1397 | 3 |

诊断分别指出对 `YR_MAX_ATOM_LENGTH == 4` 的 `bytes[4]` 和 `mask[4]` 写入
offset 4、5、6。规范化 stderr SHA-256 为
`e81d416f008a7bc28ffcd944c73c6817a9ff7f2f1424ae10d257191a65451bf1`。

这是编译器静态诊断证据，不足以单独证明存在可达越界或漏洞，也不能当作无害的
false positive 删除。若 Rust 实现复刻 atom extraction 语义，必须使用受控长度并
建立边界/差分测试；上游 C 行为还需 sanitizer、最小可达输入或编译器分析进一步
分类。

## 复现

先准备两个固定官方 checkout：

```powershell
git clone https://github.com/VirusTotal/yara.git I:\tmp\diec-yara-audit
git -C I:\tmp\diec-yara-audit checkout --detach `
  688268d83983a0d61bb68ef3d8dfd28102b7d1b4

git clone https://github.com/avast/tlshc.git I:\tmp\diec-tlshc-audit
git -C I:\tmp\diec-tlshc-audit checkout --detach `
  bb91fef822a21d480a6bee2a8d693965b5bca16e
```

YARA checkout 必须包含完整历史，因为工具会读取 TLSH 引入 blob 和 path history。
然后运行：

```powershell
python tools\upstream\audit_yara_license_closure.py `
  --official-yara-root I:\tmp\diec-yara-audit `
  --official-tlshc-root I:\tmp\diec-tlshc-audit `
  --output docs\research\data\yara-license-closure-linux.json
```

工具拒绝 dirty checkout、remote/commit/image/lock 漂移、对象数变化、未知本地
YARA patch、TLSH 来源链变化、许可证 marker 变化、warning 数变化、启用
`HAVE_LIBCRYPTO` 或 `diec` link relationship 变化。官方 checkout 和当前仓库以
readonly bind mount 进入断网容器。

## 对 Rust 重写的约束

- 当前证据不支持把 native YARA C library 纳入 Rust runtime；它并未进入固定
  `diec` CLI，规则数据可达性应另做行为基线。
- 若未来复用 YARA/TLSH 代码、算法移植或测试向量，必须保留
  component/path/commit/hash 和独立 LICENSE/NOTICE，不得依赖 XYara 根 MIT。
- 规则 1:1 复用的许可证结论必须按 `Detect-It-Easy/yara_rules` 数据路径单独
  审计，本报告只覆盖 native build target。
- 后续 upstream sync 必须重新运行本工具；132/129、51/109、warning 或
  Authenticode relationship 的任何变化都需要人工评审。
- Rust atom/字符串扫描实现不得继承未经分类的 C warning 行为；内存安全和上游
  可观察兼容要分别用安全边界测试与差分测试证明。

## 尚未完成

- Windows、macOS、qmake 及启用 OpenSSL 的 YARA 编译闭包；
- YARA archive 的符号/API 可达性和是否被其他非 CLI target 链接；
- `Detect-It-Easy/yara_rules` 的逐文件来源、条款和实际 CLI 加载行为；
- `atoms.c` warning 的 sanitizer/可达输入分类；
- 由发布/法律责任人确定 TLSH 双许可证分支及完整发布 attribution。
