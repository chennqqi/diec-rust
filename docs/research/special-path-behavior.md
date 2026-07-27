# Linux Unicode 与特殊路径行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 qmake/CMake 两个 Oracle 对 18 个路径 case、共 36 次执行
给出逐字节一致结果：

- NFC `é`、NFD `e + U+0301`、中文、emoji、普通空格、前导/尾随空格、tab、
  newline、colon、backslash 和显式 hidden 文件均能作为单文件 positional
  target 扫描；每个样本都保持 `PDF` 根类型与 `PDF`、`HeaderComment` 两条规则；
- NFC 与 NFD 名称在 ext4/overlay Linux 语义下是两个不同路径，上游不做 Unicode
  normalization；
- 目录枚举排除 `.hidden.pdf`，但显式传入该文件可以扫描；
- 目录枚举顺序由固定 `QDir::entryInfoList()` 行为决定，不等于 UTF-8 字节序，
  且 `a-case.pdf` 位于 `A-case.pdf` 之前；
- 三个显式 target 保留 argv 顺序，不重新全局排序；
- 绝对路径中的 `--leading-dash.pdf` 正常扫描；相对名称若直接作为 positional
  argument，会被 `QCommandLineParser` 当成未知选项并退出 `1`，使用 `--`
  option terminator 后才正常扫描；
- 仅含一个文件的 Unicode 目录仍不打印 filename prefix，并输出有效的单个 JSON；
  特殊目录展开 15 个非隐藏文件后，为每项插入原始路径 prefix，其中 newline/tab
  直接进入 stdout，多结果 `--json` 仍不是有效 JSON。

机器报告为
[`special-path-engine-qt5.json`](data/special-path-engine-qt5.json)，SHA-256 为
`ebdecb0fddadedc2a45511bf525f1ba66eba644b4590356cea2cf07d531bfb9d`。
报告保存每次未经规范化的 stdout/stderr，并以 `zlib+base64`、SHA-256
content-addressed artifact 形式去重。

这批证据闭合 `CAP-GAP-003` 的 Linux UTF-8/特殊名称基础子矩阵，但没有关闭整个
gap。非 UTF-8 原始字节路径、symlink/权限/超深目录，以及 Windows/macOS
路径与编码行为仍未覆盖。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| qmake image ID | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| CMake image ID | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| qmake `diec` SHA-256 | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| CMake `diec` SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| fixture TAR SHA-256 | `4745de26864b87ef7380cdc6e695a468005f470fa950c9ee763b3ef6817d68a2` |
| fixture manifest SHA-256 | `5dccc0f7f2b6c06fab2a1a7c53b94aef330e4e80a48aae5a4003f83c7f15a52d` |

报告还绑定固定镜像内 `main_console.cpp` 与 `Formats/xbinary.cpp` 的完整 SHA-256，
并验证以下正向源码契约仍存在：

1. 多文件 prefix 通过
   `QDir().toNativeSeparators(sFileName).toUtf8().data()` 写出；
2. 目录使用无显式 filter/sort 参数的 `QDir::entryInfoList()`；
3. 递归调用使用每个 entry 的 absolute path。

这里的运行结果才是具体顺序和过滤行为的兼容基线；源码契约不能替代运行实验。

## 可移植的确定性 fixture

[`generate_special_path_fixture.py`](../../tools/corpus/generate_special_path_fixture.py)
不直接在 Windows 工作区创建特殊文件。它将项目生成的 331-byte 最小 PDF 写入
一个手工编码、metadata 固定的 USTAR：

- mode、uid、gid、mtime 和 header checksum 均确定；
- 路径字段直接使用 UTF-8 bytes；
- archive 末尾固定为两个零 block；
- 不含第三方样本字节，也不提交生成出的 TAR。

这样可以稳定表达 Windows Win32 路径 API 通常难以创建或保留的尾随空格、
newline 和 backslash 名称。版本化清单是
[`special-path-fixture.json`](data/special-path-fixture.json)；测试独立使用
Python `tarfile` 复验 member 顺序、名称和全部 payload。

fixture 共 17 个文件：

- 16 个位于 `paths/special/`；
- 1 个位于 `paths/目录 空格/`；
- `.hidden.pdf` 是目录枚举的负向控制；
- `A-case.pdf`/`a-case.pdf`、NFC/NFD 是排序与 normalization 控制；
- 所有文件内容完全相同，隔离路径变量。

