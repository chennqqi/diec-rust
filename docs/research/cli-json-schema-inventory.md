# 固定上游 CLI JSON schema inventory

Status: Draft

Upstream: horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254

Last updated: 2026-07-27

## 1. 目的与边界

本文只记录固定上游 CLI 可观察 JSON 的事实，用于 Phase 0 差分语义投影。它不把
上游 JSON 当作本项目 modern canonical API，也不声称已经覆盖 engine-only
harness、未来 GUI 或尚未物化组件的全部内部字段。

证据来自：

- 固定 subtree
  `upstream/DIE-engine/src/console/main_console.cpp:110-190,292-343`；
- 26 个默认扫描基线与输出/开关矩阵
  [`behavior-baseline.md`](behavior-baseline.md)；
- entropy/info/struct 矩阵
  [`cli-special-modes.md`](cli-special-modes.md)；
- 保存完整未重排嵌套 stdout 的
  [`resource-context-chain-qt5.json`](data/resource-context-chain-qt5.json)；
- stdout 前 profiling/messages 与 stdout 后 rule error 的
  [`cli-option-behavior.md`](cli-option-behavior.md) 和
  [`database-error-behavior.md`](database-error-behavior.md)；
- 多目标、空目录、partial failure 和 filename prefix 的
  [`cli-path-behavior.md`](cli-path-behavior.md)。

## 2. 分支与 formatter 不是一个统一 schema

`main_console.cpp:121-170` 按 `entropy > info/struct > normal scan` 选择执行分支。
entropy 与 info/struct 的 formatter 优先级是
`JSON > XML > CSV > TSV > text`；普通扫描在
`main_console.cpp:178-190` 使用
`CSV > JSON > TSV > XML > plain text > colored text`。因此 case 必须显式冻结
输出种类，投影器不能只看到一个 JSON object 就猜测含义。

`main_console.cpp:110-119` 在多文件时先向 stdout 写 filename prefix。
`--messages` 又在 `main_console.cpp:337-343` 把 error/warning/info signals 接到
stdout。JSON document 前后都可能有其他 bytes，多目标还可能有多个 document；
只调用一次 `json.loads(stdout)` 会丢失兼容行为。

## 3. 普通扫描 JSON

顶层对象严格观测为：

```text
detects: array<scan-node | detection>
```

`scan-node` 的观测字段为：

```text
filetype: string
info: string
offset: decimal string
parentfilepart: string
size: decimal string
values: array<scan-node | detection>
```

`detection` 的观测字段为：

```text
info: string
name: string
string: string
type: string
version: string
```

`resource-context-chain-qt5.json` 保存了 root PE32 node、Resource child node 与
leaf detection 的完整 stdout，可复验递归 union 和数组顺序。offset/size 在上游
JSON 中是十进制字符串，不是 JSON integer。Phase 0 语义投影同时保存原字符串和
经严格无符号十进制解析的 u64；原始 JSON bytes/hash 仍由 framing 保留，所以前导
零或表示变化不会被隐藏。

已观察的语义边界包括：

- `detects` 顺序承载 all-types 顺序；
- `values` 混合 detection 与 child scan-node，数组顺序承载规则/child 顺序；
- heuristic 由 `type` 的 `~` 前缀和显示串 `(Heur)` 可观察；
- 普通 Unknown 使用 `type/name == "Unknown"`；
- `--hideunknown` 可把 scan-node 整体折叠成 `detects[]` 的顶层 detection：
  type/name/version/info 为空、`string` 保留 filetype，不能把它当作缺少
  detection；
- display `string` 包含上游拼写、空白和 format 选项影响，不能重建后替代；
- input open failure 另有 `{"error": "<message>"}` 对象，不等于
  `{"detects":[]}`。

CLI JSON 不暴露 rule source path、database layer、rule hash 或 priority。语义
模型把这两项记为明确 unavailable，而不能由 detection 文本猜测。engine harness
若能观察这些字段，需要独立 schema inventory 后新增有类型 variant。

### 3.1 hideunknown 根级 union 复验

2026-07-27 使用项目生成的 `minimal.elf` 和固定本机 oracle image
`diec-rust/upstream-oracle-cmake:74eaf505`
（image ID
`sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040`）
离线运行：

