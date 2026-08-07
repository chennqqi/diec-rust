# die-gui 与上游 Qt GUI 深入差异分析

Status: Draft
Upstream: `horsicq/DIE-engine@ab0ea3e2764c9c5616362070be5c85404e3f7756` (master)
die_widget: `horsicq/die_widget@5b483772edde713fb872bc3ca86cfde4c00ea42c`
FormatWidgets: `horsicq/FormatWidgets` (master, 2026-08-07 fetch)
XHexView: `horsicq/XHexView` (master, 2026-08-07 fetch)
XDisasmView: `horsicq/XDisasmView` (master, 2026-08-07 fetch)
XScanEngine: `horsicq/XScanEngine` (master, 2026-08-07 fetch)
XFileInfo: `horsicq/XFileInfo` (master, 2026-08-07 fetch)
diec-rust die-gui: v0.4.0（Phase 8，2026-08-06）
Last updated: 2026-08-07

## 范围

本文通过**实际运行 diec.exe 收集输出** + **上游源码静态分析**，深入对比
diec-rust `die-gui`（Tauri v2 + React）与上游 `die`（Qt6 完整 GUI）在三个
维度的差异：

1. **信息丰富度差异** — 同样功能展示的信息量差距
2. **不合理设计** — die-gui 设计缺陷或不合理之处
3. **底层库差异** — 不同解析库导致的结果显示差异

实际输出通过 `tmp/gui_diff_probe.ps1` 调用 `target\debug\diec.exe` 对 31 个
corpus 样本采集，结果存于 `tmp/probe_out/`。上游输出引用
`docs/research/data/` 下的固定基线 JSON（Qt5/Qt6 双轮）。

参考文档：
- [`upstream-gui-analysis.md`](upstream-gui-analysis.md) — 上游 GUI 源码结构
- [`docs/design/phase8-gui.md`](../design/phase8-gui.md) — Phase 8 设计文档
- [`COMPATIBILITY.md`](../../COMPATIBILITY.md) — 兼容性基线

---

## 1. 信息丰富度差异

### 1.1 扫描结果字符串格式

**上游 `ScanItemModel` 使用 `createResultStringEx` 格式化**（源码：
`XScanEngine/xscanengine.cpp:2057-2094`）：

```cpp
QString XScanEngine::createResultStringEx(SCAN_OPTIONS *pOptions, const SCANSTRUCT *pScanStruct)
{
    // 1. 启发式标记
    if (pScanStruct->bIsHeuristic)      sResult += "(Heur) ";
    else if (pScanStruct->bIsAHeuristic) sResult += "(A-Heur) ";
    // 2. 类型前缀（bShowType=true 时）
    sResult += QString("%1: ").arg(translateType(pScanStruct->sType));
    // 3. 检测名
    sResult += pScanStruct->sName;
    // 4. 版本（bShowVersion=true 时）
    sResult += QString(" (%1)").arg(pScanStruct->sVersion);
    // 5. 信息（bShowInfo=true 时）
    sResult += QString(" [%1]").arg(pScanStruct->sInfo);
    return sResult;
}
```

上游 `DIE_Widget::process()` 设置 `bShowType=true, bShowVersion=true,
bShowInfo=true`（`die_widget.cpp:178-180`），因此上游 GUI 展示的完整格式是：

```
(Heur) Type: Name (Version) [Info]
```

**die-gui `DetectionTreeView` 展示**（`App.tsx:1172-1180`）：

```tsx
<span className="text-fg-secondary">{d.type_name}: </span>
<span className="text-fg-primary">{d.name}</span>
<span className="w-20 text-center text-fg-muted">{d.type_name}</span>
<span className="w-24 text-fg-secondary">{d.version ?? ""}</span>
<span className="w-32 text-fg-muted truncate">
  {d.options ? `${d.options.split(",").length} options` : ""}
</span>
```

**实际输出对比**（`minimal.exe`，上游 `bShowType=true` 模式）：

| 维度 | 上游 GUI 显示 | die-gui 显示 |
| --- | --- | --- |
| 类型前缀 | `archive: ` | `archive: `（type_name 列） |
| 检测名 | `Resources` | `Resources`（name 列） |
| 版本 | `(1.0)` 如有 | `1.0` 如有（version 列） |
| 信息/选项 | `[100.0%, 2 files]` 完整显示 | **`2 options`** 计数，需点击展开 |
| 启发式标记 | `(Heur)` / `(A-Heur)` 前缀 | **无**（ScanDetection 无此字段） |
| 未知标记 | `Unknown: Unknown` 行（bHideUnknown 控制） | **无 Unknown 行** |

**关键信息丢失**：

1. **options 显示为计数**：die-gui 将 `options` 字段（如 `"100.0%, 2 files"`）
   按 `,` split 后显示为 `2 options`，用户必须点击展开才能看到具体内容。
   上游直接在主列显示完整 `[100.0%, 2 files]`。
2. **启发式标记缺失**：上游用 `(Heur)` / `(A-Heur)` 前缀区分启发式检测，
   die-gui 的 `ScanDetection` 结构无 `bIsHeuristic`/`bIsAHeuristic` 字段，
   无法展示。
3. **Unknown 行缺失**：上游在无检测时显示 `Unknown: Unknown` 行（除非
   `bHideUnknown`），die-gui 显示 "no detections"。

### 1.2 结果树层级结构

**上游 `ScanItemModel` 构建真正的树**（`scanitemmodel.cpp:50-87`）：

```cpp
// 按 id/parentId 构建嵌套树
for (qint32 i = 0; i < nNumberOfDetects; i++) {
    if (!mapParents.contains(pListScanStructs->at(i).id.sUuid)) {
        ScanItem *_pItemParent;
        if (pListScanStructs->at(i).parentId.sUuid.isEmpty()) {
            _pItemParent = m_pRootItem;
        } else {
            _pItemParent = mapParents.value(pListScanStructs->at(i).parentId.sUuid);
        }
        // ... 创建类型节点
        QString sTypeString = XScanEngine::createTypeString(pScanOptions, &pListScanStructs->at(i));
        ScanItem *pItemMain = new ScanItem(sTypeString, _pItemParent, ...);
        mapParents.insert(pListScanStructs->at(i).id.sUuid, pItemMain);
    }
    // ... 添加检测子节点
}
```

