# diec-rust

使用 Rust 重新实现 [horsicq/DIE-engine](https://github.com/horsicq/DIE-engine) — Detect It Easy。

[English](README.md)

## 概述

diec-rust 是 Detect It Easy 文件识别引擎的 Rust 全新实现。在保持与固定上游版本的
检测能力和规则语义兼容的前提下，改善架构、代码质量、性能、依赖规模与可移植性。

"Rust 重写"不表示逐行翻译 C++。兼容的是能力、规则语义、输入输出和边界行为；
内部设计采用清晰、安全、可测试的 Rust 架构。

## 功能

- **格式识别**：20 个格式探测（PE、ELF、Mach-O、DEX、Java class、ZIP、tar、PDF、
  PNG、JPEG、BMP、WAV、ISO 9660、CFBF 等）
- **规则兼容**：原样加载 1184/1186 条上游规则（99.83%）
- **CLI**：功能完整的命令行工具，支持 JSON/XML/CSV/TSV 输出
- **C ABI**：带版本的稳定 C ABI，使用不透明句柄，支持 FFI
- **语言绑定**：Go/cgo 和 Python ctypes
- **跨平台**：Linux、macOS、Windows（MSRV 1.88）
- **安全**：核心层无 `unsafe`，FFI 边界有 panic 隔离
- **快速**：并行数据库加载（~400ms），格式探测亚微秒级

## 快速开始

### 构建

```sh
git clone https://github.com/chennqqi/diec-rust.git
cd diec-rust
cargo build --workspace --release
```

### CLI 用法

```sh
# 扫描单个文件
./target/release/diec file.exe

# JSON 输出
./target/release/diec --output json file.exe

# 递归扫描目录
./target/release/diec --recursive /path/to/dir/

# 使用自定义数据库
./target/release/diec --customdb /path/to/rules/ file.exe
```

### 规则数据库

规则数据库随发布物打包。CLI 按以下顺序查找：

1. `--db <path>` 参数
2. `DIEC_DB_PATH` 环境变量
3. 可执行文件相邻的 `db/` 目录
4. 系统路径（`/usr/share/diec/db`、`/opt/diec/db`）
5. 开发路径（`upstream/Detect-It-Easy/db`）

要使用更新的规则，下载新版本发布物或使用 `--customdb`。

### C ABI

```c
#include "diec.h"

DiecDatabaseHandle db;
diec_v1_database_builder_new(&builder, &error);
diec_v1_database_builder_add_path_utf8(builder, 0, db_path, len, 0, &error);
diec_v1_database_builder_build(builder, &db, &error);

DiecResultHandle result;
diec_v1_scan_bytes(db, data, size, NULL, NULL, &result, &error);
```

### Python

```python
from diec import Database, scan_bytes

db = Database("/path/to/db")
result = scan_bytes(db, b"file data")
print(result.detections)
```

### Go

```go
db, err := diec.NewDatabase("/path/to/db")
result, err := diec.ScanBytes(db, []byte("file data"))
```

## 项目状态

| 阶段 | 状态 | 描述 |
|------|------|------|
| 0 | 完成 | 设计门禁 |
| 1 | 完成 | 工程骨架与测试基础设施 |
| 2 | 完成 | 核心数据模型与格式识别 |
| 3 | 完成 | 规则兼容运行时 |
| 4 | 完成 | CLI 功能对齐 |
| 5 | 完成 | C ABI 与语言集成 |
| 6 | 进行中 | 兼容性、性能与发布准备 |

详见 [ROADMAP.md](ROADMAP.md)。

## 文档

- [ROADMAP.md](ROADMAP.md) — 阶段计划、交付物和里程碑
- [AGENTS.md](AGENTS.md) — 开发和评审工程约束
- [COMPATIBILITY.md](COMPATIBILITY.md) — 兼容性报告
- [RELEASE.md](RELEASE.md) — 发布检查清单
- [NOTICES.md](NOTICES.md) — 第三方归属
- [AUDIT.md](AUDIT.md) — 供应链审计
- `docs/design/` — 架构、API、ABI 和测试设计
- `docs/research/` — 上游分析与实验结果

## 测试

```sh
# 运行所有测试
cargo test --workspace --all-features

# 运行基准测试
cargo bench -p diec-engine
cargo bench -p diec-formats

# 运行 clippy
cargo clippy --workspace --all-targets --all-features -- -D warnings
```

414 个测试，6 个 fuzz targets，0 失败。

## 上游与许可证

- 上游项目：<https://github.com/horsicq/DIE-engine>
- 许可证：MIT（与上游一致）
- 规则：MIT 许可，从固定 commit 的上游打包

详见 [NOTICES.md](NOTICES.md) 归属信息和 [AUDIT.md](AUDIT.md) 供应链详情。
