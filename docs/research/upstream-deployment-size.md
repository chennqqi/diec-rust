# 固定 Linux Qt5 上游部署体积基线

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 1. 结论

固定 Linux Qt5 CMake oracle 现在已有可重复的描述性部署体积基线。不能只比较
动态链接 ELF `diec` 的文件大小：它运行时还需要 Qt、C++/OS 动态库和原始规则树。
本次同时保留以下互不替代的口径：

| 口径 | Bytes | MiB |
| --- | ---: | ---: |
| `diec` ELF 本体 | 8,248,008 | 7.87 |
| `db`/`db_extra`/`db_custom` 原始规则 | 2,909,316 | 2.77 |
| 16 个 realpath 去重的动态依赖文件 | 54,100,576 | 51.59 |
| ELF + 规则 | 11,157,324 | 10.64 |
| ELF + 动态依赖 | 62,348,584 | 59.46 |
| ELF + 动态依赖 + 规则 | 65,257,900 | 62.23 |

未来 Rust 成对比较至少报告：

1. `binary_and_rules_bytes`：程序产物与同一固定规则集之和；
2. `full_closure_and_rules_bytes`：程序产物、该环境解析到的全部运行时库与规则之和。

第一项适合观察项目自身发布内容，但不是“自包含部署大小”；第二项可审计实际
进程闭包，但包含可能由目标 OS/package manager 预装的库。两项都不得被单个
可执行文件大小替代。

机器证据为
[`upstream-deployment-size-linux-qt5.json`](data/upstream-deployment-size-linux-qt5.json)。
它是 `descriptive_upstream_only`，且 `targets_frozen=false`；没有 Rust 产物和其他
平台数据，不能据此声称体积改善或冻结发布阈值。

后续 [`linux-cmake-install-tree.md`](linux-cmake-install-tree.md) 又固定了默认
CMake `DESTDIR`：4,916 个 regular file、60,881,050 bytes。该数字同时包含
`die`/`diec`/`diel` 和重复 GUI/lite 数据，却不包含 16 个系统动态依赖，因此既
不能替代本报告的 CLI runtime closure，也不是压缩发布包大小。后续体积比较必须
同时标注产品范围、是否包含系统库、规则是否去重以及压缩方式。

## 2. 固定身份

| 项目 | 固定值 |
| --- | --- |
| DIE-engine | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Detect-It-Easy rules | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| `diec` SHA-256 | `da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf` |
| `diec` bytes | `8248008` |
| size image | `sha256:4d8c83178ae3a6ddc96e5bfc96fb4324f0ef1d16372b7e74ef9c2d92b958bef5` |
| base benchmark image | `sha256:a5b33708eb148591d127041b6a54d05d68f8dd24bea7855e95ea88715d0bf8c5` |
| inspector SHA-256 | `93d09f465d005b61309fb99ba6f6546c7333dce75b7d7f5e1bd0e080a7216310` |
| dependency closure SHA-256 | `96e11fd18f8f1d289a345ecacc10f328bd7b3e2148dcfca29a04824d6e2189b2` |
| rule combined tree SHA-256 | `20f2b74effc2bdaf069e3b2e13060432b8890d38364511f5cde56a337348bfda` |

派生镜像只在已经固定的 benchmark 镜像上复制
[`inspect_upstream_deployment.py`](../../tools/benchmark/inspect_upstream_deployment.py)，
不会修改原始 `diec`、其链接库或规则。probe 逐字比较镜像内 inspector 与仓库
inspector 的 SHA-256，并验证镜像 revision、ELF SHA、规则 commit/hash/count/
bytes 和全部求和关系。

## 3. ELF 依赖闭包方法

inspector 对固定且已验证 SHA-256 的可信 ELF 执行：

```text
readelf -d /opt/die-build/src/console/diec
ldd /opt/die-build/src/console/diec
```

`readelf` 固定六个直接 `DT_NEEDED`：

```text
libQt5Script.so.5
libQt5Core.so.5
libstdc++.so.6
libm.so.6
libgcc_s.so.1
libc.so.6
```

