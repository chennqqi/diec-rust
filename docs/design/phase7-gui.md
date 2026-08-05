# Phase 7：GUI 设计文档

Status: Proposed
Last updated: 2026-08-05

## 目标

用 Tauri v2 实现功能对齐上游 `die` 完整 GUI 的图形界面程序 `die-gui`，
覆盖扫描、签名浏览、目录扫描、Hex 查看器、Demangle、设置、多语言和主题
等全部功能。

## 依据

- 上游 GUI 源码分析：[`docs/research/upstream-gui-analysis.md`](../research/upstream-gui-analysis.md)
- 框架选型 ADR：[`docs/design/decisions/0018-tauri-gui-framework.md`](decisions/0018-tauri-gui-framework.md)
- 现有架构：[`docs/design/architecture.md`](architecture.md)
- 现有引擎 API：`diec-engine::{Scanner, scan_bytes, scan_once, ScanResult, ScanFlags, Database}`

## 架构

### crate 定位

`diec-gui` 是 Tauri 应用 crate，属于适配层，依赖 `diec-engine`/`diec-output`/
`diec-core`，核心层不反向依赖。与 `diec-cli`/`diec-ffi`/`diec-server` 平级。

### workspace 集成

```toml
# Cargo.toml (workspace)
members = [
    "crates/diec-core",
    "crates/diec-formats",
    "crates/diec-rules",
    "crates/diec-engine",
    "crates/diec-output",
    "crates/diec-cli",
    "crates/diec-ffi",
    "crates/diec-server",
    "crates/diec-gui",       # ← 新增
    "xtask",
]
```

`diec-gui` 不加入 `diec-ffi`/`diec-server` 的依赖图，`xtask check-deps`
需更新依赖 DAG 规则以允许 `diec-gui` 依赖 `tauri`。

### IPC 架构

前端（React/TS）通过 `invoke()` 调用 Rust 命令，长任务通过 `Channel`
流式推送进度：

```
Frontend (React)  ←→  Tauri IPC  ←→  Rust Commands  ←→  diec-engine
     ↑                                                      ↓
     └──────── Channel<ScanProgress> ─────────────────  ScanResult
```

## 功能规格

### 7A：核心扫描 GUI（对标 diel + die 基础）

#### 7A-1 主窗口

| 功能 | 上游对应 | 实现 |
| --- | --- | --- |
| 文件名输入 | `lineEditFileName` + `toolButtonOpenFile` | 前端 input + Tauri dialog plugin |
| 拖放文件 | `dropEvent` | Tauri `onDragDropEvent` |
| Recent files 菜单 | `toolButtonRecentFiles` + `g_pRecentFilesMenu` | 前端 dropdown + settings |
| Advanced 切换 | `checkBoxAdvanced` | 前端 toggle |
| 全屏切换 | `fullScreenSlot` | Tauri window API |
| 单实例 | `XSingleApplication` | `tauri-plugin-single-instance` |
| 命令行参数 | `argv[1]` | Tauri `get_cli()` |
| 窗口标题 | `XOptions::getTitle` | Tauri config + 动态设置 |

#### 7A-2 扫描 widget

| 功能 | 上游对应 | 实现 |
| --- | --- | --- |
| 结果树展示 | `treeViewResult` + `ScanItemModel` | React TreeView 组件 |
| 结果列：String/Signature/Info | 3 列 | TreeView 3 列 |
| 点击 Signature → 显示源码 | `showSignature()` | invoke `get_signature_source` |
| 点击 Info → 显示帮助 | `showInfo()` → HTML/Google | 前端 modal + help docs |
| Flags 下拉 | `comboBoxFlags` | 前端 multi-select |
| Databases 下拉 | `comboBoxDatabases` | 前端 multi-select |
| Scan/Stop 按钮 | `pushButtonDieScanStart/Stop` | 前端 button + CancellationToken |
| 异步扫描 + 进度 | `QtConcurrent` + `QFutureWatcher` + `QTimer` | Tauri `Channel<ScanProgress>` |
| 扫描耗时显示 | `toolButtonElapsedTime` | 前端 label |
| 复制结果 | `copyResult()` | `navigator.clipboard` |
| 上下文菜单 | `customContextMenuRequested` | 前端 context menu |

