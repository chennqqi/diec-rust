# Linux 路径枚举—打开 TOCTOU 行为

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 结论

固定 Linux x86_64 Qt5 qmake/CMake 两个 Oracle 对 4 个 case、共 8 次执行逐字节
一致，并证明发布 CLI 的目录展开与实际文件打开之间存在可控 TOCTOU：

- stable old 控制：`z-link.bin -> empty old.bin`，第二项 entropy 为
  `total=0/status=not packed`，保留一条 0-byte record；
- stable new 控制：`z-link.bin -> 4096-byte new.bin`，第二项 entropy 为
  `total=8/status=packed`；
- old → new：目录已完整枚举并开始扫描第一项后，原子替换 symlink inode/target；
  第二项结果与 stable new **逐字节相同**，而不再与 stable old 相同；
- 枚举后 unlink：第二项 logical prefix 仍打印 `/work/case/z-link.bin:`，随后得到
  `{"records":[],"status":"","total":0}`，exit 仍为 `0`、stderr 为空。

因此 `findFiles()` 保存的是 logical path string，不是已打开 handle 或枚举时 target
identity；后续 `EntropyProcess::processRegionsFile()` 会按当时 path 重新解析。
目标可在两阶段之间被替换或删除，上游既不复验 inode/type，也不把 missing-open
映射为 CLI 错误。

机器报告：
[`path-toctou-engine-qt5.json`](data/path-toctou-engine-qt5.json)，SHA-256 为
`733b136667c39f46e2d32bfb6a15c7da7077eee98232d7ff3a06a812f6913cf9`。

## 为什么同步点可信

固定 `ScanFiles()` 源码顺序为：

1. 遍历全部 positional target，`findFiles()` 把 absolute path 追加到完整
   `QList<QString>`；
2. 计算 `nNumberOfFiles = listFileNames.count()`；
3. 进入第二个循环，从 list 取 `sFileName`；
4. 多文件时先 `printf("%s:\n", logical_path)`；
5. entropy 分支才调用 `EntropyProcess::processRegionsFile(sFileName)`。

fixture 目录只有按 name 排序的：

```text
/work/case/a-blocker.bin
/work/case/z-link.bin -> ../targets/old.bin|new.bin
```

probe 用固定 `/usr/bin/stdbuf -oL` 只改变 C stdout buffering，不修改参数或扫描
分支。父 wrapper 收到精确第一行 `/work/case/a-blocker.bin:` 后：

1. 向同一 `diec` PID 发送 `SIGSTOP`；
2. `waitpid(WUNTRACED)` 验证进程已由 signal 19 停止；
3. stable case 不修改；swap case 用 `os.replace()` 原子替换 symlink；
   unlink case 删除 symlink；
4. 记录 mutation 前后 link/target device、inode、mode、size 和 `readlink()`；
5. 发送 `SIGCONT`，等待原进程完成。

32 MiB sparse-zero blocker 让父进程有明确的第一项扫描窗口；更关键的是 old → new
最终结果与 new 控制逐字节相同，直接证明第二项尚未按 old target 打开。该实验不
依赖任意 sleep。

## 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| 平台 | `linux-x86_64-qt5` |
| qmake image | `sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab` |
| CMake image | `sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040` |
| qmake binary | `721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d` |
| CMake binary | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| fixture manifest | `aeb693989cf55e2a45209567fc7be03283139299c3dfe563cba86ad4f0e9fd55` |
| `/usr/bin/stdbuf` | `1fd37836e4a9060756fcec760b0b0f482621aad3fe13af39591a8c14b118eb5d` |
| `Formats/xbinary.cpp` | `d82bd21326bb7ba07eb343020d50af0ae2cf7e8e534d8e08d07ffa8129913c34` |
| `main_console.cpp` | `ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f` |

报告为关键源码 pattern 保存 occurrence count 与 1-based line number，包含：

```text
pListFileNames->append(fi.absoluteFilePath())
XBinary::findFiles(sFileName, &listFileNames)
nNumberOfFiles = listFileNames.count()
sFileName = listFileNames.at(i)
printf(logical path prefix)
EntropyProcess::processRegionsFile(sFileName)
```

qmake/CMake image 中 source 与 `stdbuf` bytes 必须相同，否则 probe 失败。

## 确定性 fixture

[`generate_path_toctou_fixture.py`](../../tools/corpus/generate_path_toctou_fixture.py)
生成
[`path-toctou-fixture.json`](data/path-toctou-fixture.json)，不提交 materialized
32 MiB 文件。每个 case 在全新 tmpfs 中创建：

