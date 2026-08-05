# 上游 GUI 源码分析

Status: Accepted
Upstream: `horsicq/DIE-engine@ab0ea3e2764c9c5616362070be5c85404e3f7756` (master)
Last updated: 2026-08-05

## 范围

本文分析上游 DIE-engine 的三个 GUI 变体（`die`、`diel`、`diec`）的程序结构、
功能清单、交互流程和组件依赖关系，为 diec-rust Phase 7 GUI 实现提供功能对齐
基线。分析对象固定到上述 commit，所有结论附上游源码位置。

子模块 `die_widget`、`XOptions`、`XScanEngine` 的源码来自各自 master 分支，
通过以下可复现命令获取后分析：

```sh
git clone --depth 1 https://github.com/horsicq/die_widget.git
cd die_widget && git checkout 5b483772edde713fb872bc3ca86cfde4c00ea42c

git clone --depth 1 https://github.com/horsicq/XOptions.git
git clone --depth 1 https://github.com/horsicq/XScanEngine.git
```

`die_widget` 固定到 commit `5b483772edde713fb872bc3ca86cfde4c00ea42c`
（master HEAD at analysis time）。`XOptions` 和 `XScanEngine` 使用分析时
的 master HEAD（无 tag/release 锚点，后续同步需记录新 commit）。

## 三个变体

上游 `DIE-engine` 仓库构建三个可执行文件：

| 变体 | 源码目录 | 描述 |
| --- | --- | --- |
| `die` | `gui_source/` | 完整 GUI，含 FormatsWidget、签名浏览器、Hex 查看器等 |
| `diel` | `lite_source/` | 精简 GUI，仅扫描+纯文本结果，无高级功能 |
| `diec` | `console_source/` | 命令行版本（diec-rust Phase 4 已对齐） |

三者共享 `die_script`（DiE_Script 规则引擎 facade）、`XScanEngine`（扫描编排
和结果模型）、`XOptions`（设置持久化）和 `XShortcuts`（快捷键管理）等底层
模块。`die` 和 `diel` 通过 `die_widget` 提供 DIE 扫描 widget，`die` 额外通过
`FormatWidgets`、`XHexView`、`XDisasmView` 等提供格式解析视图。

## die（完整 GUI）程序设计

### 主窗口 GuiMainWindow

源码：`gui_source/guimainwindow.{h,cpp,ui}`

**窗口布局**（720×500）：

```
┌─────────────────────────────────────────────────┐
│ File name [>][lineEditFileName][...]            │  ← groupBoxFileName
├─────────────────────────────────┬───────────────┤
│                                 │ [✓] Advanced  │
│                                 │ [Demangle]    │
│        FormatsWidget            │ [Shortcuts]   │
│      (die_widget::DIE_Widget)   │ [Options]     │
│                                 │ [About]       │
│                                 │ [Exit]        │
└─────────────────────────────────┴───────────────┘
```

**功能清单**：

- 文件输入：LineEdit + Open File 按钮 + Recent Files 菜单
- 拖放支持：`dragEnterEvent`/`dragMoveEvent`/`dropEvent` 接受文件 URL
- 命令行参数：启动时若 `argv[1]` 存在则直接处理该文件
- Advanced 复选框：切换 Advanced 模式（显示/隐藏 Demangle 按钮，切换
  FormatsWidget 的 advanced/basic 视图）
- 工具按钮：About、Options、Demangle、Shortcuts、Exit、OpenFile、RecentFiles
- 全屏切换：`fullScreenSlot()` 切换 `showFullScreen()`/`showNormal()`
- 快捷键：OpenFile、Exit、FullScreen 三个全局快捷键
- 设置持久化：`XOptions` 存储 QSS 主题、字体、语言、stay-on-top、single
  application、recent files、last directory、scan flags、database paths 等
- Windows 特性：Explorer 右键菜单集成（`ID_FILE_CONTEXT`）、MSIX 资源下载器

### 设置项 XOptions

源码：`XOptions/xoptions.h`（`die_widget` 依赖的 submodule）

**设置分类**（`ID_` 枚举）：

