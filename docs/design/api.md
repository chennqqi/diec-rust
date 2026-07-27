# Rust API、结果与 CLI 契约

Status: Draft

Last updated: 2026-07-27

## 1. 状态与证据

本文定义 Phase 0 的 API 草案，不是已发布的 semver 承诺。类型名和字段在设计门禁
通过前仍可调整；错误分类、所有权、确定性、兼容输出与安全限制不可在实现中静默
弱化。

本文依赖：

- [`architecture.md`](architecture.md)：crate 边界、数据流和有界 work queue；
- [`c-abi.md`](c-abi.md)：C ownership、status、线程和 static library；
- [`behavior-baseline.md`](../research/behavior-baseline.md)：普通扫描和输出基线；
- [`cli-path-behavior.md`](../research/cli-path-behavior.md)：多目标、目录和 partial exit；
- [`cli-special-modes.md`](../research/cli-special-modes.md)：entropy/info/struct 分派；
- [`database-error-behavior.md`](../research/database-error-behavior.md)：数据库和 I/O 错误；
- [`nested-scan-behavior.md`](../research/nested-scan-behavior.md)：嵌套 file-part 及顺序；
- [`rule-compatibility.md`](../research/rule-compatibility.md)：规则结果和脚本诊断。

固定上游 CLI 有意保留在 compatibility renderer 中，但其无效多目标 JSON、stdout
错误混入、静默数据库失败不是核心 API 语义。双输出面的理由见
[`ADR 0003`](decisions/0003-dual-output-contract.md)。

## 2. API 目标

- 一个同步、无 GUI 的 Rust scan service。
- 数据库构建与扫描分离，已验证数据库 immutable、可复用。
- borrowed bytes、owned source 和 path 入口最终进入同一 checked input。
- 单个输入返回完整、确定性、可追溯的树形结果。
- 明确区分请求失败、完整结果、受限的 partial result 和 node-local 诊断。
- 取消、timeout 和所有资源限制都有类型化配置与稳定语义。
- CLI legacy 输出可逐字节差分；canonical 输出始终是有效单文档。
- C ABI 是本 API 的适配，不反向决定 Rust 内部 layout。

## 3. 非目标

- 不稳定公开 parser、runtime context、cache 或第三方 crate 类型。
- v1 不提供 async/streaming scan、callback writer 或动态 plugin API。
- 不承诺 `ScanReport` 的内存 layout、enum discriminant 或 Rust ABI 稳定。
- 不把批量目录枚举塞入核心单文件 scanner。
- 不用一个无类型字符串错误覆盖数据库、I/O、script、limit 和 cancellation。
- 不以 canonical schema 伪装成固定上游 JSON；两者有独立名字和测试。

## 4. 顶层 Rust API 草案

公共入口由 `diec-engine` 暴露，示意签名如下：

```rust
pub struct DatabaseBuilder { /* private */ }
pub struct Database { /* immutable, private */ }
pub struct Scanner { /* reusable, !Sync until proven otherwise */ }

impl DatabaseBuilder {
    pub fn new() -> Self;
    pub fn add_layer(&mut self, layer: DatabaseLayer) -> Result<&mut Self, DatabaseError>;
    pub fn build(self) -> Result<Database, DatabaseError>;
}

impl Scanner {
    pub fn new(database: Arc<Database>) -> Result<Self, ScannerError>;
    pub fn scan(
        &mut self,
        source: ScanSource<'_>,
        request: &ScanRequest,
        cancel: &CancellationToken,
    ) -> Result<ScanReport, ScanError>;
}

pub fn scan_once(
    database: Arc<Database>,
    source: ScanSource<'_>,
    request: &ScanRequest,
    cancel: &CancellationToken,
) -> Result<ScanReport, ScanError>;
```

这些签名是设计表达，不要求 Phase 1 原样复制。必须保持的语义：

