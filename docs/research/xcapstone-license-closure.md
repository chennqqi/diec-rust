# XCapstone/Capstone 最终 ELF 贡献与许可证闭包

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 范围与结论

本报告使用固定 Linux Qt5 CMake Release 构建树，区分三个不同集合：

1. `capstone_x86` static archive 中构建了哪些 member；
2. 链接器实际从 archive 抽取了哪些 member 进入最终 `diec` ELF；
3. 这些最终贡献单元经 `.o.d` 展开的 XCapstone 内部源码/头文件闭包。

机器报告为
[`data/xcapstone-license-closure-linux.json`](data/xcapstone-license-closure-linux.json)，
生成器为
[`audit_xcapstone_license_closure.py`](../../tools/upstream/audit_xcapstone_license_closure.py)。
固定 XCapstone commit 为
`96c639939478998b81d2e662a027a00f3054cbfe`。

最终结果：

- `xcapstone.cpp.o` 作为一个 direct object 进入 link line；
- `libcapstone_x86.a` 含 11 个 member，但只有 10 个在最终非 stripped ELF 中
  具有全局符号见证；
- `MCInstrDesc.c.o` 是唯一没有最终 ELF 符号见证的 member，因此不计入最终
  binary contribution closure；
- 最终贡献为 11 个 compile source：1 个 MIT wrapper + 10 个 Capstone C
  source；
- 对这 11 个单元展开并归一化 `.o.d` 后，共 71 个唯一 XCapstone 文件；
- 71 个文件中，67 个含 Capstone 来源标记、11 个含 LLVM University of
  Illinois/NCSA 归属、2 个含 MIT permission text。

这关闭了“Capstone archive 在 link line，所以 11 个 member 都必然进入最终
产物”的过度推断。static archive member 是否贡献必须由最终产物证据判断。

## 2. 链接与 member 见证

固定 link line 同时包含：

```text
CMakeFiles/diec.dir/__/__/XCapstone/xcapstone.cpp.o
../XCapstone_86/libcapstone_x86.a
```

生成器对 archive 每个 member 执行 `nm -g --defined-only`，再与最终
`src/console/diec` 的全局定义符号求交。10 个被抽取 member 均至少有一个见证：

| Member | 示例最终 ELF 符号 |
| --- | --- |
| `MCInst.c.o` | `MCInst_Init` |
| `MCRegisterInfo.c.o` | `MCRegisterClass_contains` |
| `SStream.c.o` | `SStream_Init` |
| `X86Disassembler.c.o` | `X86_getInstruction` |
| `X86DisassemblerDecoder.c.o` | `decodeInstruction` |
| `X86IntelInstPrinter.c.o` | `X86_Intel_printInst` |
| `X86Mapping.c.o` | `X86_get_insn_id` |
| `X86Module.c.o` | `X86_global_init` |
| `cs.c.o` | `cs_close` |
| `utils.c.o` | `arr_exist` |

`MCInstrDesc.c.o` 定义的两个全局符号没有出现在最终 ELF，因此记录为
unextracted。符号交集证明的是这个固定、未 strip ELF 的 member contribution，
不证明每条机器指令在扫描路径上都可达。

## 3. 文件级许可证证据

编译依赖本身不包含许可证文件；因此报告把 compiler dependency closure 与必须
保留的许可证文本分开记录：

| 文件 | SHA-256 | 技术分类 |
| --- | --- | --- |
| `LICENSE` | `abdeb212f229d2b93a5c315763df4d7201c7d74f580ad9dc77d77dec7cbc6c69` | XCapstone wrapper MIT |
| `3rdparty/Capstone/src/LICENSE.TXT` | `404bd0cb0137ffb797258f844f53e5273f9b6d5781a1a359a2880411f49a4f30` | Capstone BSD-3-Clause |
| `3rdparty/Capstone/src/LICENSE_LLVM.TXT` | `d4cc2005623614495b43508021c85d1d2ff21d8766287605ac41fee47f499bf9` | LLVM University of Illinois/NCSA |

MIT marker 只出现在 `xcapstone.cpp` 和 `xcapstone.h`。LLVM/NCSA 来源标记出现
在 11 个最终闭包文件，包括 `MCRegisterInfo.c`、X86 disassembler/decoder/
printer 及相应 headers。Capstone BSD 条款没有逐文件嵌入 71-file 编译闭包，
只能由 `LICENSE.TXT` 提供。

因此若分发含该实现的 binary，技术清单必须至少保留：

- XCapstone 根 MIT 文本；
- Capstone BSD copyright、conditions 与 disclaimer；
- LLVM University of Illinois/NCSA copyright、conditions 与 disclaimers。

这只是按固定字节和构建贡献得到的 NOTICE 输入，不是法律意见或最终发布批准。

## 4. 方法与复现

生成器校验固定 image revision、主仓库/XCapstone commit、component lock 和
link token；容器禁网，仓库只读挂载：

```powershell
python tools/upstream/audit_xcapstone_license_closure.py `
  --output docs/research/data/xcapstone-license-closure-linux.json
```

随后：

1. 展开 `libcapstone_x86.a` 的 11 个 member；
2. 用最终 ELF 全局符号见证判断 10 个实际抽取 member；
3. 只对 direct object 与 10 个实际贡献 member 解析 `.o.d`；
4. `resolve()` 归一化 `x86/../` 和 `arch/X86/../../` alias，避免同一文件重复；
5. 对 71 个文件保存相对路径、长度、SHA-256 和保守文本 marker；
6. 单独保存三份许可证文本的路径、长度、SHA-256 和 marker。

验证：

```text
python -m unittest discover -s tools\tests \
  -p "test_xcapstone_license_closure.py"
```

测试绑定 generator、component lock、image revision、member/符号/文件计数、
三份许可证 hash，并拒绝容器或本机绝对路径进入报告。

## 5. 限制与 Rust 约束

- 当前只覆盖固定 Linux Qt5 CMake Release `diec`；qmake、Qt6、Windows、
  macOS 和 static-library 最终组合仍需分别核对。
- `nm` 见证依赖最终 ELF 未 strip；若构建参数变化，必须重新生成，不得复用
  10/11 结论。
- 本项目不应机械翻译或复制 XCapstone wrapper/Capstone 源码；优先选择许可证
  清晰、可独立审计的 Rust/native backend。
- 替换 backend 不改变行为兼容要求：x86 decode、instruction formatting 和错误
  边界仍须与固定 oracle 差分。
- 最终 Rust dependency graph、static `.a`/`.lib` 和发布包必须重新生成自己的
  SBOM/NOTICE；本报告只提供上游兼容 oracle 的来源边界。