`createTypeString`（`xscanengine.cpp:1983-2040`）为非 Header 的 file part
生成带偏移和尺寸的类型字符串：

```cpp
// 对于 Resource/Overlay/Archive entry 等子节点
sResult += XBinary::recordFilePartIdToString(pScanStruct->parentId.filePart);
sResult += XBinary::fileTypeIdToString(pScanStruct->id.fileType);
sResult += QString("[%1=0x%2,%3=0x%4]")
    .arg(tr("Offset")).arg(XBinary::valueToHexEx(pScanStruct->parentId.nOffset))
    .arg(tr("Size")).arg(XBinary::valueToHexEx(pScanStruct->parentId.nSize));
```

**上游实际输出**（`docs/research/data/resource-context-chain-qt6.json`，
`pe-manifest-resource.exe` recursive+aggressive 模式）：

```json
{
  "detects": [{
    "filetype": "PE32", "offset": "0", "parentfilepart": "Header", "size": "1024",
    "values": [
      { "name": "Unknown", "type": "Unknown", "string": "Unknown: Unknown" },
      {
        "filetype": "Binary", "offset": "608", "parentfilepart": "Resource", "size": "20",
        "values": [
          { "name": "Manifest", "type": "format", "string": "Format: Manifest[Resources]" }
        ]
      }
    ]
  }]
}
```

上游 GUI 树展示：
```
Result
└── PE32
    ├── Unknown: Unknown
    └── Resource: Binary [Offset=0x260, Size=0x14]
        └── Format: Manifest[Resources]
```

**die-gui 实际输出**（`tmp/probe_out/minimal.exe/result.json`）：

```json
{
  "path": "...minimal.exe",
  "detections": [
    { "file_type": "PE", "type": "archive", "name": "Resources" }
  ],
  "diagnostics": [...6 条脚本异常...]
}
```

die-gui 树展示：
```
PE
└── archive: Resources    archive    (无 version)    (无 options)
```

**关键信息丢失**：

| 信息 | 上游 | die-gui | 影响 |
| --- | --- | --- | --- |
| 嵌套层级 | PE → Resource → Manifest | PE → Resources（扁平） | archive/resource/overlay 子结果丢失层级 |
| file part | `parentfilepart: "Resource"` | **无** | 无法区分检测来自 Header/Resource/Overlay |
| offset/size | `offset: "608", size: "20"` | **无** | 无法定位检测在文件中的位置 |
| filetype 精确值 | `PE32` / `Binary` | `PE`（file_type 字段） | die-gui file_type 不区分 PE32/PE32+ |
| sOriginalName | archive entry 原始文件名 | **无** | 无法显示 archive 内文件名 |

### 1.3 扫描选项信息丰富度

**上游 `SCAN_OPTIONS`**（`xscanengine.h`，30+ 字段）vs **die-gui
`ScanFlagsDto`**（11 字段）。关键差异：

| 上游选项 | die-gui | 信息影响 |
| --- | --- | --- |
| `bShowType` | 硬编码 true | die-gui 无法切换类型前缀显示 |
| `bShowVersion` | 硬编码 true | die-gui 无法切换版本显示 |
| `bShowInfo` | 硬编码 true | die-gui 无法切换信息显示 |
| `bFormatResult` | **无** | die-gui 无格式化空格选项 |
| `bShowScanTime` | **无** | die-gui 无扫描耗时选项（固定显示） |
| `bLogProfiling` | 设置存在但 **未传递** | 设置无效 |
| `bIsSort` | 设置存在但 **未传递** | 设置无效 |
| `fileType`（手动覆盖） | Type 下拉 **未接线** | 无法手动覆盖文件类型 |
| `sMainDatabasePath` 等 | Databases 下拉 **未接线** | 无法选择数据库 |
| `bUseExtraDatabase`/`bUseCustomDatabase` | 硬编码 true | 无法禁用额外数据库 |
| Collection 选项 | **无** | 无 collection 功能 |

### 1.4 文件信息丰富度

**上游 `XFileInfo`**（`xfileinfo.h`）提供完整的结构化文件信息模型：

```cpp
class XFileInfo {
    void _IMAGE_DOS_HEADER(XMSDOS *pMSDOS, bool bExtra);
    void PE_IMAGE_NT_HEADERS(XPE *pPE, bool bIs64);
    void PE_IMAGE_SECTION_HEADER(XPE *pPE);
    void PE_IMAGE_RESOURCE_DIRECTORY(XPE *pPE);
    void PE_IMAGE_EXPORT_DIRECTORY(XPE *pPE);
    void _Elf_Ehdr(XELF *pELF, bool bIs64);
    void _mach_header(XMACH *pMACH, bool bIs64);
    void DEX_HEADER(XDEX *pDEX);
    void ELF_Shdr(XELF *pELF);
    void _entryPoint(XBinary *pBinary, XBinary::_MEMORY_MAP *pMemoryMap);
    // ...
};
```

上游 `DialogXFileInfo` 通过 `XFileInfoModel`（树形 QAbstractItemModel）展示
**完整的 PE/ELF/Mach-O/DEX 头部字段**，每个字段包含：
- 字段名（如 `e_lfanew`）
- 值（如 `0x80`）
- 注释（如 `PE signature offset`）
- 标志位解析（如 `IMAGE_SCN_CNT_CODE | IMAGE_SCN_MEM_EXECUTE`）
- 日期时间解析（如 `TimeDateStamp: 2024-01-15 10:30:00`）

**die-gui `FileInfoPanel`**（`file_info.rs:300-329`）展示：

```rust
pub struct FileInfo {
    pub path: String,
    pub file_name: String,
    pub size: u64,
    pub size_human: String,
    pub entropy: f64,
    pub hashes: FileHashes,  // MD5/SHA1/SHA256
    pub format: String,      // "PE32"/"ELF64" 等
    pub sections: Vec<SectionInfo>,  // name/vaddr/vsize/rawoff/rawsize/entropy
    pub symbols: Vec<SymbolInfo>,    // name/address/size/kind
}
```

