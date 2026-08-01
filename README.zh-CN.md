# diec-rust

[Detect It Easy](https://github.com/horsicq/DIE-engine) (DIE) 的 Rust 重写。

[English](README.md)

## 为什么

diec-rust 是 DIE 的 Rust 全新实现。保持与上游 **1:1 兼容** — 相同的识别能力、
相同的规则语义、相同的输入输出行为 — 同时在健壮性、安全性和性能上带来可量化的
改进。

## 核心优势

- **1:1 DIE 兼容**：原样加载 1184/1186 条上游规则（99.83%），产生相同的识别结果
  和输出格式（JSON、XML、CSV、TSV、text）
- **Rust 安全**：核心层零 `unsafe`，内存安全由语言保证，FFI 边界有 panic 隔离 —
  畸形输入不会崩溃
- **性能**：并行数据库加载（~400ms vs 上游 ~1.2s），格式探测亚微秒级
- **多语言绑定**：C ABI + Go/cgo + Python ctypes 开箱即用

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