- `Database` build 成功后 immutable，clone/`Arc` 不复制规则源字节。
- `Scanner::scan` 需要 `&mut self`，表达不可重入；在 runtime ADR 前不承诺 `Send`
  或 `Sync`。
- `scan_once` 调用同一个内部 scan service，不复制检测逻辑。
- scan 是同步的；source 只借用到返回。
- cancellation token 可从其他线程 request，scan 只读其 atomic 状态。
- 不提供隐式 global default database 或 mutable process-wide options。

## 5. Database API

```rust
pub enum DatabaseLayerKind {
    Main,
    Extra,
    Custom,
}

pub enum DatabaseSource {
    Directory(PathBuf),
    Archive(PathBuf),
    Embedded { name: String, bytes: Arc<[u8]> },
}

pub struct DatabaseLayer {
    pub kind: DatabaseLayerKind,
    pub source: DatabaseSource,
    pub required: bool,
}

pub struct DatabaseMetadata {
    pub engine_version: String,
    pub upstream_commit: String,
    pub rule_commit: String,
    pub manifest_sha256: String,
    pub layers: Vec<DatabaseLayerMetadata>,
}
```

真实 API 应用 newtype/constructor 保证 path、name 和 hash 有效，示意中的 public
fields 不代表最终可绕过校验。legacy layer 顺序固定为 main、extra、custom；
每层先形成自身 execution ordinal，再按层 append。相同 signature filename
不是 override key：跨层同名 records 全部保留，并携带 layer/source identity。
证据见
[`database-layer-behavior.md`](../research/database-layer-behavior.md)。

build 是事务性的：

- required layer 不存在、不可读、archive 无效或 manifest/hash 不匹配时失败；
- optional layer 失败也产生可检查 diagnostic，不能静默消失；
- empty database 与 database not found 是不同状态；
- unknown syntax、include failure、parse error 不得仅计数后继续；
- literal include cycle 返回带完整 path/source 的 build error；动态 cycle 由
  active stack 返回 typed diagnostic，不能依赖 VM/native stack overflow；
- build 失败不返回可扫描的 `Database`；
- metadata 保存每层 provenance、规则计数和诊断摘要。

如果未来需要“加载成功规则并报告坏规则”的 permissive 模式，必须是显式
`DatabasePolicy`，默认仍为 strict，并且差分矩阵分别测试。

## 6. ScanSource 与输入 identity

```rust
pub enum ScanSource<'a> {
    Bytes {
        data: &'a [u8],
        identity: InputIdentity,
    },
    ByteSource {
        source: &'a dyn ByteSource,
        identity: InputIdentity,
    },
    Path(&'a Path),
}

pub struct InputIdentity {
    pub display_name: Option<String>,
    pub logical_path: Option<String>,
}
```

path 入口负责打开和读取 metadata 后转为 checked source。核心 API 使用
`Path`，支持平台原生路径；C v1 的 UTF-8 path 限制只属于 FFI。canonical JSON
不得假设 native path 是 UTF-8：

- 可表示时写 UTF-8 `path`；
- 否则写 `path_display` 的明确 lossy 值和平台编码后的无损 byte/code-unit 表示；
- legacy renderer 按固定 oracle 平台的路径行为处理。

`identity` 是展示/provenance，不参与格式识别。调用 bytes API 不得伪造文件系统
metadata；规则需要 extension 时使用显式 logical name，并在结果中标记来源。

## 7. ScanRequest

```rust
pub struct ScanRequest {
    pub mode: ScanMode,
    pub detection: DetectionOptions,
    pub nesting: NestingOptions,
    pub limits: ScanLimits,
    pub diagnostics: DiagnosticOptions,
}

pub enum ScanMode {
    Detect,
    Entropy,
    Info,
    Struct(StructSelector),
}

pub struct DetectionOptions {
    pub deep: bool,
    pub heuristic: bool,
    pub aggressive: bool,
    pub all_types: bool,
    pub format_display: bool,
    pub hide_unknown: bool,
}

pub struct NestingOptions {
    pub resources: bool,
    pub overlays: bool,
    pub archives: bool,
}
```

