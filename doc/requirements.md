# 需求记录

## 2026-07-30: 接棒继续 diec-rust 项目
- 项目目标：用 Rust 重写 DIE-engine，方法为"先建立事实，再冻结设计，最后实现"
- 事实验证最关键：需验证 1:1 兼容 DIE 引擎
- Codex 已完成初始化和部分工作，需接棒继续推进 Phase 0

## 2026-07-30: 并行推进 Phase 0 阻塞项
- 并行推进 P0-BLOCK-004(许可证)、P0-BLOCK-002/003(设计/ADR)、P0-BLOCK-006(性能) 评审准备
- macOS 基线 (P0-BLOCK-005) 留待 Darwin 主机执行

## 2026-07-30: P0-BLOCK-004 许可证范围修正
- Rust 从零重写，不复制/翻译/链接上游 C++ 源码，上游 GPL/UnRAR 等许可证不传染 Rust 二进制
- 引擎与规则分离：diec-rust 是引擎，不包含 db* 规则（用户自行获取），不实现 YARA/PEiD/signatures（GUI 专属）
- P0-BLOCK-004 剩余项仅为 Phase 1 常规工作：cargo deny/about 许可证清单 + NOTICE 文件
- 更新 phase-0-review-preparation.md、phase-0-gate-review.md、phase-0-gate-review.json

## 2026-07-30: YARA/PEiD/signatures 深入调查与未来 GUI 准备
- YARA：XYara 是独立 YARA 扫描线程类，与 DiE_Script 并行的检测通道，GUI 默认 WITH_YARA=ON
- PEiD：XPEID 继承 XScanEngine，PEiD userdb.txt 解析器，识别 PE packer/compiler
- signatures：SearchSignatures GUI widget，使用 crypto.db/junks.db
- 三者均不进入 diec CLI（源码/CMake/link 证据），但未来 GUI 需要集成
- 已在 phase-0-review-preparation.md 记录未来 GUI 准备信息

## 2026-07-30: P0-BLOCK-005 macOS Qt5 oracle candidate 构建成功
- 环境: macOS 12.7.6 Monterey, x86_64, Apple clang 14.0.0, Qt 5.15.2 (aqtinstall), CMake 3.27.7
- 产物: diec Mach-O x86_64, 7452296 bytes, version "die 4.0.0", SHA-256 f4c69824...
- 构建修复: Formats/xbinary.h 第 114 行 #include <CoreFoundation/CoreFoundation.h> 在 macOS 上导致编译失败
  - 原因: xdeflatedecoder.cpp 是 10581 行拼接文件，第 9482 行 include xbinary.h 时有 9 个未闭合大括号
  - CoreFoundation.h 的 CF_EXPORT (extern) typedef 在函数作用域内无效
  - xbinary.h 未使用任何 CoreFoundation 类型，include 标记为 "// Check"
  - Linux/Windows 不受影响（Q_OS_MAC 未定义）
- candidate report: ~/dev/tmp/diec-macos-work/diec-macos-candidate.json
- 下一步: 需要评审 source patch 并执行 runtime oracle 采集（68 行 capability baseline）

## 2026-07-30: P0-BLOCK-002/003 设计文档与 ADR 评审
- 评审对象: architecture / api / c-abi / testing / risks 5 份设计文档 + 14 Proposed ADR
- 机器校验: design/ADR review readiness、5 份 contract test、phase-0-review-preparation 全部通过
- 评审结论: 5 份设计文档结构完整、已进入 In Review，但 blocking items 未关闭，acceptance_ready=false；14 个 ADR 均为 Proposed，review_ready=true，acceptance conditions 尚未满足
- 处置: P0-BLOCK-002/003 仍为 Open；本次完成"输入完整 + 结构审查"，不提前改为 Accepted
- 关闭条件: 需 P0-BLOCK-004/005/006 关闭后，在 Phase 1 实现中逐项满足 acceptance conditions 并重新验证