`ldd` 必须解析每个直接依赖且不得出现 `not found` 或未知输出行。
`linux-vdso` 是内核映射而不是磁盘文件，因此排除；动态 loader 作为真实文件计入。
每个解析路径经过 `realpath`，symlink alias 按最终真实路径去重，然后记录原请求
名、解析路径、真实路径、字节数和文件 SHA-256。

本次得到 16 个真实文件：

| 类别 | 文件 |
| --- | --- |
| Qt | `libQt5Core.so.5.15.13`、`libQt5Script.so.5.15.13` |
| toolchain runtime | `libstdc++.so.6.0.33`、`libgcc_s.so.1` |
| OS/transitive | loader、libc、libm、zlib、zstd、glib、double-conversion、ICU 三库、PCRE2 两库 |

报告不把“system”与“需要随包分发”混成一个主观扣除规则；所有 16 个真实文件都
进入完整闭包。`ldd` 可能执行不可信 ELF 的 loader 路径，因此本工具只允许用于
已经固定来源和哈希的上游 oracle，不是任意样本分析器。

## 4. 规则资产口径

规则口径与
[`runtime-rule-assets-license.json`](data/runtime-rule-assets-license.json)
完全一致：

| Tree | Files | Bytes | Tree SHA-256 |
| --- | ---: | ---: | --- |
| `db` | 2,124 | 2,832,469 | `8000138ce96a6a892aaa3cba8dee60960694c42dcfa24b3787f02c25858f1650` |
| `db_extra` | 142 | 76,651 | `77c4e0da796baa9a71ec1a699a37e61ed73783c0d3dc5d49044185dc80a38ec1` |
| `db_custom` | 2 | 196 | `36c10cd4d87826c78f07a0c801c1ae374f4b6364936056d44a045e9150ba5815` |

每个 tree 内按 UTF-8 path bytes 排序；组合哈希按既有声明顺序
`db → db_extra → db_custom` 累加。文件哈希输入为 relative path、NUL、
8-byte big-endian size、原始 bytes 和该文件的 binary SHA-256。inspector 拒绝
规则树中的 symlink，防止统计逃逸到树外。

## 5. 可重复执行

先保证固定 benchmark image 已按
[`upstream-performance-baseline.md`](upstream-performance-baseline.md)
构建，然后离线派生 size image：

```powershell
docker build --network none `
  -f tools\upstream\Dockerfile.upstream-size-qt5 `
  -t diec-rust/upstream-size-qt5:74eaf505 tools

$report = Join-Path $env:TEMP upstream-deployment-size-linux-qt5.json
python tools\benchmark\probe_upstream_deployment_size.py `
  --image diec-rust/upstream-size-qt5:74eaf505 `
  --output $report

python -m unittest discover -s tools\tests `
  -p "test_upstream_deployment_size.py" -v
```

容器运行使用 `--network none`。完成采集后的语义校验失败会写出带 `failures`
的报告；环境或执行错误则直接拒绝生成可信报告。只有 `passed=true`、
`failures=[]` 才能进入基线。提交报告不包含宿主临时路径。

## 6. 解释边界与后续门禁

- `st_size` 是未压缩磁盘文件字节，不是 OCI layer、安装包或压缩 archive 大小。
- 完整闭包包含 OS 可能提供的库；实际发行包也可能增加 LICENSE、SBOM、签名、
  launcher、debug symbols 或 package metadata。
- 当前只测 Linux x86_64 glibc/Qt5 CMake Release；Windows DLL、macOS dylib、
  musl、arm64 和其他 build profile 必须分别采集。
- 本报告没有按 package ownership 推导“应随包分发”的子集；在发行策略冻结前，
  不用主观 system-library 排除规则制造更小数字。
- Rust staticlib、CLI 和语言绑定产物尚不存在。它们出现后必须使用同一规则
  identity，分别报告 stripped/unstripped、static/dynamic closure 和发行包口径。
- size 证据已经补齐固定 Linux upstream 一侧，但 Rust 成对数据、跨平台基线和
  评审后的 size target 仍是 `P0-BLOCK-006` 的开放项。