## 目录枚举顺序

固定 Oracle 对 `paths/special/` 观察到以下 15 项顺序（hidden 项不在其中）：

```text
 leading-space.pdf
--leading-dash.pdf
00-ascii.pdf
a-case.pdf
A-case.pdf
backslash\name.pdf
colon:name.pdf
emoji-😀.pdf
é-nfd.pdf
line<LF>break.pdf
space name.pdf
tab<TAB>name.pdf
trailing-space.pdf<SPACE>
é-nfc.pdf
中文.pdf
```

报告保存的是实际 UTF-8 与控制字符，本文只在代码块中把 LF/TAB/尾随空格显示为
占位符。目录 case 原始 stdout SHA-256 为
`f8e08376092ab23152337913c2cac526e752f4ebc59c4e28b31c78de22838e17`。

这不是跨平台排序承诺。Rust 的 legacy-compatible 模式必须在目标平台差分确认
后决定是否复制 Qt 的平台排序；安全、确定性的结构化 API 则应定义自身排序与原始
路径表示，不能把 Linux 本轮顺序外推到 Windows/macOS。

## 前导短横线与显式顺序

相对 `--leading-dash.pdf` 未加 terminator 时：

- exit code 为 `1`；
- stdout 为空；
- stderr 含 `Unknown option 'leading-dash.pdf'.`；
- stderr SHA-256 为
  `ca8afaf3f0d7c0df735d67440bffcf7520f00c55f2b3b994df73ab6278d4153b`。

加入 `--`，或传入以 `/work/...` 开头的绝对路径，均 exit `0` 并正常扫描 PDF。
因此 Rust CLI 若兼容同一参数语法，必须保留 option terminator；调用方不能假设
任意 basename 都可不加保护地作为相对 positional argument。

显式 `emoji -> NFC -> ASCII` 三目标 case 的 prefix 顺序与 argv 完全相同，
stdout SHA-256 为
`b9f6cab51648dcb3b9dc273a996bef9a52bb04de5754f96c10568650e03c9aa9`。

## 复现

```powershell
$baseline = Join-Path $env:TEMP diec-special-path-baseline
$fixture = Join-Path $env:TEMP diec-special-path-fixture
$report = Join-Path $env:TEMP special-path-engine-qt5.json

python tools\corpus\generate_baseline_corpus.py $baseline
python tools\corpus\generate_special_path_fixture.py $baseline $fixture
python tools\upstream\probe_special_path_behavior.py `
  --fixture-dir $fixture `
  --output $report
```

每次 container：

```text
network=none
cpus=1
memory=512 MiB
pids=128
root=read-only
fixture mount=read-only
work tmpfs=16 MiB
timeout=60 seconds
```

TAR 只展开到每个隔离 container 的 `/work` tmpfs，不写宿主路径。两个 Oracle
均使用固定三层数据库路径；探针要求 18 个 case 的 exit/stdout/stderr 逐字节相同。

## 兼容与安全要求

- 路径模型必须能无损区分 NFC/NFD，并在 Unix 上避免强制 Unicode normalization。
- Rust `Path`/`OsStr` 层不得过早转换为 UTF-8 `String`。非 UTF-8 输入的公共 API、
  JSON 表示和 C ABI 编码策略仍需在实现前冻结。
- CLI 原始兼容输出必须保留 filename prefix 中的控制字符；安全结构化输出应将
  路径作为字段正确转义。两者若不同，需用明确模式与差分测试区分。
- 目录枚举必须设置 symlink、depth、entry count、权限错误与取消策略；不能因上游
  缺少限制而继承无限递归风险。
- hidden 过滤、case ordering 与 platform-native separator 都是可观察行为，
  不得用本轮 Linux 结果替代跨平台 Oracle。

## 剩余缺口

- Linux 非 UTF-8 filename bytes 与其诊断/输出表示；
- symlink、循环、权限错误、超深目录、超大目录及取消；
- locale 改变后的排序，以及不同 filesystem normalization/case 行为；
- Linux Qt6 的完整能力矩阵；
- Windows/macOS separator、绝对路径、reserved name、Unicode normalization、
  case sensitivity 与枚举顺序。

因此 `CAP-GAP-003`、`CAP-GAP-007` 和 `CAP-GAP-008` 均保持开放；本报告只减少
Linux Qt5 下的已知语料缺口，不把局部证据提升为跨平台完成声明。