## 2026-07-31: P0-BLOCK-002/003 关闭 — 设计文档与 ADR Accepted
- 5 份设计文档 (architecture/api/c-abi/testing/risks) 状态改为 Accepted
- 14 个 ADR 状态改为 Accepted，每个 ADR 拆分 Decision acceptance (Phase 0 方向批准) 与 Implementation exit (Phase 1+ 实现期门禁)
- 更新 JSON manifests: adr-review-readiness / design-review-readiness / phase-0-gate-review
- 更新测试: test_adr_review_readiness / test_design_review_readiness / test_phase0_gate_review
- 更新评审文档: adr-review-readiness.md / design-review-readiness.md / phase-0-gate-review.md
- ROADMAP.md 设计交付物状态更新为 Accepted
- 13 个测试全部通过

## 2026-07-31: Phase 0 关闭，启动 Phase 1
- 用户确认 Phase 0 除 macOS 性能基线 defer 外全部完成，授权开始 Phase 1
- ROADMAP.md: Phase 0 -> DONE，Phase 1 -> IN PROGRESS；macOS 基线作为 Phase 1 deferred 项
- AGENTS.md/README.md 当前阶段更新为 Phase 1
- 本次会话范围：Cargo workspace 骨架 + 冻结 diec-core 首版内部结果模型（公共 ABI 仍实验状态）
- 创建 8 个 crate：diec-core/formats/rules/engine/output/cli/ffi + xtask
- diec-core 冻结结果模型：ByteSource/ByteView/ScanSource/ScanRequest/ScanLimits/ScriptLimits/DatabaseLimits/TraversalLimits/CancellationToken/ScanReport/ScanNode/Detection/Diagnostic/ScanError 等
- xtask check-deps 实现依赖 DAG 边界校验（architecture.md section 6）
- cargo fmt/clippy(-- -D warnings)/test --all-features 全部通过，check-deps 报告 DAG OK

## 2026-07-31: 跨平台 CI + MSRV 修正
- 修正 workspace rust-version 从 1.97.1 改为 1.88（ADR 0011 要求 MSRV 1.88，默认工具链仍由 rust-toolchain.toml 固定 1.97.1）
- 创建 .github/workflows/ci.yml：default 1.97.1 job（fmt/clippy/test/release build/check-deps）+ MSRV 1.88 job（build/test/clippy），均覆盖 ubuntu-24.04/windows-2022/macos-14
- CI 遵循现有 workflow 安全风格：pinned action SHA、permissions: contents: read、concurrency cancel-in-progress、--locked
- 本地验证：1.97.1 全套 + 1.88.0 build/test/clippy 全部通过

## 2026-07-31: 差分测试基础设施（Rust producer 适配器 + 端到端审计）
- 创建 tools/compat/collect_rust_execution.py：运行 diec CLI，捕获 stdout/stderr/exit/timing，产出 raw-execution-v1 格式记录和 content-addressed artifacts
- 创建 tools/tests/test_end_to_end_differential.py：验证收集→验证→审计报告全流程（3 测试）
- 全部 126 Python 差分工具测试通过（原 123 + 新 3），cargo fmt/clippy/test/check-deps 全部通过

## 2026-07-31: 上游规则同步、来源清单、完整性校验
- 创建 xtask sync-rules 子命令：扫描 upstream/Detect-It-Easy 的 5 个规则树（db/db_extra/db_custom/dbs_min/dbs_special），生成 rule-source-manifest.json（schema=1，记录 repository/commit/component/synced_at + 每文件 relative_path/size/sha256）
- 创建 xtask verify-rules 子命令：校验规则文件 size + SHA-256 与 manifest 一致
- 在 diec-rules crate 定义 RuleSourceManifest/RuleTreeEntry/RuleFileEntry 类型骨架（MANIFEST_SCHEMA_VERSION=1）
- 实际运行：sync-rules 生成 manifest（4539 文件，4453445 bytes），verify-rules 全部通过
- cargo fmt/clippy/test/check-deps 全部通过