| 分类 | 设置项 |
| --- | --- |
| View | `STAYONTOP`、`STYLE`、`QSS`、`QSS_DATABASE_UPDATE_URL`、`LANG`、`SINGLEAPPLICATION`、`SHOWLOGO`、`FONT`/`FONT_CONTROLS`/`FONT_TABLEVIEWS`/`FONT_TREEVIEWS`/`FONT_TEXTEDITS`、`COLUMNS`/`COLUMN_SIZES`、`ADVANCED`、`SELECTSTYLE` |
| File | `SAVELASTDIRECTORY`、`SAVERECENTFILES`、`SAVEBACKUP`、`CONTEXT`（Windows 右键菜单）、`PATH` |
| Feature | `READBUFFERSIZE`（默认 8KB）、`FILEBUFFERSIZE`（默认 2MB）、`SSE2`、`AVX2` |
| Scan | `SCANAFTEROPEN`、`FLAG_RECURSIVE`/`FLAG_OVERLAY`/`FLAG_RESOURCES`/`FLAG_ARCHIVES`/`FLAG_DEEP`/`FLAG_HEURISTIC`/`FLAG_AGGRESSIVE`/`FLAG_VERBOSE`/`FLAG_ALLTYPES`、`USECACHE`、`FORMATRESULT`、`LOG_PROFILING`、`HIGHLIGHT`、`SORT`、`HIDEUNKNOWN`、`ENGINE`/`ENGINE_EMPTY`/`ENGINE_DIE_ENABLED`/`ENGINE_NFD_ENABLED`/`ENGINE_PEID_ENABLED`/`ENGINE_YARA_ENABLED` |
| Scan Database | `DIE_DATABASE_MAIN_PATH`/`MAIN_UPDATE_URL`、`DIE_DATABASE_EXTRA_PATH`/`EXTRA_UPDATE_URL`、`DIE_DATABASE_CUSTOM_PATH`、`DIE_DATABASE_EXTRA_ENABLED`/`CUSTOM_ENABLED`、`YARA_DATABASE_PATH`/`UPDATE_URL`、`PEID_DATABASE_PATH`/`UPDATE_URL`、`DIRECTORY_PATH`、`SUBDIRECTORIES` |
| Scan Collection | `COLLECTION_ALLFILETYPES`/`ALLTYPES`/`UNKNOWN`/`FILETYPES`/`TYPES`/`RESULT_PATH`/`CATALOG_ENABLED`/`CATALOG_FORMAT`/`COPY_ENABLED`/`COPY_FORMAT`/`COPY_REMOVE`/`COPY_MOVETOFIRST`/`LOG` |
| Scan Color | `COLOR_INSTALLER`、`COLOR_SFX`、`COLOR_ARCHIVE` 等（结果高亮颜色） |

设置通过 `QSettings` 持久化到 INI 文件（`X_OPTIONSFILE`），`die` 和 `diel`
使用不同文件名（`X_OPTIONSFILE` vs `X_OPTIONSFILELITE`）。

### Options 对话框 DialogOptions

源码：`gui_source/dialogoptions.{h,cpp,ui}`

包含六个子选项 widget：

1. `XScanEngineOptionsWidget` — 扫描引擎选项（flags、database、engine enable）
2. `SearchSignaturesOptionsWidget` — 签名搜索选项
3. `XHexViewOptionsWidget` — Hex 视图选项
4. `XDisasmViewOptionsWidget` — 反汇编视图选项
5. `XOnlineToolsOptionsWidget` — 在线工具选项
6. `XInfoDBOptionsWidget` — InfoDB 选项

## die_widget 模块

源码：`die_widget/`（submodule，`die_widget@5b48377`）

### DIE_Widget（基础扫描 widget）

源码：`die_widget.{h,cpp,ui}`

**布局**（873×645）：

```
┌──────────────────────────────────────────────────┐
│ TreeViewResult (3 columns: String/Signature/Info)│
│                                                  │
├──────────────────────────────────────────────────┤
│ [Signatures][Flags▼][Databases▼]    [Scan]       │  ← pageScan
│ [Directory][Log][>]            [ElapsedTime]     │
├──────────────────────────────────────────────────┤
│ ▓▓▓▓▓▓▓▓▓▓ progressBar0/1/2/3/4                  │  ← pageProgress
└──────────────────────────────────────────────────┘
```