`ScanRequest::default()` 使用安全、文档化且版本化的 project defaults，不从环境变量
读取。上游 flag 到字段的映射由 CLI adapter 显式完成：

- 上游 `--recursivescan` 映射 resources + overlays，不表示目录枚举；
- archive 是独立 engine 能力，不能暗中绑定 recursive；
- mode 分派保持 `entropy > struct > info > detect` 的 legacy 优先级；
- Rust typed API 一次只能选择一个 `ScanMode`，避免矛盾组合。

`aggressive` 只改变兼容策略阈值，不能关闭 hard safety limits。

## 8. ScanLimits

```rust
pub struct ScanLimits {
    pub timeout: Duration,
    pub max_input_bytes: u64,
    pub max_total_read_bytes: u64,
    pub max_total_decompressed_bytes: u64,
    pub max_single_allocation_bytes: u64,
    pub max_nodes: u64,
    pub max_diagnostics: u64,
    pub max_archive_entries: u64,
    pub max_depth: u32,
    pub max_queue_items: u64,
    pub script: ScriptLimits,
}
```

每个字段有非零安全 hard maximum；调用方可降低，不能越过编译/发布策略上限。
`Duration::ZERO` 在 Rust API 中不表示“无限”，而表示使用 project default。
需要禁用某个 soft deadline 时使用显式 enum，而不是魔法值；hard allocation、
depth 和 integer limits 永远存在。

`ScriptLimits` 至少控制 heap、stack、instruction/fuel 和 runtime deadline。
数据库 load 也有独立 `DatabaseLimits`，防止在 scan 前耗尽资源。

limits 是全 scan 累计预算。child work 不重置额度。所有触发点记录：

- `LimitKind`；
- configured limit、observed/requested value；
- scan stage 和 node；
- 结果是否完整。

默认值、aggressive 倍率和上游 off-by-one 兼容将在 benchmark/queue spike 后冻结，
不在 Draft 中猜测数字。

## 9. Cancellation 与 deadline

```rust
#[derive(Clone)]
pub struct CancellationToken { /* atomic, private */ }

impl CancellationToken {
    pub fn new() -> Self;
    pub fn cancel(&self);
    pub fn is_cancelled(&self) -> bool;
}
```

token 是 one-way、幂等的。Rust API 不提供 scan 期间 reset；复用时创建新 token，
避免 reset 与 reader race。C ABI 的 reset 若保留，只能在没有 scan 引用时调用。

scanner 在 I/O、probe、parser 大循环、解压、规则执行和 work queue 边界检查。
runtime interrupt 同时观察 token 与 monotonic deadline。取消优先级：

1. 调用前已取消：不开始扫描，返回 `ScanError::Cancelled`。
2. 执行中取消：停止创建新 work，安全清理 runtime，返回 `Cancelled`。
3. deadline 与 cancel 同时可见：返回先被上下文记录的终止原因；测试使用注入 clock
   固定顺序。

cancel/timeout 不返回成功 `ScanReport`，避免调用方误用不确定截断点的结果。错误
details 可以报告停止 stage 和已消耗预算，但不暴露部分 detections。可确定地完成
某个 child 后遇到 node/count hard limit，则按下一节返回带 `Limited` 状态的报告。
固定上游并非如此：callback false 和 `_breakScan()` 会保留当前规则结果，调用前
已停止还会产生 `Unknown`，同时 `PDSTRUCT` 标记 stopped/not-success。因此本段
是 modern API 候选差异，而非上游事实；证据与接受门禁见
[`engine-contract-behavior.md`](../research/engine-contract-behavior.md) 和
[`ADR 0009`](decisions/0009-cancellation-result-contract.md)。

## 10. ScanReport 与 completion