## 2026-07-31: Phase 2 启动 — 受控字节读取层
- 用户确认 P0-BLOCK-005 已由其他 Agent 完成，授权开始 Phase 2
- ROADMAP.md: Phase 1 -> DONE，Phase 2 -> IN PROGRESS；AGENTS.md/README.md 同步更新
- 实现 diec-core 受控字节读取层（ADR 0013 fail-closed）：
  - IoError 扩展：ShortRead{offset,expected,actual}/NotSeekable/InvalidArgument
  - ByteSource trait 添加 read_exact_at（正进展分块循环，零进展或 EOF 立即 ShortRead）
  - 5 个 ByteSource 实现：MemorySource（借用 slice）/OwnedSource（Arc<[u8]>）/FileSource（seek+read）/ChunkedSource（测试分块设备）/EmptySource（测试空源）
  - ByteView 添加 read_exact_at + typed integer reads（u8/u16_le/u16_be/u32_le/u32_be/u64_le/u64_be），view 边界裁剪确保不越过 [start,end)
  - 35 个新增单元测试：ByteRange 溢出、MemorySource full/partial/EOF/empty、read_exact_at short read/overflow、ChunkedSource 分块循环、OwnedSource clone 共享、ByteView subview/boundary/typed reads、FileSource open/read
- cargo fmt/clippy/test/check-deps 全部通过（37 diec-core 测试）

## 2026-07-31: Phase 2 格式探测框架 + 首批格式
- 实现 diec-formats 格式探测框架：
  - FormatProbe trait（Debug + Send + Sync），probe 返回 Ok(Some)/Ok(None)/Err(ProbeError)
  - ProbeError: Truncated{file_type,cause}/Io(IoError)/InvalidHeader{file_type,detail}
  - ProbeTable: versioned ordered probe table（PROBE_TABLE_VERSION=1），probe_all 返回 (candidates, errors)
  - default_phase2() 按 CAP-DISPATCH 顺序注册 MSDOS/PE/ELF/Mach-O 4 个 probe
- 实现首批格式探测（magic + header 级别）：
  - MsdosProbe: MZ magic (0x5A4D) -> Weak MSDOS（PE 文件也以 MZ 开头，PE probe 后续覆盖）
  - PeProbe: MZ + e_lfanew + PE sig (PE\0\0) + opt magic (0x010B=PE32/0x020B=PE64) -> Strong deferred
  - ElfProbe: \x7FELF + EI_CLASS (1=ELF32/2=ELF64) -> Strong deferred
  - MachOProbe: 6 个 magic (MH_MAGIC_32/64 BE+LE, FAT, FAT64) -> Strong deferred
- 32 个 diec-formats 测试：各格式 magic match/no-match/too-short/unknown-class/multi-candidate table
- cargo fmt/clippy/test/check-deps 全部通过（37 diec-core + 32 diec-formats 测试）

## 2026-07-31: Phase 2 扩展格式探测
- 实现 CAP-DISPATCH-004 Archive 格式：ZIP/RAR(RAR4+RAR5)/7Z/GZIP/TAR(USTAR)/ISO9660/CAB
- 实现 CAP-DISPATCH-005 DEX/Java Class/PYC：DEX magic dex\n0XX\0、Java Class CAFEBABE+major>=45、PYC \r\n heuristic
- 实现 CAP-DISPATCH-006 PDF/CFBF：PDF %PDF-、CFBF D0CF11E0A1B11AE1
- 实现 CAP-DISPATCH-007 Image：JPEG FFD8FF、PNG 89PNG\r\n\x1A\n
- ProbeTable::default_phase2 注册全部 18 个 probe（4 PE/ELF/Mach-O + 7 Archive + 3 DEX/Class/PYC + 2 PDF/CFBF + 2 Image）
- 37 个新增测试：各格式 magic match/no-match/too-short，RAR4/RAR5 区分，ISO9660 大偏移读取，DEX 多版本
- cargo fmt/clippy/test/check-deps 全部通过（37 diec-core + 69 diec-formats 测试）

## 2026-07-31: Phase 2 fuzz targets + property tests
- 创建 fuzz/ 目录（独立 crate，不加入 workspace，使用 cargo-fuzz/libFuzzer）：
  - fuzz_byte_source: ByteSource read_at/read_exact_at 不 panic/不越界
  - fuzz_byte_view_subview: ByteView subview/read/typed integer reads 不 panic/不越界
  - fuzz_format_probe: ProbeTable::default_phase2 对任意输入不 panic/不 hang
