# Linux 与 Windows Unicode、原始字节和特殊路径行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 Linux x86_64 Qt5 qmake/CMake 两个 Oracle 对 23 个路径 case、共 46 次执行
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
  直接进入 stdout，多结果 `--json` 仍不是有效 JSON；
- USTAR 解包前置证明确认 `nonutf8/` 中同时存在一个 ASCII PDF 与三个非法 UTF-8
  basename；按父目录扫描时，`QDir::entryInfoList()` 静默跳过三个非法名称，只
  扫描 ASCII control，exit `0`、无 stderr，stdout 与单独扫描 control 逐字节相同；
- 容器内用 `os.execve` 的 bytes argv 显式传入三个非法路径时，Qt 分别将非法字节
  转成 1、2、2 个 U+FFFD replacement character；重编码后的路径已不存在，三个
  case 都向 stdout 打印 `Cannot find:`、exit `1`、stderr 为空。

机器报告为
[`special-path-engine-qt5.json`](data/special-path-engine-qt5.json)，SHA-256 为
`0b5fc241e2c30449e1df11aa08532a7b0adbf9c81362d552bf7770f8cd159f82`。
报告保存每次未经规范化的 stdout/stderr，并以 `zlib+base64`、SHA-256
content-addressed artifact 形式去重。

这批证据闭合原 `CAP-GAP-003` 的 Linux UTF-8 与首轮非 UTF-8/特殊名称子矩阵。
symlink/权限/超深或超大目录、locale/filesystem 差异在本页当时尚未覆盖，随后由
专用路径实验补齐；跨平台路径差异仍由独立 gap 跟踪。
Windows 首轮可表示性/Unicode/Hidden/顺序矩阵现已补充如下；macOS 路径与编码
行为仍未覆盖。

## Windows Qt5 可表示性与特殊路径

Windows fixture 和机器报告分别为
[`windows-special-path-fixture.json`](data/windows-special-path-fixture.json)、
[`windows-qt5-cli-special-paths.json`](data/windows-qt5-cli-special-paths.json)。
固定 Windows x86_64 Qt5 qmake oracle 对 17 个 case 各运行两次，共 34 次，
没有 determinism、expected-exit 或 minimal-PDF detection projection failure。

默认 Win32/NTFS fixture 可以同时保留 NFC/NFD，并可创建中文、emoji、普通/
前导空格、前导短横线和点号名称；默认大小写不敏感使 `A-case`/`a-case` 互为
别名。尾随空格、colon、backslash、TAB/LF、任意非 UTF-8 bytes 不能作为同语义
basename 一比一复用，原因逐项写入 fixture manifest。

目录枚举稳定顺序为：

```text
leading_space, leading_dash, dot_hidden, ascii, upper_case,
emoji, nfd, space, nfc, cjk
```

排除 Windows 特有的 dot-file 项后，与 Linux 共同可表示的 9 项相对顺序一致。
`.dot-hidden.pdf` 没有 `FILE_ATTRIBUTE_HIDDEN`，因此在 Windows 被枚举；真正设置
Hidden attribute 的文件被排除。显式三目标仍保持 argv 顺序，相对前导短横线
仍需要 `--` terminator。

报告 SHA-256 为
`f4e2f4ced3190a51df3bfa34cbdf8ad949130aadab324c7e725365a2c7fa8e68`。
该特殊名称矩阵本身尚未覆盖 UNC/extended-length、junction/reparse/cycle、
ACL denial、ADS 和大小写敏感目录，不能据此关闭完整 Windows path gap；
其中 Junction/长路径/ADS 已分别由后续独立 Windows 报告首轮覆盖。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| qmake image ID | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| CMake image ID | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| qmake `diec` SHA-256 | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| CMake `diec` SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| fixture TAR SHA-256 | `f432b70835ea45d623fd6412a709228da2c2f89d98744b1e12d6467afac0e4ab` |
| fixture manifest SHA-256 | `46947670f1f8dc024d31b04860dbd3049f86f4fd53cb301f9e08ab04f0f586a5` |

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
- 三个 raw member 分别包含孤立 `ff`、overlong `c0 af` 和截断 `e2 82`；
- archive 末尾固定为两个零 block；
- 不含第三方样本字节，也不提交生成出的 TAR。

这样可以稳定表达 Windows Win32 路径 API 通常难以创建或保留的尾随空格、
newline 和 backslash 名称。版本化清单是
[`special-path-fixture.json`](data/special-path-fixture.json)；测试独立使用
Python `tarfile` 复验 member 顺序、名称和全部 payload。