**信息丰富度对比**：

| 信息项 | 上游 XFileInfo | die-gui FileInfoPanel | 差距 |
| --- | --- | --- | --- |
| DOS HEADER 字段 | 全部（e_magic/e_cblp/e_cp/...） | **无** | die-gui 不解析 DOS 头 |
| PE NT HEADERS | 全部（Signature/Machine/...） | **无** | die-gui 不解析 PE 头 |
| Section 头部 | 完整 IMAGE_SECTION_HEADER | name/vaddr/vsize/rawoff/rawsize/entropy | die-gui 缺少 Characteristics 标志解析 |
| Resource 目录 | 完整 IMAGE_RESOURCE_DIRECTORY | **无** | die-gui 无 resource 目录展示 |
| Export 目录 | 完整 IMAGE_EXPORT_DIRECTORY | **无** | die-gui 无 export 目录展示 |
| Import 目录 | 完整 IMAGE_IMPORT_DIRECTORY | **无** | die-gui 无 import 目录展示 |
| Entry Point | 地址 + 反汇编入口 | **无** | die-gui 无 entry point |
| ELF Ehdr | 全部（e_ident/e_type/e_machine/...） | **无** | die-gui 不解析 ELF 头 |
| Mach-O header | 全部（magic/cputype/...） | **无** | die-gui 不解析 Mach-O 头 |
| DEX HEADER | 全部 | **无** | die-gui 不解析 DEX 头 |
| 文件哈希 | MD5/SHA1/SHA256/... | MD5/SHA1/SHA256 | 等价 |
| 熵 | 整体 + 块级 + 可视化 | 整体 + 块级（柱状图） | die-gui 缺少可视化视图 |
| 符号表 | 完整（含 demangle） | name/address/size/kind，**限制 500 个** | die-gui 有数量限制，无 demangle |
| MIME 类型 | `XMIMEWidget` | **无** | die-gui 无 MIME |

### 1.5 诊断信息丰富度

**上游 `SCAN_RESULT`**（`xscanengine.h`）：

```cpp
struct SCAN_RESULT {
    qint64 nScanTime;
    QString sFileName;
    qint64 nSize;
    XBinary::FT ftInit;
    QList<SCANSTRUCT> listRecords;
    QList<ERROR_RECORD> listErrors;
    QList<DEBUG_RECORD> listDebugRecords;
    QList<XHandler::RECORD> listHandlers;
};

struct ERROR_RECORD {
    QString sString;       // 错误消息
    qint64 nLineNumber;    // 行号
    QString sFileName;     // 签名文件名
};

struct DEBUG_RECORD {
    QString sString;
    qint64 nLineNumber;
    QString sFileName;
    qint64 nElapsedTime;   // 每签名耗时（profiling）
};
```

上游 `DIE_Widget::on_pushButtonDieLog_clicked`（`die_widget.cpp:310-323`）
展示完整错误列表（含签名文件名和行号）。`on_toolButtonElapsedTime_clicked`
（`die_widget.cpp:422-429`）打开 `DialogDIESignaturesElapsed` 展示每签名
profiling。

**die-gui 实际输出**（`tmp/probe_out/minimal.exe/result.json` diagnostics）：

```json
"diagnostics": [
  "PE/compiler_RealBasic.4.sg: script exception in 'PE/compiler_RealBasic.4.sg': TypeError: not a function stack: ...",
  "PE/cryptor_404crypter.1.sg: script exception in ...",
  // ... 6 条
]
```

die-gui `App.tsx:1199-1209` 展示为 `<details>` 折叠面板，标题显示
`Diagnostics (6)`，内容为 `result.diagnostics.join("\n")`。

**信息差距**：

| 信息 | 上游 | die-gui |
| --- | --- | --- |
| 错误消息 | 有 | 有（字符串） |
| 行号 | `nLineNumber` | **无**（仅嵌入字符串） |
| 签名文件名 | `sFileName` 独立字段 | **无**（仅嵌入字符串） |
| profiling 耗时 | `nElapsedTime` 每签名 | **无** |
| handlers | `listHandlers` | **无** |
| 展示方式 | 独立 Log 对话框 + Profiling 对话框 | 折叠面板，仅计数 |

### 1.6 进度信息丰富度

**上游 `PDSTRUCT`** 提供 5 个进度通道（`progressBar0-4`），200ms QTimer
轮询（`die_widget.cpp:166`）。每个通道可展示不同扫描阶段的进度。

**die-gui**：单文件扫描无进度数据（仅 spinner + "Scanning..." 文本）。
目录扫描有 `DirectoryScanProgress`（current/total）。

---

## 2. 不合理设计

### 2.1 Hex 查看器设计缺陷

**上游 `XHexView`**（`xhexview.h`）是完整的虚拟滚动 Hex 查看/编辑器：

```cpp
class XHexView : public XDeviceTableEditView {
    enum COLUMN { COLUMN_LOCATION, COLUMN_ELEMENTS, COLUMN_SYMBOLS };
    enum ELEMENT_MODE {
        ELEMENT_MODE_HEX, ELEMENT_MODE_BYTE, ELEMENT_MODE_WORD,
        ELEMENT_MODE_DWORD, ELEMENT_MODE_QWORD,
        ELEMENT_MODE_UINT8, ELEMENT_MODE_INT8, // ... 13 种数据类型
    };
    void goToOffset(qint64 nOffset);
    void setBytesProLine(qint32 nBytesProLine);
    // 17 个快捷键功能（xhexview.cpp:28-44）
};
```