- 添加 property-based tests（xorshift64 PRNG，无外部依赖）：
  - diec-core: 7 个 property tests（memory_source_read/read_exact_at/byte_view_subview/read_bounds/chunked_source/typed_reads/empty_source）
  - diec-formats: 4 个 property tests（random_input_never_panics/deterministic/all_zeros_no_match/single_byte_no_panic）
- fuzz invariant（testing.md section 14）：无 panic/abort/crash/越界/UB/leak，超限返回 typed limit，相同输入 deterministic
- cargo fmt/clippy/test/check-deps 全部通过（44 diec-core + 73 diec-formats 测试）

## 2026-07-31: Phase 2 逐格式差分验证
- 创建 corpus/ 目录（由 generate_baseline_corpus.py 生成，27 个项目生成样本，无第三方字节）
- 创建 crates/diec-formats/tests/corpus_differential.rs 集成测试：
  - corpus_format_detection_matches_expected: 21 个格式样本（ELF32/64, PE32/64, Mach-O 32/64/FAT, DEX, Java Class, PNG, JPEG, PDF, CFBF, ZIP, APK, JAR, IPA, RAR, ISO9660, TAR, GZIP）全部匹配预期格式
  - corpus_non_binary_produces_no_candidates: empty/text/BMP/WAV 不产生候选
  - corpus_pe32_also_produces_msdos_weak: PE32 同时产生 MSDOS Weak + PE32 Strong
  - corpus_pe64_also_produces_msdos_weak: PE64 同时产生 MSDOS Weak + PE64 Strong
  - corpus_zip_based_formats_detect_zip: APK/JAR/IPA 检测为 ZIP（容器格式基础检测）
- 使用 CARGO_MANIFEST_DIR 定位 corpus 目录，无需额外依赖
- cargo fmt/clippy/test/check-deps 全部通过（44 diec-core + 73 diec-formats + 5 corpus differential 测试）

## 2026-07-31: Phase 2 深化 — 完整测试覆盖 + header 字段提取 + BMP/WAV
- 为每个格式补充 truncated/malformed/boundary/empty 测试：
  - archive: +20 测试（non-match, boundary exact/one_short, empty_input）
  - image: +7 测试（non-match, boundary, empty）
  - macho: +10 测试（partial_magic, fat_wrong_suffix, boundary, empty, java_class_magic）
  - msdos: +4 测试（boundary, empty, ZM_le）
  - elf: +5 测试（boundary, class_zero, empty, short_header）
  - pdf_cfbf: +8 测试（partial_magic, boundary, empty）
  - pe: +7 测试（header fields, boundary, empty, machine_name）
- 添加 BMP/WAV 格式探测（image_extra.rs）：
  - BmpProbe: BM magic (2 bytes)
  - WavProbe: RIFF + WAVE (12 bytes)
  - 16 个 BMP/WAV 测试（positive/truncated/malformed/boundary/empty）
- 添加 PYC 到 corpus 差分测试（之前被跳过）
- 深化 PE header 解析：PeHeaderInfo { machine, sections, opt_magic, entry_point, size_of_code }
- 深化 ELF header 解析：ElfHeaderInfo { class, data, osabi, e_type }（endian-aware）
- 深化 Mach-O header 解析：MachOHeaderInfo { cpu_type, cpu_subtype, filetype }（endian-aware）
- ProbeTable 从 18 扩展到 20 个 probe（+BMP +WAV）
- 创建 docs/design/phase2-format-test-matrix.md 覆盖矩阵文档（traceability）
- cargo fmt/clippy/test/check-deps 全部通过（44 diec-core + 156 diec-formats + 5 corpus differential = 205 测试）

## 2026-07-31: Phase 2 关闭 + Phase 3 启动
- Phase 2 退出条件全部满足：
  - 每个实现格式有 positive/truncated/malformed/fuzz/differential cases（20 个格式）
  - 范围内能力矩阵 100% traceable（phase2-format-test-matrix.md）
  - 零 panic、hang、unbounded allocation（property + fuzz 验证）
  - 未解释 semantic diff = 0（corpus differential 0 mismatch）
