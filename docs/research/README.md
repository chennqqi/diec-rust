# 调研文档

本目录只记录上游事实、实验结果和证据，不提前写入本项目的实现决策。

Phase 0 计划形成：

- [`upstream-baseline.md`](upstream-baseline.md)：版本、构建、submodule、依赖和许可证（Draft）。
- [`capability-matrix.md`](capability-matrix.md)：CLI/engine 能力与证据索引（Draft）。
- [`capability-coverage-report.md`](capability-coverage-report.md)：68 个稳定能力在
  Linux Qt5/Qt6、Windows 和 macOS 上的 runtime/source-only、corpus-missing
  与 platform-missing 闭集报告（Draft）。
- [`source-only-closure-plan.md`](source-only-closure-plan.md)：Linux Qt5
  source-only 闭集及最后一项 depth/expanded-byte 关闭证据（Draft）。
- [`archive-limit-behavior.md`](archive-limit-behavior.md)：受资源约束的 archive
  depth 64/约 32 MiB 累计展开量递增、peak RSS 与 cooperative cancellation
  证据（In Review）。
- [`archive-iteration-boundary.md`](archive-iteration-boundary.md)：aggressive
  archive 第 99999/100000/100001 条哨兵、源码循环顺序和受控分配失败证据
  （In Review）。
- [`archive-adversarial-behavior.md`](archive-adversarial-behavior.md)：ZIP
  deflate/ZipCrypto、高压缩比、CRC/压缩流/offset/method 畸形、local-header
  fallback 与 mixed-member filter（In Review）。
- [`archive-truncation-behavior.md`](archive-truncation-behavior.md)：7Z、
  RAR4、CAB 和 ISO9660 的 26-case EOF 前缀阶梯、104 次固定 Qt5 oracle
  与格式识别/成员展开边界（In Review）。
- [`archive-structure-behavior.md`](archive-structure-behavior.md)：7Z、
  RAR4、CAB 和 ISO9660 的 56-case CRC/size/offset/method/record-field/0/max
  突变及 224 次固定 Qt5 oracle（In Review）。
- [`archive-multirecord-behavior.md`](archive-multirecord-behavior.md)：7Z、
  RAR4、CAB 和 ISO9660 的正序/逆序/重名/空首记录两成员矩阵及 64 次固定
  Qt5 oracle（In Review）。
- [`iso9660-endian-behavior.md`](iso9660-endian-behavior.md)：ISO9660
  17 个 `both16`/`both32` 字段的 LE-only/BE-only 冲突对、35 个样本及
  140 次固定 Qt5 oracle（In Review）。
- [`archive-format-behavior.md`](archive-format-behavior.md)：
  7Z Copy/LZMA/LZMA2/PPMd7/BZip2/Deflate/Deflate64 与
  x86/ARM64 BCJ+LZMA2、BCJ2+LZMA2 no-branch/E8/E9/JCC、RAR4、CAB
  Store/MSZIP、ISO9660 正向解包、7Z 七种基础 coder+AES 与完整 x86/ARM64
  filter × 七种基础 coder × AES 成功密码契约、Copy/PPMd7 错误密码残留输出、
  BCJ2+LZMA2+4×AES 正确密码失败边界及 CAB
  LZX/Quantum 普通/激进失败边界、
  发布 CLI 默认对照与 7Z/CAB `Binary` 顶层 quirk（Draft）。
- [`archive-rar5-store-behavior.md`](archive-rar5-store-behavior.md)：
  项目生成 RAR5 Store 单成员与 solid 双成员、8 次固定 Qt5 oracle、源码
  solid-store 分派及明确排除专有压缩算法/第三方 binary 的语料边界（Draft）。
- [`archive-rar-compressed-behavior.md`](archive-rar-compressed-behavior.md)：
  固定外部 CC0 候选的 RAR3/RAR5 method-5、solid 状态、许可证边界和
  aggressive oracle（Draft）。
- [`archive-gap-closure.md`](archive-gap-closure.md)：
  固定 engine 五类解包 family 闭集、成对运行控制、100000/100001、
  depth-64/33,554,546-byte 证据及 `CAP-GAP-006` disposition（Draft）。
- [`npm-dispatch-reachability.md`](npm-dispatch-reachability.md)：
  NPM 精确归档路径检测、公共 GZIP 自动分派不可达、强制 NPM 规则分支及
  双 Qt5 release 对照（Draft）。
- [`generic-archive-dispatch-reachability.md`](generic-archive-dispatch-reachability.md)：
  ZIP/TAR/GZIP 自然分派、singleton `FT_ARCHIVE` 门控、强制通用 adapter
  重检测及双 Qt5 quiet/verbose 对照（Draft）。
- [`signature-path-filter-behavior.md`](signature-path-filter-behavior.md)：
  private signature-file path comparator 的严格绝对路径语义及公共不可达边界
  （Draft）。
- [`debug-data-dispatch-behavior.md`](debug-data-dispatch-behavior.md)：
  同一 PE 的 resource 正控制、direct debug 正例与 recursive debug 负例
  （Draft）。
- [`legacy-dispatch-oracle.md`](legacy-dispatch-oracle.md)：Amiga Hunk/Atari ST
  的固定源码边界、8-case 生成语料和双 Qt5 oracle 执行门禁（Draft）。
- [`dos-dispatch-reachability.md`](dos-dispatch-reachability.md)：DOS/COM 七个
  公共 detector 成员与 BW DOS16M branch-only 路径的固定源码审计（Draft）。
