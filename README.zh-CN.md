# diec-rust

[Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE) 的 Rust 重写。

[English](README.md)

> **⚠️ 开发中 — 不建议用于生产环境**
>
> 本项目仍在积极开发中。检测覆盖率、API 稳定性和输出格式可能在提交间
> 发生变化。部分依赖反汇编（Capstone）的 PE 保护器/打包器规则尚未支持。
> 请勿在生产环境中使用。

## 为什么

目标是与上游 DIE 兼容 — 相同的检测能力、相同的规则语义、相同的输出格式 —
加上 Rust 的内存安全和多语言绑定。

## 核心优势

- **DIE 兼容**：通过 rquickjs 运行时原样加载上游规则；PE/ELF/MACH host API
  桥接实现了最常用的方法
- **Rust 安全**：核心层零 `unsafe`，FFI 边界 panic 隔离，畸形输入不崩溃
- **性能**：并行数据库加载（比顺序加载快 3 倍），格式探测亚微秒级
- **多语言绑定**：C ABI + Go/cgo + Python ctypes

## 已知限制

- `getDisasmString` 返回空字符串（未集成 Capstone）；依赖反汇编的保护器规则
  （PELock、Arxan、VMProtect、GenericHeuristicAnalysis）会漏检测
- 部分检测名称/版本号与上游有差异（submodule 规则版本与上游 3.21 自带规则版本不同）
- `format` 类型检测在某些情况下可能产生重复条目

## Benchmark

数据库加载：**160ms**（并行）vs **480ms**（优化前顺序）— **3 倍提升**。
格式探测：**60-407ns** 每文件。

测试方法和原始数据：[tools/benchmark/](tools/benchmark/) ·
[benchmark_results.json](tools/benchmark/results/benchmark_results.json)

复现：
```sh
python tools/benchmark/run_benchmarks.py --quick
```

## 兼容性

**454 个测试通过**，上游规则加载，28 个基线 + 20 个边缘语料验证 —
无崩溃、无误检、无挂起。

与上游 DIE 3.21 差分测试：
- diec.exe 自身检测：**5/5 完全匹配**（linker、compiler、tool、debug data、C/C++ runtime）
- 6 个大型系统 DLL（0.5-61MB）：**6/6 完全匹配**
- 28 文件语料：17/28 匹配（剩余差异为规则版本差异和 format 类型去重行为差异）

测试方法和原始数据：[tools/benchmark/](tools/benchmark/) ·
[compatibility_results.json](tools/benchmark/results/compatibility_results.json)

复现：
```sh
python tools/benchmark/run_compatibility.py
python tools/compat/compare_upstream.py
```

## 快速开始

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust && cargo build --workspace --release
./target/release/diec --alltypes file.exe
```

Python / Go / C 绑定：见 [README.md](README.md) 或 [bindings/](bindings/)。

## 许可证

MIT — 与上游一致。详见 [NOTICES.md](NOTICES.md)。
