# XBinary signature language

Status: Draft

Upstream: `horsicq/Formats@1151e7254fdee3c0294ff7095edbdd7bfccf8201`,
`horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-26

## 结论

Binary 规则中的 `X.c` 不是普通 hex 比较。固定 XScanEngine 的
[`Binary_Script::c`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.cpp#L893)
转发到
[`Binary_Script::compare`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.cpp#L95)，
最终使用 XBinary 的 signature normalizer、record parser 和 matcher。
[`fSig`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.cpp#L883)
则把同一语言用于范围搜索。

因此 Rust 兼容层必须把 signature 作为有语法、有控制流并依赖 format memory map
的输入处理。未知或畸形输入不能直接折叠成“不匹配”；需要区分 parse diagnostic、
合法但不匹配、越界、需要上下文和上游兼容怪癖。

## 固定源码路径

| 阶段 | 固定源码 |
| --- | --- |
| 语法声明与 record layout | [`xbinary.h` `ST`/`SIGNATURE_RECORD`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.h#L1352) |
| 注释形式的 token 清单 | [`xbinary.h` signature format](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.h#L1639) |
| 规范化 | [`XBinary::convertSignature`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L11595) |
| record parser | [`XBinary::getSignatureRecords`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L15766) |
| matcher | [`XBinary::_compareSignature`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L15814) |
| 快速字符串比较 | [`XBinary::compareSignatureStrings`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L11503) |

## 规范化

`convertSignature` 按 `QString`/`QChar` 行为执行：

- 引号外只删除 U+0020，不删除 tab、CR、LF 等其他 whitespace；
- 引号外 `?` 转成 `.`，其余字符转小写；
- 单引号切换 quoted 状态，本身不进入结果；
- quoted QChar 经 `toLatin1()` 后编码为两个小写 hex nibble；
- 未闭合单引号不会产生错误，余下内容全部作为 quoted bytes 转换。

最后一项是已观察到的宽松兼容行为，不应成为新规则的推荐语法。

## Record grammar 与执行

| 源 token | Record | 固定实现行为 |
| --- | --- | --- |
| `00`–`ff`、`'text'` | `ST_COMPAREBYTES` | 精确字节比较 |
| `..` 或 `??` | `ST_SKIP` | 消耗一个任意字节 |
| `**` | `ST_NOTNULL` | 字节必须非零 |
| `%%` | `ST_ANSI` | `0x20 <= byte < 0x80` |
| `!%` | `ST_NOTANSI` | 不在上述 ANSI 范围 |
| `_%` | `ST_NOTANSIANDNULL` | 非 ANSI 且非零 |
| `%&` | `ST_ANSINUMBER` | 实现只接受 ASCII `0`–`9` |
| `+...bytes` | `ST_FINDBYTES` | 每个 `+` 增加 32-byte 搜索 window |
| `$$`/`$$$$`/… | `ST_RELOFFSET` | 读取 1/2/4/8-byte 相对偏移并跳转 |
| `##`/`####`/… | `ST_ADDRESS` | 读取 1/2/4/8-byte 地址并映射到文件 offset |

header 注释把 `%&` 描述为 ANSI alphanumeric，但
[`_isMemoryAnsiNumber`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L7317)
实际只接受 `0x30..=0x39`。兼容实现必须以 matcher 为准，并用回归测试固定此差异。

相对偏移和地址不是纯 byte-pattern：endianness、`FT_AMIGAHUNK`、
`FT_COM`/`FT_MSDOS`、code base、segment address 以及
`offsetToAddress`/`addressToOffset` 都会改变结果。parser 可以独立实现，但 matcher
需要完整 format memory-map context。

## 上游宽松行为

固定 parser 以重复字符数量除以二得到 byte/width，未统一验证偶数长度；
`QByteArray::fromHex` 也接受奇数 nibble。Qt 5.15.13 oracle 在固定
`diec-rust/upstream-oracle:74eaf505` 镜像中得到：

```text
QByteArray::fromHex("abc").toHex() == "0abc"
```

动态 inventory 中有 5 个 pattern 需要这种宽松模式：

- 4 个 pattern 有未闭合 quoted string；
- 1 个 pattern 同时有奇数 hex run 和单个 `.`，因此产生两个 quirk。

本项目的 strict parser 对它们给出错误；显式 upstream-compatible 模式复现并返回
quirk 清单。这样既能保持固定规则兼容，又不会静默接纳未来未知语法。无效后缀导致
的“部分 record 仍可能被 compare”行为尚未建立完整 oracle，不在本轮结论内。

## 动态 inventory

`trace-binary-detects` 对固定 292 条 Binary 规则和项目生成的 128-byte 样本记录了
32 条规则、331 次 `X.c` 调用、317 个唯一 pattern。可重复提取工具为
[`extract_signature_inventory.py`](../../tools/rules/extract_signature_inventory.py)，
机器清单位于
[`signature-pattern-inventory.json`](data/signature-pattern-inventory.json)。

该清单是单一样本的动态覆盖，不是全规则静态语言清单；未执行分支中的动态构造
pattern 仍可能缺失。

## 纯 Rust spike

隔离 spike 位于
[`spikes/signature-parser/`](../../spikes/signature-parser/)，正式 workspace/API
不得依赖它。当前结果：

- runtime dependency 为零；`serde_json` 只用于测试读取 inventory；
- strict 模式解析 312/317，拒绝上述 5 个宽松 pattern；
- upstream-compatible 模式解析 317/317，并返回 6 个具体 quirk；
- raw matcher 已覆盖 literal、wildcard、五类 byte predicate 和 bounded find；
- relative offset/address 被解析为结构化 operation，但 raw matcher 明确返回
  `MemoryMapRequired`；
- 空串、奇数 token、未知字符、无 find needle 和未闭合结构均有结构化错误。

机器摘要见
[`signature-parser.json`](data/signature-parser.json)。

## 下一步门禁

1. 对固定 `db`/`db_extra` 做 AST 或 runtime-assisted 全调用点 inventory，覆盖
   非执行分支和动态拼接。
2. 建立直接调用固定 XBinary 的 C++ oracle harness，覆盖每种 record、畸形输入、
   越界和 partial-parse 行为。
3. 为 relative/address operation 提供 PE、ELF、Mach-O、COM/MSDOS、AmigaHunk
   memory-map 向量。
4. 比较 XScanEngine header-signature fast path 与通用 matcher 的边界差异。
5. 只有 parser、matcher 和 `find_signature` 差分门禁通过后，才能替换当前
   rquickjs spike 中的五-pattern 特判。
