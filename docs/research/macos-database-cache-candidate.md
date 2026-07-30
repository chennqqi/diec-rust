# macOS Qt5 database cache/permission 候选计划

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Components:
`horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-30

## 结论

仓库已具备固定 macOS x86_64/Qt 5.15.2 database-cache engine harness 的
build/run candidate 和离线 validator，但尚未在 Darwin runner 执行，不能形成
macOS runtime 结论或接纳任何 capability row。

发布 `diec` 的 `SCAN_OPTIONS` 零初始化后从未设置 `bUseCache`，也没有 cache
CLI option。因此 release CLI 只能证明 `bUseCache=false` 的 ZIP/directory
database 行为；cache miss/hit、stale、损坏恢复、写失败和 cancellation poisoning
必须通过链接未修改上游 engine 的专用入口观察。该 reachability 边界已有固定
源码与 Linux/Windows runtime 证据，见
[`database-archive-cache.md`](database-archive-cache.md)。

## 固定 build closure

[`build_macos_database_cache_harness.py`](../../tools/upstream/build_macos_database_cache_harness.py)
先验证：

- native Darwin x86_64；
- bundle-local `oracle-candidate.json`；
- 固定上游/root/rules/submodule、Qt 和 CLI artifact identity；
- qmake build directory 与 oracle 报告中的路径一致；
- source tracked state 与 CLI bytes 在 harness 构建前后不变。

它不创建另一套 engine 项目。固定 oracle 已生成
`<qmake-build>/console_source/Makefile`；builder 只做三个闭集替换：

1. `main_console.cpp` → `database_cache_harness_macos_adapter.cpp`；
2. `main_console.o` → `database_cache_harness_macos_adapter.o`；
3. `DESTDIR_TARGET` → 独立 harness 路径。

替换计数不足、多个 target assignment、残留 main token、预存输出或路径含空白
都会失败。其余 object、compile flags、includes、libraries 和 link recipe 原样
复用固定 console Makefile。

macOS adapter 只在调用共享
[`database_cache_harness_main.cpp`](../../tools/upstream/database_cache_harness_main.cpp)
前执行 `QStandardPaths::setTestModeEnabled(true)`。build bundle 保存：

- 原始与补丁 Makefile；
- 共享 harness 与 adapter 原始 bytes；
- build stdout/stderr；
- artifact size/SHA-256、Mach-O x86_64、`file` 与 `otool -L`；
- generator/validator/source/Qt/oracle hash。

[`validate_macos_database_cache_harness_build.py`](../../tools/upstream/validate_macos_database_cache_harness_build.py)
只使用 bundle 内 build inputs 重算补丁和 hash，不需要信任或访问报告中的 runner
本地路径。synthetic 测试会篡改 Makefile、raw log、artifact 和 admission，
validator 必须逐项拒绝。

## 固定 runtime 协议

[`collect_macos_database_cache_harness.py`](../../tools/upstream/collect_macos_database_cache_harness.py)
要求非 root 进程、空 working directory 和不存在的固定
`/tmp/diec-database-cache-harness`。它为 child 设置 collector-owned `HOME`；
adapter 的 test mode 必须令 `cache_path` 同时：

- 位于该 HOME 下；
- 含 `qttest` marker；
- 以 `.cache` 结尾。

任一条件不满足都失败，避免读写普通 Detect It Easy 用户 cache。collector 使用
固定 project-generated database fixture 连续执行两轮，保留 4 个 raw stream，
严格解析 JSON duplicate/non-finite 值，并要求 exit `0`、stderr 为空。

共享 harness 的 19 个有序 case 为：

```text
initial_miss
unchanged_hit
same_stats_stale_hit
stats_changed_rebuild
bad_magic_fallback
bad_version_fallback
empty_cache_fallback
magic_only_fallback
magic_version_only_fallback
truncated_record_fallback
record_tail_truncated_fallback
cache_write_denied
cache_write_recovery
concurrent_identical_writers
database_directory_permission_denied
database_file_permission_denied
canceled_cache_hit
canceled_cache_miss
poisoned_empty_cache_hit
```

报告重算 Linux 已命名 relationship、逐 case semantic projection 与 cache-size
delta。平台差异不会被 normalizer 隐藏；normalizer 只替换：

- 固定 `/tmp` database/rule path → `<work>`；
- 已验证的 collector HOME prefix → `<qt-test-home>`。

case、cache hash/size、scan result/error 和 raw stream 均不修改。

[`validate_macos_database_cache_harness.py`](../../tools/upstream/validate_macos_database_cache_harness.py)
从 raw stdout 重新解析两轮 19-case observation，重算 normalization、
relationship、Linux projection、determinism 和 summary，并拒绝未声明 raw file
或 admission 翻转。

## Workflow 与计数

手动
[`macos-qt5-oracle-candidate.yml`](../../.github/workflows/macos-qt5-oracle-candidate.yml)
先生成固定 database fixture，再 build/validate harness，最后 collect/validate
runtime。上传物包含 build report、harness artifact、engine report、
`build-input/` 和 `raw/`；workflow 仍只有 `contents: read`，不会提交报告。

本候选增加：

- 2 次 engine harness process execution；
- 4 个 engine runtime raw stream；
- 2 个单列 build stdout/stderr。

本 database-cache 增量落地时，CLI 口径为 2,108 次执行/4,216 个 raw stream，
加上本 harness 后候选 runtime 为 2,110 次执行/4,220 个 raw stream。后续
privilege-path candidate 已把当前总口径更新到
[`macos-qt5-oracle-plan.md`](macos-qt5-oracle-plan.md)；build log 始终不计入
runtime stream。

## 尚未证明

- 尚无一次真实 Darwin build 或 harness run；
- 尚未知道 macOS cache bytes/size、19 项 relationship 或 Linux projection
  是否相同；
- POSIX mode denial 只覆盖 hosted-runner 当前非 root 用户；
- database-cache harness 自身仍未覆盖 root、ACL、ownership、sandbox profile、
  network filesystem；
- 独立 privilege-path CLI candidate 已覆盖 root/ACL/ownership 的受限矩阵，
  但尚未在 Darwin 运行，且不能替代 engine cache 行为；
- changed-during-read、不同内容 writer、crash-interrupted publish 和恶意超大
  cache 输入仍缺；
- 本候选不是 Rust cache 格式、锁、事务化 publish 或资源限制设计的验证。

因此 `platform_admitted=false`、`capability_rows_admitted=0` 和 68 个
`platform_missing` 必须保持不变。
