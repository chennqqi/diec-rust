# 调研文档

本目录只记录上游事实、实验结果和证据，不提前写入本项目的实现决策。

Phase 0 计划形成：

- [`upstream-baseline.md`](upstream-baseline.md)：版本、构建、submodule、依赖和许可证（Draft）。
- [`capability-matrix.md`](capability-matrix.md)：CLI/engine 能力与证据索引（Draft）。
- [`capability-coverage-report.md`](capability-coverage-report.md)：68 个稳定能力在
  Linux Qt5/Qt6、Windows 和 macOS 上的 runtime/source-only、corpus-missing
  与 platform-missing 闭集报告（Draft）。
- [`source-only-closure-plan.md`](source-only-closure-plan.md)：剩余 10 个 Linux
  Qt5 source-only 能力的缺失证据、fixture、harness、强断言和关闭方式（Draft）。
- [`legacy-dispatch-oracle.md`](legacy-dispatch-oracle.md)：Amiga Hunk/Atari ST
  的固定源码边界、8-case 生成语料和双 Qt5 oracle 执行门禁（Draft）。
- [`dos-dispatch-reachability.md`](dos-dispatch-reachability.md)：DOS/COM 七个
  公共 detector 成员与 BW DOS16M branch-only 路径的固定源码审计（Draft）。
- [`source-analysis.md`](source-analysis.md)：模块关系及扫描/规则调用链（Draft）。
- [`rule-compatibility.md`](rule-compatibility.md)：规则语法、内建函数和宿主 API（Draft）。
- [`rule-runtime-spike.md`](rule-runtime-spike.md)：Boa 全库解析、真实复杂规则、宿主绑定和资源限制验证（Draft）。
- [`rquickjs-rule-runtime-spike.md`](rquickjs-rule-runtime-spike.md)：rquickjs/QuickJS-NG 全库执行、sloppy 语义、native 构建和资源限制验证（Draft）。
- [`rquickjs-static-link.md`](rquickjs-static-link.md)：rquickjs/QuickJS-NG 的 Windows/Linux Rust staticlib、C 链接、CRT、系统依赖和许可证闭包（Draft）。
- [`nintendo-certified-rule.md`](nintendo-certified-rule.md)：唯一 legacy 规则的项目生成语料与真实 detect 基线（Draft）。
- [`binary-rule-lifecycle.md`](binary-rule-lifecycle.md)：Binary 数据库分层、init/include 选择、共享引擎生命周期和排序缺陷（Draft）。
- [`rule-orchestration.md`](rule-orchestration.md)：priority、数据库分层、init/include、mode/file-type 过滤和 Unknown 的端到端基线（Draft）。
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
- [`yara-license-closure.md`](yara-license-closure.md)：XYara 内嵌 YARA v4.5.2 的实际构建闭包、官方内容映射、TLSH/Authenticode/Bison 许可证和 compiler warning（Draft）。
- [`rule-asset-provenance.md`](rule-asset-provenance.md)：Detect release 与 XYara/XPEID/signatures 数据树的逐文件哈希、历史、可见许可信号、CLI 可达性和打包路径（Draft）。
- [`runtime-rule-assets-license.md`](runtime-rule-assets-license.md)：`db`/`db_extra`/
  `db_custom` 的 2,268 文件分发身份、根 MIT/文件级标记、归属信号和未关闭法律
  评审（Draft）。
- [`process-benchmark-runner.md`](process-benchmark-runner.md)：严格 plan、输入/
  executable 身份、bounded output、wall time/peak RSS 和统计报告的跨平台进程级
  benchmark 契约（Draft）。