上游 XHexView 快捷键功能（`xhexview.cpp:28-44`）：
- `X_ID_HEX_DATA_INSPECTOR` — 数据检查器
- `X_ID_HEX_DATA_CONVERTOR` — 数据转换器
- `X_ID_HEX_MULTISEARCH` — 多重搜索
- `X_ID_HEX_GOTO_OFFSET` — 跳转到偏移
- `X_ID_HEX_GOTO_ADDRESS` — 跳转到地址
- `X_ID_HEX_DUMPTOFILE` — 转储到文件
- `X_ID_HEX_SELECT_ALL` — 全选
- `X_ID_HEX_COPY_DATA` — 复制数据
- `X_ID_HEX_COPY_OFFSET` — 复制偏移
- `X_ID_HEX_COPY_ADDRESS` — 复制地址
- `X_ID_HEX_FIND_STRING` — 查找字符串
- `X_ID_HEX_FIND_SIGNATURE` — 查找签名
- `X_ID_HEX_FIND_VALUE` — 查找值
- `X_ID_HEX_FIND_NEXT` — 查找下一个
- `X_ID_HEX_SIGNATURE` — 签名
- `X_ID_HEX_FOLLOWIN_DISASM` — 跟踪到反汇编
- `X_ID_HEX_FOLLOWIN_MEMORYMAP` — 跟踪到内存映射

**die-gui `HexViewer`**（`hex_viewer.rs:34-61`，`HexViewer.tsx`）：

```rust
pub fn read_hex_dump(path: &str, offset: u64, max_bytes: usize) -> Result<HexDump, String> {
    // 读取 max_bytes 字节，格式化为 16 字节/行的 HexLine
    // 无搜索、无跳转、无选择、无编辑
}
```

**不合理设计点**：

| 问题 | die-gui 实现 | 上游实现 | 影响 |
| --- | --- | --- | --- |
| **分页而非虚拟滚动** | 4096 字节/页，Prev/Next 翻页 | 虚拟滚动，任意大小文件流畅 | **大文件（>4KB）体验极差**，100KB 文件需翻 25 页 |
| **无搜索** | 无 | 字符串/签名/值搜索 + FindNext | 无法在 Hex 中定位内容 |
| **无跳转** | 无 | goToOffset/goToAddress | 无法快速定位 |
| **无选择/复制** | 无 | SelectAll/CopyData/CopyOffset/CopyAddress | 无法复制 Hex 数据 |
| **无数据类型切换** | 固定 Hex 显示 | 13 种数据类型（Byte/Word/DWord/QWord/...） | 无法以不同数据类型查看 |
| **无数据检查器** | 无 | DataInspector 实时解析当前字节 | 缺少结构化数据查看 |
| **无跟踪到反汇编** | 无 | FOLLOWIN_DISASM | Hex 和反汇编无法联动 |
| **无编辑** | 无 | XHexEdit 可编辑 | 无法修改文件内容 |
| **无 CodePage** | 固定 ASCII | 支持 QTextCodec | 无法以不同编码查看 |
| **无 Location 列** | 仅 Offset/Hex/ASCII | Location/Elements/Symbols 三列 | 缺少符号标注 |
| **pageSize 硬编码** | 4096 固定 | 可配置 bytesProLine | 无法调整每行字节数 |

**最不合理之处**：分页设计。对于 PE 文件（通常 100KB-10MB），用户需要
翻 25-2500 页才能浏览整个文件。上游虚拟滚动可以流畅浏览任意大小文件。
die-gui 应改为虚拟滚动（如 `react-window` 或自定义虚拟列表）。

### 2.2 反汇编器设计缺陷

**上游 `XDisasmView`**（`xdisasmview.h`）是完整的反汇编查看器：

```cpp
class XDisasmView : public XDeviceTableEditView {
    enum COLUMN {
        COLUMN_ARROWS,      // 跳转箭头
        COLUMN_BREAKPOINT,  // 断点
        COLUMN_LOCATION,    // 地址
        COLUMN_LABEL,       // 标签
        COLUMN_BYTES,       // 字节
        COLUMN_OPCODE,      // 指令
        COLUMN_COMMENT      // 注释
    };
    enum VIEWMETHOD { VIEWMETHOD_NONE, VIEWMETHOD_ANALYZED };
    enum VIEWDISASM { VIEWDISASM_COMPACT, VIEWDISASM_FULL };
    void setViewMethod(VIEWMETHOD viewMethod);  // 分析模式
    void showReferences(XADDR nAddress);         // 交叉引用
    void analyzeAll();                           // 全部分析
    // 7 个快捷键功能
};
```

上游 XDisasmView 快捷键功能（`xdisasmview.h`）：
- `_goToEntryPointSlot` — 跳转到入口点
- `_goToXrefSlot` — 跳转到交叉引用
- `_signatureSlot` — 签名
- `_hexSlot` — 跟踪到 Hex
- `_referencesSlot` — 引用视图
- `_analyzeAll` — 全部分析
- `_analyzeAnalyze` / `_analyzeSymbols` / `_analyzeFunctions` — 分析符号/函数

**die-gui `Disassembler`**（`disassembler.rs:62-120`，`Disassembler.tsx`）：

```rust
pub fn disassemble_bytes(data: &[u8], base_address: u64, bitness: u32, syntax: Syntax)
    -> Result<DisassemblyResult, String> {
    let mut decoder = Decoder::with_ip(bitness, data, base_address, DecoderOptions::NONE);
    for instr in decoder.iter() {
        // 格式化为 address/bytes/mnemonic
        // Stop if Ret/Retf/Ud0  ← 问题：遇到返回就停止！
        if m == Mnemonic::Ret || m == Mnemonic::Retf || m == Mnemonic::Ud0 {
            break;
        }
    }
}
```

**不合理设计点**：

| 问题 | die-gui 实现 | 上游实现 | 影响 |
| --- | --- | --- | --- |
| **遇到 Ret 就停止** | `break` on Ret/Retf/Ud0 | 完整反汇编 | **只反汇编到第一个 ret 就停止**，函数后的代码无法查看 |
| **无跳转箭头** | 无 | COLUMN_ARROWS 绘制跳转线 | 无法可视化跳转关系 |
| **无断点** | 无 | COLUMN_BREAKPOINT | 无调试支持 |
| **无标签** | 无 | COLUMN_LABEL | 无法显示函数/跳转标签 |
| **无注释** | 无 | COLUMN_COMMENT | 无指令注释 |
| **无交叉引用** | 无 | showReferences | 无法查看引用 |
| **无分析模式** | 无 | VIEWMETHOD_ANALYZED | 无代码分析 |
| **无入口点跳转** | 无 | _goToEntryPointSlot | 无法快速跳到入口 |
| **无 Hex 联动** | 无 | _hexSlot | 反汇编和 Hex 无法联动 |
| **硬编码 256 字节** | max_bytes=256 | 完整反汇编 | **只反汇编 256 字节**，大函数显示不全 |
| **无符号解析** | 无 | XInfoDB 集成 | 无法显示符号名 |

