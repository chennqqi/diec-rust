# YARA、PEiD 与二进制签名资产溯源

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-27

本文审计 DIE-engine 固定版本中容易与 `db*` JavaScript 检测规则混淆的三类
辅助数据：

- YARA `.yar`；
- PEiD `userdb`；
- `signatures` 的 crypto/junk `.db`。

结论只描述固定源码、构建和运行时事实，不构成法律意见。

## 结论

- 当前 `src/console/diec` 只构造 `DiE_Script`，只提供 `$data/db`、
  `$data/db_extra` 和 `$data/db_custom` 三类数据库路径。其源码、CMake source
  list 和最终 link line 均没有 YARA、PEiD 或 `signatures` 数据入口。
- 上述资产因此不是固定 `diec` CLI 的可观察扫描能力，不能加入当前 CLI 差分
  oracle，也不能用它们的存在扩大 Rust CLI 的兼容范围。
- 它们仍是上游源码/发布物的一部分：GUI CMake 启用并链接 YARA，qmake GUI
  source collection 包含 XYara 与 XPEID；SearchSignatures 使用
  `$data/signatures`；安装及 AppImage 脚本复制三类组件资产。
- `Detect-It-Easy/yara_rules` 与 `XYara/yara_rules` 不是同一快照：8 个共同路径
  全部字节不同，XYara 还多 2 个文件。两树分别有 10,056 与 10,069 条语法级
  YARA rule。
- `Detect-It-Easy/peid_rules` 与 `XPEID/peid` 也不是同一快照：8 个共同路径
  全部字节不同，并各有独有路径。两树分别有 8,890 与 4,136 个语法级 section。
- 四个 component root `LICENSE` 均以 MIT License 开头，但这不能覆盖数据文件
  自己可见的 GPLv2、归属保留请求或未声明来源。当前逐文件证据不足以批准原样
  分发全部 YARA/PEiD/signature 资产。

机器报告为
[`data/rule-assets.json`](data/rule-assets.json)，生成器为
[`audit_rule_assets.py`](../../tools/upstream/audit_rule_assets.py)。

## 固定版本

| 组件 | Commit | 资产路径 |
| --- | --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` | build/runtime evidence |
| Detect-It-Easy | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` | `yara_rules/`, `peid_rules/` |
| XYara | `34a733e9c733669ad8dcaf4588d51197a08545e3` | `yara_rules/` |
| XPEID | `15c2e2951ab2443c7794e8f88c9fc5c65b217f28` | `peid/` |
| signatures | `5d80fb2863d02e9366aee7b3ade6abb7d6598dbb` | tracked `*.db` |

三个独立 component checkout 均验证 origin、精确 HEAD 和 clean worktree；主仓库
及 Detect-It-Easy 使用固定 source image。所有 checkout 只读挂载，容器运行
`--network=none`。

## 资产清单

tree hash 按排序后的 `path + NUL + bytes + NUL + file SHA-256` 计算。YARA 数量
是行首 `rule` 声明数，PEiD 数量是 section header 数；它们是完整性指标，不表示
规则已经通过对应 runtime 的语义验证。

| 集合 | 文件 | 字节 | YARA rules | PEiD sections | Tree SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| Detect release YARA | 8 | 3,490,324 | 10,056 | 0 | `24684a5ca84971ec11aac060955ad77f255ec58195e1a44551cd3c965422501f` |
| Detect release PEiD | 11 | 2,459,045 | 0 | 8,890 | `9333a04068a80b2e3349477cfd8080c684b58fcb61e08ad2525c58355e4f9d38` |
| XYara component YARA | 10 | 3,900,619 | 10,069 | 0 | `a9ca2ae58309386ec9b6045eae5344fbf4873adc6449a832ea2749428196f3df` |
| XPEID component PEiD | 14 | 1,157,703 | 0 | 4,136 | `8423847fa72e06444dfcc20c3914b14c2140ee222006ea92e89aab355f4eb331` |
| signatures data | 4 | 6,170,981 | 0 | 0 | `0cc6bff37cc9a65260ee0a8aec30d852639029eec0be9d229ee1ad610a7d40a5` |

工具同时逐文件记录 path、bytes、SHA-256、换行风格、首个非空行、可见标记和
component git history。仓库中物化的 Detect-It-Easy subtree 两个 tree hash
均与固定 image 内容相同。

## 两套 YARA 数据不是镜像

共同的 8 个文件为：

