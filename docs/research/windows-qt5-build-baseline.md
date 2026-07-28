# 上游 Windows Qt5 CLI 构建基线

Status: Draft  
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`  
Last updated: 2026-07-29

## 结论

固定上游及其 58 个递归 submodule 可以在 Windows x64、MSVC 2019、Qt
5.15.2 环境中，从 tracked-clean 检出通过 qmake/jom 构建 `diec 4.0.0`。
构建产物成功加载固定
`Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6` 规则，并对项目
生成的最小 PE64 返回稳定 JSON 和退出码 `0`。

本仓库用
[`build_windows_qt5_oracle.ps1`](../../tools/upstream/build_windows_qt5_oracle.ps1)
固定源码、规则、Qt 二进制身份和构建目标。它产生的是 **Windows Qt5 qmake CLI
候选 oracle**，不是固定上游官方 workflow 的发布包。Windows 的 68 项能力仍
保持 `platform_missing`，直到完整差分语料在该平台执行并归档。

机器证据见
[`data/windows-qt5-build-baseline.json`](data/windows-qt5-build-baseline.json)。

## 固定环境

| 输入 | 观测值 |
| --- | --- |
| Host | Windows build `26100`, x86_64 |
| Visual Studio | 2019 Build Tools `16.11.47` |
| MSVC compiler | `19.29.30159.0` |
| MSVC tools | `14.29.30133` |
| Qt | `5.15.2`, `win64_msvc2019_64`, module `qtscript` |
| qmake | spec `win32-msvc` |
| jom | `1.1.4`, SHA-256 `93eb6b9d…365cc2e8` |

Qt 使用 `aqtinstall 3.3.0` 安装，且没有关闭 aqt 的 archive hash 校验：

```powershell
python -m aqt install-qt windows desktop 5.15.2 win64_msvc2019_64 `
  -O <qt-root> --modules qtscript --timeout 30
```

构建脚本进一步校验安装后的关键文件：

| 文件 | SHA-256 |
| --- | --- |
| `bin/qmake.exe` | `e873ad3a689a0628c3037a6440221dcd2e426395edf14ffa6379612dede26d36` |
| `bin/Qt5Core.dll` | `8d2ff4ce9096ddccc4f4cd62c2e41fc854cfd1b0d6e8d296645a7f5fd4ae565a` |
| `bin/Qt5Script.dll` | `0b58e5e79df13110a8258f14d7b3658d1dd0c8dddc337a164b89d4ac12a0638f` |

## 官方 Windows workflow 的两个断点

固定 commit 的 x64 workflow 在
`.github/workflows/builder.yml:219-249` 安装 MSVC x64、Qt 5.15.2
`win64_msvc2019_64` 和 `qtscript`，然后设置 `QMAKE_PATH` 并调用
`build_win_generic_check.cmd`。

### 环境变量契约漂移

workflow 在第 239 行设置 `QMAKE_PATH`，但被调用脚本没有使用 qmake：
`build_win_generic_check.cmd:7-16` 使用 CMake/NMake，并只读取
`QT_PREFIX_PATH`。workflow 没有设置后者。因此不能只凭 workflow 文件宣称固定
commit 的 Windows job 可重放。

### CMake xsimd 架构探测

即使手工传入正确的 Qt prefix，CMake `4.0.1` + NMake 的实际配置仍显示：

```text
CMAKE_SYSTEM_PROCESSOR=
CMAKE_C_COMPILER_ARCHITECTURE_ID=x64
```

`Formats/xsimd/CMakeLists.txt:15-18` 只用空的
`CMAKE_SYSTEM_PROCESSOR` 判断 x86，因而没有生成
`xsimd_sse2` 和 `xsimd_avx2`。主 `xsimd` 仍编译并引用 SIMD 函数，最终
`diec` 链接产生 46 个 `LNK2019` 和一个 `LNK1120`。增量重现返回退出码 `2`；
外部原始日志 SHA-256 为
`c7757f813abdfe57b7727f8e8003735024748ab4334458589c0a0fcff683e9e5`。

命令行传入 `-DCMAKE_SYSTEM_PROCESSOR=AMD64` 后，平台初始化仍将变量恢复为空，
所以它不是可靠 workaround。修复官方 CMake 路径需要单独验证 toolchain/platform
设置或上游源码修复；本基线没有修改上游源码来掩盖该缺陷。

## qmake 构建路径

上游 qmake 工程对 SIMD 有显式顺序：

