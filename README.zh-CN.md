# diec-rust

[Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE) 的 Rust 重写。

[English](README.md)

## 为什么

与上游 DIE 1:1 兼容 — 相同的识别能力、相同的规则语义、相同的输出格式 —
加上 Rust 的内存安全和多语言绑定。

## 核心优势

- **1:1 DIE 兼容**：原样加载 2037 条上游规则，相同的识别结果和输出
  （JSON/XML/CSV/TSV/text）
- **Rust 安全**：核心层零 `unsafe`，FFI 边界 panic 隔离，畸形输入不崩溃
- **性能**：并行数据库加载（比顺序加载快 3 倍），格式探测亚微秒级
- **多语言绑定**：C ABI + Go/cgo + Python ctypes

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

**414 个测试通过**，2037 条规则加载，27 个基线 + 20 个边缘语料验证 —
无崩溃、无误检、无挂起。

测试方法和原始数据：[tools/benchmark/](tools/benchmark/) ·
[compatibility_results.json](tools/benchmark/results/compatibility_results.json)

复现：
```sh
python tools/benchmark/run_compatibility.py
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