**最不合理之处**：`break on Ret`。这意味着如果入口点附近有一个 `ret`
（如 thunk 函数），反汇编器只显示几条指令就停止。用户无法看到后续代码。
应改为完整反汇编指定范围，或至少提供"继续"按钮。

### 2.3 扫描结果 options 展示缺陷

**die-gui `App.tsx:1178-1180`**：

```tsx
<span className="w-32 text-fg-muted truncate">
  {d.options ? `${d.options.split(",").length} options` : ""}
</span>
```

**问题**：将 options 字段（如 `"100.0%, 2 files"`）显示为 `2 options` 计数，
用户必须点击展开才能看到具体内容。这增加了交互成本，且 `split(",")` 可能
错误分割包含逗号的值。

**上游**：直接在主列显示完整 `[100.0%, 2 files]`，无需额外交互。

**建议**：直接显示 options 字符串，或至少显示前 N 个字符 + tooltip。

### 2.4 Settings 面板非模态设计

**die-gui**：Settings 是内联折叠面板（非模态），用户可以在 Settings 打开
时操作其他控件，可能导致设置和操作冲突。

**上游**：`DialogOptions` 是模态对话框，阻塞主窗口，确保用户先完成设置
再操作。

### 2.5 数据库选择未接线

**die-gui**：文件信息栏有 Databases `<select>`，但 `commands.rs:scan_file`
始终使用 `resolve_db_paths()` 自动检测的路径，不传递用户选择的数据库。

**上游**：`comboBoxDatabases` 多选框，`DIE_Widget::process` 读取选择并
设置 `m_scanOptions.bUseExtraDatabase`/`bUseCustomDatabase`。

### 2.6 文件类型手动覆盖未接线

**die-gui**：Advanced 模式的 `AdvancedToolbar` 有 Type `<select>`，但
`scan_file` 命令不接收 `file_type` 参数。

**上游**：`comboBoxType`（`FormatsWidget`）通过 `XFormats::setFileTypeComboBox`
填充，选择后设置 `m_scanOptions.fileType`，覆盖自动检测。

### 2.7 符号表 500 个限制

**die-gui `FileInfoPanel.tsx:202`**：

```tsx
{info.symbols.slice(0, 500).map((s, i) => (
```

硬编码 500 个符号限制，超过显示 "Showing first 500 of N symbols"。

**上游**：`XSymbolsWidget` 无限制，使用虚拟滚动。

### 2.8 无签名源码关联入口

**die-gui**：Advanced 模式下选中检测结果，底部显示签名源码。但非 Advanced
模式下无任何查看签名源码的入口（上下文菜单的 "View signature source" 需要
`signature_path`，而 `ScanDetection.signature_path` 可能为 None）。

**上游**：每行结果右侧有 Signature 图标列（COLUMN_SIGNATURE），点击即打开
签名浏览器，无论是否 Advanced 模式。

---

## 3. 底层库差异导致的结果显示差异

### 3.1 文件类型检测差异

**die-gui `file_info.rs:121-168`** 使用手写 magic bytes 检测：

```rust
fn detect_format(data: &[u8]) -> String {
    if data.starts_with(b"MZ") {
        // 检查 PE signature at e_lfanew
        let pe_offset = u32::from_le_bytes([data[0x3c], data[0x3d], data[0x3e], data[0x3f]]);
        if &data[pe_offset..pe_offset + 4] == b"PE\0\0" {
            let machine = u16::from_le_bytes([data[pe_offset + 4], data[pe_offset + 5]]);
            return match machine {
                0x14c => "PE32", 0x8664 => "PE32+", _ => "PE",
            };
        }
        return "DOS MZ";
    }
    // ELF/Mach-O 类似手写检测
}
```

**上游 `XFormats::getFileTypes`** 使用完整的格式探测器集合（XBinary +
XPE + XELF + XMACH + XDEX + ...），支持 50+ 文件类型。

**实际差异**（`tmp/probe_out/` vs 上游基线）：

| 样本 | die-gui format | 上游 filetype | 差异 |
| --- | --- | --- | --- |
| `minimal.exe` | `PE32` | `PE32` | 等价 |
| `minimal-pe64.exe` | `PE32+` | `PE64` | **命名不同**（PE32+ vs PE64） |
| `minimal.elf` | `ELF64` | `ELF64` | 等价 |
| `minimal.macho` | `Mach-O 64` | `Mach-O 64` | 等价 |
| `minimal-fat.macho` | `Mach-O 32`（只检测第一个） | `Mach-O FAT` | **die-gui 不识别 FAT** |
| `minimal.iso` | `Unknown` | `ISO9660` | **die-gui 不识别 ISO** |
| `minimal.rar` | `Unknown` | `RAR` | **die-gui 不识别 RAR** |
| `payload.txt.gz` | `Unknown` | `GZIP` | **die-gui 不识别 GZIP** |
| `Minimal.class` | `Unknown` | `JavaClass` | **die-gui 不识别 Java Class** |
| `minimal.dex` | `Unknown` | `DEX` | **die-gui 不识别 DEX** |
| `minimal.cfbf` | `Unknown` | `CFBF` | **die-gui 不识别 CFBF** |
| `minimal.pdf` | `Unknown` | `PDF` | **die-gui 不识别 PDF** |
| `pixel.png` | `Unknown` | `PNG` | **die-gui 不识别 PNG** |
| `pixel.jpg` | `Unknown` | `JPEG` | **die-gui 不识别 JPEG** |
| `pixel.bmp` | `Unknown` | `Windows Bitmap` | **die-gui 不识别 BMP** |
| `tone.wav` | `Unknown` | `RIFF` | **die-gui 不识别 WAV** |