- [`upstream-build-baseline.md`](upstream-build-baseline.md)：固定 Linux Qt5/qmake CLI 构建与行为实验（Draft）。
- [`upstream-cmake-differential.md`](upstream-cmake-differential.md)：官方 CMake CLI 构建及与 qmake 的原始输出差分（Draft）。
- [`upstream-qt6-differential.md`](upstream-qt6-differential.md)：固定 Qt 6 CMake CLI 构建、Qt 5/Qt 6 原始差分与规则 warning 最小化（Draft）。
- [`behavior-baseline.md`](behavior-baseline.md)：确定性安全语料、原始输出哈希和多格式行为（Draft）。
- [`cli-json-schema-inventory.md`](cli-json-schema-inventory.md)：固定 CLI normal/entropy/info/struct JSON 字段、类型、顺序与失败边界（Draft）。
- [`cli-special-modes.md`](cli-special-modes.md)：entropy/info/struct 的 schema、优先级和边界行为（Draft）。
- [`cli-path-behavior.md`](cli-path-behavior.md)：多目标、目录递归、输出聚合和错误顺序（Draft）。
- [`cli-option-behavior.md`](cli-option-behavior.md)：verbose/messages/profiling channel 与 test/create test 遗留入口行为（Draft）。
- [`database-error-behavior.md`](database-error-behavior.md)：数据库缺失/损坏、规则错误和不可读输入（Draft）。
- [`database-archive-cache.md`](database-archive-cache.md)：ZIP 规则数据库边界、发布 CLI cache 可达性，以及 engine cache stale/corrupt/cancel 行为（Draft）。
- [`database-layer-behavior.md`](database-layer-behavior.md)：main/extra/custom 同名规则、分层顺序、加载与运行时 gate（Draft）。
- [`nested-scan-behavior.md`](nested-scan-behavior.md)：archive/resource/overlay 的选项可达性、结果树和资源限制（Draft）。
- [`data/cli-dependencies.toml`](data/cli-dependencies.toml)：固定组件依赖边、LICENSE blob 和 bundled code 证据。
- [`data/xarchive-license-closure-linux.json`](data/xarchive-license-closure-linux.json)：XArchive 106 个实际编译单元、217 个依赖文件及许可证/来源标记。
- [`data/embedded-compression-origins.json`](data/embedded-compression-origins.json)：聚合 Brotli/Zstandard 与固定官方 commit/生成物/许可证的内容对照。
- [`data/yara-license-closure-linux.json`](data/yara-license-closure-linux.json)：YARA 51-object target、109-file dependency closure、官方 v4.5.2/TLSH 来源链和文件级许可证证据。
- [`data/rule-assets.json`](data/rule-assets.json)：五组固定 YARA/PEiD/signature 资产、逐文件历史/哈希、release/component 差异及 CLI/GUI/打包可达性证据。
- [`data/runtime-rule-assets-license.json`](data/runtime-rule-assets-license.json)：
  runtime 三层规则树的 2,268 文件 hash、作者/URL/许可标记和 22 个 PNG 清单。
- [`data/baseline-corpus.json`](data/baseline-corpus.json)：生成语料的文件名、意图、大小和 SHA-256。
- [`data/capability-traceability.json`](data/capability-traceability.json)：68 个稳定
  `CAP-*` 的验证层级、证据路径、平台范围和 12 个显式 coverage gap。
- [`data/capability-coverage.json`](data/capability-coverage.json)：68 行 × 4 平台
  的 272-cell 闭集分类、十二个 gap 到能力的显式映射和未分类计数。
- [`data/source-only-closure.json`](data/source-only-closure.json)：与当前十个
  source-only 行严格相等的可执行关闭清单。
- [`data/legacy-dispatch-corpus.json`](data/legacy-dispatch-corpus.json)：
  Amiga Hunk/Atari ST 正例、截断、错误端序和近似 magic 控制的 hash-bound 清单。
- [`data/dos-dispatch-source-audit.json`](data/dos-dispatch-source-audit.json)：
  DOS/COM detector、BW legacy magic、scanner 分支和 property bypass 的
  SHA/line-bound 审计。
- [`data/path-corpus.json`](data/path-corpus.json)：由基线字节组成的确定性嵌套目录树。
- [`data/database-fixture.json`](data/database-fixture.json)：项目生成的数据库成功/故障 fixture。
- [`data/database-archive-linux-qt5.json`](data/database-archive-linux-qt5.json)：两套固定 Qt5 oracle 的 17-case ZIP 数据库矩阵及两侧原始 stream。
- [`data/database-cache-cli.json`](data/database-cache-cli.json)：发布 CLI cache-disabled 源码身份、删除副作用与 engine cache header 摘要。
- [`data/database-cache-engine-qt5.json`](data/database-cache-engine-qt5.json)：固定 Qt5 engine harness 的 cache miss/hit/stale/corrupt/cancel 九状态原始报告。
- [`data/database-layer-fixture.json`](data/database-layer-fixture.json)：三层同名/priority 规则的项目生成 fixture 清单。
- [`data/database-layers-engine-qt5.json`](data/database-layers-engine-qt5.json)：固定 Qt5 engine 的三层 materialization、同名保留和 runtime gate 原始报告。
- [`data/nested-corpus.json`](data/nested-corpus.json)：安全的 archive/resource/overlay 嵌套语料清单。
- [`data/resource-context-chain-qt5.json`](data/resource-context-chain-qt5.json)：RT_MANIFEST 父扫描、resource context、scan ID 与原样规则结果的四模式端到端基线。
- [`data/subdevice-source-audit.json`](data/subdevice-source-audit.json)：固定 XScanEngine/Formats 源码哈希、resource/overlay 调度及 debug-data 可达性审计。
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