```rust
pub struct ScanReport {
    pub schema_version: SchemaVersion,
    pub engine: EngineMetadata,
    pub database: DatabaseIdentity,
    pub request: EffectiveRequest,
    pub input: InputMetadata,
    pub completion: Completion,
    pub nodes: Vec<ScanNode>,
    pub root: NodeId,
    pub diagnostics: Vec<Diagnostic>,
    pub usage: ResourceUsage,
}

pub enum Completion {
    Complete,
    Limited { reason: LimitReached },
}
```

返回 `Ok(report)` 表示 report 自洽、可序列化，不表示每条规则都命中或没有 node
diagnostic。`Limited` 只用于确定性边界：例如已经完成前 N 个有序 entry，准备加入
N+1 时触发 node/entry/depth/decompressed cap。report 必须标出未处理原因和位置。

以下情况返回 `Err` 且无 report：

- request 无效、根输入无法打开/读取；
- database/runtime 初始化失败；
- 根输入在建立可用 root 前超过 limit；
- cancel、timeout、allocation failure；
- internal invariant 或 panic boundary。

script parse error 默认在 database build 阶段失败。单规则 runtime exception 的
默认策略仍是开放门禁：若上游会继续其他规则，兼容实现可将其记录为 node
diagnostic 并继续；不得静默忽略。策略需固定规则差分后冻结。

C ABI 中 `LIMIT_EXCEEDED` 表示无可用 report 的 hard failure；带
`Completion::Limited` 的自洽 report 返回 `OK`，limit metadata 位于 canonical
JSON。这样保持“非 OK 时 out_result 为 null”的所有权契约。

## 11. Node、detection 与 provenance

```rust
pub struct NodeId(u32);

pub struct ScanNode {
    pub id: NodeId,
    pub parent: Option<NodeId>,
    pub child_ordinal: u32,
    pub part: FilePart,
    pub provenance: Provenance,
    pub range: ByteRange,
    pub format_candidates: Vec<FormatCandidate>,
    pub detections: Vec<Detection>,
    pub diagnostics: Vec<DiagnosticId>,
    pub children: Vec<NodeId>,
}

pub struct Detection {
    pub file_type: FileType,
    pub kind: DetectionKind,
    pub name: String,
    pub version: Option<String>,
    pub info: Option<String>,
    pub display: String,
    pub rule: Option<RuleIdentity>,
    pub heuristic: bool,
}
```

最终字段需从上游 schema inventory 继续细化，但以下语义冻结：

- `NodeId` 只在所属 report 内有效，不序列化内存地址或随机 UUID。
- parent/children 双向关系必须一致，children 按发现 ordinal。
- offset/size 是相对根输入还是父 view 必须由字段名区分，不复用含糊字段。
- `FilePart` 能表达 root、resource、debug-data、overlay、stream/archive entry
  及 unknown。能够表示不等于默认调度：legacy-compatible recursive 按固定上游
  只调度 resource/overlay。
- detection 保留上游原始拼写和 display，不自动修正 `Complier` 等文本。
- format candidate 与 rule detection 是不同集合。
- unknown/hideunknown 是显式 detection 表示，不通过缺字段猜测。
- rule identity 保存 source path、database layer 和稳定 rule id/hash。

所有字符串均有长度预算。无效 UTF-8 内容使用 bytes/escaped 表示，不做未经标记的
lossy 转换。

## 12. Diagnostic 与错误分类

```rust
pub struct Diagnostic {
    pub severity: Severity,
    pub code: DiagnosticCode,
    pub stage: ScanStage,
    pub node: Option<NodeId>,
    pub byte_range: Option<ByteRange>,
    pub rule: Option<RuleIdentity>,
    pub message: String,
}

pub enum ScanError {
    InvalidRequest { field: &'static str, reason: String },
    Io(IoError),
    Database(DatabaseError),
    Unsupported(UnsupportedError),
    LimitExceeded(LimitReached),
    Cancelled(TerminationContext),
    Timeout(TerminationContext),
    Script(ScriptError),
    AllocationFailed,
    Internal(InternalError),
}
```