```text
python tools/corpus/generate_baseline_corpus.py <temporary-corpus>
docker run --rm --network=none -v <temporary-corpus>:/corpus:ro \
  diec-rust/upstream-oracle-cmake:74eaf505 \
  /opt/die-build/src/console/diec \
  --json --hideunknown \
  --database /opt/die-source/Detect-It-Easy/db \
  --extradatabase /opt/die-source/Detect-It-Easy/db_extra \
  --customdatabase /opt/die-source/Detect-It-Easy/db_custom \
  /corpus/minimal.elf
```

结果中的唯一 `detects[0]` 精确字段为
`info=""`、`name=""`、`string="ELF64"`、`type=""`、`version=""`，没有
`filetype/offset/parentfilepart/size/values`。因此根 `detects` 和 node 内
`values` 都必须是 `scan-node | detection` 的有序 union；依据 key presence
区分 variant，未知字段仍拒绝。

## 4. Entropy JSON

`cli-special-modes.md` 固定的顶层字段为：

```text
total: finite number
status: string
records: array<entropy-record>
```

每个 record 严格包含：

```text
name: string
offset: non-negative integer
size: non-negative integer
entropy: finite number
status: string
```

records 是 format memory map 的非 virtual 区域，顺序和数值均有语义。不能对浮点
值擅自设置 tolerance；阈值边界尚未完成实验，仍是调研缺口。

## 5. Info 与 Struct JSON

两者顶层均为 `{"data": ...}`。`data` 是 string 或递归 object：

- `--info` 通常是 `data.Info.<field> = string`；
- `--struct Hash` 等使用相同树形 formatter；
- 未知 struct 精确返回 `{"data": ""}`。

所有已观察叶子都是 string，包括 Size。object key 的观测顺序在 formatter 间存在
差异，所以投影把 object 转为有序 `{name,value}` entries，而不是对 key 排序后
比较。任意非 string/object leaf 当前都明确成为 projection failure。

## 6. 原始 streams 与失败

语义投影必须同时携带：

- termination；
- stdout 的全部 framing segments；
- stderr 和可选 runtime log；
- 每个 raw segment 按 LF 单调拆分的有序 line record；body 使用精确 UTF-8 或
  无法 decode 时的标准 base64，`none`/`lf`/`crlf` 单独保留结尾；
- 每个 segment、stream、execution verification、framing 和 contract 的 hash。

模型把真正参与两侧结构比较的 output/termination/streams 放在 `comparison`
子树；producer revision/executable 和 evidence hashes 留在同一 artifact 的
provenance 字段中，但不参与 semantic equality。否则 upstream 与 Rust 两侧会因
来源本来就不同而产生伪差异。

未知字段、未知 JSON shape、document 数量不符或 framing limit 都产生显式
`projection_failure`，同时保留原始 parsed value/bytes 引用。它们不得降级为空
成功。

## 7. v1 覆盖与开放项

Phase 0 `semantic-result-v1` 覆盖固定 CLI 的：

- normal scan、递归 detection tree、all-types 顺序和 Unknown/heuristic；
- entropy；
- info/struct；
- normal scan 的结构化 open error；
- 无 JSON 的 raw 模式；
- JSON 前后 diagnostics、多 document、stderr/runtime log 和所有 termination。

以下内容没有被本文外推为已闭合：

- engine-only result 中可观察的 rule identity/priority、handlers 和 debug records；
- PE/ELF/Mach-O/DEX format-specific struct 的畸形及非空集合变体；通用方法、
  11 个方法可达性和空集合、packed entropy 临界浮点已由
  [`cli-special-modes.md`](cli-special-modes.md) 固定；
- Windows/macOS 的 native path 与非 Unicode filename 表示；
- modern canonical `ScanReport` 的完整字段与 schema；
- engine-only/modern variant 的 full differential report integration；typed
  legacy comparator、exact waiver audit 和 planned multi-case report 已实现。

遇到这些 shape 时 v1 必须失败并保留证据；新增 variant 前先补固定源码/实验与
golden，不能放宽为任意 JSON。