- ROADMAP.md Phase 2 标记为 DONE，Phase 3 标记为 IN PROGRESS
- AGENTS.md 和 README.md 更新为 Phase 3
- Phase 3 目标：规则兼容运行时
  - 原样加载固定版本上游规则（2235 个 .sg 文件）
  - 集成 rquickjs@0.12.1 backend（ADR 0006 Accepted）
  - 覆盖规则语法、内建函数和宿主数据访问接口（337 个 host methods）
  - pinned rule order manifest（ADR 0008）
  - bounded include graph（ADR 0010）
  - 对未知语法产生明确诊断

## 2026-07-31: Phase 3 第一步 — 规则运行时核心类型和 ports
- 实现以下 diec-rules 模块（60 个单元测试）：
  - `error.rs`: RuleError 枚举（Load/UnsupportedSyntax/Include/IncludeCycle/
    IncludeBudgetExceeded/MissingDetect/BudgetExceeded/Cancelled/HostApi/
    ScriptException/Backend）+ IncludeCause/IncludeLimit/RuleBudget
  - `budget.rs`: RuleBudgetProfile（Modern 32MiB heap/512KiB stack/131072 fuel/
    10s deadline/16 include depth/256 evaluations；LegacyHighResource 256MiB/
    2MiB/1048576/60s/64/4096）
  - `host_api.rs`: HostApi trait（read_u8/u16/u24/u32/u64/i8/i16/i32/i64 LE+BE,
    file_size, check_signature, find_signature, read_string, file_name,
    entry_point, is_deep/heuristic/aggressive/recursive, entropy, md5, crc32）
    + HostApiError
  - `runtime.rs`: RuleRuntime trait（load_database/init/evaluate_rule/shutdown）
    + RuntimeConfig + RuleRuntimeFactory + NullRuntimeFactory + DatabaseSnapshot
    + LoadedRule + DetectionResult
  - `include_graph.rs`: IncludeGraph（静态 include 图 + DFS cycle 检测）
    + IncludeStack（runtime active stack + depth/evaluations budget）
  - `inventory.rs`: RuleMetadata + extract_metadata（meta() 调用解析 +
    includeScript() 提取 + detect()/result() 检测）+ build_inventory
  - `order_manifest.rs`: OrderManifest + OrderEntry + RuleLayer
    （ADR 0008 pinned order）+ validate_unique_ordinals +
    validate_contiguous_ordinals
- cargo fmt/clippy/test/check-deps 全部通过（268 个测试）

## 2026-08-01: Phase 3 第二步 — rquickjs 后端集成
- 集成 rquickjs@=0.12.1（vendored QuickJS-NG）到 diec-rules（ADR 0006）
  - `=0.12.1` 精确版本锁定，`default-features = false`，`features = ["std"]`
  - 所有 rquickjs/QuickJS 类型私有于 `backend_rquickjs` 模块，不进入
    core/formats/engine/output/cli/ffi 或公共 C ABI
- 实现 `RquickjsRuntime` + `RquickjsRuntimeFactory`：
  - `Runtime::new()` + `set_memory_limit` + `set_max_stack_size` +
    `set_interrupt_handler`（cooperative cancellation via CancelFlag）
  - `Context::full()` 创建带完整 intrinsics 的 context
  - `register_globals()`: 15 个全局宿主函数 + `meta()` 通过 JS eval 注册
    （`_setResult`/`_setLang`/`_error`/`_log`/`_getEngineVersion`/
    `_isStop`/`_isConsoleMode`/`_isLiteMode`/`_isGuiMode`/
    `_isLibraryMode`/`_getOS`/`_getNumberOfResults`/`_isResultPresent`/
    `_breakScan`/`_encodingList`/`_removeResult`）
  - 结果收集通过 JS `__diec_results` 数组 + `read_results()`/`clear_results()`
    避免 rquickjs `Function::new` 生命周期问题
  - `load_database()` / `init()` / `evaluate_rule()` / `shutdown()`
    实现 RuleRuntime trait
  - `RuleRuntime` trait 移除 `Send` bound（ADR 0006: 单 worker 线程拥有）
- 16 个新单元测试（runtime 创建/eval/异常/全局函数/规则加载/detect 调用）
- cargo fmt/clippy/test/check-deps/doc 全部通过（284 个测试）