使用 `QStackedWidget` 在 scan 页和 progress 页之间切换。

**功能清单**：

- **结果展示**：`QTreeView` + `ScanItemModel`，3 列：
  - `COLUMN_STRING`（Stretch）— 检测字符串（如 "Linker: Microsoft Linker"）
  - `COLUMN_SIGNATURE`（Fixed 20px）— 签名图标，点击打开签名源码
  - `COLUMN_INFO`（Fixed 20px）— 信息图标，点击打开 HTML 帮助或 Google 搜索
- **扫描控制**：
  - `comboBoxFlags` — 扫描标志多选（Recursive/Overlay/Resource/Archive/Deep/Heuristic/Aggressive/Verbose/AllTypes/FirstWrapperOnly）
  - `comboBoxDatabases` — 数据库多选（Main/Extra/Custom，Extra 项禁用）
  - `pushButtonDieScanStart` — 启动扫描
  - `pushButtonDieScanStop` — 停止扫描（设置 `pdStruct.bIsStop = true`）
- **异步扫描**：`QtConcurrent::run` + `QFutureWatcher`，扫描在后台线程
  执行，完成后 `onScanFinished` 更新 UI
- **进度显示**：5 个 `QProgressBar`（progressBar0-4），`QTimer` 200ms 轮询
- **签名浏览器**：`pushButtonDieSignatures` → `DialogDIESignatures`
- **额外信息**：`pushButtonDieExtraInformation` → `DialogTextInfo`（格式化
  扫描结果全文）
- **日志**：`pushButtonDieLog` → `DialogTextInfo`（错误和警告列表），按钮
  文本显示错误计数
- **目录扫描**：`pushButtonDieScanDirectory` → `DialogDIEScanDirectory`
- **耗时**：`toolButtonElapsedTime` 显示扫描毫秒数，点击 →
  `DialogDIESignaturesElapsed`（签名级 profiling）
- **上下文菜单**：`customContextMenuRequested` → 复制结果等操作
- **信号**：`scanStarted()`、`scanFinished()`、`currentFileType(int)`、
  `scanProgress(int)`

**扫描流程**（`die_widget.cpp:143-221`）：

1. 构建 `SCAN_OPTIONS`（flags、databases、showType/Version/Info、
   logProfiling、hideUnknown、sort、fileType）
2. 启动 200ms 定时器
3. `QtConcurrent::run(scan)`：
   - 加载数据库（首次 `m_dieScript.loadDatabase`，后续复用）
   - `m_dieScript.scanFile(m_sFileName, &m_scanOptions, &m_pdStruct)`
   - emit `scanFinished()`
4. `onScanFinished`：
   - 构建 `ScanItemModel`（3 列）设置到 TreeView
   - `expandAll()`，设置列宽和 resize mode
   - 更新 Log 按钮文本（含错误计数）
   - 更新 ElapsedTime 按钮文本

### DIEWidgetAdvanced（高级模式 widget）

源码：`diewidgetadvanced.{h,cpp,ui}`（944×482）

**布局**：

```
┌────────────────────────────────────────────────────┐
│ [Type▼][Flags▼][Databases▼]  [Signatures][Save][Scan]│
├────────────────────────────────────────────────────┤
│ TreeViewResult                                     │
│ ─────────────── (QSplitter Vertical) ──────────────│
│ DIE_SignatureEdit (plainTextEditSignature, readOnly)│
├────────────────────────────────────────────────────┤
│ lineEditSignatureName (readOnly)                   │
└────────────────────────────────────────────────────┘
```

**额外功能**（相比基础 widget）：

- `comboBoxType` — 手动选择文件类型覆盖自动检测
- `QSplitter` 分割结果树和签名源码编辑器
- `DIE_SignatureEdit` — 带语法高亮的签名源码查看器（`die_highlighter.h`）
- `toolButtonSave` — 保存扫描结果
- 选中结果项时显示对应签名源码（`onSelectionChanged`）