public error code/variant 是程序判断依据，message 只用于展示且不保证逐字节稳定。
错误应保留 source chain，但 canonical JSON 不泄漏本机绝对路径、内存地址或
平台敏感 debug 数据，除非调用方显式请求并标为非稳定。

分类必须区分：

- not found、permission denied、short read 和 changed-during-read；
- database not found、empty、invalid archive、hash mismatch；
- unknown syntax、parse、include、host API 和 runtime exception；
- unsupported format/feature 与 malformed input；
- 每一种 limit、cancel 和 timeout；
- caller error 与 internal invariant。

畸形或未知文件不是顶层错误：只要安全扫描完成，返回 `Complete` report，其中可有
unknown detection 或 parser diagnostic。

Rust error 与 C ABI 的初始映射如下；C 数值以 `c-abi.md` 为准：

| Rust outcome/error | C ABI status |
| --- | --- |
| `Ok(Complete)` / `Ok(Limited)` | `DIEC_STATUS_OK` |
| invalid request/argument | `DIEC_STATUS_INVALID_ARGUMENT` |
| input/path error | `DIEC_STATUS_IO` |
| database build/init | `DIEC_STATUS_DATABASE` |
| unsupported feature/syntax | `DIEC_STATUS_UNSUPPORTED` |
| 无可用 report 的 hard limit | `DIEC_STATUS_LIMIT_EXCEEDED` |
| cancelled | `DIEC_STATUS_CANCELLED` |
| deadline | `DIEC_STATUS_TIMEOUT` |
| scan-level script failure | `DIEC_STATUS_SCRIPT` |
| allocation failure | `DIEC_STATUS_ALLOCATION_FAILED` |
| internal invariant | `DIEC_STATUS_INTERNAL` |

`WRONG_THREAD`、`BUSY`、`ABI_MISMATCH` 和 `PANIC` 是 C adapter/boundary 状态，
不伪造为正常 Rust engine error。

## 13. Canonical JSON schema

canonical JSON 是库、FFI 和现代 CLI 的稳定数据面，与上游 legacy JSON 分开。
顶层对象按固定顺序包含：

```text
schema_version
engine
database
request
input
completion
root
nodes
diagnostics
usage
```

规则：

- UTF-8、无 BOM；FFI byte view 不含结尾 NUL。
- integer 不转成浮点；所有 offset/size/budget 使用非负整数。
- finite 浮点使用冻结的最短 round-trip 表示；NaN/Infinity 不允许进入 schema。
- optional 缺失与 JSON `null` 的语义逐字段定义，不能混用。
- object key order 和 array order固定；serializer 不依赖 map iteration。
- canonical bytes 以 `\n` 结尾与否在 `testing.md` golden 前冻结。
- schema version 与 engine/database/ABI version 相互独立。
- profiling/timing 如加入，放入明确 non-canonical extension，默认关闭。

初始 schema 在 `testing.md` 建立 JSON Schema、golden corpus 和跨平台 byte equality
后才能从 Draft 变为 Accepted。

## 14. Batch 与目录枚举

单文件 scanner 不枚举目录。`diec-cli` 使用独立 `TargetExpander`：

```rust
pub struct BatchRequest {
    pub targets: Vec<OsString>,
    pub traversal: TraversalPolicy,
    pub scan: ScanRequest,
}

pub struct BatchReport {
    pub items: Vec<BatchItem>,
    pub diagnostics: Vec<BatchDiagnostic>,
    pub completion: BatchCompletion,
}
```

顺序规则：

- positional target 保持用户顺序；
- 每个目录使用明确的跨平台排序键和 depth-first 策略；
- 重复 target 默认不去重，以兼容上游；
- modern mode 在每个 item 中保存 path/result/error，不把错误文本拼进 JSON；
- legacy mode 复现固定平台已验证的 filename prefix 和 partial stdout。

