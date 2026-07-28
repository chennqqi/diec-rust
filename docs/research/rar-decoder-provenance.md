# XArchive RAR 解码器来源与复用边界

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux Qt5 CLI 实际编译的
`XArchive/Algos/xrardecoder.cpp` 与 `.h` 不能在当前证据下作为 XArchive
MIT 代码直接翻译进 Rust：

- 两个固定文件合计 26,627 个去注释 C/C++ token；
- 对比 UnRAR 7.1.10 Git 镜像固定 commit
  `9f1ce54025e0175634cbdb21b06341aa29eba591`，12-token shingle 覆盖
  25,086 个 token（94.212641%），64-token shingle 仍覆盖 19,759 个
  token（74.206632%）；
- 64-token 唯一来源跨 17 个 UnRAR 文件，包括 RAR 1.5/2.x/3.x/5.x
  unpack、PPM model、RAR VM、suballocator 和 bit reader，不是少量公共接口或
  通用样板的偶合；
- XArchive 两个文件声明 horsicq MIT，但没有 UnRAR 修改分发要求的 notice；
- 固定 UnRAR `license.txt` 要求修改源码分发时携带指定 notice，并限制使用源码
  重建专有 RAR 压缩算法。

机器证据见
[`data/rar-decoder-origin.json`](data/rar-decoder-origin.json)，SHA-256 为
`5e7716b42c2fba533d9aa07e3cdd0fa65b8d28bd4b5ff7519e5bb33b696c6067`。

这是一项内容来源和许可证文本差异的技术结论，不是侵权或许可有效性的法律结论。
在发布/法律责任人完成书面评审前，本项目：

- 不复制、翻译或改写 XArchive 的 RAR decoder；
- 可以继续把固定 DIE/XArchive 二进制作为黑盒 oracle；该行为不会把 decoder
  源码或二进制导入本仓库及未来 Rust 静态库；
- 不因 oracle 能解压某个 RAR 方法，就推定相应压缩样本可以再分发；
- RAR 压缩 backend 选型必须单独建立来源、许可证、static-link 和资源限制闭包。

因此 `P0-BLOCK-004` 保持 Open，并新增明确的 bundled code 评审项。本报告完成
时 `CAP-GAP-006` 仍缺合法、可重复的压缩/solid 语料；后续压缩/solid oracle
及五类 engine family closure 已由
[`archive-rar-compressed-behavior.md`](archive-rar-compressed-behavior.md) 和
[`archive-gap-closure.md`](archive-gap-closure.md)
补齐。加密/multi-volume 等仍是 method/feature 扩展，不改变 decoder 许可证
评审未关闭的结论。

## 固定对象与历史

| 对象 | 固定身份 | SHA-256 / 说明 |
| --- | --- | --- |
| XArchive | `horsicq/XArchive@0fcd4e8d3e9933baac3b12246d82ac026557ffd0` | DIE-engine gitlink |
| 当前 decoder `.cpp` | `Algos/xrardecoder.cpp`, 128,003 bytes | `55f36d7b0188f5093ffad5723637fedafae32321b1fde3cf2f81ff5983e94026` |
| 当前 decoder `.h` | `Algos/xrardecoder.h`, 27,390 bytes | `29e0f4e1091df88f992f2cf5688df044bfbb46e607cb6536cbd5b4e234665540` |
| 首次引入 | `d48321dcc54b5011756853437de1a7220fd2a440`, 2025-09-23 | subject 仅为 `Add new file(s): 2025-09-23` |
| UnRAR 对照 | `pmachapman/unrar@9f1ce54025e0175634cbdb21b06341aa29eba591` | 镜像标记 7.1.10；是首次引入前该镜像最后一个 commit |
| UnRAR license | `license.txt`, 1,976 bytes | `6ecc1687808b7d66b24f874755abfed7464d9751ed0001cd4e8e5d9bf397ff8a` |

首次引入的两个 XArchive 文件已带 horsicq MIT header，提交没有记录第三方来源、
版本或许可证。后续 reformat、copyright year 和 input-validation commit 改变了
当前文件 hash，但没有补入 UnRAR notice。

`pmachapman/unrar` 明确作为 Git 镜像使用，不冒充 RARLAB 官方 Git 仓库。RARLAB
官方 addons 页面提供当前 UnRAR source，官方 RAR 5 格式说明也把解压算法细节指向
UnRAR source。固定镜像 `readme.txt` 自述其 portable UnRAR 源码由 RAR source
自动生成。报告分别保存镜像 remote/commit、官方入口 URL、readme 与 license
hash，避免把三种证据混为一谈。

