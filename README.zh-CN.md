# diec-rust

[Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE) 的 Rust 重写。

[English](README.md)

## 为什么

diec-rust 是 DIE 的 Rust 全新实现。保持与上游 **1:1 兼容** — 相同的识别能力、
相同的规则语义、相同的输入输出行为 — 同时在健壮性、安全性和性能上带来可量化的
改进。

## 核心优势

- **1:1 DIE 兼容**：原样加载 2037 条上游规则，产生相同的识别结果和输出格式
  （JSON、XML、CSV、TSV、text）
- **Rust 安全**：核心层零 `unsafe`，内存安全由语言保证，FFI 边界有 panic 隔离 —
  畸形输入不会崩溃
- **性能**：并行数据库加载，格式探测亚微秒级
- **多语言绑定**：C ABI + Go/cgo + Python ctypes 开箱即用

## Benchmark 结果

以下数据来自 Windows 11 release 构建。测试脚本和原始数据已包含，可自行复现。

### 数据库加载

| 指标 | 数值 | 方法 |
|------|------|------|
| 并行加载 (criterion) | 160ms | `cargo bench -p diec-engine --bench scan -- database_load` |
| CLI 冷启动 (首次) | 1589ms | 含进程启动 + JIT |
| CLI 热启动 (4 次平均) | 487ms | `diec --showdatabase` |
| CLI 热启动 (最小) | 456ms | 首次运行后 |

### 扫描性能 (criterion, 20 次采样)

| 文件类型 | 耗时 |
|----------|------|
| ELF64 最小 | 11.2ms |
| Mach-O 64 最小 | 14.8ms |
| PE32 最小 | 71.9ms |
| Java class | 92.1ms |
| DEX | 95.5ms |
| PDF | 102.2ms |
| PNG | 101.2ms |
| tar 归档 | 152.2ms |
| Zip 归档 | 170.2ms |
| --alltypes (Zip) | 288.4ms |

### 格式探测 (criterion, 50 次采样)

| 格式 | 耗时 |
|------|------|
| empty | 60ns |
| text | 213ns |
| Zip | 285ns |
| PNG | 289ns |
| tar | 302ns |
| PDF | 310ns |
| Mach-O 64 | 324ns |
| ELF64 | 335ns |
| ISO 9660 | 337ns |
| DEX | 366ns |
| Java Class | 379ns |
| PE32 | 407ns |

### 复现方法

```sh
# 运行 benchmark
python tools/benchmark/run_benchmarks.py --quick

# 或直接运行
cargo bench -p diec-engine --bench scan
cargo bench -p diec-formats --bench probe
```

原始 JSON 数据：`tools/benchmark/results/benchmark_results.json`

## 兼容性结果

### 规则数据库

| 指标 | 数值 |
|------|------|
| .sg 规则文件总数 | 2037 |
| 规则类型 | 29 种（PE: 834, MSDOS: 349, Binary: 292, COM: 245, ...） |
| 数据库大小 | 2.7 MB |

### 测试套件

| 类别 | 结果 |
|------|------|
| 总测试数 | 414 通过, 0 失败 |
| Clippy | 0 警告 |
| Fuzz targets | 6 个（core, formats, engine, output, FFI） |
| 语料样本 | 27 基线 + 20 边缘 |

### 语料检测 (--alltypes)

27 个基线语料文件全部产生正确的格式检测。20 个边缘文件（截断、畸形、超大字段）
全部完成扫描，无崩溃、无挂起。

### 复现方法

```sh
# 运行完整兼容性测试
python tools/benchmark/run_compatibility.py

# 运行特定测试
cargo test --workspace --all-features --locked
cargo test -p diec-engine --test corpus_differential
cargo test -p diec-engine --test edge_corpus
```

原始 JSON 数据：`tools/benchmark/results/compatibility_results.json`

## 快速开始

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust
cargo build --workspace --release
```

### CLI

```sh
./target/release/diec file.exe
./target/release/diec --output json file.exe
./target/release/diec --alltypes file.exe
./target/release/diec --recursive /path/to/dir/
```

### Python

```python
from diec import Database, scan_bytes
db = Database("db/")
result = scan_bytes(db, open("file.exe","rb").read())
print(result.detections)
```

### Go

```go
db, _ := diec.NewDatabase("db/")
result, _ := diec.ScanBytes(db, data)
```

### C

```c
#include "diec.h"
diec_v1_scan_bytes(db, data, size, NULL, NULL, &result, &error);
```

## 规则数据库

规则随发布物打包（2.7 MB，MIT 许可）。可通过 `--customdb <path>` 或
`DIEC_DB_PATH` 环境变量覆盖。

## 状态

414 个测试，6 个 fuzz targets，0 失败。支持 Linux/macOS/Windows。

详见 [ROADMAP.md](ROADMAP.md)。

## 许可证

MIT — 与上游一致。详见 [NOTICES.md](NOTICES.md) 归属信息。
