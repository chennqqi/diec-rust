# 上游 CLI 输出转义与嵌套顺序

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Component: `horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-28

## 1. 范围

本文固定发布 `diec` 普通扫描的五种无颜色 formatter：

- JSON、XML、CSV、TSV 和 plain text 对规则结果特殊字符的处理；
- JSON/XML 的嵌套父子表示；
- CSV/TSV/plain text 的嵌套遍历顺序；
- 两套 Linux Qt5 构建的原始字节一致性。

项目生成的
[`output-boundary-fixture.json`](data/output-boundary-fixture.json)
通过一条 ASCII JavaScript 规则向 type/name/version/info 注入引号、反斜杠、
斜杠、分号、逗号、tab、CR、LF、XML 元字符、撇号、Snowman、CJK、emoji
及 U+2028/U+2029。嵌套 case 复用
[`nested-corpus.json`](data/nested-corpus.json) 中的
`PE32 -> Resource -> PDF`。

机器报告为
[`cli-output-boundaries-linux-qt5.json`](data/cli-output-boundaries-linux-qt5.json)。
它保存 10 个 case、20 次进程执行的完整 stdout/stderr Base64、长度和
SHA-256，以及机器可检查的 13 条事实。

## 2. 固定身份与源码

| Build | Image ID | Binary SHA-256 |
| --- | --- | --- |
| qmake Qt5 | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| CMake Qt5 | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |

两者 revision 均为
`74eaf505c250ab47e709024e9dc41657cd8f2254`。报告还从两个镜像分别计算并要求
以下文件哈希相等：

- `src/console/main_console.cpp`：
  `ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f`；
- `XScanEngine/scanitemmodel.cpp`：
  `53299fa3811510ab9dd791ed2d9ac51e82289f9fbbed303eabf991d642ac6037`；
- `XScanEngine/scanitemmodel.h`：
  `3150ab7ad6e75b522a853e774bf349f83ba551ab6cbe7f547068bcf4d8255676`；
- `die_script/die_scriptengine.cpp`：
  `f9b9d69a17dc930556c7308fce46d3287d18dd9f927c91d6733ce994594fcb72`。

固定 `ScanItemModel` 实现决定 formatter 语义：

- `_toJSON()` 递归构造 `QJsonObject/QJsonArray`，最终由
  `QJsonDocument::Indented` 序列化；
- `_toXML()` 用 `QXmlStreamWriter` 写 attribute/text，但父节点元素名直接取
  `ScanItem::data(0)` 的显示字符串；
- `_toCSV()` 直接拼接 `%1;%2;%3;%4;%5\n`；
- `_toTSV()` 直接拼接五个 tab 分隔字段；
- `_toFormattedString()` 只按深度添加四空格缩进。

CSV/TSV 路径没有 quoting、doubling 或 delimiter/newline escaping。

## 3. 可重复实验

```text
python tools/corpus/generate_output_boundary_fixture.py <output-fixture>
python tools/corpus/generate_nested_corpus.py <nested-fixture>

python tools/upstream/probe_cli_output_boundaries.py \
  --left-image diec-rust/upstream-oracle:74eaf505-repro \
  --left-binary /opt/die-source/build/release/diec \
  --right-image diec-rust/upstream-oracle-cmake:74eaf505 \
  --right-binary /opt/die-build/src/console/diec \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --output-fixture-dir <output-fixture> \
  --nested-corpus-dir <nested-fixture> \
  --output docs/research/data/cli-output-boundaries-linux-qt5.json
```

每个进程断网、1 CPU、512 MiB、128 PIDs，两个 fixture 只读挂载。全部 case
exit 0、stderr 为空，两套构建的原始 stdout 逐字节相同。

## 4. 特殊字符结果

三条规则结果的顺序固定为 `format -> compiler -> tool`。第一条结果的字段同时
含全部边界字符；第二条再提供 delimiter/tab/newline；第三条是无 version 的
正常尾记录，证明前述字符没有阻止后续 record 输出。

| Formatter | 结果 |
| --- | --- |
| JSON | 是有效 UTF-8 JSON；解析后的四字段与注入值逐字符相同；quote、backslash、tab、CR、LF 被 JSON escaping，Snowman/CJK/emoji/U+2028/U+2029 保留为 UTF-8 |
| XML | flat case 是可解析 XML；attribute 中 quote、tab、CR、LF、`<>&` 分别使用 entity/numeric reference，解析后字段与注入值相同 |
| CSV | 不加引号、不 doubling；字段内 `;` 增加列，CR/LF 增加物理行，因此输出不是可靠的五列 CSV |
| TSV | 不加引号；字段内 tab 增加列，CR/LF 增加物理行，因此输出不是可靠的五列 TSV |
| plain text | 字段原样进入显示串；tab/CR/LF 改变可见布局和逻辑行数 |

报告中的事实名
`csv_is_unquoted_and_delimiter_ambiguous` 与
`tsv_is_unquoted_and_delimiter_ambiguous` 明确固定这种破损，而不是用宽泛
normalizer 把它修正成合法表格。

## 5. 嵌套结果

`pe-pdf-resource.exe --recursivescan` 的语义顺序是：

```text
PE32
  Unknown: Unknown
  Resource PDF (offset 608, size 331)
    Format: PDF(1.4)
    Complier: HeaderComment(e2e3cfd3)
```

各 formatter 的可观察契约：

- JSON 保留完整 parent/child tree、`parentfilepart=Resource`、offset/size 和
  两层数组顺序；
- XML 先输出 Unknown，再进入 Resource，再输出 PDF/HeaderComment，遍历顺序
  与 JSON 相同；但动态元素名是
  `Resource: PDF[Offset=0x0260,Size=0x014b]`，含 colon、space、`[`、`]`，
  最终 stdout **不是 well-formed XML**。机器事实为
  `xml_dynamic_nested_element_is_not_well_formed`；
- CSV/TSV 完全省略 PE32/Resource parent，只按 depth-first 顺序输出三条 leaf；
- plain text 保留 PE32、Resource parent 和四空格逐层缩进。

因此，不能从 CSV/TSV 重建父子关系，也不能把上游 `--xml` 一概宣传为有效 XML。
差分测试必须保留原始字节；只比较成功解析后的文档会直接漏掉 nested XML。

## 6. 对 Rust 输出设计的约束

- legacy renderer 必须逐 formatter 建模，不能共用一个“安全结构化输出”实现后
  仍声称原始兼容；
- legacy JSON 保留字段、字符串、数组顺序和十进制 string offset/size；
- legacy XML 若追求逐字节兼容，必须保留动态元素名导致的非法输出，并在 API/
  文档中明确它只属于 compatibility profile；
- modern canonical XML（若提供）使用固定合法 element name，把显示文本放入
  attribute/text，并明确标记为与 legacy 不同；
- legacy CSV/TSV 保留无转义字节；modern tabular export 必须采用具名、安全且
  可解析的 quoting/escaping contract，不能复用同一个命令名冒充等价；
- canonical JSON 和 C ABI 不继承上述无效 XML/CSV/TSV framing。

## 7. 尚未覆盖

- Windows/macOS 与 Qt6 的 formatter 字节差异；
- native filename encoding 和多目标 filename prefix 的特殊字符；属于
  `CAP-GAP-003/007/008`；
- entropy/info/struct 模型自身产生特殊字符时的 formatter 边界；
- 非 PE 的更多 nested parent 显示字符串。固定实现已证明动态元素名的通用风险，
  但本实验只把 PE Resource case 采纳为 golden。