- [`result-metadata-behavior.md`](result-metadata-behavior.md)：`SCAN_RESULT`
  四个标量字段、四个公共扫描入口的 filename/size/filetype/time 契约及
  Qt5 harness（Draft）。
- [`result-list-behavior.md`](result-list-behavior.md)：`SCAN_RESULT` 的
  records/errors/debug/handlers 四列表、顺序和重复项 Qt5 契约（Draft）。
- [`result-flag-behavior.md`](result-flag-behavior.md)：`SCANSTRUCT` 的
  heuristic/advanced heuristic/unknown 三标记真值表（Draft）。
- [`result-id-behavior.md`](result-id-behavior.md)：`SCANSTRUCT.id`、
  `parentId` 的完整字段及 resource edge/UUID 父子关系（Draft）。
- [`result-enum-behavior.md`](result-enum-behavior.md)：`SCANSTRUCT` 原始
  type/name、数值 enum、规范字符串及 Unknown 边界（Draft）。
- [`source-analysis.md`](source-analysis.md)：模块关系及扫描/规则调用链（Draft）。
- [`rule-compatibility.md`](rule-compatibility.md)：规则语法、内建函数和宿主 API（Draft）。
- [`rule-runtime-spike.md`](rule-runtime-spike.md)：Boa 全库解析、真实复杂规则、宿主绑定和资源限制验证（Draft）。
- [`rquickjs-rule-runtime-spike.md`](rquickjs-rule-runtime-spike.md)：rquickjs/QuickJS-NG 全库执行、sloppy 语义、native 构建和资源限制验证（Draft）。
- [`rquickjs-static-link.md`](rquickjs-static-link.md)：rquickjs/QuickJS-NG 的 Windows/Linux Rust staticlib、C 链接、CRT、系统依赖和许可证闭包（Draft）。
- [`nintendo-certified-rule.md`](nintendo-certified-rule.md)：唯一 legacy 规则的项目生成语料与真实 detect 基线（Draft）。
- [`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)：Binary 数据库分层、init/include 选择、共享引擎生命周期和排序缺陷（Draft）。
- [`rule-orchestration.md`](rule-orchestration.md)：priority 比较器边界、数据库分层、init/include、mode/file-type 过滤、Unknown 及 `CAP-GAP-010` 闭合基线（Draft）。
- [`signature-language.md`](signature-language.md)：signature 文法、固定 oracle、静态/动态调用清单和边界行为（Draft）。
- [`pe-rule-runtime-differential.md`](pe-rule-runtime-differential.md)：真实 PE32 context、`PE.compareEP` 与原样 Cygwin32 规则的 Qt5/Rust 正反截断差分（Draft）。
- [`elf-rule-runtime-differential.md`](elf-rule-runtime-differential.md)：真实 ELF32/ELF64 context、`ELF.compareEP` 与原样 Burneye 规则的 Qt5/Rust 正反截断差分（Draft）。
- [`macho-rule-runtime-differential.md`](macho-rule-runtime-differential.md)：真实 Mach-O64 x86_64/arm64 context、`MACH.compareEP` 与原样 Rust compiler 规则的 Qt5/Rust 差分（Draft）。
- [`dex-rule-runtime-differential.md`](dex-rule-runtime-differential.md)：真实 DEX035 string-table context、`DEX.isDexStringPresent` 与原样 QDBH 规则的 Qt5/Rust 正反截断差分（Draft）。
- [`apk-rule-runtime-differential.md`](apk-rule-runtime-differential.md)：真实 APK/ZIP central-directory context、`APK.isArchiveRecordPresent` 与原样 QDBH 规则的 Qt5/Rust 正反截断差分（Draft）。
- [`archive-rule-runtime-differential.md`](archive-rule-runtime-differential.md)：真实 ZIP metadata context、`Archive.isVerbose`/format getters 与原样 Archive 规则的 Qt5/Rust verbose 门控和截断差分（Draft）。
- [`pdf-rule-runtime-differential.md`](pdf-rule-runtime-differential.md)：真实 PDF object/string context、`PDF.getStringValuesByKey`/header comment 与原样 Tools 规则的 Qt5/Rust 类型、去重和截断差分（Draft）。
- [`rule-syntax-inventory.md`](rule-syntax-inventory.md)：全规则 AST 语法、全局引用和宿主调用形状清单（Draft）。
- [`host-api-inventory.md`](host-api-inventory.md)：XScanEngine C++ slot、继承、默认参数与规则调用覆盖（Draft）。
- [`global-host-api-inventory.md`](global-host-api-inventory.md)：die_script 非格式 native globals、规则顶层函数与直接调用分类（Draft）。
- [`global-host-api-runtime-differential.md`](global-host-api-runtime-differential.md)：真实 `DiE_ScriptEngine` 的 Qt 5/Qt 6 global HostApi 转换、副作用与异常差分（Draft）。
- [`format-host-api-runtime-differential.md`](format-host-api-runtime-differential.md)：真实格式 QObject 的 Qt 5/Qt 6 参数数量、转换、stderr 与异常差分（Draft）。
- [`global-typo-error-behavior.md`](global-typo-error-behavior.md)：两个固定规则未定义 global 的可达性、Qt 5 错误和 CLI framing（Draft）。
- [`script-scope-semantics.md`](script-scope-semantics.md)：Qt Script 跨规则 lexical 环境与 QuickJS 差分（Draft）。
- [`script-state-semantics.md`](script-state-semantics.md)：Qt Script 跨规则 var/function/global 持久状态与 wrapper 风险（Draft）。
- [`c-static-link-spike.md`](c-static-link-spike.md)：Windows/Linux C staticlib、所有权、panic/CRT 和系统依赖验证（Draft）。
- [`rust-toolchain-upgrade-1.97.1.md`](rust-toolchain-upgrade-1.97.1.md)：固定默认 Rust 1.97.1、保留 MSRV 1.88 的 Rust 门禁与 Windows/Linux static-link 复验（Draft）。
- [`cli-dependency-and-license.md`](cli-dependency-and-license.md)：CLI 源码/链接依赖闭包与许可证初审（Draft）。
- [`xarchive-license-closure.md`](xarchive-license-closure.md)：固定 Linux Qt5 CMake CLI 的 XArchive 编译单元、头文件依赖与文件级许可证证据（Draft）。
- [`embedded-compression-origins.md`](embedded-compression-origins.md)：XArchive 聚合 Brotli/Zstandard 的固定官方源码、token 指纹与许可证追溯（Draft）。
- [`rar-decoder-provenance.md`](rar-decoder-provenance.md)：XArchive RAR
  decoder 与固定 UnRAR 7.1.10 的 token 来源、许可证 notice 差异和 Rust
  复用门禁（Draft）。
- [`yara-license-closure.md`](yara-license-closure.md)：XYara 内嵌 YARA v4.5.2 的实际构建闭包、官方内容映射、TLSH/Authenticode/Bison 许可证和 compiler warning（Draft）。
- [`rule-asset-provenance.md`](rule-asset-provenance.md)：Detect release 与 XYara/XPEID/signatures 数据树的逐文件哈希、历史、可见许可信号、CLI 可达性和打包路径（Draft）。
- [`runtime-rule-assets-license.md`](runtime-rule-assets-license.md)：`db`/`db_extra`/
  `db_custom` 的 2,268 文件分发身份、根 MIT/文件级标记、归属信号和未关闭法律
  评审（Draft）。
- [`runtime-png-provenance.md`](runtime-png-provenance.md)：runtime 22 个 PNG
  的原仓库 Git/blob 历史、两次来源提交、C100/R100、PNG metadata、来源时/
  pinned LICENSE 与贡献政策边界（In Review）。
- [`process-benchmark-runner.md`](process-benchmark-runner.md)：严格 plan、输入/
  executable 身份、bounded output、wall time/peak RSS 和统计报告的跨平台进程级
  benchmark 契约（Draft）。
- [`upstream-performance-baseline.md`](upstream-performance-baseline.md)：固定
  Linux Qt5 容器内的 process/database/单文件/batch/nested latency、noise 和
  peak-RSS 描述性基线（In Review）。
- [`upstream-performance-affinity.md`](upstream-performance-affinity.md)：固定
  Linux Qt5 五层 warm suite 的单 WSL2/Linux vCPU affinity 复验、cgroup
  证明、control RSS 采样边界与剩余物理核心/cold 门禁（In Review）。
- [`upstream-build-baseline.md`](upstream-build-baseline.md)：固定 Linux Qt5/qmake CLI 构建与行为实验（Draft）。
- [`upstream-cmake-differential.md`](upstream-cmake-differential.md)：官方 CMake CLI 构建及与 qmake 的原始输出差分（Draft）。
- [`upstream-qt6-differential.md`](upstream-qt6-differential.md)：固定 Qt 6 CMake CLI 构建、Qt 5/Qt 6 原始差分与规则 warning 最小化（Draft）。
- [`qt6-capability-closure-plan.md`](qt6-capability-closure-plan.md)：将现有
  Qt6 证据保守映射到全部 68 项能力，并为 `CAP-GAP-007` 生成可执行的逐项
  闭环清单（In Review）。
- [`qt6-cli-runtime-evidence.md`](qt6-cli-runtime-evidence.md)：固定 Qt5/Qt6
  的 26 样本分派、五样本七 formatter 和 escaping/nested 输出差分，并保留
  PE 的 Qt6 stderr 差异（In Review）。
- [`behavior-baseline.md`](behavior-baseline.md)：确定性安全语料、原始输出哈希和多格式行为（Draft）。
- [`cli-json-schema-inventory.md`](cli-json-schema-inventory.md)：固定 CLI normal/entropy/info/struct JSON 字段、类型、顺序与失败边界（Draft）。
- [`cli-output-boundaries.md`](cli-output-boundaries.md)：固定 JSON/XML/CSV/TSV/plain text 的 Unicode/控制字符转义、嵌套排序和格式缺陷；闭合 `CAP-GAP-004`（Draft）。
- [`scan-option-boundaries.md`](scan-option-boundaries.md)：固定 deep 实际增量、aggressive resource gate、默认 21/aggressive 2001 精确计数及 PE 每目录 1000 项 parser 限制；闭合 `CAP-GAP-005`（Draft）。
- [`cli-special-modes.md`](cli-special-modes.md)：entropy/info/struct 的 schema、优先级、临界熵、层级 filter、格式方法和多目标行为；闭合 `CAP-GAP-001`（Draft）。
- [`cli-path-behavior.md`](cli-path-behavior.md)：多目标、目录递归、输出聚合和错误顺序（Draft）。
- [`special-path-behavior.md`](special-path-behavior.md)：固定 Linux Qt5 的
  NFC/NFD、非 UTF-8 原始字节、控制字符、hidden、前导短横线和目录排序
  （In Review）。
- [`path-filesystem-behavior.md`](path-filesystem-behavior.md)：固定 Linux Qt5 的
  file/directory/dangling symlink、alias 重复、mode-000 权限、depth-64 与
  self-cycle OS 边界（In Review）。
- [`large-directory-behavior.md`](large-directory-behavior.md)：固定 Linux Qt5
  flat/nested 4096-entry 完整枚举、顺序、描述性资源及 CLI 未接线
  `PDSTRUCT` cancellation 的源码边界（In Review）。
- [`path-toctou-behavior.md`](path-toctou-behavior.md)：固定 Linux Qt5 在完整
  枚举后的 symlink old→new 原子替换、unlink、stable controls 与当前路径
  reopen 行为（In Review）。
- [`path-locale-filesystem-behavior.md`](path-locale-filesystem-behavior.md)：
  固定 Linux Qt5 完整 `C`/`C.utf8`/`POSIX` locale 清单与 tmpfs/
  `ext2/ext3` volume 的两个大小写排序 profile，闭合 `CAP-GAP-003`
  （Draft）。
- [`cli-option-behavior.md`](cli-option-behavior.md)：verbose/messages/profiling channel 与 test/create test 遗留入口行为（Draft）。
- [`database-error-behavior.md`](database-error-behavior.md)：数据库缺失/损坏、规则错误和不可读输入（Draft）。
- [`database-archive-cache.md`](database-archive-cache.md)：ZIP 规则数据库边界、发布 CLI cache 可达性，以及 engine cache stale/corrupt/cancel 行为（Draft）。
- [`database-layer-behavior.md`](database-layer-behavior.md)：main/extra/custom 同名规则、分层顺序、加载与运行时 gate（Draft）。
- [`engine-contract-behavior.md`](engine-contract-behavior.md)：engine 过滤/排序/停止/入口，以及 device/subdevice short-read、I/O、seek 和范围边界；闭合 `CAP-GAP-009` 与 `CAP-GAP-011`（Draft）。
- [`nested-scan-behavior.md`](nested-scan-behavior.md)：archive/resource/overlay 的选项可达性、结果树和资源限制（Draft）。
- [`data/cli-dependencies.toml`](data/cli-dependencies.toml)：固定组件依赖边、LICENSE blob 和 bundled code 证据。
- [`data/xarchive-license-closure-linux.json`](data/xarchive-license-closure-linux.json)：XArchive 106 个实际编译单元、217 个依赖文件及许可证/来源标记。
- [`data/embedded-compression-origins.json`](data/embedded-compression-origins.json)：聚合 Brotli/Zstandard 与固定官方 commit/生成物/许可证的内容对照。
- [`data/rar-decoder-origin.json`](data/rar-decoder-origin.json)：固定
  XArchive RAR decoder 的引入历史、UnRAR 7.1.10 镜像、两档 token shingle
  与开放法律评审。
- [`data/yara-license-closure-linux.json`](data/yara-license-closure-linux.json)：YARA 51-object target、109-file dependency closure、官方 v4.5.2/TLSH 来源链和文件级许可证证据。
- [`data/rule-assets.json`](data/rule-assets.json)：五组固定 YARA/PEiD/signature 资产、逐文件历史/哈希、release/component 差异及 CLI/GUI/打包可达性证据。
- [`data/runtime-rule-assets-license.json`](data/runtime-rule-assets-license.json)：
  runtime 三层规则树的 2,268 文件 hash、作者/URL/许可标记和 22 个 PNG 清单。
- [`data/runtime-png-history.json`](data/runtime-png-history.json)：22 个 PNG
  的逐 blob/chunk/CRC、三种历史口径、两次来源 commit 和开放法律评审证据。
- [`data/baseline-corpus.json`](data/baseline-corpus.json)：生成语料的文件名、意图、大小和 SHA-256。
- [`data/output-boundary-fixture.json`](data/output-boundary-fixture.json)：输出转义规则、输入和嵌套语料的 hash-bound 清单。
- [`data/cli-output-boundaries-linux-qt5.json`](data/cli-output-boundaries-linux-qt5.json)：10-case 双 Qt5 formatter oracle 的完整原始 streams、身份和派生事实。
- [`data/cli-output-boundaries-linux-qt5-qt6.json`](data/cli-output-boundaries-linux-qt5-qt6.json)：
  10-case Qt5/Qt6 escaping/nested formatter 完整原始 streams、身份和派生事实。
- [`data/cli-output-matrix-linux-qt5-qt6.json`](data/cli-output-matrix-linux-qt5-qt6.json)：
  26 样本分派与五样本七 formatter 的 Qt5/Qt6 成对流哈希和 detection tree。
- [`data/scan-option-boundary-fixture.json`](data/scan-option-boundary-fixture.json)：deep/aggressive 规则与 1/22/2002-resource PE 的 hash-bound 清单。
- [`data/scan-option-boundaries-linux-qt5.json`](data/scan-option-boundaries-linux-qt5.json)：8-case 双 Qt5 scan-option oracle 的去重原始 streams、身份和派生事实。
- [`data/capability-traceability.json`](data/capability-traceability.json)：68 个稳定
  `CAP-*` 的验证层级、证据路径、平台范围和三个开放 coverage gap。
- [`data/capability-coverage.json`](data/capability-coverage.json)：68 行 × 4 平台
  的 272-cell 闭集分类、三个开放 gap 到能力的显式映射和未分类计数。
- [`data/qt6-capability-closure-plan.json`](data/qt6-capability-closure-plan.json)：
  将固定 Qt6 证据保守映射到全部 68 项能力，并给出剩余逐项实验。
- [`image-dispatch-behavior.md`](image-dispatch-behavior.md)：固定七种非
  JPEG/PNG 图像的自然 Binary fallback、强制 generic Image null adapter 和
  `CAP-GAP-012` 闭合证据。
- [`data/source-only-closure.json`](data/source-only-closure.json)：与当前空
  source-only 闭集严格相等的可执行关闭清单。
- [`data/legacy-dispatch-corpus.json`](data/legacy-dispatch-corpus.json)：
  Amiga Hunk/Atari ST 正例、截断、错误端序和近似 magic 控制的 hash-bound 清单。
- [`data/legacy-dispatch-linux-qt5.json`](data/legacy-dispatch-linux-qt5.json)：
  Amiga 正常分发及 Atari detector-only/Binary fallback 的双 Qt5 成对基线。
- [`data/dos-dispatch-source-audit.json`](data/dos-dispatch-source-audit.json)：
  DOS/COM detector、BW legacy magic、scanner 分支和 property bypass 的
  SHA/line-bound 审计。
- [`data/dos-dispatch-corpus.json`](data/dos-dispatch-corpus.json)：七个公共
  DOS/COM filetype 的 19-case 正例、截断、近似 magic、chain、后缀和大小边界。
- [`data/dos-dispatch-linux-qt5.json`](data/dos-dispatch-linux-qt5.json)：
  七个公共 DOS/COM filetype 的 19-case 双 Qt5 runtime 基线。
- [`data/bw-dispatch-engine-qt5.json`](data/bw-dispatch-engine-qt5.json)：
  BW DOS16M automatic-negative 与 compact-property forced-positive 引擎基线。
- [`data/result-metadata-engine-qt5.json`](data/result-metadata-engine-qt5.json)：
  四个公共扫描入口的 `SCAN_RESULT` 标量字段、filename 语义和原始流哈希。
- [`data/result-list-fixture.json`](data/result-list-fixture.json)：两条重复
  detection、runtime error、parse error 和安全 Binary 输入的逐文件哈希。
- [`data/result-lists-engine-qt5.json`](data/result-lists-engine-qt5.json)：
  四个结果列表的空/非空、顺序、重复项和 handler option runtime 基线。
- [`data/result-flag-fixture.json`](data/result-flag-fixture.json)：normal、
  `~` heuristic、`!` advanced heuristic 与空数据库的逐文件哈希。
- [`data/result-flags-engine-qt5.json`](data/result-flags-engine-qt5.json)：
  三个独立结果 flag 的四行 Qt5 runtime 真值表和原始流哈希。
- [`data/result-ids-engine-qt5.json`](data/result-ids-engine-qt5.json)：
  PE root/resource child 的完整 ID、parent ID、UUID anchor 与 edge 元数据。
- [`data/result-enum-fixture.json`](data/result-enum-fixture.json)：已知别名、
  heuristic、自定义原文与 Unknown fallback 的安全规则和输入哈希。
- [`data/result-enums-engine-qt5.json`](data/result-enums-engine-qt5.json)：
  原始 type/name、数值 enum、规范投影和保留 Unknown 槽位 Qt5 基线。
- [`data/signature-path-fixture.json`](data/signature-path-fixture.json)：
  main/extra 两层同名规则、良性 Binary 输入及七组 path-filter case 的哈希清单。
- [`data/signature-path-engine-qt5.json`](data/signature-path-engine-qt5.json)：
  private comparator 的 exact/empty/missing/case/`..`/basename Qt5 运行时矩阵。
- [`data/path-corpus.json`](data/path-corpus.json)：由基线字节组成的确定性嵌套目录树。
- [`data/special-path-fixture.json`](data/special-path-fixture.json)：确定性
  USTAR 特殊路径语料清单，不提交生成出的 TAR。
- [`data/special-path-engine-qt5.json`](data/special-path-engine-qt5.json)：
  23-case 双 Qt5 特殊路径/非 UTF-8 Oracle 的完整原始 streams、身份和冻结排序。
- [`data/path-filesystem-fixture.json`](data/path-filesystem-fixture.json)：
  symlink、权限、64 层目录与 self-cycle 的 deterministic GNU tar 清单。
- [`data/path-filesystem-engine-qt5.json`](data/path-filesystem-engine-qt5.json)：
  9-case 双 Qt5 文件系统路径 Oracle 的原始 streams、预检与冻结边界。
- [`data/large-path-fixture.json`](data/large-path-fixture.json)：empty、single、
  flat 256/4096 和 nested 4096 的 deterministic materialization plan。
- [`data/large-path-engine-qt5.json`](data/large-path-engine-qt5.json)：5-case 双
  Qt5 大目录 Oracle、完整原始 streams、source cancellation contract 与资源记录。
- [`data/path-toctou-fixture.json`](data/path-toctou-fixture.json)：32 MiB blocker、
  old/new targets、四个 mutation case 与 SIGSTOP/SIGCONT 同步协议。
- [`data/path-toctou-engine-qt5.json`](data/path-toctou-engine-qt5.json)：4-case
  双 Qt5 TOCTOU Oracle、mutation identity、source order 与原始 streams。
- [`data/path-locale-fixture.json`](data/path-locale-fixture.json)：21 个
  locale/case/normalization/非法 UTF-8 basename 与两种 filesystem 的确定性计划。
- [`data/path-locale-filesystem-engine-qt5.json`](data/path-locale-filesystem-engine-qt5.json)：
  3 locale × 2 filesystem × 2 Oracle 的完整顺序、charmap、原始 streams
  与源码契约。
- [`data/database-fixture.json`](data/database-fixture.json)：项目生成的数据库成功/故障 fixture。
- [`data/database-archive-linux-qt5.json`](data/database-archive-linux-qt5.json)：两套固定 Qt5 oracle 的 17-case ZIP 数据库矩阵及两侧原始 stream。
- [`data/database-cache-cli.json`](data/database-cache-cli.json)：发布 CLI cache-disabled 源码身份、删除副作用与 engine cache header 摘要。
- [`data/database-cache-engine-qt5.json`](data/database-cache-engine-qt5.json)：
  固定 Qt5 engine harness 的 cache miss/hit/stale、header/record corruption、
  cancel、write/permission failure 和 8-writer concurrency 十九状态原始报告。
- [`data/database-layer-fixture.json`](data/database-layer-fixture.json)：三层同名/priority 规则的项目生成 fixture 清单。
- [`data/database-layers-engine-qt5.json`](data/database-layers-engine-qt5.json)：固定 Qt5 engine 的三层 materialization、同名保留和 runtime gate 原始报告。
- [`data/nested-corpus.json`](data/nested-corpus.json)：安全的 archive/resource/overlay 嵌套语料清单。
- [`data/archive-iteration-boundary-corpus.json`](data/archive-iteration-boundary-corpus.json)：
  三个 100001-record ISO9660 的确定性哨兵位置、大小和 SHA-256 清单。
- [`data/archive-iteration-boundary-engine-qt5.json`](data/archive-iteration-boundary-engine-qt5.json)：
  aggressive 第 100000 条可达、第 100001 条不可达的固定源码、镜像、原始输出
  和资源报告。
- [`data/archive-adversarial-corpus.json`](data/archive-adversarial-corpus.json)：
  12 个项目生成 ZIP 压缩、加密、畸形和 filter 控制的 hash manifest。
- [`data/archive-adversarial-engine-qt5.json`](data/archive-adversarial-engine-qt5.json)：
  44 次 release/harness default/archive/aggressive 原始输出、源码契约和结构摘要。
- [`data/archive-truncation-corpus.json`](data/archive-truncation-corpus.json)：
  7Z/RAR4/CAB/ISO9660 四个完整控制的 26 个确定性 EOF 前缀及逐文件哈希。
- [`data/archive-truncation-engine-qt5.json`](data/archive-truncation-engine-qt5.json)：
  26-case × 4 模式的 104 次原始输出、源码契约和严格截断边界摘要。
- [`data/archive-structure-corpus.json`](data/archive-structure-corpus.json)：
  四格式 56 个 control/结构字段 mutation 的 changed-byte 与 hash-bound 清单。
- [`data/archive-structure-engine-qt5.json`](data/archive-structure-engine-qt5.json)：
  56-case × 4 模式的 224 次原始输出、源码契约和结构字段行为摘要。
- [`data/archive-multirecord-corpus.json`](data/archive-multirecord-corpus.json)：
  四格式 × 正序/逆序/重名/空首记录的 16 个项目生成两成员 archive 清单。
- [`data/archive-multirecord-engine-qt5.json`](data/archive-multirecord-engine-qt5.json)：
  16-case × 4 模式的 64 次原始输出、固定身份及记录顺序/重名/空成员摘要。
- [`data/iso9660-endian-corpus.json`](data/iso9660-endian-corpus.json)：
  ISO9660 17 个双端序字段 × LE/BE 单侧 alternate 加控制的 35-case 清单。
- [`data/iso9660-endian-engine-qt5.json`](data/iso9660-endian-engine-qt5.json)：
  35-case × 4 模式的 140 次原始输出、固定身份及 LE/BE 冲突行为摘要。
- [`data/archive-format-corpus.json`](data/archive-format-corpus.json)：
  项目生成的七种 7Z 单 coder、x86/ARM64 BCJ+LZMA2、
  BCJ2+LZMA2 no-branch/E8/E9/JCC filter 链、七种基础 coder+7zAES、
  x86/ARM64 BCJ+LZMA2+7zAES、
  BCJ2+LZMA2+4×7zAES、RAR4
  store、CAB Store/MSZIP/LZX、带固定 LGPL 来源切片的 Quantum 与 ISO9660
  fixture 清单。
- [`data/archive-format-engine-qt5.json`](data/archive-format-engine-qt5.json)：
  四十一个 archive/coder 样本的 default/release/archive/aggressive 原始输出、
  六十六个 7Z AES 直接密码 case、固定身份和结构化摘要。
- [`data/rar5-store-corpus.json`](data/rar5-store-corpus.json)：
  两个项目生成 RAR5 Store/solid fixture 的 header、成员、solid 位与 hash-bound
  清单。
- [`data/rar5-store-engine-qt5.json`](data/rar5-store-engine-qt5.json)：
  RAR5 Store 单 PDF 与 solid 双 PDF 的 8 次固定 Qt5 原始输出、源码契约和
  结构化摘要。
- [`data/rar-compressed-fixture-source.json`](data/rar-compressed-fixture-source.json)：
  四个外部非 SFX RAR3/RAR5 压缩样本的固定来源、CC0/creator evidence、
  header/method/solid 结构和开放再分发评审。
- [`data/rar-compressed-engine-qt5.json`](data/rar-compressed-engine-qt5.json)：
  RAR3/RAR5 压缩/solid 的 16-run 固定 engine oracle、原始输出和确定性投影。
- [`data/archive-gap-closure.json`](data/archive-gap-closure.json)：
  六份固定 archive oracle 与 Formats/XScanEngine 源码共同生成的
  `CAP-GAP-006` 机器闭合报告。
- [`data/npm-dispatch-fixture.json`](data/npm-dispatch-fixture.json)：
  项目生成的 NPM 精确路径正例、无效 JSON 正例及路径/大小写近似反例清单。
- [`data/npm-dispatch-engine-qt5.json`](data/npm-dispatch-engine-qt5.json)：
  NPM 直接检测、自动/强制 engine 分派、双 Qt5 release 原始输出及源码/规则
  哈希契约。
- [`data/generic-archive-dispatch-fixture.json`](data/generic-archive-dispatch-fixture.json)：
  项目生成的 ZIP/TAR/GZIP 通用 Archive 分派 fixture 清单。
- [`data/generic-archive-dispatch-engine-qt5.json`](data/generic-archive-dispatch-engine-qt5.json)：
  自动/强制 quiet/verbose 分派、双 Qt5 release 原始输出和源码/规则哈希契约。
- [`data/resource-context-chain-qt5.json`](data/resource-context-chain-qt5.json)：RT_MANIFEST 父扫描、resource context、scan ID 与原样规则结果的四模式端到端基线。
- [`data/subdevice-source-audit.json`](data/subdevice-source-audit.json)：固定 XScanEngine/Formats 源码哈希、resource/overlay 调度及 debug-data 可达性审计。
- [`data/debug-dispatch-fixture.json`](data/debug-dispatch-fixture.json)：
  同时含 RT_MANIFEST resource 与 CodeView/RSDS debug directory 的项目生成 PE。
- [`data/debug-dispatch-engine-qt5.json`](data/debug-dispatch-engine-qt5.json)：
  Formats 枚举、public recursive omission 与 direct debug detection 的 paired
  Qt5 报告。
- [`data/boa-rule-runtime.json`](data/boa-rule-runtime.json)：Boa spike 输入哈希、固定版本和稳定结果摘要。
- [`data/rquickjs-rule-runtime.json`](data/rquickjs-rule-runtime.json)：rquickjs spike 输入哈希、固定版本和稳定结果摘要。
- [`data/rquickjs-static-link.json`](data/rquickjs-static-link.json)：rquickjs staticlib 三条 native smoke、链接依赖和 18-package 许可证清单。
- [`data/context-rule-qt5.json`](data/context-rule-qt5.json)：三条原样 Binary 规则在 resource/debugdata/text context 下的 8-case Qt5 基线。
- [`data/pe-rule-fixture.json`](data/pe-rule-fixture.json)：原样 Cygwin32 PE 规则的项目生成正例、反例和截断 PE32 输入。
- [`data/pe-rule-qt5.json`](data/pe-rule-qt5.json)：固定 XPE/PE_Script/QScriptEngine 的 3-case PE 规则 oracle。
- [`data/elf-rule-fixture.json`](data/elf-rule-fixture.json)：原样 Burneye ELF 规则的项目生成 ELF32/ELF64 正例、反例和截断输入。
- [`data/elf-rule-qt5.json`](data/elf-rule-qt5.json)：固定 XELF/ELF_Script/QScriptEngine 的 6-case ELF 规则 oracle。
- [`data/macho-rule-fixture.json`](data/macho-rule-fixture.json)：原样 Rust compiler Mach-O 规则的项目生成 x86_64/arm64 正例、反例和截断输入。
- [`data/macho-rule-qt5.json`](data/macho-rule-qt5.json)：固定 XMACH/MACH_Script/QScriptEngine 的 4-case Mach-O 规则 oracle。
- [`data/dex-rule-fixture.json`](data/dex-rule-fixture.json)：原样 QDBH DEX 规则的项目生成 string-table 正例、反例和 EOF 截断输入。
- [`data/dex-rule-qt5.json`](data/dex-rule-qt5.json)：固定 XDEX/DEX_Script/QScriptEngine 的 3-case DEX 规则 oracle。
- [`data/apk-rule-fixture.json`](data/apk-rule-fixture.json)：原样 QDBH APK 规则的项目生成 central record 正例、大小写反例和 local-record 截断输入。
- [`data/apk-rule-qt5.json`](data/apk-rule-qt5.json)：固定 XAPK/APK_Script/QScriptEngine 的 3-case APK 规则 oracle。
- [`data/archive-rule-fixture.json`](data/archive-rule-fixture.json)：原样 Archive metadata 规则的项目生成 stored ZIP、quiet 反例和 central-directory-only 输入。
- [`data/archive-rule-qt5.json`](data/archive-rule-qt5.json)：固定 XZip/Archive_Script/QScriptEngine 的 3-case Archive 规则 oracle。
- [`data/pdf-rule-fixture.json`](data/pdf-rule-fixture.json)：原样 PDF Tools 规则的项目生成 literal/hex/name object 与缺失 `endobj` 输入。
- [`data/pdf-rule-qt5.json`](data/pdf-rule-qt5.json)：固定 XPDF/PDF_Script/QScriptEngine 的 3-case PDF 规则 oracle。
- [`data/nintendo-certified-corpus.json`](data/nintendo-certified-corpus.json)：PS3/PS Vita Certified File 分支语料清单。
- [`data/nintendo-certified-baseline.json`](data/nintendo-certified-baseline.json)：双 oracle 原始输出哈希和 detection 摘要。
- [`data/binary-rule-lifecycle.json`](data/binary-rule-lifecycle.json)：固定 Binary records、helper 解析、源码 hash 和比较器环证据。
- [`data/binary-rule-order-linux-qt5.json`](data/binary-rule-order-linux-qt5.json)：固定 qmake/CMake oracle 的 292 条 Binary profiling 执行顺序。
- [`data/rule-orchestration-fixture.json`](data/rule-orchestration-fixture.json)：项目生成的规则编排数据库、输入和期望模式顺序清单。
- [`data/rule-orchestration-linux-qt5.json`](data/rule-orchestration-linux-qt5.json)：固定 qmake/CMake oracle 的规则编排原始哈希与规范化基线。
- [`data/cli-option-behavior-linux.json`](data/cli-option-behavior-linux.json)：固定 qmake/CMake oracle 的 verbose/messages/profiling 与 test/create test 原始 CLI 基线。
- [`data/script-scope-fixture.json`](data/script-scope-fixture.json)：项目生成的跨规则作用域 fixture 清单。
- [`data/script-scope-qt5.json`](data/script-scope-qt5.json)：固定 qmake/CMake oracle 的作用域行为基线。
- [`data/script-state-fixture.json`](data/script-state-fixture.json)：项目生成的跨规则持久状态 fixture 清单。
- [`data/script-state-qt5.json`](data/script-state-qt5.json)：固定 qmake/CMake oracle 的持久状态行为基线。
- [`data/binary-cross-rule-state.json`](data/binary-cross-rule-state.json)：固定 Binary 顺序的跨规则状态静态审计摘要。
- [`data/signature-parser.json`](data/signature-parser.json)：signature 文法、Rust spike、固定 oracle 身份和差分覆盖摘要。
- [`data/signature-oracle-vectors.json`](data/signature-oracle-vectors.json)：89 个项目生成的 XBinary/`Binary_Script` 输入向量。
- [`data/signature-oracle-qt5.json`](data/signature-oracle-qt5.json)：固定 Qt 5 harness 的 89-case 原始结构化基线。
- [`data/signature-static-inventory.json`](data/signature-static-inventory.json)：全规则具名 signature API 调用点和保守静态值清单。
- [`data/net-bytecode-patterns.json`](data/net-bytecode-patterns.json)：固定 PE Generic 规则的 .NET bytecode pattern 有限值域。
- [`data/rule-syntax-inventory.json`](data/rule-syntax-inventory.json)：2235 个规则脚本的 AST、运算符、global 和宿主调用机器清单。
- [`data/host-api-inventory.json`](data/host-api-inventory.json)：固定 XScanEngine 宿主声明、继承和规则 arity 覆盖清单。
- [`data/host-api-arity-qt5.json`](data/host-api-arity-qt5.json)：固定 Qt 5 QObject wrapper 的额外实参与缺失方法异常基线。
- [`data/host-api-arity-qt6.json`](data/host-api-arity-qt6.json)：固定 Qt 6 QObject wrapper 的参数转换、diagnostic 与异常基线。
- [`data/host-api-arity-qt5-qt6.json`](data/host-api-arity-qt5-qt6.json)：两个格式 QObject runtime observation 的逐字段机器差分。
- [`data/global-host-api-inventory.json`](data/global-host-api-inventory.json)：固定 die_script global 注册面、规则函数和 undeclared direct-call 分类。
- [`data/global-host-api-qt5.json`](data/global-host-api-qt5.json)：真实 `DiE_ScriptEngine` 的 Qt 5 native global 转换与副作用基线。
- [`data/global-host-api-qt6.json`](data/global-host-api-qt6.json)：真实 `DiE_ScriptEngine` 的 Qt 6 native global 转换、异常与副作用基线。
- [`data/global-host-api-qt5-qt6.json`](data/global-host-api-qt5-qt6.json)：两个 runtime observation 的逐字段机器差分。
- [`data/global-typo-corpus.json`](data/global-typo-corpus.json)：两个未定义 global 分支的 project-generated 安全最小语料及规则哈希。
- [`data/global-typo-errors-qt5.json`](data/global-typo-errors-qt5.json)：固定 qmake/CMake oracle 的 detection、trailing diagnostic 与原始输出哈希。
- [`data/global-typo-errors-qt5-qt6.json`](data/global-typo-errors-qt5-qt6.json)：固定 Qt 5/Qt 6 oracle 的相同 detection 与 runtime-specific `ReferenceError` 文本。
- [`data/qt5-qt6-cli.json`](data/qt5-qt6-cli.json)：固定 CMake Qt 5/Qt 6 CLI 的基础、安全语料和不可读输入原始差分。
- [`data/qt6-rule-warnings.json`](data/qt6-rule-warnings.json)：Qt6 PE warning 的可重复二分及唯一规则来源。
- [`data/qt-integer-bridge-fixture.json`](data/qt-integer-bridge-fixture.json)：项目生成的四类 Qt 整数返回桥接规则清单。
- [`data/c-static-link.json`](data/c-static-link.json)：C static-link spike 输入哈希、ABI 符号、平台依赖和稳定结果摘要。
- [`data/rust-toolchain-upgrade-1.97.1.json`](data/rust-toolchain-upgrade-1.97.1.json)：默认/MSRV 工具链身份、五个 spike 门禁和六条 native C consumer 复验摘要。

每份文档遵守 [`../README.md`](../README.md) 的证据和状态约定。实验附件如需版本化，应使用文本格式并放入主题对应的子目录。