#### 7A-3 扫描命令

```rust
#[derive(Serialize, Deserialize)]
pub struct ScanFlagsDto {
    pub recursive: bool,
    pub deep: bool,
    pub heuristic: bool,
    pub verbose: bool,
    pub aggressive: bool,
    pub alltypes: bool,
    pub overlay: bool,
    pub resources: bool,
    pub archives: bool,
}

#[derive(Serialize, Deserialize)]
pub struct ScanDetectionDto {
    pub file_type: String,
    pub type_name: String,
    pub name: String,
    pub version: Option<String>,
    pub options: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct ScanResultDto {
    pub path: String,
    pub detections: Vec<ScanDetectionDto>,
    pub diagnostics: Vec<String>,
    pub scan_time_ms: u64,
    pub file_size: u64,
    pub file_type: String,
}

#[derive(Serialize, Deserialize)]
#[serde(tag = "event", content = "data")]
pub enum ScanProgress {
    Started { file_name: String, file_size: u64 },
    Progress { current: u64, total: u64, message: String },
    Finished { result: ScanResultDto },
    Error { message: String },
}

#[tauri::command]
async fn scan_file(
    state: tauri::State<'_, AppState>,
    path: String,
    flags: ScanFlagsDto,
    on_progress: tauri::ipc::Channel<ScanProgress>,
) -> Result<ScanResultDto, String>;

#[tauri::command]
async fn scan_bytes(
    state: tauri::State<'_, AppState>,
    file_name: String,
    data: Vec<u8>,
    flags: ScanFlagsDto,
) -> Result<ScanResultDto, String>;

#[tauri::command]
async fn stop_scan(state: tauri::State<'_, AppState>) -> Result<(), String>;
```

#### 7A-4 设置持久化

| 设置分类 | 上游 `XOptions` ID | 实现 |
| --- | --- | --- |
| View | STYLE/QSS/LANG/FONT_*/STAYONTOP/ADVANCED | CSS 主题 + i18n + 前端 state |
| File | SAVELASTDIRECTORY/SAVERECENTFILES/SAVEBACKUP | settings.json |
| Scan | SCANAFTEROPEN/FLAG_*/HIDEUNKNOWN/SORT/LOG_PROFILING | settings.json |
| Database | DIE_DATABASE_*_PATH | settings.json + Tauri dialog |
| Engine | ENGINE_DIE/NFD/PEID/YARA_ENABLED | settings.json |

设置文件路径：`app_config_dir()/settings.json`，通过
`tauri-plugin-store` 或自定义 JSON 持久化。

### 7B：高级功能（对标 die 完整 GUI）

#### 7B-1 签名浏览器

| 功能 | 上游 `DialogDIESignatures` | 实现 |
| --- | --- | --- |
| 签名树（按文件类型分组） | `QTreeWidget` | React TreeView |
| 签名源码查看 | `DIE_SignatureEdit` + `die_highlighter` | Monaco/CodeMirror 编辑器 |
| 运行单个签名 | `pushButtonRun` | invoke `run_signature` |
| 调试模式运行 | `pushButtonDebug` | invoke `run_signature` (debug=true) |
| 编辑签名 | `checkBoxReadOnly` toggle | 编辑器 readOnly toggle |
| 保存签名 | `pushButtonSave` | invoke `save_signature` |
| 文本搜索 | `pushButtonFind/FindNext` | 编辑器内置搜索 |

```rust
#[tauri::command]
async fn list_signatures(
    state: tauri::State<'_, AppState>,
) -> Result<Vec<SignatureGroupDto>, String>;

#[tauri::command]
async fn get_signature_source(
    state: tauri::State<'_, AppState>,
    file_type: String,
    name: String,
) -> Result<SignatureSourceDto, String>;

#[tauri::command]
async fn run_signature(
    state: tauri::State<'_, AppState>,
    file_path: String,
    file_type: String,
    signature_name: String,
    debug: bool,
) -> Result<ScanResultDto, String>;
```

#### 7B-2 目录扫描

| 功能 | 上游 `DialogDIEScanDirectory` | 实现 |
| --- | --- | --- |
| 选择目录 | `pushButtonOpenDirectory` | Tauri dialog |
| 扫描目录 | `pushButtonScan` | invoke `scan_directory` |
| 子目录递归 | `bSubdirectories` | 前端 checkbox |
| 结果累积 | `appendResult` | 前端 list + Channel |
| 清除/保存 | `pushButtonClear/Save` | 前端 button |

