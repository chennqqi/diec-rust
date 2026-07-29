# Windows Qt5 路径闭环行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 范围与身份

本实验关闭 `CAP-CLI-IN-003` 在 Windows Qt5 上剩余的目录规模、reparse、
TOCTOU、UNC 和访问拒绝边界。机器报告为
[`data/windows-path-closure-qt5.json`](data/windows-path-closure-qt5.json)，
SHA-256 为
`a88f64018bada18f4104278e5f79323009fce79916c64a5a061ed3864cbf3dd1`。
夹具清单为
[`data/windows-path-closure-fixture.json`](data/windows-path-closure-fixture.json)，
采集器与生成器分别为
[`collect_windows_path_closure.py`](../../tools/upstream/collect_windows_path_closure.py)
和
[`generate_windows_path_closure_fixture.py`](../../tools/corpus/generate_windows_path_closure_fixture.py)。

实验固定：

- 上游 commit `74eaf505c250ab47e709024e9dc41657cd8f2254`；
- 规则 commit `c2c17dfa5ea4e078ba31eab55d87430c96622fb6`；
- Windows Qt5 `diec.exe` SHA-256
  `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e`；
- 23 个 case、每个两轮，共 46 次进程执行和 46 个 observation；
- 21 条命名关系全部成立，语义失败与关系失败均为 0。

## 2. 观察结果

### 2.1 大目录与顺序

`empty_0`、`single_1`、`flat_256`、`flat_4096` 和 `nested_4096` 五个
case 均完整结束。两个 4096-case 都输出 4096 个文档；相对路径保持完整、
升序且两轮一致，没有截断、去重或资源超时。

### 2.2 Reparse 边界

- 显式 dangling Junction 与 dangling parent 均退出 0，stdout/stderr 为空；
- two-node Junction cycle 不超时，输出 64 个相同最小 PDF 文档；
- cycle 不做 identity 去重，达到的最大相对前缀长度为 328 个 UTF-16 code
  unit，完整输出哈希在两轮间稳定。

该 64 层是本固定 Windows/Qt/文件系统组合的可观察结果，不应解释成 DIE-engine
自有递归预算。

### 2.3 同步 TOCTOU

采集器先让 128 个 1 MiB blocker 被枚举，并以 stdout 达到 4096 bytes 作为
可审计同步点，再替换或移除排在末尾的 Junction：

- stable-old 打开 0-byte 目标；
- stable-new 打开 4096-byte、entropy 8 的目标；
- old→new 在枚举后替换时打开新目标；
- 枚举后删除 Junction 时保留前 129 个冻结文档，并为末项产生 missing-result
  shape。

因此目录项列表先被冻结，实际内容仍按随后打开时的路径解析。

### 2.4 UNC 与扩展 UNC

实验使用已安装的 WSL `Ubuntu` UNC redirector，不创建或修改 SMB machine
share：

- `\\wsl.localhost\Ubuntu\...` 的普通文件和目录成功，检测结果与本地最小
  PDF 相同；
- 对应 `\\?\UNC\wsl.localhost\Ubuntu\...` 文件和目录均以固定
  `CR_CANNOTFINDFILE=1` 拒绝；
- 不存在的 UNC 路径退出 1；
- redirector 上 mode-denied 文件/目录不暴露 PDF；混合目录仍保留可见 PDF。

### 2.5 本地 NTFS DACL

对当前 SID 施加显式 deny 后，文件和目录均不可扫描；包含被拒绝 child 的混合
父目录仍返回可见 PDF。采集器在 `finally` 路径恢复 DACL，并在报告生成前验证
文件重新可读。

Active Directory 身份不是上游源码中的独立分支。固定源码只经
`QFileInfo`/`QDir` 枚举，再按冻结 path 打开；因此本实验用本地 NTFS DACL 和
WSL redirector 权限覆盖“本地拒绝”和“网络提供者拒绝”两种可观察行为，不把
未加入域的主机伪装成 domain profile。

## 3. 源码约束

报告绑定：

- `src/console/main_console.cpp` SHA-256
  `ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f`；
- `Formats/xbinary.cpp` SHA-256
  `d82bd21326bb7ba07eb343020d50af0ae2cf7e8e534d8e08d07ffa8129913c34`。

源码路径证明 CLI 使用 `QFileInfo`/`QDir` 递归形成文件列表，再逐项交给扫描
路径；没有 ACL、域、reparse 或 UNC 专用分支。运行证据决定具体 Windows
行为，源码证据只限定可合理区分的行为分支。

## 4. 可重复采集

先生成并校验夹具清单：

```text
python tools/corpus/generate_windows_path_closure_fixture.py --check
```

在具备 NTFS Junction 权限、`icacls` 和 WSL UNC redirector 的 Windows 主机上：

```text
python tools/upstream/collect_windows_path_closure.py ^
  --binary <fixed-diec.exe> ^
  --source-dir <clean-fixed-upstream> ^
  --qt-dir <Qt-5.15.2-msvc2019_64> ^
  --baseline-fixture-dir <generated-windows-corpus> ^
  --work-dir <empty-work-dir> ^
  --raw-dir <work-dir>\raw ^
  --wsl-distro Ubuntu ^
  --repetitions 2 ^
  --output docs/research/data/windows-path-closure-qt5.json
```

原始 stdout/stderr 共 92 个 stream，保留在外部隔离证据目录；仓库只提交
去本机路径、账号和 SID 的结构化报告。采集器拒绝非空/越界 raw 目录，清理 WSL
fixture 和 Junction cycle，并恢复 DACL。

验证：

```text
python -m unittest discover -s tools\tests -p "test_*windows_path_closure*.py"
python tools/research/build_windows_closure_plan.py --check
```

## 5. 结论与限制

本证据与既有 Unicode、特殊名、Junction alias/chain、ADS 和 324/325-code-unit
路径证据合并后，`CAP-CLI-IN-003` 在固定 Windows Qt5 oracle 上达到
`evidence_complete`。这允许 Windows 68 行 closure 达到 68/0/0。

结论不外推到 macOS、其他 Qt/Windows 版本、其他 UNC provider、EFS、integrity
level 或真实资源耗尽。未观察 profile 若将来形成新的可达行为分支，应作为能力
扩展重新进入固定实验，而不能由本报告推断。