安全 traversal 必须有目录深度、文件数、总字节和 deadline；默认不跟随 directory
symlink/junction。该行为可能偏离上游无界递归，必须在 CLI safety ADR 或 ADR 0003
评审时明确。不可读 entry 产生 item diagnostic，是否继续由 policy 决定。

## 15. CLI 命令面

初始 binary 名为 `diec`，保留上游兼容 flags，并增加不冲突的现代输出：

```text
diec [SCAN OPTIONS] [OUTPUT OPTIONS] TARGET...
diec --showdatabase
diec --showstructs
diec --version
```

输出 profile：

- `--output legacy-auto|legacy-json|legacy-xml|legacy-csv|legacy-tsv|legacy-text`：
  compatibility renderer；
- `--output json`：单目标 canonical JSON；多目标 canonical `BatchReport`；
- `--output ndjson`：每个 target 一个独立 canonical item，适合 streaming batch；
- `--output text`：现代无颜色文本；`--color auto|always|never` 单独控制颜色。

为保持现有兼容基线，直接使用上游 legacy formatter flags 时进入 legacy profile。
modern `--output` 与 legacy formatter flags 同时出现是 usage error，不猜优先级。
未指定输出时的最终默认 profile 仍是 ADR 0003 的开放门禁；oracle 测试必须显式
使用 legacy profile，不能让默认变化隐藏兼容回归。

`--directory-recursion`/traversal policy 与 `--recursivescan` 分开。help 明确后者只
控制输入内部 resource/overlay。archive scan 使用独立 `--archives`。

entropy、info 和 struct 共享 ScanReport envelope，但 mode-specific payload 不
强行伪装成 detections。legacy renderer 保留专用 formatter 优先级和空文件边界。

## 16. CLI stdout、stderr 与退出码

modern profile：

- 成功数据只写 stdout；
- diagnostics 和进度只写 stderr，structured stdout 永远保持有效；
- `--quiet` 不删除 JSON 中的 diagnostic；
- 多目标 JSON 始终是一个 `BatchReport`，空目录也是有效空 items array；
- stdout write/pipe failure 是 I/O exit，不继续无意义扫描。

建议稳定退出码分类：

| Code | 含义 |
| ---: | --- |
| 0 | 全部请求完成；可包含 unknown detection |
| 1 | batch partial：至少一项失败或受限，其他项有结果 |
| 2 | usage/invalid request |
| 3 | database load/validation |
| 4 | input/path I/O，且无成功 item |
| 5 | unsupported feature/runtime |
| 6 | resource limit |
| 7 | cancelled |
| 8 | timeout |
| 9 | script/runtime failure |
| 10 | internal/panic |

数值仍是 Draft；冻结时需与 C status 映射表和 shell 约定评审。single item 的
`Completion::Limited` 返回 6；batch 同时有成功项时返回 1，并在每项保留原因。

legacy profile 使用固定上游 exit/stdout/stderr 映射，包括缺失+存在继续扫描、
filename prefix、特殊模式优先级和已验证的无效多文档输出。安全硬上限、panic 或
无法复刻的平台边界不能伪装成上游成功；这些偏差记录 diagnostic、非零 exit 和
差分 waiver。

## 17. 兼容级别

每个 CLI 差分 case 标记：

- `Exact`：exit、stdout、stderr 逐字节相同；
- `Semantic`：结构、顺序和字段相同，仅文档化的非语义表示不同；
- `SafetyDeviation`：因 hard limit、symlink、编码或资源保护有意偏离；
- `Unsupported`：尚未实现且显式报错，不能静默回退。

核心 API 不暴露“忽略所有错误以匹配上游”的总开关。兼容转换只在 legacy CLI
adapter；规则字符串、排序和 detection tree 等语义仍由同一 report 提供。

