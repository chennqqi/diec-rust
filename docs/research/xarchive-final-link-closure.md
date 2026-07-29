# XArchive 静态库 member 最终链接闭包

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux x86_64、Qt 5、CMake Release 构建会编译 XArchive 四个静态库的
22 个 member，并把四个 archive 都写入 `diec` link line；但 GNU ld extraction
map 证明最终 ELF 只抽取其中一个：

| Archive | 构建 member | 最终抽取 | 抽取 member |
| --- | ---: | ---: | --- |
| `libbzip2.a` | 8 | 0 | — |
| `liblzma.a` | 2 | 1 | `LzmaDec.c.o` |
| `libppmd.a` | 4 | 0 | — |
| `libzlib.a` | 8 | 0 | — |
| 合计 | 22 | 1 | 21 个未抽取 |

`LzmaDec.c.o` 的 inclusion reason 是：

```text
CMakeFiles/diec.dir/__/__/XStaticUnpacker/xnsis.cpp.o (LzmaDec_Init)
```

因此此前 [`xarchive-license-closure.md`](xarchive-license-closure.md) 的
“106 个编译源”应严格理解为构建/link-input 闭包：84 个 XArchive 直接对象加
22 个 archive 构建 member。最终 ELF 的 XArchive 编译源贡献闭包是 84 个直接
对象加 1 个被抽取 member，共 85 个。两份结论回答不同问题，并不冲突。

机器报告位于
[`data/xarchive-final-link-closure-linux.json`](data/xarchive-final-link-closure-linux.json)。
它重放原 link command 生成 GNU ld map，且重放 ELF 与固定 ELF 的 SHA-256
逐字节相同。

## 为什么不能只比较最终符号

本轮还对每个 archive member 与最终 ELF 执行
`nm -g --defined-only` 名称交集。21 个未抽取 member 中有 8 个仍出现非空交集：

- bzip2：`bzip2.c.o`、`bzlib.c.o`、`crctable.c.o`、`decompress.c.o`、
  `huffman.c.o`、`randtable.c.o`；
- zlib：`deflate.c.o`、`inflate.c.o`。

同名全局符号可由其他对象或库提供，所以“member 定义的符号名出现在最终 ELF”
不是抽取证明。XCapstone 与 XSIMD 的符号见证结果恰好与 link map 一致，但后续
archive 审计应优先使用 linker map/trace；符号交集只能作为辅助证据。

## 最终抽取 member 的文件与许可证证据

`LzmaDec.c.o.d` 的 XArchive 内依赖闭包为五个文件：

```text
3rdparty/lzma/src/7zTypes.h
3rdparty/lzma/src/Compiler.h
3rdparty/lzma/src/LzmaDec.c
3rdparty/lzma/src/LzmaDec.h
3rdparty/lzma/src/Precomp.h
```

五个文件都包含 Igor Pavlov 与 Public Domain marker。该结论只分类四个静态
archive 的最终抽取部分；84 个直接 XArchive 对象仍全部进入最终链接，其中的
RAR、Brotli、Zstandard 等许可证/来源风险不因本报告而消失。

未抽取的 bzip2、PPMd、zlib 和 `Lzma2Dec` 仍是本次默认构建产生的 archive
内容；若发布包携带这些 `.a`、其他 target 链接它们，或其他平台/feature 改变
抽取集合，仍须按对应构建/发布闭包履行许可证义务。

本页是技术链接与许可证据，不是法律批准；`P0-BLOCK-004` 保持 Open。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| XArchive | `0fcd4e8d3e9933baac3b12246d82ac026557ffd0` |
| source image | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| component lock SHA-256 | `9fabcaf6a0062fcae7007ea5af13a98876e8a6e08b3e2e4727fdff06d974c63c` |
| link line SHA-256 | `b2a4c7953997137d45f06eb3541d5da2efe127e85905c62311f5e03e5a500afb` |
| original/replayed ELF SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| GNU ld map SHA-256 | `91dc73e22c7e22226b6a354f6ac5e7e22743f10c16a718af915d895fafeecd70` |
| prior build-closure report SHA-256 | `27231a08db8747c4cf164d2cbc6cc159c2190f2e91f76557615045dfe0e9d058` |

四个 archive 也逐一 hash-bind：

| Archive | SHA-256 |
| --- | --- |
| `libbzip2.a` | `bf586b5a049514b66507fccadce0fd34568287917be46a6611c38590d59f8305` |
| `liblzma.a` | `b00a2ef5ef4a83076bc0f26294f0276bbfa4a594832e2eb200713087ecb785de` |
| `libppmd.a` | `34dd0bc1fb8b7f92f934334e89805b4d3d56980c19c963bb40ad0d7904e64307` |
| `libzlib.a` | `d306537c392978554ddc10d47c5c573181aedd8b26760e6950af791a53f14d4b` |

## 方法与复现

[`audit_xarchive_final_link_closure.py`](../../tools/upstream/audit_xarchive_final_link_closure.py)
在固定、禁网、只读挂载的 source image 中：

1. 校验 DIE-engine、XArchive、component lock 和前置 106-unit 报告；
2. 解析固定 `link.txt`，要求 84 个直接对象与四个 archive 身份不漂移；
3. 将原 link token 中的 output 替换为固定 `/tmp` 路径，并增加 GNU ld
   `-Map` 参数，不通过 shell 重组命令；
4. 要求重放 ELF 与原 ELF 逐字节相同；
5. 从 map 的 `Archive member included to satisfy reference` 段解析抽取集合和
   inclusion reason；
6. 对四个 archive 的全部 22 个 member、`.o.d`、源码和符号名称交集建立闭集；
7. 对唯一抽取 member 保存五文件依赖闭包、SHA-256 与 license markers。

```powershell
python tools\upstream\audit_xarchive_final_link_closure.py `
  --output docs\research\data\xarchive-final-link-closure-linux.json

python -m unittest discover -s tools\tests `
  -p test_xarchive_final_link_closure.py
```

审计器对 image/commit、prior report、link hash、84/22/1/21 计数、唯一 inclusion
reason、重放 ELF、八个符号假阳性和文件闭包 fail closed。报告不保存本机或
`/opt` 路径。

## 对 Rust 设计的约束

- 不应为了“复刻链接行”而无条件引入 bzip2、PPMd 或 zlib backend；固定 CLI
  最终 ELF 对这四个 archive 的唯一实际抽取需求是 NSIS 使用的 LZMA decoder。
- 这不代表 bzip2/zlib/PPMd 检测或解压能力可以删除：相关能力也可能由 84 个
  直接对象中的聚合实现提供，必须按行为矩阵和差分实验决定 Rust backend。
- static archive contribution 审计应保存 linker map/trace；仅保存 link line、
  archive member list 或最终符号名交集都不足以证明抽取。
- Rust 最终 `.a` 及 C/Go/Python 发布包必须按实际 target/feature 重新生成
  member、native dependency、SBOM 和 NOTICE 闭包。

## 尚未完成

- Windows/MSVC、macOS、Qt6、qmake 与其他 target/feature 的 archive extraction；
- 84 个直接对象的最终 section/function reachability（不作为源码归属豁免）；
- Rust archive backend 的行为、性能、依赖和发布许可证闭包；
- 发布/法律责任人的书面组合评审。
