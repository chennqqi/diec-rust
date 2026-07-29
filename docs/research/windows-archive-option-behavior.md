# Windows Qt5 Engine-only Archive Option 基线

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Rules: `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`

Last updated: 2026-07-29

## 1. 结论

原生 Windows x86_64 Qt5 直接执行了 `bIsArchivesScan` 的完整 64-case
engine matrix，关闭 `CAP-NEST-003`：

- 8 个项目生成 nested fixture × 8 种 archive/recursive/aggressive 组合；
- 每个 case 连续运行两轮，共 128 次进程执行和 128 次 case observation；
- 64 个 case 的 detection tree 均与固定 Linux Qt5 相同；
- 32 个不含 archive option 的 case 又与已提交 Windows release CLI tree
  相同；
- 三个 archive fixture 在无 archive option 时均为 0 Stream，显式 archive
  option 后均产生 Stream；
- `archive` 单独启用即可解包，`aggressive` 单独启用不能替代它；
- ZIP→ZIP 的 archive option 跨层传播并产生 2 个 Stream child。

机器报告：
[`archive-option-engine-windows-qt5.json`](data/archive-option-engine-windows-qt5.json)，
160510 bytes，SHA-256
`c848a85640d2c89648d749ab4c3a723d9782e4095bf55ab29cc4614b75d3d00e`。

## 2. 固定构建

[`build_windows_archive_option_harness.ps1`](../../tools/upstream/build_windows_archive_option_harness.ps1)
校验固定源码、规则、58 个递归 submodule、Qt 5.15.2、release CLI、
Makefile 和 `main_console.obj` 身份。构建复用固定 qmake Release engine
objects，只替换 console main object；没有修改 engine object。

[`archive_harness_main.cpp`](../../tools/upstream/archive_harness_main.cpp)
只把 `bIsArchivesScan` 暴露为研究用 `--archive` 参数，扫描、数据库加载和 JSON
渲染仍调用上游实现。Windows 构建只把三个 Linux 固定数据库路径改写为相对于
已验证源码根的 `Detect-It-Easy/db`、`db_extra` 和 `db_custom`，manifest
记录原始/适配后源码哈希及每项精确替换次数。

固定产物：

- `diec-archive-option-harness.exe`：3,102,720 bytes；
- SHA-256：
  `1c7d14386ded050e9a88231ec8996c13bd430dd2bf292c66e8f85df6006f89fe`。

## 3. 输入与矩阵

输入绑定
[`nested-corpus.json`](data/nested-corpus.json)，manifest SHA-256
`b382bd0a903cd4dda5a8128508f7a3f514a67a721baacda4c6722c99aefc4229`。
八个样本均由项目生成：

- ZIP→PDF；
- ZIP→ZIP→PDF；
- ZIP→22 PDF；
- PE→PDF overlay；
- PE→PDF resource；
- PE→22 PDF resources；
- PE→Manifest resource；
- PE→ZIP overlay→PDF。

每个样本执行：

1. default；
2. archive；
3. aggressive；
4. archive+aggressive；
5. recursive；
6. recursive+aggressive；
7. archive+recursive；
8. archive+recursive+aggressive。

collector 为每次执行在外部 raw 目录保留 stdout/stderr，版本化报告只保存哈希、
检测树内容寻址目录和逐 case 引用。两轮共得到 18 个唯一 stdout、1 个空
stderr 和 18 个唯一 detection tree。

## 4. 差分与边界

[`collect_windows_archive_option.py`](../../tools/upstream/collect_windows_archive_option.py)
绑定两个现有报告：

- Linux Qt5/Qt6 archive-option 报告 SHA-256
  `5cdadeb09d97a0afd03b2f73ebbb5eb4ffd227b9a21973d34d5a3db739bb8d65`；
- Windows release nested 报告 SHA-256
  `e877e112deb244ab1cbf9edf221e94e155cda711a182f216478eeaf9da40e21b`。

比较不删除、重排或改写 detection tree 字段。十一项关系全部成立，包括：

- 64 个 case 双轮确定且与 Linux Qt5 相同；
- 32 个无 archive case 与 Windows release CLI 相同；
- 显式 archive option 正例和 aggressive-only 负例；
- nested ZIP option 传播；
- archive/resource 默认 21 和 aggressive 22 的相邻控制。

21/22 只作为本 option matrix 的控制，不单独关闭精确计数能力。
后续 [`windows-count-boundary-behavior.md`](windows-count-boundary-behavior.md)
已关闭 archive 99999/100000/100001 与 resource 21/2001；
[`windows-archive-limit-behavior.md`](windows-archive-limit-behavior.md)
已关闭 depth 64、累计展开量和 cancellation 边界。

## 5. 兼容性影响

发布 CLI 的 recursive/aggressive 组合不是 archive 解包开关。Rust 实现需要：

- 在核心扫描选项中独立表示 archive scan；
- 保持 legacy CLI 默认不设置该选项；
- 允许 option 向嵌套 archive 传播；
- 不把 aggressive 静默等价为 archive scan。

未来 CLI 若显式暴露 archive scan，应作为新增扩展选项，不得改变 legacy 默认
输出。

## 6. 复现

```powershell
python tools\corpus\generate_nested_corpus.py <fixture-dir>

powershell -ExecutionPolicy Bypass `
  -File tools\upstream\build_windows_archive_option_harness.ps1 `
  -SourceDir <verified-source-root> `
  -BuildDir <fixed-qmake-build-root> `
  -QtDir <qt-5.15.2-msvc2019_64> `
  -VsDevCmd <Visual-Studio-VsDevCmd.bat> `
  -OutputBinary <harness-root>\diec-archive-option-harness.exe `
  -OutputJson <harness-root>\build-manifest.json

python tools\upstream\collect_windows_archive_option.py `
  --binary <harness-root>\diec-archive-option-harness.exe `
  --source-dir <verified-source-root> `
  --qt-dir <qt-5.15.2-msvc2019_64> `
  --fixture-dir <fixture-dir> `
  --build-manifest <harness-root>\build-manifest.json `
  --raw-dir <raw-dir> `
  --output docs\research\data\archive-option-engine-windows-qt5.json

python -m unittest discover -s tools\tests `
  -p "test_*windows_archive_option*.py"
```
