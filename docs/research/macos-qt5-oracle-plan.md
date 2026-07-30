# macOS x86_64 Qt5 oracle bootstrap 计划

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 1. 当前结论

macOS 是四平台能力闭集里唯一仍为 `platform_missing` 的平台。本页建立固定
macOS x86_64 Qt5 CLI oracle 的可执行 bootstrap，但当前 Windows 主机不能运行
它，因此：

- **没有**提交 macOS runtime observation；
- **没有**将任何 macOS 能力提升为 observed；
- `CAP-GAP-008` 的 macOS 部分继续 open；
- Phase 0 继续保持 `IN PROGRESS`。

机器计划为
[`data/macos-qt5-oracle-plan.json`](data/macos-qt5-oracle-plan.json)，由
[`build_macos_qt5_oracle_plan.py`](../../tools/research/build_macos_qt5_oracle_plan.py)
确定性生成。其结果必须保持
`infrastructure_ready_runtime_missing`，直到独立 macOS 主机产出并验证候选
构建记录。

仓库现在还提供只允许手动触发的
[`macos-qt5-oracle-candidate.yml`](../../.github/workflows/macos-qt5-oracle-candidate.yml)。
它固定使用 `macos-15-intel`、Qt 5.15.2 `clang_64`、QtScript、上游 commit
和完整递归 submodule，并同时运行 oracle identity 与临时文件 cache-state
candidate。它还对 26 个项目生成的基础样本各执行两轮默认 JSON 扫描，保留
64 次通用 CLI/corpus 执行的每份原始 stdout/stderr；在同一输入上继续运行
338 个 primary option/output/special case 的双轮矩阵，再把普通 output 与
entropy/info/struct special 的 26-case 组合扩展到其余 21 个样本，增加 546
个 case 的双轮矩阵；工作流还从固定 manifest 重建 database fixture，对 18
个 release CLI database/error case 双轮采集；随后从固定 manifest 重建五文件
path tree 和八个 nested fixture，执行 14 个 path case 与 8 × 4 个 nested
case 的双轮矩阵；同一 database fixture 再执行 17 个 ZIP database case 的
双轮矩阵。合计 1,994 次执行和 3,988 个 raw stream，并与固定 Linux Qt5
detection projection 或 exit code 比较。
remaining 矩阵在尚无
Linux 对应全矩阵时保留结构、有效性与 priority 约束，不伪造跨平台等价。
database 矩阵则只做明确列出的实参路径替换与 CRLF→LF，再与固定 Linux
stdout hash、exit code、load-error marker 和 JSON 有效性比较。
所有第三方 Action 都绑定完整
commit SHA，checkout 不持久化凭据，工作流权限仅为 `contents: read`。
上传物保留 14 天，仍包含 runner 本地路径，仅供下载评审；工作流本身不会提交
报告或修改能力矩阵。

GitHub 托管 runner label 不是不可变镜像锁。实际运行仍须以报告中的 macOS、
Xcode、clang、CMake、qmake 和 Qt 文件 hash 为准，并在评审后决定是否建立
独立的已审 toolchain lock。

## 2. 上游 macOS 入口审计

固定上游包含两个相关入口：

1. `.github/workflows/builder.yml` 中 `build-osx` 整段被注释；它曾指定
   `macos-latest`、Qt 5.15.2、`clang_64`、`qtscript` 和 `build_mac.sh`，
   但没有固定 runner image、Xcode、clang、CMake、action commit 或 Qt 文件
   hash，不能直接作为可重复 oracle。
2. `build_mac.sh` 使用 CMake 构建完整 GUI bundle，再查找并复制 `diec`。
   这会把 GUI、bundle、deploy 和 CLI 构建耦合，不适合本项目的 CLI-only
   能力基线。

固定源码 SHA-256：

| 路径 | SHA-256 |
| --- | --- |
| `.github/workflows/builder.yml` | `b8053dda9c53682b7c931230a427d6ef2880c20bf27fe023a3eb973409ab1d57` |
| `build_mac.sh` | `b5055e2bfe3c9dd5da38629f88d4c89fd511288699c0ffa02b4d2423caee9512` |
| `build.pri` | `a1e09eda22d1e85a51d6d56e8a6669885e6a07a96c2fceb1948c1ce49ec28e1f` |
| `console_source/console_source.pro` | `29d00c74ae2c7d81f0deaa9443e0bb21f6f3e44ba44eb8fdde422896ed58d38c` |

`console_source.pro` 明确 `CONFIG -= app_bundle`，因此 qmake CLI target 能在
macOS 上生成普通 Mach-O executable，无需 GUI bundle。