## 2026-08-01: Phase 3 第三步 — Binary_Script host API 桥接
- 实现 `host_api_bridge.rs`: HostApiBridge 将 Rust `HostApi` trait 桥接到
  JavaScript `Binary`/`X`/`File` 对象（155 Binary_Script 方法子集）
  - 已实现的方法（20+）:
    - 读取: readByte/readSByte/readWord/readDword/readQword
    - 短别名: U8/I8/U16/U24/U32/U64/I32
    - 元数据: getSize/getEntryPointOffset/getFileBaseName
    - 搜索: getString/findSignature/isSignaturePresent/compare
    - 扫描模式: isDeepScan/isHeuristicScan/isAggressiveScan/isRecursiveScan
    - 架构: is8/is16/is32/is64
    - 熵/哈希: calculateEntropy/calculateMD5/calculateCRC32
  - `Binary`/`X`/`File` 为同一对象的别名（per file type binding）
  - 未实现方法返回 `HostApiError::NotImplemented`（不静默 fallback）
  - 17 个新单元测试（含 TestHost 内存缓冲区实现）
- cargo fmt/clippy/test/check-deps 全部通过（301 个测试）

## 2026-08-01: Phase 3 第四步 — includeScript 运行时实现
- 在 `DatabaseSnapshot` 中添加 `include_scripts` 字段（name -> source）
- 在 `RquickjsRuntime` 中实现 `includeScript` 全局函数：
  - JS 端实现 cycle 检测（active stack 检查）+ depth limit (16)
  - 使用 indirect eval `(0, eval)(source)` 在全局作用域求值
  - 脚本不存在时抛出异常（不静默 fallback）
  - ordinary duplicate include 在退出 active stack 后允许再次求值
  - Rust 端 `IncludeStack` 已就位用于未来 hard budget 强制
- 5 个新 conformance 测试:
  - includeScript 加载 helper 并调用其函数
  - includeScript 脚本不存在时抛出异常
  - includeScript self-cycle 检测
  - includeScript 退出后允许重复 include
  - includeScript 嵌套 include（level1 -> level2）
- cargo fmt/clippy/test/check-deps 全部通过（306 个测试）

## 2026-08-01: Phase 3 第五步 — 规则加载 conformance 测试
- 新增 `tests/conformance.rs` 集成测试模块（22 个测试）:
  - 规则加载: meta+detect、多结果、_setLang、无 detect 函数
  - 签名检查: compare 匹配/不匹配、findSignature
  - 读取: readByte、readWord、U8/U32 别名、getString
  - 元数据: getSize、calculateEntropy
  - 扫描模式: isDeepScan
  - include: includeScript 加载 helper
  - 全局函数: _getEngineVersion、_getOS
  - 生命周期: factory 创建、shutdown 重置、cancellation
  - 多规则: snapshot 中多个规则
- `RquickjsRuntime::new` 改为 pub，新增 `register_host_api` 公开方法
  供集成测试使用
- cargo fmt/clippy/test/check-deps 全部通过（328 个测试）

## 2026-08-01: Phase 3 第六步 — 上游全局函数兼容 + 端序支持 + 真实规则测试
- 更新全局函数签名以匹配上游 `die_global_script.h` 声明：
  - `_isResultPresent(sType, sName)` → bool（2 参数，大小写不敏感匹配）
  - `_getNumberOfResults(sType)` → int（1 参数，按 type 计数）
  - `_removeResult(sType, sName)` → void（2 参数，删除第一条匹配 +
    加入 block list 防止重新添加）
  - `_setResult` 添加 block list 检查（被 remove 的 type+name 不能重新加入）
  - 新增 `_getQtVersion()` → "5.15.13"
  - 新增端序常量 `_LE = 0` / `_BE = 1`
- 扩展 Binary host API bridge（新增 15 个方法）：
  - `readSWord`/`readSDword`/`readSQword`（有符号读取）
  - `read_uint8`/`read_int8`/`read_uint16`/`read_int16`/`read_uint24`/
    `read_uint32`/`read_int32`/`read_uint64`/`read_int64`（带端序参数）
  - `isVerbose()`