## 18. 线程、所有权与并发

- `Database` 计划为 `Send + Sync`，须由 runtime 实现证明。
- `Scanner` 初始 `!Sync`；是否 `Send` 在 runtime ADR 后决定。
- 同一 `Scanner` 不并发调用，Rust 的 `&mut self` 静态阻止常规误用。
- `ScanReport` immutable owned，计划为 `Send + Sync`，不借用 scanner/runtime。
- `CancellationToken` 为 `Clone + Send + Sync`。
- parallel batch 使用 scanner-per-worker，有界 worker pool 和输入 ordinal merge。

不允许 result 持有 source raw pointer、mmap borrow 或 runtime handle。需要保存的
小段证据必须在预算内复制或用 root-owned backing store 维持明确生命周期。

## 19. 版本与兼容

独立版本：

- Rust crate semver；
- canonical result schema version；
- C ABI version；
- database/manifest/cache version；
- 固定 upstream/rules commit identity。

Rust semver 不能替代 schema version。schema major 改变字段语义或删除字段；minor
只允许 additive 且旧 reader 可忽略的字段。legacy profile 名称应携带 upstream
baseline identity，升级基线需保留旧 oracle 或明确迁移。

## 20. 测试契约

- API compile tests：所有权、borrow、Send/Sync 和不可重入预期。
- error table tests：每个 error/diagnostic 到 C status、CLI exit 和 JSON code。
- canonical golden：所有安全 corpus、嵌套树、错误、limited 和跨平台序列化。
- legacy golden：固定 oracle 的 raw exit/stdout/stderr，不只比较解析后 JSON。
- cancellation：调用前、各 stage、runtime interrupt 和 deterministic fake clock。
- limits：每种边界的 `limit-1/limit/limit+1`，验证 partial 与 hard error。
- path batch：顺序、重复、空目录、missing+existing、symlink 和非 UTF-8。
- FFI：非 OK 时 result null；OK/limited report 的 canonical JSON 与 Rust 相同。

`testing.md` 必须定义哪些字段允许规范化，并证明不会隐藏层级、顺序、规则错误或
offset/size 差异。

## 21. 开放问题与冻结门禁

- `ScanReport` 的完整字段 inventory 和 canonical JSON Schema。
- runtime exception 是 node diagnostic 继续，还是 scan-level error。
- 同层 ZIP duplicate、完全相同 sort key，以及 directory/ZIP 混合层的精确顺序
  （跨层同名 directory records 已固定为全部保留且不 override）。
- project default limits、aggressive 倍率及 `Limited` 的允许触发点。
- Scanner 是否 `Send`，database 是否可无条件 `Sync`。
- modern 与 legacy 的无参数默认 profile。
- native path 在 canonical JSON 的跨平台无损编码。
- modern CLI exit code 数值和 batch fail-fast/continue 默认值。
- directory symlink、permission、TOCTOU 和 changed-during-read policy。
- modern canonical entropy/info/struct 是否进入同一 schema major 或使用 mode
  payload schema；legacy CLI compatibility 已由 `semantic-result-v1` 的封闭
  mode union 表示，不替代该 modern API 决策。

上述项目必须由固定 baseline、spike 或 `testing.md` 的可执行用例关闭；不能仅凭
实现方便作决定。

## 22. API 验收条件

- Rust API、canonical schema、C status 和 CLI exit 有完整映射表及测试。
- 单文件、batch、partial、limited、cancel 和 timeout 没有含糊返回状态。
- 所有 source 入口使用同一 checked input 和 scan service。
- legacy profile 覆盖固定上游 raw output；modern structured output 始终有效。
- CLI/FFI 不复制检测、嵌套、排序或诊断逻辑。
- 资源默认值和边界由可重复实验支持。
- API、ADR 0003 与 `testing.md` 完成评审后，本文才可标记 Accepted。