## 3. Bootstrap 契约

[`build_macos_qt5_oracle.sh`](../../tools/upstream/build_macos_qt5_oracle.sh)
采用与 Linux/Windows qmake oracle 对齐的 CLI-only 路径，并 fail closed：

- 仅接受 Darwin x86_64；
- 固定上游 commit、规则 commit 和 58 个递归 submodule；
- 拒绝 root/submodule tracked changes；
- 固定 Qt `5.15.2`、qmake spec `macx-clang`；
- 要求外部空 build directory，拒绝既有 `diec` 产物；
- 只构建 `sub-build_libs-make_first` 和
  `sub-console_source-make_first`；
- 要求产物只有 `x86_64` architecture，且 `--version` 精确为
  `die 4.0.0`；
- 记录 qmake、QtCore、QtScript、产物和关键上游文件 SHA-256；
- 记录 macOS、CPU、Xcode、clang、CMake、qmake、Mach-O 描述及 `otool -L`；
- 构建前后再次验证 tracked source 未被修改。

候选报告由
[`validate_macos_qt5_oracle_report.py`](../../tools/upstream/validate_macos_qt5_oracle_report.py)
严格检查 duplicate key、固定身份、字段闭集、hash、architecture、依赖与
admission guard。报告保留本机绝对路径，只能存放在外部证据目录；进入仓库前
必须另行去路径并绑定原始报告 hash。

## 4. 在 macOS x86_64 上执行

首选从 GitHub Actions 页面手动运行 `macOS Qt5 oracle candidate`。成功后下载
`macos-qt5-candidates-<run-id>-<attempt>`，先核对 `SHA256SUMS`，再审计八份
candidate JSON 和 `raw/` 原始流。其中 CLI validator 会重新计算
raw hash、determinism、Linux projection 和完整文件闭集；差异会被原样记录，
不会被 normalizer 隐藏。该动作不会自动纳入或提交证据。

先准备固定递归 checkout 和 Qt 5.15.2 `clang_64`，其中必须包含 QtScript。
build/report 目录必须在 source tree 之外：

```text
bash tools/upstream/build_macos_qt5_oracle.sh \
  --source-dir /private/tmp/DIE-engine-74eaf505 \
  --qt-dir /Users/runner/Qt/5.15.2/clang_64 \
  --build-dir /private/tmp/diec-macos-qmake-build \
  --output /private/tmp/diec-macos-candidate.json \
  --jobs 4

python3 tools/upstream/validate_macos_qt5_oracle_report.py \
  /private/tmp/diec-macos-candidate.json
```

首次成功记录仍只是 candidate。必须评审并固定：

- macOS product/build version 和 runner image；
- Xcode、Apple clang、CMake、qmake 版本；
- qmake、QtCore、QtScript 三个 SHA-256；
- Mach-O dependency 闭集、SDK/min-version、codesign 状态；
- 第二个干净 build 的语义与产物差异。

## 5. 从 candidate 到 68 行 closure

候选构建通过后仍需：

1. 用项目生成的安全语料采集默认 CLI、option/output/special、database、
   result/engine、dispatch 和 nested 行；
2. 每个 case 至少双轮，保留原始 stdout/stderr 与结构化投影；
3. 单独固定 APFS 默认 case sensitivity/normalization、Unicode NFD/NFC、
   symlink/cycle、权限、4096-entry、TOCTOU、长路径和文件名非法边界；
4. 与 Linux Qt5 逐字段比较，所有差异必须分类，normalizer 不得隐藏语义；
5. 生成 68 行 macOS closure，达到 68 complete/0 partial/0 missing 后才允许
   总覆盖生成器接纳该平台。

当前机器计划明确要求 68 行和至少双轮；它本身不替代任何 runtime evidence。
通用 CLI/corpus、primary matrix 与 remaining matrix 已把普通
output/special 扩展到全部 26 个生成样本，并加入 18-case release CLI
database/error、46-case path/nested 和 17-case ZIP-database release CLI
矩阵，但仍只属于候选证据：
Unicode normalization、symlink/cycle、permission、large-directory、
filesystem-order、TOCTOU 等平台 path profile，database cache/permission
与 engine-only harness 仍须分别采集，
`capability_rows_admitted` 必须保持 0。

## 6. 本机可执行验证

```text
python tools/research/build_macos_qt5_oracle_plan.py --check
python -m unittest discover -s tools\tests \
  -p "test_macos_qt5_oracle_bootstrap.py"
```

测试绑定 bootstrap/validator 与上游入口文件 SHA-256，验证 synthetic candidate
的完整契约，并确认任何 commit、architecture 或 admission 漂移都会被拒绝。