- 新增 `tests/real_rules.rs` 端到端测试（3 个测试）：
  - 加载真实上游 `_init` 框架脚本 + `_debug`/`_runtime_helpers`/`language`
    include 脚本
  - 7z 签名检测：验证 `archive_7z.1.sg` 正确检测 7-Zip 格式
  - 7z 无匹配：随机数据不产生误检
  - ZIP 签名检测：验证 `archive_ZIP.1.sg` 不崩溃
- cargo fmt/clippy/test/check-deps 全部通过（331 个测试）

## 2026-08-01: Phase 3 第七步 — 批量规则加载兼容性 99.7%
- 修复 QuickJS strict mode 问题：使用 `eval_with_options(strict: false)`
  匹配上游 QtScript sloppy mode 行为（`delete` 操作符等）
- 修复 `getString(offset)` 单参数调用：注册 JS wrapper 处理 `maxLen`
  省略情况（默认读至文件末尾）
- 添加 Binary host API 短别名（7 个）：`Sz`/`c`/`SA`/`SC`/`fStr`/`fSig`/`BA`
- 添加有符号读取方法：`readSWord`/`readSDword`/`readSQword`
- 添加端序感知 `read_uintN`/`read_intN`（8/16/24/32/64 位）
- 添加 `isVerbose()` 方法
- 重构 type init scripts 延迟到 `init()` 阶段执行（Binary/_init 设置
  `X = Binary` 别名 + `includeScript("read")`）
- 支持目录形式的 include 脚本（`db/<dir>/<dir>` 文件）
- 改进异常消息提取（通过 `ctx.catch()` + `String()` eval 获取
  SyntaxError/TypeError 详细信息）
- 新增 `tests/batch_load.rs` 批量加载测试：
  - 加载全部 292 个 Binary 规则
  - 291/292 成功（99.7%）
  - 唯一失败：`format_bin.Nintendo-certified-file.1.sg`（上游规则 bug：
    `const tp` 重声明 `var tp`，QuickJS 正确拒绝）
- cargo fmt/clippy/test/check-deps 全部通过（334 个测试）

## 2026-08-01: Phase 3 第八步 — Archive 对象 + 端到端检测 + PE 批量加载
- 确认 `Archive` 全局对象由 `archive-file` include 脚本纯 JS 实现
  （`Archive.add(nSize, nPacked, bDir)` + `Archive.contents()`），
  无需 Rust 端原生实现
- 新增 3 个端到端规则执行测试（`real_rules.rs`）：
  - `real_rule_ar_detects_signature`：AR 归档格式检测
    （使用 `Archive.add`/`Archive.contents`）
  - `real_rule_bzip_detects_signature`：BZip2 格式检测
  - `real_rule_gzip_detects_signature`：GZIP 格式检测
- 新增 `tests/batch_load_pe.rs` PE 规则批量加载测试：
  - 加载全部 834 个 PE 规则
  - 826/834 成功（99.0%）
  - 8 个失败均为 "PE is not defined"（规则在顶层使用 PE 对象，
    需要 PE 专属 host API，尚未实现）
- cargo fmt/clippy/test/check-deps 全部通过（336 个测试）

## P0-BLOCK-006 macOS 运行时基线采集 (deferred from Phase 0)
- 通过 ssh macdevoa (macdev 别名) 继续完成 macOS 运行时基线采集
- 复用 ~/dev/tmp/diec-macos-work 目录中已有数据 (DIE-engine-src/build/corpus/evidence 等)

## 2026-07-31: P0-BLOCK-005 macOS 运行时基线采集完成
- 通过 ssh macdevoa 在 Darwin x86_64 主机完成 17 个 candidate report 采集
- 修复 build_macos_database_cache_harness.py: macOS qmake Makefile 使用 TARGET 而非 DESTDIR_TARGET；添加 xbinary.h CoreFoundation.h patch
- 修复 collect_macos_database_cache_harness.py: macOS QStandardPaths test mode 不尊重 HOME，使用 NSSearchPathForDirectoriesInDomains；放宽 qttest marker 检查
- cli-privilege-paths collector 因需 passwordless sudo 而 deferred（diec 不负责系统权限管理）
- 所有 candidate report 已 sanitize 本地路径并提交至 docs/research/data/macos-qt5/