```text
DiE_BasicHeuristics_by_DosX.yar
DiE_EnhancedHeuristics_by_DosX.yar
DiE_InterestingThings_by_DosX.yar
crypto_signature.yar
malware_analisys.yar
packer.yar
packer_compiler_signatures.yar
peid.yar
```

8 个文件全部字节不同。XYara 另有 `DosX_Heuristic.yar` 和 `info.ini`。
差异不只是换行：例如 `packer.yar` 在 Detect release 有 1,664 条 rule，
XYara 有 1,665 条；完整逐文件 hash 见机器报告。因此同步规则时不能用其中一个
目录覆盖另一个，也不能把 “Detect release rules” 和 “XYara component rules”
作为同一 canonical tree。

固定主仓库的发布脚本引用 `XYara/yara_rules`，不是
`Detect-It-Easy/yara_rules`：

- `build_linux_portable.sh`；
- `install.sh`；
- `create_appimage.sh`；
- Windows/macOS generic packaging scripts。

这证明组件树是这些主仓库打包路径的输入；它不证明固定 `diec` CLI 会读取它。

## 两套 PEiD 数据不是镜像

8 个共同 PE 路径全部字节不同。Detect release 独有：

```text
PE/file_format.userdb.txt
PE/split_userdb.ps1
PE/userdb.txt
```

XPEID 独有：

```text
Binary/archive.userdb.txt
Binary/file_format.userdb.txt
COM/packer.userdb.txt
MSDOS/dos_extender.userdb.txt
PE/crypter.userdb.txt
info.ini
```

`Detect-It-Easy/peid_rules/PE/split_userdb.ps1` 还保存了
`C:\tmp_build\...` 本机绝对路径；它是维护脚本证据，不是扫描规则。
XPEID 的 13 个 userdb 文件使用 CRLF，并以
`; PEiD signature database - <category>` 开头；Detect release 文件使用 LF，
没有该 component header。

`install.sh`、`create_appimage.sh` 和 `XPEID/xpeid.cmake` 引用
`XPEID/peid`。固定 CMake GUI 没有把 XPEID source 加入当前 GUI target，但
qmake `gui_source/gui_source_tr.pro` 明确收集 `XPEID/xpeid.cpp`。因此 PEiD
是 qmake GUI/替代 scan engine 路径，不能外推为 CMake `diec` CLI 能力。

## signatures 数据

固定仓库跟踪四个 `.db`：

| 路径 | 字节 | 关系 |
| --- | ---: | --- |
| `crypto.db` | 3,085,459 | 主仓库打包脚本直接复制 |
| `signatures/generic/crypto.db` | 3,085,459 | 与根 `crypto.db` 字节完全相同 |
| `Junks/x86.db` | 22 | legacy 路径 |
| `signatures/x86/junks.db` | 41 | 与 legacy junk 文件不同 |

`signatures.cmake` 只在定义 `X_RESOURCES` 时安装结构化 `signatures/`。
SearchSignatures widget 默认路径是 `$data/signatures`，并 include 该 CMake
文件；主仓库的 portable/install/AppImage 脚本则显式复制根 `crypto.db`。
四个数据文件没有被工具发现文件内许可证/来源标记，当前证据只有 component
root MIT。

## 当前 CLI 可达性

| 证据 | 固定事实 |
| --- | --- |
| `src/console/main_console.cpp` | 构造 `DiE_Script die_script`；仅注册 main/extra/custom database |
| `src/console/CMakeLists.txt` | include die_script、XOptions、entropyprocess、XFileInfo；无 XYara/XPEID/FormatWidgets |
| `src/console/CMakeFiles/diec.dir/link.txt` | 无 XYara、XPEID、FormatWidgets、YARA 或 signatures token |
| `src/gui/CMakeLists.txt` | `WITH_YARA=ON`，定义 `USE_YARA`，链接 `yara`，安装 `XYara/yara_rules` |
| `gui_source/gui_source_tr.pro` | 收集 `XYara/xyara.cpp` 与 `XPEID/xpeid.cpp` |
| `XScanEngine/xscanengineconsole.cpp` | 替代引擎 console 对 YARA/PEiD 使用 `$data/yara`、`$data/peid` |
| SearchSignatures | 默认 `$data/signatures`，include `signatures.cmake` |

每个证据文件的 SHA-256 都保存在机器报告中。结论是：

```text
固定 diec CLI runtime scope:
  Detect-It-Easy/db
  Detect-It-Easy/db_extra
  Detect-It-Easy/db_custom

不在固定 diec CLI runtime scope:
  Detect-It-Easy/yara_rules
  Detect-It-Easy/peid_rules
  XYara/yara_rules
  XPEID/peid
  signatures/*.db
```