```rust
#[tauri::command]
async fn scan_directory(
    state: tauri::State<'_, AppState>,
    dir: String,
    flags: ScanFlagsDto,
    subdirectories: bool,
    on_progress: tauri::ipc::Channel<DirectoryScanProgress>,
) -> Result<Vec<ScanResultDto>, String>;
```

#### 7B-3 签名 Profiling

| 功能 | 上游 `DialogDIESignaturesElapsed` | 实现 |
| --- | --- | --- |
| 每签名耗时 | `DEBUG_RECORD.nElapsedTime` | invoke `get_scan_profiling` |
| 按耗时排序 | 表格排序 | 前端 table sort |

#### 7B-4 Hex 查看器

| 功能 | 上游 `DialogDieHexViewer` + `XHexView` | 实现 |
| --- | --- | --- |
| Hex dump 显示 | `XHexView` | 前端 hex viewer 组件 |
| 偏移/ASCII/Hex 列 | `XHexView` columns | 前端 grid |
| 搜索 | `XHexView` search | 前端 search |
| 跳转偏移 | `XHexView` goto | 前端 input |

候选前端库：`hexyjs`、`react-hex-editor` 或自实现。

#### 7B-5 Demangle

| 功能 | 上游 `XDemangleWidget` + `XDemangle` + `XCppfilt` | 实现 |
| --- | --- | --- |
| C++ 符号 demangle | `XDemangle` | Rust `cpp_demangle` crate |
| GCC/MSVC/Itanium ABI | `XCppfilt` | `cpp_demangle` (Itanium) + `msvc-demangle` |

```rust
#[tauri::command]
async fn demangle(symbol: String, compiler: String) -> Result<String, String>;
```

#### 7B-6 Options 对话框

| 功能 | 上游 `DialogOptions` | 实现 |
| --- | --- | --- |
| 扫描引擎选项 | `XScanEngineOptionsWidget` | 前端 form |
| 签名搜索选项 | `SearchSignaturesOptionsWidget` | 前端 form |
| Hex 视图选项 | `XHexViewOptionsWidget` | 前端 form |
| 反汇编选项 | `XDisasmViewOptionsWidget` | 前端 form（反汇编未实现时禁用） |
| 在线工具选项 | `XOnlineToolsOptionsWidget` | 前端 form |
| InfoDB 选项 | `XInfoDBOptionsWidget` | 前端 form |

#### 7B-7 多语言

上游使用 `XTranslation`（Qt translation system）。Tauri 方案：

- 前端使用 `react-i18next`
- 翻译文件：`frontend/src/i18n/{en,zh-CN,...}.json`
- 语言切换：settings → i18n.changeLanguage
- 上游支持的语言从 `XTranslation` submodule 获取（en/ru/zh/zh-TW/ja/ko/
  de/es/fr/it/pl/pt-BR/tr等）

#### 7B-8 主题样式

上游使用 QSS（Qt 样式表）。Tauri 方案：

- CSS 变量定义主题色
- 上游内置主题：`orange_fix`（Windows 默认）、`Fusion`（style）
- 实现 light/dark/system 三种主题 + 自定义 QSS 等价 CSS

#### 7B-9 快捷键

上游使用 `XShortcuts`。Tauri 方案：

- 前端 `react-hotkeys-hook` 或 `useKeyPress`
- 全局快捷键：Open(Ctrl+O)、Exit(Ctrl+Q)、Fullscreen(F11)
- Hex/Disasm/Table 分组快捷键

#### 7B-10 自动更新

上游 Windows 使用 `XUpdate`。Tauri 方案：

- `tauri-plugin-updater`
- 更新源：GitHub Releases（与现有 release workflow 对齐）
- 签名验证：Tauri updater 公钥签名

### 7C：扩展功能（需独立 ADR）

以下功能依赖 native 库或上游未集成的引擎，需各自 ADR 记录权衡：

