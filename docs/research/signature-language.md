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
转发到 `find_signature`。它复用规范化和部分 record，但按 token 选择 control-record、
SigByte 或 plain-hex 三条搜索路径，不能视为 `compare` 的简单范围循环。

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
| SigByte parser | [`XBinary::_signatureToSigBytes`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L4391) |
| 范围搜索 | [`XBinary::find_signature`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L4658) |
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

上表描述 `compareSignature` 的 record matcher。header 注释把 `%&` 描述为
ANSI alphanumeric，但
[`_isMemoryAnsiNumber`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xbinary.cpp#L7317)
实际只接受 `0x30..=0x39`。兼容实现必须以 matcher 为准，并用回归测试固定此差异。

相对偏移和地址不是纯 byte-pattern：endianness、`FT_AMIGAHUNK`、
`FT_COM`/`FT_MSDOS`、code base、segment address 以及
`offsetToAddress`/`addressToOffset` 都会改变结果。parser 可以独立实现，但 matcher
需要完整 format memory-map context。

## `compare` 与 `find_signature` 不是同一语义

`find_signature` 先检查规范化 pattern：

- 含 `$`、`#` 或 `+` 时使用 `getSignatureRecords`，再选择 anchor 并回调
  `_compareSignature`；
- 含 wildcard/byte-class token 时使用 `_signatureToSigBytes` 和
  `_findSigBytes`；
- 其他输入直接交给 `QByteArray::fromHex` 和 `find_array`。

SigByte matcher 与 record matcher 已有可观察差异：

- `%&` 的 record matcher 只接受数字，SigByte 使用 `g_alphaNumTable`，字母也匹配；
- record ANSI 范围是 `0x20..0x7f`，即包括 DEL `0x7f`；SigByte ANSI 是
  `0x20..0x7e`；
- 对 `!%`，DEL 的两侧结论相反；
- SigByte 路径在前三个以上 token 非固定、随后至少三个 token 固定时，先搜索固定
  anchor，再回调 record matcher 校验整个 pattern；因此 `%&%&%&414243` 对
  `ABCABC` 不会采用 SigByte 的 alphanumeric 结论，而会因 record matcher
  只接受数字而失败；
- plain-hex find 会容忍 `QByteArray::fromHex` 忽略的无效字符，而
  `isSignatureValid` 仍可返回 false；
- 以 `+` 开头的 pattern 可以在 offset 0 直接 compare 成功，但
  `find_signature` 先找到 needle 后从该位置再次执行 `ST_FINDBYTES`，窗口越界时
  返回 `-1`。固定 `++'MZ'`/66-byte 向量复现了该行为。

所以未来 Rust API 至少需要独立的 `compare_at` 与 `find` conformance；不能用
“循环调用 compare”替代上游 find，也不能让两者共享一个未经验证的 class table。

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
quirk 清单。这样既能保持固定规则兼容，又不会静默接纳未来未知语法。固定 oracle
还确认 `41x` 的 validity 为 false、诊断为 `Invalid signature: 41x`，但 compare
仍使用已形成的 `41` record 并返回 true；这类 partial parse 必须作为 legacy
compatibility profile，而不是 strict parser 默认行为。

## 动态与静态 inventory

`trace-binary-detects` 对固定 292 条 Binary 规则和项目生成的 128-byte 样本记录了
32 条规则、331 次 `X.c` 调用、317 个唯一 pattern。可重复提取工具为
[`extract_signature_inventory.py`](../../tools/rules/extract_signature_inventory.py)，
机器清单位于
[`signature-pattern-inventory.json`](data/signature-pattern-inventory.json)。

该清单是单一样本的动态覆盖，不是全规则静态语言清单；未执行分支中的动态构造
pattern 仍可能缺失。

为覆盖未执行分支，
[`extract_static_signature_inventory.js`](../../tools/rules/extract_static_signature_inventory.js)
使用固定规则 subtree 自带的 UglifyJS 3.19.3 parser（BSD-2-Clause）解析
`db`/`db_extra` 全部 `.sg`。parser 的 18-file manifest SHA-256 为
`08dce1589c2782677f197d6289ebce3edc968aa0a35c982c0e6b66788e9e70a6`；
2175 个规则文件、2,771,327 bytes 的 manifest SHA-256 为
`a3254bdea9f58544f50eeff02378b48d24f70dbb782ecca1662e222b35596ae0`。
结果 2175/2175 parse、0 failure。

静态 AST 清单
[`signature-static-inventory.json`](data/signature-static-inventory.json)
保存每个调用点的路径、行列、receiver、方法、pattern 参数表达式和保守静态值：

| 方法 | 调用点 |
| --- | ---: |
| `c` | 1191 |
| `compare` | 1367 |
| `compareEP` | 2783 |
| `compareOverlay` | 217 |
| `fSig` | 120 |
| `findSignature` | 113 |
| `isSignatureInSectionPresent` | 105 |
| `isSignaturePresent` | 72 |
| **总计** | **5968** |

5968 个调用点分布在 1615 个文件，receiver 均落在已知格式宿主集合；同名未知
receiver 候选为 0。参数分类为 5855 个直接字符串、108 个可保守枚举的静态表达式
（字符串拼接、条件分支、sequence，或只有一次初始化且未检测到写入的变量引用）
和 5 个动态表达式。有限、非逃逸且元素可静态枚举的数组，其动态下标采用全部元素
并集；数组只允许下标和 `length` 读取，发生方法调用、传参、别名或其他逃逸即保持
动态。每个表达式最多枚举 4096 个值，超限也保持动态。静态可枚举得到 5628 个唯一
pattern：包含动态样本观察到的全部 317 个，另有
5311 个未被该样本执行的 pattern。

另有三个纯字符串转换只有在规则路径、函数名及函数源码 SHA-256 全部匹配时才允许
静态执行：`convertStringToUnicodeSignature`、`generateUnicodeSignatureMask`
和 `toUtf16LE`。固定规则三项均验证通过，0 failure；篡改任一函数源码的回归
fixture 会使其调用保持动态。该门禁又闭合 10 个调用、22 个唯一 pattern。

| 路径与函数 | 函数源码 SHA-256 |
| --- | --- |
| `db/PE/__GenericHeuristicAnalysis_By_DosX.7.sg` → `convertStringToUnicodeSignature` | `3c056d3048e21c54c20476f49deb81126a52edf6b7ce6a17848960f726cdc1d9` |
| `db/PE/protector_VMProtect_NET.2.sg` → `generateUnicodeSignatureMask` | `1dab6af286316c2cccda2a3a3bc6698b287df9e2ab872f8b9b7ebbe69cfec4af` |
| `db_extra/PE/protector_Protection_Plus_SDK.2.sg` → `toUtf16LE` | `2039971c64346d49c427088f7f58b8c62f58104886bc06d7084ad37e91117d5b` |

具名 helper 的标量参数只在函数不逃逸、每个直接调用点参数均可静态求值时传播
全部调用值并集。顶层函数还要求名字在全规则库中唯一，且不存在其他规则中的
unresolved direct call；嵌套函数依赖词法作用域。全库审计了 2290 个顶层定义：
95 个名字唯一、7 个名字重复、72 个 unresolved direct-call 名字，最终 95 个顶层
定义满足门禁。清单保存 26 个有限参数记录；其中 signature 参数传播闭合 12 个调用、
增加 125 个唯一 pattern。动态参数中不再有 `Call` AST。

三个同名顶层 `validateReferences` helper 因共享 global scope 不进入上述通用参数
门禁，而使用更窄的数组参数门禁。固定执行协议保证每条规则文本求值后立即取得并
调用该规则的 `detect`；额外的全语料审计要求三个 helper 分别匹配路径、函数名和
完整函数源码 SHA-256，并要求 `db`/`db_extra` 中所有同名引用都直接绑定到当前
规则已验证的定义。三个固定定义和三个直接调用全部通过，0 个不安全引用：

| 路径 | helper 源码 SHA-256 | 数组元素 |
| --- | --- | ---: |
| `db/PE/cryptor_LimeCrypter.2.sg` | `aee17a5bf77037e78a05883d33a50edabfe0e5b4eb1126ba515f11767193f71d` | 4 |
| `db/PE/cryptor_PEUnion.2.sg` | `ceb0109b92a60190e3cc926a6678acac7d36d5ea0d35020351db5186c5460c05` | 14 |
| `db_extra/PE/cryptor_njCrypter.2.sg` | `aee17a5bf77037e78a05883d33a50edabfe0e5b4eb1126ba515f11767193f71d` | 8 |

数组实参还必须保持固定源码中的伪命名参数形状
`references = [<非空纯字符串数组>]`，目标必须是未声明 global，helper 不能逃逸，
所有直接调用都必须满足且总元素数受 4096 上限约束。函数源码改变、直接数组实参
或 helper 逃逸 fixture 均保持动态。三条 `finite_array_parameter_values` 记录闭合
正/负分支共 6 个调用，增加 14 个唯一 pattern。

函数作用域常量还要求：目标符号在该函数内只有一次 `=` 写入，该写入是函数第一条
直接语句；值从赋值结束起生效，并在首个直接符号函数调用处失效。条件写入、重复
写入和调用屏障 fixture 均保持动态。全库仅产生 5 条此类记录；其中
`audio.1.sg::isAVP` 的 `d1 = "48E7FCFE"` 闭合 20 个调用、增加 2 个唯一
pattern。

精确的函数局部同 binding 自赋值 `x = x` 不改变值，因此不计作 mutation；该规则
不适用于顶层 binding、不同符号赋值、compound assignment 或后续真实写入；一个
正例与四个负例固定此边界。全库仅因此闭合
`__GenericHeuristicAnalysis_By_DosX.7.sg` 的
`njRatDataSeparatorPattern` 一个调用，得到一个新增 pattern
`7C0027007C0027007C0000`。

有限对象键传播要求：对象是同一代码块内先声明的单变量、所有值均为字符串的对象
字面量；对象只能用于 `for…in` 和下标读取，不能逃逸或修改；key 在该函数内只能由
这一条 `for…in` 写入；`__proto__` 键明确拒绝。另有全语料 plain-object 原型门禁：
2175 个文件中的唯一 `Object` 引用解析为未声明的全局内建，并且是
`Object.prototype.hasOwnProperty.call`，`globalThis`、`eval`、`Function`、
`__proto__`、`constructor` 的敏感引用均为 0；任一不安全引用会关闭全部对象键传播。

固定 Qt 5.15.13 `QScriptEngine` 探针在可重复 oracle 镜像
`diec-rust/upstream-oracle:74eaf505-repro`
（image ID
`sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab`）
中确认 `Object.prototype` 没有可枚举
继承键，并按源码顺序枚举 PDB 的四个 own key。源码与原始结果分别见
[`qtscript_object_enumeration_probe.cpp`](../../tools/upstream/qtscript_object_enumeration_probe.cpp)
和
[`qtscript-object-enumeration.json`](data/qtscript-object-enumeration.json)。
该门禁恰好闭合 `format_PDB.1.sg:35` 的一个调用，新增四个唯一 pattern。

复现实验（POSIX shell）：

```sh
docker run --rm -v "${PWD}/tools/upstream:/src:ro" \
  diec-rust/upstream-oracle:74eaf505-repro sh -lc \
  'mkdir /tmp/qtscript-enum && cd /tmp/qtscript-enum &&
   /usr/lib/qt5/bin/qmake /src/qtscript_object_enumeration_probe.pro &&
   make -j2 &&
   ./qtscript-object-enumeration-probe'
```

块内相邻赋值传播只接受函数局部字符串 binding 的简单 `=`：右值必须可静态枚举，
下一条语句必须直接包含使用该 binding 的已知识别宿主 signature 调用，且该语句中
不得出现未知/直接函数调用或对目标的再次写入，目标也不得被嵌套 lambda 捕获。
值域仅从赋值结束持续到下一条语句结束；跨语句间隔、条件单语句赋值、目标重写和
未知调用 fixture 均保持动态；精确
`x = x` 由独立无操作规则处理，不重复记账。全库恰好产生两条记录：
`__GenericHeuristicAnalysis_By_DosX.7.sg:6219` 对有限
`requiredDotNetImports` 数组构造五个 `importSignature` 值，并闭合 6220 行调用；
其中四个是新增唯一 pattern；同文件 6368 行构造 46 个值并闭合 6369 行调用。

第二条记录依赖一项独立、受限的对象数组元素传播。源必须是在同一块内紧邻循环前
声明的单变量、非空且非逃逸的数组；每个元素必须是无重复敏感键的对象字面量，值
只能是字符串、数字、布尔、`null`、未遮蔽的全局 `undefined` 或非空字符串数组。
循环只接受
`for (var j = 0; j < source.length; j++)`，第一条语句必须是
`target = source[j]`；目标必须是未被闭包捕获且全函数仅有这一处符号写入的局部
binding。对象标量属性只能读取，数组属性只能读取 `length` 或下标，传参、别名、
属性写入、有副作用的字面量值、非零起点、循环区间内额外索引写入及非首条赋值
fixture 均保持动态。值域仅在该循环内有效；函数作用域 `var j` 可在不重叠的其他
循环复用，但目标循环区间只能有规范 `j++`。全库恰好产生一条
`finite_object_element_assignments` 机器记录：
`maliciousImportPatterns` 的 12 个对象给出 46 个 `references` 签名值，其中
41 个是新增唯一 pattern。

确定性循环仅在可证明的 canonical 形态下折叠：目标必须由紧邻循环的单变量
声明初始化；循环必须是固定安全整数范围的
`for (var i = start; i < limit; i++)`；循环体只能有一条
`target += <静态字符串>`；迭代和值笛卡尔积仍受 4096 上限约束。循环结果从循环
结束后生效，并在首个直接符号函数调用处失效。动态上界、额外循环体语句和非紧邻
初始化 fixture 均保持动态。全库恰有两条记录：
`protector_NetReactor.2.sg` 的 5 次累积与
`protector_VMProtect_NET.2.sg` 的 12 次累积，各闭合一个调用并各增加一个唯一
pattern。

固定 XScanEngine `modules/binary_script.h` 的 slot 声明和
`modules/binary_script.cpp:893` 的 `Binary_Script::c(const QString &, qint64)`
实现证明 signature 始终是第一个参数，没有反向重载。因此 `audio.1.sg` 的
`X.c(p+o, "'PACK'FFFF")` 和 `X.c(p+8, "'PACK'FFFF")` 仍按 Qt 参数转换保留为
输入依赖调用，不能把第二参数改当 signature。

“包含动态 317/317”证明动态清单是静态清单的子集，不证明 5628 是完整运行时值域。
剩余 5 个调用仍依赖偏移量或输入数据流；非静态 computed
method name 也不能仅凭 AST 属性名归因。当前可以把具名 signature API 的语法调用
点范围视为完整，但运行时 pattern value 范围仍未闭合。

## 固定 Qt 5 XBinary oracle

[`signature_harness_main.cpp`](../../tools/upstream/signature_harness_main.cpp)
直接实例化固定 XBinary，通过 JSON 向量调用 `convertSignature`、
`isSignatureValid`、`compareSignature`、`find_signature` 和
`compareSignatureStrings`。Dockerfile 继承现有固定 CMake Qt 5 oracle image，
复用上游 target 的对象与链接命令，只替换 console main object；不修改 Formats
源码。

输入由
[`generate_signature_oracle_vectors.py`](../../tools/corpus/generate_signature_oracle_vectors.py)
生成，共 63 个项目自有向量。原始输出保存为
[`signature-oracle-qt5.json`](data/signature-oracle-qt5.json)，自动探针
[`probe_signature_harness.py`](../../tools/upstream/probe_signature_harness.py)
在禁网、512 MiB、1 CPU、128 PID 限制下验证 image revision、binary hash、
输入 identity 及 baseline 原始 bytes。当前结果 63/63，stdout/baseline
SHA-256 均为
`fd8dc107545ea5eac4383af72f449617c556a679d8c7e74b844f77b39b04f222`。

构建与复现：

```sh
docker --context=default buildx build \
  --load \
  --provenance=false \
  --file tools/upstream/Dockerfile.signature-harness-qt5 \
  --tag diec-rust/upstream-signature-harness:74eaf505 \
  tools/upstream

python tools/upstream/probe_signature_harness.py \
  --docker-context default \
  --image diec-rust/upstream-signature-harness:74eaf505 \
  --binary /opt/die-build/src/console/diec-signature-harness \
  --vectors docs/research/data/signature-oracle-vectors.json \
  --baseline docs/research/data/signature-oracle-qt5.json \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254
```

### `Binary_Script::compare` header fast path

固定
[`Binary_Script::compare`](https://github.com/horsicq/XScanEngine/blob/dfe4a419e4f491bb23688ba03c5a5bf39e34da83/modules/binary_script.cpp#L95)
不会始终调用 record matcher。构造器先缓存最多 256 bytes 的 header signature；
`compare` 对规范化签名执行以下 fast-path 判定：

- `nSignatureSize` 是规范化 `QString` 的字符数，而 header cache size 是 bytes；
- 条件是 `nSignatureSize + nOffset < m_nHeaderSignatureSize`，使用严格 `<`；
- `$`、`#`、`+`、`%` 或 `*` 强制进入通用 matcher；
- 通过判定后调用 `compareSignatureStrings`，否则调用 `compareSignature`。

这不只是性能分支。5 个项目向量已端到端构造 `Binary_Script` 并调用 `compare`：

- 对 256-byte 输入和 invalid suffix `41x`，XBinary record matcher 会用已经形成的
  `41` record 返回 true；offset 0 和 252 满足 fast-path 条件，
  `compareSignatureStrings` 返回 false；
- offset 253 时 `3 + 253 == 256`，严格 `<` 不成立，回退 record matcher 并返回
  true，同时保留 `Invalid signature: 41x` diagnostic；
- 普通 `41` 在 offset 253（fast path）和 254（严格边界回退）均返回 true，
  证明差异来自 matcher 选择而非输入字节。

因此 Rust Host API 不能把 `X.c` 无条件简化为 record matcher；至少 legacy
compatibility profile 必须保留这一 wrapper-level 可观察行为。

`compareEP` 和 `compareOverlay` 的实现又有两处不同：

- 两个构造器字段都把最多 256 bytes 的缓存保存为 hex `QString`，随后直接用
  `QString::size()` 得到 512，而 header 分支会除以二得到 256；
- 分支判定使用原始 `sSignature.size()`，不是规范化后字符串长度。

项目生成的 PE32 把 entry point 固定在文件 offset `0x200`，overlay 固定在
`0x600` 且长度为 512 bytes。EP 和 overlay 各 5 个端到端向量得到完全相同的
wrapper 行为：

- 合法 `41` 位于相对 offset 508 和 509 时，通用 EP/overlay matcher 返回 true；
  wrapper 却因 `2 + offset < 512` 错走 fast path，从实际 256-byte cache 外取空串
  并返回 false；
- offset 510 时 `2 + 510 == 512`，严格 `<` 不成立，wrapper 回退通用 matcher
  并返回 true；
- 同在 offset 508，把 pattern 写成规范化结果相同的 `" 41 "` 后，原始长度 4
  使 `4 + 508 == 512`，wrapper 改走通用 matcher 并返回 true；
- `41x` 在 offset 0 再次确认 fast-path string matcher false，而对应通用 matcher
  使用 partial record 返回 true。

这证明 cache 长度单位错误和原始/规范化长度混用都能改变合法输入上的检测结果，
不能作为内部不可观察的性能细节忽略。当前实验固定了一个有效 PE32 entry point
和足长 overlay；不存在、短小、无效以及非 PE 上下文仍待扩展。

### 合成 memory-map 差分

oracle schema v2 允许每个项目自有向量显式注入 `_MEMORY_MAP`，但仍调用未修改的
固定 XBinary matcher。7 个向量覆盖：

- PE：raw offset 有间隙、virtual address 连续时的 32-bit relative jump；
- ELF：big-endian 16-bit relative jump；
- Mach-O：跨 record 的 64-bit absolute address；
- COM：相对跳转使用 16-bit offset wrap，忽略 address map；
- MS-DOS：16-bit absolute address 加 `nCodeBase`，以及 32-bit
  segment:offset 加 `nStartLoadOffset`；
- AmigaHunk：16-bit relative value 不增加 operand width。

纯 Rust `MemoryMap` port 与固定 oracle 7/7 一致。实验还确认
`isOffsetValid` 在 `nBinarySize != 0` 时只检查整个 binary 范围，不要求 cursor
落在某个 record；因此 Rust matcher 不能额外施加 record 连续性约束。

这些合成向量隔离 matcher 分支，不单独证明格式 parser 构造出的 map 正确。
因此 generator 另行产生带两个映射区域的 PE32/64、ELF32/64 和 Mach-O32/64，
以及最小 COM、MS-DOS、AmigaHunk 文件。harness 分别直接实例化固定格式 parser，
先验证 `isValid()`，再把真实 `getMemoryMap()` 交给同一 signature matcher：

- PE32/64、ELF32/64 使用 relative jump 跨越不连续 raw region；
- Mach-O32/64 分别使用 32/64-bit absolute address 跨 segment；
- COM 验证 16-bit relative 分支；
- MS-DOS 用 far pointer 验证 `nStartLoadOffset`；
- AmigaHunk 验证大端 relative word 不增加 operand width。

九种格式/位宽组合均有效且 compare 成功；Rust 从上游派生 map 重放后 9/9
一致。该端到端层当前仍未覆盖畸形、重叠和 virtual-only map。

## 纯 Rust spike

隔离 spike 位于
[`spikes/signature-parser/`](../../spikes/signature-parser/)，正式 workspace/API
不得依赖它。当前结果：

- runtime dependency 为零；`serde_json` 只用于测试读取 inventory；
- strict 模式解析 312/317，拒绝上述 5 个宽松 pattern；
- upstream-compatible 模式解析 317/317，并返回 6 个具体 quirk；
- raw matcher 已覆盖 literal、wildcard、五类 byte predicate 和 bounded find；
- relative offset/address 在没有上下文时明确返回 `MemoryMapRequired`，传入显式
  `MemoryMap` 后覆盖通用映射、端序、COM/MS-DOS 和 AmigaHunk 特殊分支；
- 空串、奇数 token、未知字符、无 find needle 和未闭合结构均有结构化错误；
- 16 个 context-free `compareSignature` 向量与固定 Qt 5 XBinary oracle 16/16
  一致，7 个合成 memory-map 向量 7/7 一致，9 个真实格式 parser map 向量
  9/9 一致；
- 独立 `find_signature` 实现覆盖 plain-hex、SigByte、control-record 三条路径，
  包括范围截断、固定/最长/类锚点和无锚点回退；19 个聚焦向量与固定 oracle
  19/19 一致，未以循环调用 raw matcher 代替搜索算法；
- wrapper-level oracle 对 header `compare`、`compareEP`、`compareOverlay` 各覆盖
  5 个向量并全部通过，固定了三种 cache-size/边界行为。

机器摘要见
[`signature-parser.json`](data/signature-parser.json)。

## 下一步门禁

1. 对 5 个动态 signature 参数做 scope/data-flow 或受控 runtime-assisted
   求值，并审计 computed method name；不得把 5628 个静态值当作完整值域。
2. 扩展现有 XBinary oracle，覆盖更多畸形组合、buffer boundary 和取消行为。
3. 补齐畸形/重叠/virtual-only map 的项目生成文件，端到端验证各格式
   `getMemoryMap` 边界。
4. 扩展 `Binary_Script` wrapper oracle 到不存在/短小 overlay、无效 entry point
   和非 PE parser，确认错误与 fallback 行为。
5. 扩展 `find_signature` 差分到 malformed partial-parse、更多 buffer boundary
   和锚点优化组合，并验证取消行为；现有 19-case spike 不作为完整性证明。
6. 只有 parser、matcher 和 `find_signature` 差分门禁通过后，才能替换当前
   rquickjs spike 中的五-pattern 特判。