上游包中存在文件不等于 CLI 读取文件。后续发布物审计仍需记录这些被复制但对
CLI 不可达的文件，以免无意分发未完成许可核对的资产。

## 文件级许可证与来源信号

四个仓库级 LICENSE hash：

| Component | LICENSE SHA-256 |
| --- | --- |
| Detect-It-Easy | `be0fe2d727cd0a754fb0b2fdc579ead8f19ef575840b4daef221be201701eaad` |
| XYara | `abdeb212f229d2b93a5c315763df4d7201c7d74f580ad9dc77d77dec7cbc6c69` |
| XPEID | `374e26cb4e674f28a1b261b8f394f0ce6f1950bd1200d85cc1a9aa23858007d1` |
| signatures | `b15e85faef7d7294e40453fd4bf6fcb09138836312b2e61d1a17512e57e35a45` |

逐文件可见信号：

- `crypto_signature.yar`、`packer.yar`、
  `packer_compiler_signatures.yar` 明确写有 “GNU-GPLv2 license”；
- 三个 `DiE_*_by_DosX.yar` 要求保留 copyright information，但没有被本轮
  发现的 SPDX 或完整许可文本；
- `DosX_Heuristic.yar` 只有 author metadata，没有显式许可声明；
- `malware_analisys.yar` 包含多项作者 metadata，没有统一文件级许可声明；
- `peid.yar` 声明由 `peid2yara.py` 生成并列出多个第三方 database URL，
  没有说明这些输入数据库各自的许可；
- XPEID userdb 只有 category header；没有逐文件来源或许可声明；
- signatures 四个 `.db` 没有可见来源或许可声明。

根 MIT 是重要证据，但不能自动改变明确 GPL 文件或未知第三方数据库的条款。
在取得上游说明、追溯原始来源并完成书面评审前，本项目不得把这些资产标成
“MIT 已关闭”，也不得因目标是 1:1 复用而跳过许可门禁。

## Git 历史证据

外部 component checkout 使用完整 git history。机器报告为每个文件保存首次和
最后一次可见 commit/time：

- XYara 的旧文件分别源于 2023 年提交；大部分当前 release-derived YARA 文件
  在 `0ea7c032...`（2026-04-19）进入 component；
- XPEID 的数据库在 `d52bc6d...`、`2ec3c6b...`、`695d2e0...` 分批进入，
  并在 `050f6ada...` 更新；
- signatures 根 `crypto.db` 自 `9fcacfa7...` 保持不变，结构化目录在
  `d8f3a4d...` 引入。

这些提交证明文件何时进入 horsicq component，不证明其更早第三方来源或许可。

## 复现

准备三个完整、clean、detached checkout，并固定到上表 commit。使用占位路径：

```powershell
python tools\upstream\audit_rule_assets.py `
  --xyara-root <xyara-checkout> `
  --xpeid-root <xpeid-checkout> `
  --signatures-root <signatures-checkout> `
  --output docs\research\data\rule-assets.json

python -m unittest discover -s tools/tests -p "test_*rule_assets.py" -v
```

生成器验证 checkout origin/HEAD/clean、组件 lock、image revision、镜像内四个
component HEAD、物化 Detect subtree hash、运行时关系和只读/断网执行。报告不含
扫描时间或本机路径，可逐字节重复生成。

## 对 Rust 项目的约束

- 当前 CLI 兼容实现只以 `db`、`db_extra`、`db_custom` 为规则 runtime 输入；
  YARA/PEiD/SearchSignatures 不能伪装为 CLI 必需能力。
- 未来 GUI 或明确新增辅助 engine 时，必须单独建立 YARA/PEiD/signature
  capability matrix、runtime differential、规则完整性与许可证门禁。
- 任何规则同步都必须指定“Detect release tree”或“component tree”，不能只写
  `yara_rules`/`peid_rules`。
- 原样资产按固定 path/hash 保存；不得用格式化、换行转换或合并重复文件来掩盖
  upstream 差异。
- 发布脚本不得仅因上游会复制这些目录就默认把它们加入 Rust CLI 包。

## 尚未关闭

- 三个 GPLv2 YARA 文件的分发组合和项目整体许可影响；
- DosX、`malware_analisys.yar`、`peid.yar` 输入数据库、PEiD userdb 和
  signatures `.db` 的原始来源/许可证明；
- 官方 release artifacts 是否与固定 source packaging script 内容完全一致；
- Windows/macOS GUI 与辅助 engine 的运行时资产读取 trace；
- 由发布/法律责任人完成书面许可评审。