- `Formats/xsimd/xsimd.pro` 先列出 `xsimd_sse2`、`xsimd_avx2`，再列出
  `xsimd`；
- `xsimd.depends = xsimd_sse2 xsimd_avx2`；
- 主 xsimd 工程显式链接两个 MSVC `.lib`。

从完整、tracked-clean 的递归检出运行：

```powershell
tools\upstream\build_windows_qt5_oracle.ps1 `
  -SourceDir <recursive-die-source> `
  -QtDir <qt-root>\5.15.2\msvc2019_64 `
  -VsDevCmd "<vs2019>\VC\Auxiliary\Build\vcvars64.bat" `
  -BuildDir <external-build-dir> `
  -JomPath <qt-tools>\jom.exe `
  -Jobs 4 `
  -OutputJson <external-build-dir>\identity.json
```

脚本在构建前拒绝：

- 非固定 DIE-engine/rules commit；
- 不是恰好 58 个 clean recursive submodule；
- 主仓库或任一 submodule 的 tracked 修改；
- Qt 版本、qmake spec 或三个关键 Qt 文件 hash 不匹配。

随后依次构建 `sub-build_libs-release` 和
`sub-console_source-release`。qmake 会在 submodule 中生成未跟踪 `libs/`，
并在主源码树生成未跟踪 `build/`；这些是构建产物，不应提交。一次完整 clean
build 使用 jom 4 workers 耗时 `287,880 ms`。

## 产物与运行检查

clean build 产物：

| 属性 | 观测值 |
| --- | --- |
| Path | `<source>/build/release/diec.exe` |
| Version | `die 4.0.0` |
| Size | `3,236,352` bytes |
| SHA-256 | `e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e` |

`dumpbin /dependents` 显示直接依赖为 Qt5Script、Qt5Core、MSVC/Universal CRT 和
Kernel32。archive、Capstone 和 xsimd 等上游依赖以静态 `.lib` 进入 CLI；Qt 与
MSVC runtime 仍是动态依赖。

项目生成语料 `minimal-pe64.exe` 的 SHA-256 为
`63c706607b3d34624313df7356702ff99ce4080f09e6b07ec4b01dfe4dd5e1c3`。
使用固定主规则目录执行 `-j -D <db> <sample>` 得到：

```text
exit code:    0
stdout bytes: 489
stdout SHA:   12362e46500734dd6400230460718e7e100fddb39d069b9249d4d765034455c0
stderr bytes: 0
```

结构化投影为 `PE64`、offset `0`、size `512`、parent part `Header`，唯一值为
`Unknown: Unknown`。初步构建和后续 clean-script 构建的原始 stdout/stderr
hash 相同。

## 可重复性边界

当前证据证明“从一次独立 clean recursive checkout 可重复构建并运行”，不证明
bit-for-bit reproducible：

- 位于不同绝对路径的初步产物大小相同、行为输出相同，但可执行文件及静态库
  SHA-256 不同；
- 初步源树此前经过一次 CMake configure，因此两次产物不是严格同输入实验；
- MSVC archive/PE 时间戳、绝对路径和其他非确定输入尚未逐项隔离；
- 只完成 help/version 和一个 PE64 JSON smoke，尚未运行 68 项 Windows 差分；
- 尚未验证 x86、ARM64、完整 GUI/lite、install/package 和官方 release zip；
- `cl` 对 x64 的 `/arch:SSE2` 给出 D9002 ignored warning；x64 ABI 本身要求
  SSE2，但该 warning 仍应保留在构建日志中。

下一步先让 Windows oracle 接入现有 corpus/differential harness，按能力矩阵保存
原始与规范化输出；然后独立处理官方 CMake 路径和二进制确定性。macOS 固定构建
仍是三平台基线的剩余大项。

## 上游证据

- [Windows x64 workflow](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/.github/workflows/builder.yml#L219-L249)
- [`build_win_generic_check.cmd`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_win_generic_check.cmd)
- [`die_source.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/die_source.pro)
- [`build_libs.pro`](https://github.com/horsicq/DIE-engine/blob/74eaf505c250ab47e709024e9dc41657cd8f2254/build_libs/build_libs.pro)
- [`Formats/xsimd/CMakeLists.txt`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/CMakeLists.txt)
- [`Formats/xsimd/xsimd.pro`](https://github.com/horsicq/Formats/blob/1151e7254fdee3c0294ff7095edbdd7bfccf8201/xsimd.pro)