fixture 共 21 个文件：

- 16 个位于 `paths/special/`；
- 1 个位于 `paths/目录 空格/`；
- `paths/nonutf8/` 包含 1 个 ASCII control 与 3 个原始非法 UTF-8 basename；
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

## 非 UTF-8 目录与显式 argv

探针在运行 `diec` 前，先在同一个只读 fixture/临时 `/work` 模型中调用
`os.listdir(b"...")`，得到四个 basename 的原始十六进制：

```text
61736369692d636f6e74726f6c2e706466
696e76616c69642d633061662dc0af2e706466
696e76616c69642d66662dff2e706466
7472756e63617465642d653238322de2822e706466
```

因此目录实验不是“非法文件没有成功解包”。但 `diec --json
/work/paths/nonutf8` 的 stdout SHA-256 为
`5a475aa450326d3096db01352fe524bbda579173a645f0f502a74bba27a32e35`，
恰好等于单独扫描 `ascii-control.pdf`：

- 只有一个 PDF root；
- 没有 filename prefix；
- 没有 U+FFFD；
- stderr 为空；
- exit `0`。

三个显式 raw argv 则均 exit `1`，输出一个 `Cannot find:`，不产生 PDF root。
对应 stdout SHA-256 和 replacement 数为：

| 原始非法序列 | U+FFFD 数 | stdout SHA-256 |
| --- | ---: | --- |
| `ff` | 1 | `58da8d8676a5e382e9093371147d1c2d8ec8416c57f152130d271f942eeb88e6` |
| `c0 af` | 2 | `860db1ea8c00651c30ed6696e489205298900c67b38f6a242056bc7a384c1ac3` |
| `e2 82` | 2 | `818700a7b873a54c3dbbdb28c2becc3e03244f9fad2a2334c3da0027f1906401` |

这证明固定上游 Linux CLI **不能无损扫描非 UTF-8 文件名**。Rust 核心若使用
`Path`/`OsStr` 可以安全支持这些输入，但 legacy-compatible CLI 必须把这种改进
视为明确的可观察偏离；canonical API/JSON 需要无损 byte 表示，不能先 lossy
转换再尝试打开路径。

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
均使用固定三层数据库路径；探针要求 23 个 case 的 exit/stdout/stderr 逐字节相同。

## 兼容与安全要求

- 路径模型必须能无损区分 NFC/NFD，并在 Unix 上避免强制 Unicode normalization。
- Rust `Path`/`OsStr` 层不得像固定 Qt CLI 一样过早 lossy 转换。非 UTF-8 输入的
  公共 API、JSON 表示和 C ABI 编码策略仍需在实现前冻结。
- CLI 原始兼容输出必须保留 filename prefix 中的控制字符；安全结构化输出应将
  路径作为字段正确转义。两者若不同，需用明确模式与差分测试区分。
- 目录枚举必须设置 symlink、depth、entry count、权限错误与取消策略；不能因上游
  缺少限制而继承无限递归风险。
- hidden 过滤、case ordering 与 platform-native separator 都是可观察行为，
  不得用本轮 Linux 结果替代跨平台 Oracle。

## 剩余缺口

- symlink、循环、权限错误、超深目录、超大目录及取消；
- NUL 不可能成为 POSIX basename；其他无效 byte 序列可按风险继续扩展，但首轮
  directory 与 explicit argv 行为已固定；
- locale 改变后的排序，以及不同 filesystem normalization/case 行为；
- Linux Qt6 的完整能力矩阵已由
  [`qt6-path-boundary-runtime-evidence.md`](qt6-path-boundary-runtime-evidence.md)
  重放；Windows/macOS 仍缺；
- Windows/macOS separator、绝对路径、reserved name、Unicode normalization、
  case sensitivity 与枚举顺序。

本页完成时 `CAP-GAP-003` 尚保持开放；后续
[`path-filesystem-behavior.md`](path-filesystem-behavior.md)、
[`large-directory-behavior.md`](large-directory-behavior.md)、
[`path-toctou-behavior.md`](path-toctou-behavior.md) 与
[`path-locale-filesystem-behavior.md`](path-locale-filesystem-behavior.md)
已闭合其余 Linux Qt5 子矩阵。`CAP-GAP-007` 和 `CAP-GAP-008` 仍保持开放，
不能把局部 Linux 证据提升为跨平台完成声明。