### DialogDIESignatures（签名浏览器/调试器）

源码：`dialogdiesignatures.{h,cpp,ui}`

**功能**：

- `QTreeWidget` 按文件类型分组列出所有签名
- `DIE_SignatureEdit` 签名源码编辑器（可编辑，`checkBoxReadOnly` 切换）
- `pushButtonRun` — 运行选中签名
- `pushButtonDebug` — 调试模式运行
- `pushButtonClearResult` — 清除结果
- `pushButtonSave` — 保存修改的签名
- `pushButtonFind`/`pushButtonFindNext` — 文本搜索
- `DialogFindText` 搜索对话框
- 三个用户数据角色：`UD_FILEPATH`、`UD_FILETYPE`、`UD_NAME`

### DialogDIEScanDirectory（目录扫描）

源码：`dialogdiescandirectory.{h,cpp,ui}`

**功能**：

- `pushButtonOpenDirectory` — 选择目录
- `pushButtonScan` — 扫描目录（含子目录选项）
- 结果累积显示
- `pushButtonClear` — 清除结果
- `pushButtonSave` — 保存结果
- `resultSignal(QString)` — 发送扫描结果文本

### DialogDIESignaturesElapsed（签名 profiling）

源码：`dialogdiesignatureselapsed.{h,cpp,ui}`

显示每个签名的执行耗时，用于性能分析。

### DialogDieHexViewer（Hex 查看器）

源码：`dialogdiehexviewer.{h,cpp,ui}`

简单的 Hex 查看器对话框，基于 `XHexView`。

### DIEOptionsWidget（DIE 选项 widget）

源码：`dieoptionswidget.{h,cpp,ui}`

DIE 特定选项：数据库路径选择（Main/Extra/Custom + YARA rules）。

## diel（精简 GUI）程序设计

源码：`lite_source/litemainwindow.{h,cpp,ui}`

**布局**：

```
┌──────────────────────────────────────┐
│ File name [lineEditFileName][Open]   │
│ [Type▼][Flags▼][Databases▼] [Scan]   │
│ ┌──────────────────────────────────┐ │
│ │ plainTextEditResult              │ │
│ │ (扫描结果纯文本)                  │ │
│ └──────────────────────────────────┘ │
│ Scan time: N msec        [Exit]      │
└──────────────────────────────────────┘
```

**功能**（极简）：

- 文件输入：LineEdit + OpenFile 按钮 + 拖放
- 文件类型选择：`comboBoxType`（`XFormats::setFileTypeComboBox`）
- 扫描标志：`comboBoxFlags`
- 数据库选择：`comboBoxDatabases`（Extra 禁用）
- 扫描按钮：同步调用 `g_pDieScript->scanFile`
- 结果展示：`plainTextEditResult`（`ScanItemModel::toFormattedString`）
- 扫描耗时：`labelScanTime`
- ESC 键关闭窗口
- 独立选项文件（`X_OPTIONSFILELITE`）
- 默认 flags：Recursive + Deep + Verbose

**与 die 的差异**：

- 无 TreeView，使用纯文本
- 无签名浏览器、Hex 查看器、Demangle
- 无 Options 对话框、Shortcuts 对话框
- 无 Advanced 模式
- 无 Recent Files
- 无全屏切换
- 同步扫描（无 QtConcurrent）

## XScanEngine 扫描选项与结果模型

源码：`XScanEngine/xscanengine.h`

### SCAN_OPTIONS

```cpp
struct SCAN_OPTIONS {
    bool bIsDeepScan, bIsHeuristicScan, bIsFirstWrapperScan;
    bool bIsVerbose, bIsRecursiveScan, bIsResourcesScan;
    bool bIsArchivesScan, bIsOverlayScan, bIsAggressiveScan;
    bool bIsAllTypesScan, bUseCache, bShowInternalDetects;
    bool bResultAsXML/JSON/CSV/TSV/PlainText;
    bool bSubdirectories, bIsImage, bIsTest, bHandleInfo;
    XBinary::FT fileType;  XBinary::FILEPART initFilePart;
    bool bLog, bLogProfiling, bShowScanTime;
    bool bShowType, bShowVersion, bShowInfo, bFormatResult;
    bool bHideUnknown, bShowEntropy, bShowFileInfo;
    bool bIsSort;
    QString sMainDatabasePath, sExtraDatabasePath, sCustomDatabasePath;
    bool bUseExtraDatabase, bUseCustomDatabase;
    // Collection 选项...
};
```