| Path | 内容 |
| --- | --- |
| `/work/case/a-blocker.bin` | 32 MiB sparse zero，SHA-256 `83ee4724…c4302` |
| `/work/targets/old.bin` | 0 byte，SHA-256 `e3b0c442…b855` |
| `/work/targets/new.bin` | `bytes(0..255)` × 16，4096 bytes，SHA-256 `c8f5d034…f193` |
| `/work/case/z-link.bin` | 相对 symlink，初始指向 old 或 new |

wrapper 在启动 Oracle 前分块重算 blocker/old/new 的 size/SHA-256；fixture manifest
固定 action、初始 target、预期 open target 和完整同步协议。

## 精确结果

| Case | Action | Link result | stdout SHA-256 |
| --- | --- | --- | --- |
| `stable_old` | none | `total=0`, `not packed`, 1 record | `d2bdb2d9ad473838d3529143c33278ab5d09991f9c0b7755b3bf092f128f2d4c` |
| `stable_new` | none | `total=8`, `packed`, 1 record | `49f59670345f16c63d0d1143e8fd219a1081659da30c5e8d7150ca260a2b4f57` |
| `swap_old_to_new` | atomic symlink replace | 与 stable new 相同 | `49f59670345f16c63d0d1143e8fd219a1081659da30c5e8d7150ca260a2b4f57` |
| `remove_old_after_enumeration` | unlink | empty status, 0 records | `31dfa241dfb8647d9949db4fe2a405e864c1c298184da4254b4572fa03e948f0` |

每个 stdout 都包含两个固定 prefix。probe 分割并严格解析两个 JSON document：

- blocker 必须报告一条 size `33554432`、entropy `0` 的 `not packed` record；
- old 必须报告 size `0` record；
- new 必须报告 size `4096`、entropy `8` record；
- missing-open 必须报告空 `records` 和空 `status`。

swap case 中，每次 Oracle 的 link inode 与 resolved target inode 在 mutation 前后
都不同；stable control 前后 identity 完全相同；unlink 后三项 identity 均为 null。

## 受限执行

每个 case/Oracle 使用全新 container：

```text
network=none
cpus=1
memory=512 MiB
pids=128
root filesystem=read-only
work tmpfs=64 MiB
core size=0
child timeout=30 seconds
host safety timeout=60 seconds
```

stdout/stderr 以 `zlib+base64` 从 wrapper 返回，再按原始 SHA-256 content address
保存。qmake/CMake 的 exit/stdout/stderr 必须逐字节一致。resource usage 只作为
本次运行身份记录，不用于性能结论。

复现：

```powershell
python tools\corpus\generate_path_toctou_fixture.py `
  --output docs\research\data\path-toctou-fixture.json
python tools\upstream\probe_path_toctou_behavior.py `
  --output docs\research\data\path-toctou-engine-qt5.json
```

## 兼容与安全含义

- legacy raw profile 在对应 case 中应保留 logical symlink prefix、old → new
  当前目标结果，以及 unlink 后 exit `0`/空 error shape。
- modern `SafeCanonical` 不能只在枚举时 `stat()` 后按字符串 reopen；这仍有相同
  race。它需要 directory-handle-relative open，并在打开后复验 root confinement、
  file type 与 stable identity。
- 检测到 identity/type/parent 改变时，应返回 ADR 0014 的
  `ChangedDuringTraversal`；不能扫描替换目标后仍把结果归因于枚举时对象。
- legacy hardening 与上游 raw exact 的差异属于 `SafetyDeviation`，必须绑定
  [`ADR 0014`](../design/decisions/0014-bounded-path-expansion.md) 和 ADR 0004
  精确 waiver，normalizer 不得隐藏。
- unlink case 说明 entropy CLI 把 missing-open 映射为空成功文档；canonical API
  必须用 typed diagnostic 与真实 empty file 区分。

## 剩余缺口

- 固定镜像 locale 与 tmpfs/volume ordering 已由后续
  [`path-locale-filesystem-behavior.md`](path-locale-filesystem-behavior.md)
  覆盖；其他 Linux filesystem 实现不从该代表性矩阵外推；
- Windows symlink/junction/reparse point 的 handle-relative open；
- macOS case-sensitive/case-insensitive volume 与 normalization；
- Rust `TargetExpander` production implementation 的 rename/link/target-swap
  adversarial system tests。

本页闭合原 `CAP-GAP-003` 的 Linux 枚举—打开 TOCTOU 子矩阵；后续
locale/filesystem 实验闭合最后一个固定 Linux Qt5 子矩阵。
`CAP-GAP-007`/`CAP-GAP-008` 的平台缺口不变，不能把本结论外推到 Windows
或 macOS。