**注意**：die-gui 的 `detect_format` 仅用于 FileInfoPanel 的 `format` 字段
展示，不影响扫描结果（扫描使用 diec-engine 的格式探测）。但 FileInfoPanel
展示的 format 与上游差距很大。

### 3.2 PE 解析库差异

**die-gui** 使用 `goblin`（`file_info.rs:175`）解析 PE：

```rust
if let Ok(goblin::Object::PE(pe)) = goblin::Object::parse(data) {
    for sec in &pe.sections {
        // name/virtual_address/virtual_size/pointer_to_raw_data/size_of_raw_data
    }
    for export in &pe.exports {
        // name/rva/size
    }
}
```

**上游** 使用 `XPE`（自实现 PE 解析器），支持：
- 完整 IMAGE_DOS_HEADER / IMAGE_NT_HEADERS / IMAGE_SECTION_HEADER
- IMAGE_RESOURCE_DIRECTORY（递归）
- IMAGE_EXPORT_DIRECTORY
- IMAGE_IMPORT_DIRECTORY（递归）
- IMAGE_BOUND_IMPORT_DIRECTORY
- IMAGE_DELAY_IMPORT_DIRECTORY
- PE Rich Header
- PE TLS
- PE .NET metadata
- PE Manifest
- PE Version Info

**实际差异**（`tmp/probe_out/pe-with-resources.exe`）：

| 信息 | die-gui (goblin) | 上游 (XPE) |
| --- | --- | --- |
| Sections | name/vaddr/vsize/rawoff/rawsize/entropy | 完整 + Characteristics 标志解析 |
| Exports | name/rva/size | 完整 + ordinal/forwarder |
| Imports | **无** | 完整（DLL + 函数列表） |
| Resources | **无** | 完整递归目录树 |
| .NET metadata | **无** | 完整 |
| Rich Header | **无** | 完整 |
| TLS | **无** | 完整 |
| Manifest | **无** | 完整 |
| Version Info | **无** | 完整 |

### 3.3 ELF 解析库差异

**die-gui** 使用 `goblin`（`file_info.rs:215`）解析 ELF：

```rust
if let Ok(goblin::Object::Elf(elf)) = goblin::Object::parse(data) {
    for sec in &elf.section_headers { /* name/sh_addr/sh_offset/sh_size */ }
    for sym in &elf.syms { /* name/st_value/st_size/st_type */ }
}
```

**上游** 使用 `XELF`，支持：
- 完整 Elf Ehdr（e_ident/e_type/e_machine/e_version/...）
- Elf Shdr（全部字段 + SHF_* 标志解析）
- Elf Phdr（程序头）
- Elf Sym（符号表 + 版本信息）
- Elf Dynamic（动态段）
- Elf Rel/Rela（重定位）

**实际差异**（`tmp/probe_out/elf-with-deps.elf`）：

| 信息 | die-gui (goblin) | 上游 (XELF) |
| --- | --- | --- |
| Ehdr | **无** | 完整 |
| Sections | name/addr/offset/size/entropy | 完整 + SHF_* 标志 |
| Phdr | **无** | 完整 |
| Symbols | name/value/size/type | 完整 + 版本信息 |
| Dynamic | **无** | 完整 |
| Relocations | **无** | 完整 |

### 3.4 Mach-O 解析库差异

**die-gui** 使用 `goblin`（`file_info.rs:258`）解析 Mach-O：

```rust
if let Ok(goblin::Object::Mach(mach)) = goblin::Object::parse(data)
    && let goblin::mach::Mach::Binary(macho) = mach {
    for seg in macho.segments.iter() {
        for (sec, sec_data) in seg.sections() { /* name/addr/size/offset */ }
    }
    for (name, nlist) in macho.symbols().flatten() { /* name/n_value/type */ }
}
```

**问题**：`Mach::Binary` 只处理单架构 Mach-O，FAT 格式（`minimal-fat.macho`）
不会被解析。

**上游** 使用 `XMACH` + `XMACHOFat`，支持：
- 完整 mach_header（magic/cputype/cpusubtype/filetype/...）
- Load Commands（全部类型）
- Segments + Sections（完整字段）
- Symbols（nlist 完整解析）
- Libraries（DYLD 加载库列表）
- FAT 多架构支持

### 3.5 反汇编引擎差异

**die-gui** 使用 `iced-x86`（`disassembler.rs:6`）：

```rust
use iced_x86::{Decoder, DecoderOptions, Formatter, GasFormatter, IntelFormatter, NasmFormatter};
```

**上游** 使用 `XCapstone`（Capstone 绑定）+ `XDisasmAbstract`。

**差异**：

| 特性 | die-gui (iced-x86) | 上游 (Capstone) |
| --- | --- | --- |
| 架构支持 | x86/x64 only | x86/x64/ARM/ARM64/MIPS/PPC/... |
| 语法 | Intel/AT&T/NASM | Intel/AT&T |
| 分析模式 | 无 | VIEWMETHOD_ANALYZED（交叉引用、函数识别） |
| 符号解析 | 无 | XInfoDB 集成 |
| 指令注释 | 无 | COLUMN_COMMENT |

**关键差异**：die-gui 只支持 x86/x64，上游支持多架构。对于 ARM/ARM64
二进制（如 APK 内的 .so、iOS Mach-O），die-gui 无法反汇编。

### 3.6 哈希计算差异

**die-gui**（`file_info.rs:112-118`）使用 `md5`/`sha1`/`sha2` crates：

```rust
let md5 = hex::encode(md5::Md5::digest(data));
let sha1 = hex::encode(sha1::Sha1::digest(data));
let sha256 = hex::encode(sha2::Sha256::digest(data));
```

**上游 `XHashWidget`** 支持更多哈希算法：
- MD5/SHA1/SHA256
- SHA224/SHA384/SHA512
- CRC32/CRC64
- SSDeep（模糊哈希）
- TLSH（局部敏感哈希）