### SCAN_RESULT

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
```

### 扫描标志位 SF_*

| 标志 | 值 | 说明 |
| --- | --- | --- |
| `SF_DEEPSCAN` | 0x00000001 | 深度扫描 |
| `SF_HEURISTICSCAN` | 0x00000002 | 启发式扫描 |
| `SF_ALLTYPESSCAN` | 0x00000004 | 所有类型 |
| `SF_RECURSIVESCAN` | 0x00000008 | 递归扫描（resource/overlay） |
| `SF_VERBOSE` | 0x00000010 | 详细输出 |
| `SF_AGGRESSIVESCAN` | 0x00000020 | 激进扫描 |
| `SF_OVERLAYSCAN` | 0x00000040 | Overlay 扫描 |
| `SF_RESOURCESSCAN` | 0x00000080 | 资源扫描 |
| `SF_ARCHIVESSCAN` | 0x00000100 | 归档扫描 |
| `SF_FIRSTWRAPPERONLY` | 0x00000200 | 仅首层包装 |
| `SF_USECACHE` | 0x01000000 | 使用缓存 |
| `SF_SORT` | 0x02000000 | 排序结果 |
| `SF_HIDEUNKNOWN` | 0x04000000 | 隐藏未知 |
| `SF_FORMATRESULT` | 0x10000000 | 格式化结果 |

## die 完整 GUI 的非扫描功能

`die` 通过 `FormatsWidget`（`FormatWidgets` submodule）集成大量格式查看器：

- **XHexView** — Hex 查看器（`XHexView` submodule）
- **XDisasmView** — 反汇编视图（`XDisasmView` + `XDisasmCore` + `XCapstone`）
- **XDemangleWidget** — C++ 符号 demangle（`XDemangleWidget` + `XDemangle` + `XCppfilt`）
- **XMemoryMapWidget** — 内存映射视图
- **XEntropyWidget** — 熵视图
- **XHashWidget** — 哈希计算视图
- **XRegionsWidget** — 区段视图
- **XSymbolsWidget** — 符号表视图
- **XVisualizationWidget** — 可视化视图
- **XExtractorWidget** — 提取器（`XExtractor`）
- **XDataConvertorWidget** — 数据转换器
- **XMIMEWidget** — MIME 类型视图
- **yara_widget** — YARA 规则视图
- **peid_widget** — PEID 签名视图
- **nfd_widget** — NFD（Nauz File Detector）视图
- **archive_widget** — 归档视图
- **XOnlineTools** — 在线工具（VirusTotal 等）
- **XInfoDB** — 信息数据库
- **XGithub** — GitHub 集成
- **XUpdate** — 自动更新

这些功能大多依赖独立的 submodule，且部分（XCapstone/YARA）依赖 native 库。

## 组件依赖关系

```
GuiMainWindow (gui_source)
├── DIE_Widget (die_widget)
│   ├── DiE_Script (die_script) — 规则引擎 facade
│   │   └── XScanEngine — 扫描编排
│   ├── ScanItemModel — 结果模型
│   ├── DialogDIESignatures — 签名浏览器
│   ├── DialogDIEScanDirectory — 目录扫描
│   ├── DialogDIESignaturesElapsed — profiling
│   ├── DialogDieHexViewer — Hex 查看器
│   └── DIEOptionsWidget — DIE 选项
├── DialogOptions (gui_source)
│   ├── XScanEngineOptionsWidget
│   ├── SearchSignaturesOptionsWidget
│   ├── XHexViewOptionsWidget
│   ├── XDisasmViewOptionsWidget
│   ├── XOnlineToolsOptionsWidget
│   └── XInfoDBOptionsWidget
├── FormatsWidget (FormatWidgets) — 格式查看器容器
│   ├── XHexView, XDisasmView, XDemangleWidget
│   ├── XMemoryMapWidget, XEntropyWidget, XHashWidget
│   ├── XRegionsWidget, XSymbolsWidget, XVisualizationWidget
│   └── ... (20+ widget submodules)
├── XOptions — 设置持久化
├── XShortcuts — 快捷键管理
├── XTranslation — 多语言
├── XStyles — 主题样式
├── XSingleApplication — 单实例
└── XUpdate (Windows) — 自动更新
```

## diec-rust 对齐分析

### 已有基础

diec-rust Phase 1-6 已实现：

- `diec-engine::Scanner` — 扫描编排，`scan_once`/`scan_bytes` 入口
- `diec-engine::ScanResult` — 结果模型（detections + diagnostics）
- `diec-engine::ScanFlags` — 扫描标志（recursive/deep/heuristic/verbose/
  aggressive/alltypes/overlay/resources/archives）
- `diec-engine::Database` — 规则数据库（immutable，Arc 共享）
- `diec-output` — text/json/xml/csv/tsv 输出格式
- `diec-cli` — CLI 适配层
- `diec-ffi` — C ABI
- `diec-server` — HTTP/JSON 服务层（ADR 0017）

### GUI 需新增的能力

| 上游功能 | diec-rust 现状 | Phase 7 需实现 |
| --- | --- | --- |
| 文件扫描+结果展示 | `scan_bytes` 已有 | Tauri 前端 + IPC |
| 扫描标志控制 | `ScanFlags` 已有 | 前端 combo box → IPC |
| 数据库选择 | `DatabaseBuilder` 已有 | 前端 database path 配置 |
| 异步扫描+进度 | `CancellationToken` 已有 | Tauri Channel 流式进度 |
| 结果树展示 | `ScanResult` 已有 | 前端 TreeView 渲染 |
| 签名浏览/调试 | 无 | 新增签名列表+源码查看 |
| 目录批量扫描 | CLI `--recursive` 已有 | 前端目录选择+批量调用 |
| Hex 查看器 | 无 | 新增（前端或 Rust 后端） |
| 反汇编视图 | `getDisasmString` stub | 需 Capstone 集成（P5 限制） |
| Demangle | 无 | 新增（cpp_demangle crate） |
| 设置持久化 | 无 | 新增（前端 localStorage 或 Rust INI） |
| 多语言 | 无 | 新增（i18n） |
| 主题样式 | 无 | 新增（CSS/QSS 替代） |
| Recent files | 无 | 新增 |
| 拖放支持 | 无 | Tauri drop 事件 |
| 单实例 | 无 | Tauri single-instance plugin |
| 自动更新 | 无 | Tauri updater plugin |

### 不可对齐项

- **YARA 引擎**：上游通过 `XYara` 集成 YARA，diec-rust 未集成 YARA。
  YARA 是大型 native 依赖，需单独 ADR。
- **PEID 签名**：上游通过 `XPEID` 加载 PEID 数据库，diec-rust 未实现。
- **NFD（Nauz File Detector）**：上游通过 `nfd_widget` 集成，diec-rust 未实现。
- **反汇编**：`getDisasmString` 当前返回空字符串（README 已知限制），
  Capstone 集成需单独 ADR。
- **在线工具**：VirusTotal 等在线 API 集成，需网络功能和 API key。
- **XInfoDB**：上游的文件信息数据库，diec-rust 无等价物。

## 限制

- 本文仅分析 GUI 源码结构和功能清单，不评估 Tauri 与 Qt 的 UI/UX 等价性。
- `FormatWidgets` 的 20+ 子模块未逐一深入分析，仅列出功能名称。
- 上游 `die` 的完整功能依赖约 50 个 submodule，diec-rust 全功能对齐需
  分批实现，本文为功能清单基线，具体实现优先级见 Phase 7 设计文档。
- YARA、PEID、NFD、Capstone 等 native 依赖的集成需各自 ADR 记录权衡。