## 内容对照

审计器采用词法 token，不比较空白、缩进或注释，但保留标识符、常量、字符串和
运算符。对每个 12-token 与 64-token 连续窗口建立 UnRAR 顶层 150 个
`.cpp/.hpp` 文件索引，再计算 XArchive decoder token 的覆盖。

| shingle | 覆盖 token | 覆盖率 | 匹配窗口 | 唯一来源文件 |
| ---: | ---: | ---: | ---: | ---: |
| 12 | 25,086 / 26,627 | 94.212641% | 21,986 | 25 |
| 64 | 19,759 / 26,627 | 74.206632% | 13,093 | 17 |

64-token 的 17 个唯一来源为：

```text
compress.hpp       getbits.cpp       getbits.hpp       largepage.hpp
model.cpp          model.hpp         rarvm.cpp         suballoc.cpp
suballoc.hpp       unpack.cpp        unpack.hpp        unpack15.cpp
unpack20.cpp       unpack30.cpp      unpack50.cpp      unpack50frag.cpp
unpackinline.cpp
```

较长 shingle 会刻意漏掉 Qt 类型替换、类名前缀、错误处理和局部重构，因此
74.21% 不是“只有 74.21% 来源相同”，也不能推导剩余 25.79% 的作者身份；它只是一
个保守、可重复的长连续 token 下界。相反，94.21% 的短 shingle 也不能单独证明
逐行复制。两档覆盖、跨算法模块的唯一来源、相同内部结构与提交时间共同构成来源
判断。

## 许可证边界

固定 UnRAR license 允许在软件中处理 RAR archive，但：

- 禁止用源码开发 RAR-compatible archiver 或重建专有压缩算法；
- 修改后的 UnRAR 源码单独或随软件分发时，需要在 license、文档或源码注释中保留
  规定文本。

XArchive decoder 文件只有 horsicq MIT 文本，没有该 notice 或 Alexander Roshal
归属。根 XArchive MIT 不能自动解释这种文件内容/notice 差异。本项目也不能仅凭
上游仓库的许可证标签，把 decoder 改写为 Rust 后作为 MIT 发布。

RARLAB 的 RAR/WinRAR EULA 另说明：已购买许可的所有者创建并分发 RAR archives
不收取额外 royalties。该条款不证明本项目拥有 creator license，也不自动授予
任意第三方 `.rar` fixture 的版权。因此当前不使用 trial creator 生成并提交压缩
语料，不导入来源不明的公开 `.rar`。

## 可重复方法

准备两个固定、完整历史 checkout：

```powershell
git clone https://github.com/horsicq/XArchive.git XArchive
git -C XArchive checkout 0fcd4e8d3e9933baac3b12246d82ac026557ffd0

git clone https://github.com/pmachapman/unrar.git unrar
git -C unrar checkout 9f1ce54025e0175634cbdb21b06341aa29eba591
```

运行：

```powershell
python tools\upstream\audit_rar_decoder_origin.py `
  --xarchive-root <XArchive-checkout> `
  --unrar-root <unrar-checkout> `
  --output docs\research\data\rar-decoder-origin.json
```

工具拒绝错误 commit、remote 或 dirty checkout，核验 decoder 首次引入历史，固定
当前/首次引入文件 hash、镜像 license/readme hash、两档 token shingle 以及所有
关系断言。报告不记录时间或本机路径；相同输入重复生成字节一致。

## 后续工作

1. 由发布/法律责任人决定 UnRAR 条款、XArchive MIT 声明差异及本项目可接受的
   backend/NOTICE 方案；未完成前保持
   `implementation_constraint.copy_or_translation_approved=false`。
2. 调查具有明确 fixture 再分发许可的 RAR 解码项目或官方测试向量；逐个固定
   archive 来源 commit、blob hash、生成方式、方法/版本和许可证。
3. 只在语料许可闭合后运行固定 DIE oracle，覆盖 RAR15/20/29/50/70、solid、
   encryption、multi-volume、CRC/size 损坏和 dictionary 极值。
4. Rust backend 选型时比较纯 Rust、受约束 UnRAR 集成和洁净室实现；任何 native
   依赖或特殊许可证必须建立 ADR，且静态 `.a/.lib` 发布义务可履行。