**差异**：die-gui 仅 3 种哈希，上游支持 8+ 种。缺少 SSDeep/TLSH 影响
恶意软件相似性分析。

### 3.7 熵计算差异

**die-gui**（`file_info.rs:75-93`）使用 Shannon 熵：

```rust
pub fn shannon_entropy(data: &[u8]) -> f64 {
    // 标准 Shannon 熵，[0.0, 8.0]
}
```

**上游 `XEntropyWidget`** 使用相同的 Shannon 熵，但提供：
- 整体熵
- 块级熵（可配置块大小）
- 可视化图表（彩色热图）
- 熵直方图

**die-gui** 有整体熵 + 块级熵（256 字节块，`compute_entropy_graph`），
但块大小不可配置，无热图可视化。

### 3.8 归档解析差异

**die-gui**（`commands.rs:846-861`）使用 `zip` crate，仅支持 ZIP：

```rust
let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
// 仅 ZIP
```

**上游 `XArchive`** 支持：
- ZIP
- RAR
- 7Z
- TAR
- GZIP
- BZIP2
- CAB
- AR
- CPIO
- ISO
- NSIS
- InstallShield
- InnoSetup
- ... 20+ 归档格式

**实际差异**（`tmp/probe_out/`）：

| 归档格式 | die-gui | 上游 |
| --- | --- | --- |
| ZIP | 支持（list_archive） | 支持 |
| RAR | **不支持** | 支持 |
| 7Z | **不支持** | 支持 |
| TAR | **不支持**（扫描能识别但 ArchiveViewer 无法列出） | 支持 |
| GZIP | **不支持** | 支持 |
| ISO | **不支持** | 支持 |

### 3.9 YARA 引擎差异

**die-gui**（`yara_scanner.rs`）使用 `yara-rust`（YARA Rust 绑定）。

**上游** 使用 `XYara`（YARA C 库绑定）。

**差异**：YARA 规则兼容性可能因 YARA 版本不同而有差异。die-gui 的
`yara-rust` 依赖 YARA C 库，与上游相同，但版本可能不同。

### 3.10 PEID 签名差异

**die-gui**（`peid_scanner.rs`）使用自实现 PEID 签名匹配。

**上游** 使用 `peid_widget`（基于 XPEID）。

**差异**：die-gui 支持内置 `.userdb` 文件，上游支持用户自定义 PEID
数据库。匹配算法可能不同（die-gui 可能不支持所有 PEID 签名特性）。

---

## 4. 差异分类汇总

### 4.1 信息丰富度缺失（P1）

| 优先级 | 差异 | 影响 | 修复建议 |
| --- | --- | --- | --- |
| P1 | options 显示为计数 | 用户需额外点击 | 直接显示 options 字符串 |
| P1 | 嵌套结果树 | archive/resource 子结果丢失层级 | 扩展 ScanDetection 增加 id/parentId |
| P1 | 启发式标记缺失 | 无法区分 Heur/A-Heur 检测 | 扩展 ScanDetection 增加 bIsHeuristic |
| P1 | file part/offset/size 缺失 | 无法定位检测位置 | 扩展 ScanDetection 增加字段 |
| P1 | 数据库选择未接线 | Databases 下拉无效 | scan_file 接收 database 参数 |
| P1 | 文件类型覆盖未接线 | Type 下拉无效 | scan_file 接收 file_type 参数 |
| P2 | Unknown 行缺失 | 无检测时无 Unknown 标记 | 根据 hide_unknown 显示 Unknown 行 |
| P2 | 诊断信息不完整 | 缺行号/签名文件名独立字段 | 扩展 diagnostics 为结构化 |
| P2 | profiling 缺失 | 无每签名耗时 | 扩展 ScanResult 增加 profiling |
| P2 | PE/ELF/Mach-O 头部字段 | FileInfoPanel 仅 sections/symbols | 集成 XFileInfo 等价功能 |
| P2 | Imports/Resources/.NET | 完全缺失 | 扩展 file_info.rs |
| P3 | 进度条 | 单文件扫描无进度 | Channel<ScanProgress> |
| P3 | 多语言 | 5 种 vs 22 种 | 扩展 i18n |

### 4.2 不合理设计（P1/P2）

| 优先级 | 问题 | 修复建议 |
| --- | --- | --- |
| P1 | Hex 分页而非虚拟滚动 | 改为虚拟滚动（react-window） |
| P1 | Hex 无搜索/跳转/复制 | 增加 search_bytes/goto/copy IPC |
| P1 | Disasm 遇到 Ret 就停止 | 移除 break，完整反汇编 |
| P1 | Disasm 硬编码 256 字节 | 可配置 max_bytes，默认更大 |
| P2 | Disasm 无跳转箭头/标签/注释 | 扩展 Instruction 结构 |
| P2 | Disasm 仅 x86/x64 | 考虑增加 ARM 支持（Capstone） |
| P2 | Settings 非模态 | 改为模态对话框 |
| P2 | 符号表 500 限制 | 改为虚拟滚动 |
| P3 | Hex 无数据类型切换 | 增加 ELEMENT_MODE |
| P3 | Disasm 无 Hex 联动 | 增加 follow-in-hex |

### 4.3 底层库差异（P2/P3）

| 优先级 | 差异 | 修复建议 |
| --- | --- | --- |
| P2 | FileInfo format 检测仅 PE/ELF/Mach-O | 扩展 detect_format 或复用 diec-engine |
| P2 | PE 解析 goblin 缺 Imports/Resources | 扩展 parse_pe_sections 或换 pelite |
| P2 | Mach-O 不支持 FAT | 处理 Mach::Fat |
| P2 | 归档仅 ZIP | 增加 tar/rar/7z 支持 |
| P3 | 哈希仅 3 种 | 增加 CRC32/SSDeep |
| P3 | 反汇编仅 x86/x64 | 考虑 ARM 支持 |
| P3 | 熵块大小不可配置 | 增加 block_size 参数 |

### 4.4 die-gui 增值功能