| 功能 | 依赖 | ADR |
| --- | --- | --- |
| 反汇编视图 | Capstone（`xcapstone`） | ADR 0019（待定） |
| YARA 规则 | YARA（`yara-rust`） | ADR 0020（待定） |
| PEID 签名 | PEID 数据库 | ADR 0021（待定） |
| NFD 视图 | Nauz File Detector | ADR 0022（待定） |
| 在线工具 | VirusTotal 等 API | ADR 0023（待定） |
| 熵视图 | 熵计算 | 复用 CLI `--entropy` |
| 哈希视图 | MD5/SHA1/SHA256 | Rust `sha2`/`md-5` |
| 内存映射视图 | PE/ELF section map | 复用 `diec-formats` |
| 区段视图 | PE/ELF regions | 复用 `diec-formats` |
| 符号表视图 | PE/ELF symbols | 复用 `diec-formats` |
| 归档视图 | archive 内容 | 复用 `diec-formats` |
| 数据转换器 | hex/dec/ascii/base64 | 前端实现 |
| 提取器 | overlay/archive 提取 | 复用 `diec-engine` |

## 测试策略

### 单元测试

- IPC 命令的 Rust 端单元测试（mock `AppState`）
- 设置序列化/反序列化测试
- DTO 转换测试（`ScanResult` → `ScanResultDto`）

### 集成测试

- Tauri WebView smoke test（三平台 CI）
- 端到端：打开文件 → 扫描 → 结果展示 → 签名查看
- 目录扫描端到端
- 设置持久化往返测试

### 差分测试

- GUI 扫描结果与 CLI `diec` 输出差分（同一文件、同一 flags）
- 签名列表与上游 `DialogDIESignatures` 树结构对齐

### 跨平台 CI

扩展现有 `.github/workflows/`：

- `gui-build` job：Linux/Windows/macOS 构建 `diec-gui`
- `gui-smoke` job：WebView 启动 + 基本交互 smoke test
- Linux 需安装 `libwebkit2gtk-4.1-dev`、`libgtk-3-dev`、`libayatana-appindicator3-dev`

## 交付物

### 代码

- `crates/diec-gui/` — Tauri 应用 crate
- `crates/diec-gui/src/commands.rs` — IPC 命令
- `crates/diec-gui/src/state.rs` — AppState（Database 缓存）
- `crates/diec-gui/src/settings.rs` — 设置持久化
- `crates/diec-gui/frontend/` — React 前端
- `crates/diec-gui/tauri.conf.json` — Tauri 配置

### 文档

- `docs/design/phase7-gui.md`（本文）
- `docs/design/decisions/0018-tauri-gui-framework.md`
- `docs/research/upstream-gui-analysis.md`
- 更新 `ROADMAP.md` Phase 7
- 更新 `README.md` GUI 章节

### CI/CD

- `.github/workflows/gui-build.yml` — GUI 构建矩阵
- 发布物包含 `die-gui` 可执行文件（三平台）

## 退出条件

- 功能对齐上游 `die` 完整 GUI（扫描、签名浏览、目录扫描、Hex、Demangle、
  设置、多语言、主题、快捷键、Recent files、拖放、单实例）
- 三平台（Linux/Windows/macOS）构建通过
- GUI 扫描结果与 CLI 差分 0 不匹配
- `cargo fmt --check` + `cargo clippy --workspace --all-targets --all-features -- -D warnings` 通过
- `cargo test --workspace --all-features` 通过
- 7C 扩展功能（反汇编/YARA/PEID/NFD/在线工具）可 deferred 到后续 Phase

## 实现顺序

1. **7A-0**：创建 `diec-gui` crate 骨架 + Tauri 配置 + workspace 集成
2. **7A-1**：主窗口 + 文件输入 + 拖放
3. **7A-2**：扫描命令 + 结果树 + Flags/Databases 控件
4. **7A-3**：异步扫描 + Channel 进度 + Stop
5. **7A-4**：设置持久化 + Recent files
6. **7B-1**：签名浏览器
7. **7B-2**：目录扫描
8. **7B-3**：签名 Profiling
9. **7B-4**：Hex 查看器
10. **7B-5**：Demangle
11. **7B-6**：Options 对话框
12. **7B-7**：多语言
13. **7B-8**：主题样式
14. **7B-9**：快捷键
15. **7B-10**：自动更新
16. **CI/CD**：GUI 构建矩阵 + 发布