| 功能 | 说明 |
| --- | --- |
| Rust 符号 demangle | `rustc-demangle` crate（上游无） |
| NASM 反汇编语法 | iced-x86 支持（上游 Capstone 无） |
| 状态栏 | 底部状态显示 |
| 拖放视觉 overlay | 拖放时全屏遮罩 |
| Ctrl+C 复制结果 | 快捷键复制 |
| 内置 YARA/PEID 规则选择 | 前端下拉选择内置规则 |
| DataConverter | 数据格式转换 |
| MemoryMapViewer 可视化条 | 虚拟地址布局彩色条形图 |

---

## 5. 实际输出对比示例

### 5.1 minimal.exe（PE32，512 字节）

**diec-rust CLI 输出**（`tmp/probe_out/minimal.exe/`）：

```
# text.txt
corpus\minimal.exe: archive: Resources

# result.json（关键部分）
{
  "detections": [{"file_type": "PE", "type": "archive", "name": "Resources"}],
  "diagnostics": [6 条脚本异常]
}

# info.txt
corpus\minimal.exe: size: 512

# entropy.txt
corpus\minimal.exe: entropy: 0.358655 (512)
```

**上游 die GUI 展示**（基于源码推断）：

```
Result
└── PE32
    └── archive: Resources
```

**差异**：
- die-gui `file_type: "PE"`，上游 `PE32`（不区分 32/64 位）
- die-gui 无嵌套树（PE32 → archive: Resources 是扁平的）
- 上游 Log 按钮显示 `Log(6)`，die-gui 显示 `Diagnostics (6)` 折叠面板

### 5.2 minimal.apk（ZIP，350 字节）

**diec-rust CLI 输出**：

```
# text.txt
corpus\minimal.apk: archive: Zip (2.0) [100.0%, 2 files]

# result.json
{
  "detections": [{
    "file_type": "Binary", "type": "archive", "name": "Zip",
    "version": "2.0", "options": "100.0%, 2 files"
  }]
}
```

**die-gui DetectionTreeView 展示**：

```
Binary
└── archive: Zip    archive    2.0    2 options
    └── 100.0%
    └──  2 files
```

**上游 die GUI 展示**：

```
Result
└── Binary
    └── archive: Zip (2.0) [100.0%, 2 files]
```

**差异**：
- die-gui options 显示为 `2 options`（需点击展开），上游直接显示
  `[100.0%, 2 files]`
- die-gui `file_type: "Binary"`，上游 `Binary`（等价）

### 5.3 minimal.pdf（PDF，331 字节）

**diec-rust CLI 输出**：

```
# text.txt
corpus\minimal.pdf: complier: HeaderComment (e2e3cfd3)
corpus\minimal.pdf: format: PDF (1.4)

# result.json
{
  "detections": [
    {"file_type": "PDF", "type": "complier", "name": "HeaderComment", "version": "e2e3cfd3"},
    {"file_type": "PDF", "type": "format", "name": "PDF", "version": "1.4"}
  ]
}
```

**die-gui DetectionTreeView 展示**：

```
PDF
├── complier: HeaderComment    complier    e2e3cfd3
└── format: PDF                format      1.4
```

**上游 die GUI 展示**：

```
Result
└── PDF
    ├── complier: HeaderComment (e2e3cfd3)
    └── format: PDF (1.4)
```

**差异**：基本等价，但 die-gui 版本和类型分列展示，上游合并为单字符串。

### 5.4 minimal-fat.macho（FAT Mach-O，360 字节）

**diec-rust CLI 输出**：

```
# text.txt
corpus\minimal-fat.macho: converter: lipo

# result.json
{
  "detections": [{"file_type": "Mach-O", "type": "converter", "name": "lipo"}]
}
```

**die-gui FileInfoPanel**：`format: "Mach-O 32"`（只检测第一个架构）

**上游**：`filetype: "Mach-O FAT"`，FileInfo 展示所有架构。

**差异**：die-gui 不识别 FAT 格式，FileInfo 只显示第一个架构。

---

## 6. 建议优先级

### P1（影响核心功能正确性和可用性）

1. **修复 Hex 虚拟滚动**：替换分页为虚拟滚动，支持任意大小文件
2. **修复 Disasm break-on-Ret**：移除 `break`，完整反汇编指定范围
3. **接线 Databases 选择**：scan_file 接收 database 参数
4. **接线 Type 手动覆盖**：scan_file 接收 file_type 参数
5. **嵌套结果树**：扩展 ScanDetection 增加 id/parentId/offset/size
6. **options 直接显示**：移除计数，直接显示 options 字符串
7. **启发式标记**：扩展 ScanDetection 增加 bIsHeuristic

### P2（影响功能完整度）

8. **Hex 搜索/跳转/复制**：增加 IPC 命令
9. **Disasm 完整列**：增加 arrows/label/comment
10. **PE Imports/Resources**：扩展 file_info.rs
11. **Mach-O FAT 支持**：处理 Mach::Fat
12. **诊断结构化**：扩展 diagnostics 为结构化（行号/文件名）
13. **profiling**：扩展 ScanResult 增加 profiling 数据
14. **符号表虚拟滚动**：移除 500 限制

### P3（对齐完整度，可延后）

15. 多架构反汇编（ARM/ARM64）
16. 更多哈希算法（CRC32/SSDeep）
17. 更多归档格式（RAR/7Z/TAR）
18. 多语言扩展到 22 种
19. NFD/InfoDB/可视化/提取器/MIME
20. 自动更新（ADR 0019）

---

## 7. 限制

- 上游 `die` 未在本地运行，上游 GUI 展示基于源码静态分析推断。
- die-gui 前端组件的渲染细节基于源码阅读，未做视觉截图对比。
- 上游 submodule（die_widget/FormatWidgets/XHexView 等）部分未在本地检出，
  分析依据 GitHub raw 文件获取。
- 实际输出对比基于 diec-rust CLI（diec.exe）输出，die-gui 前端展示基于
  源码推断（CLI 和 GUI 共用 diec-engine，结果数据一致，展示方式不同）。
- 上游 GUI 的确切渲染效果（颜色、字体、布局细节）未做像素级对比。
