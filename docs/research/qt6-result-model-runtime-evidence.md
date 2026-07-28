# Linux Qt6 结果模型运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

五个固定 Linux amd64 Qt6 engine harness 完整导出 `SCAN_RESULT`/`SCANSTRUCT`
的 scalar、四类列表、flags、IDs、type/name enum 和 record metadata。
所有原 Qt5 关系断言在 Qt6 上通过，所有进程 exit 0、stderr 为空。

逐字段 Qt5/Qt6 比较只得到五处已分类差异：

- metadata：一个 `nScanTime` 实测值，属于非确定性耗时；
- IDs：root UUID、child UUID 和 child parent UUID 三个随机值；shape、非空、
  唯一性及 parent 指向关系保持；
- lists：parse-error 文本从 Qt5
  `1: SyntaxError: Parse error` 变为 Qt6
  ``2: SyntaxError: Expected token `}'``；
- flags 与 enums：完整 harness output 无差异。

比较器保留这些原始值，不删除字段。除上述路径外的全部 harness output、
relationships 和 fixture identity 相同。

`CAP-RESULT-006` 由两组已固定证据组合闭合：Qt5/Qt6 global HostApi 的 20 个
共同正常 record 完全相同，覆盖非空 version/info 及 priority 30/70/90；
engine-contract 覆盖 signature basename、absolute signature path 及 priority
12/30/100。Qt5 缺参调用额外产生三个 `"undefined"` record、Qt6 不产生，
该已知 runtime 差异仍完整保留，不被当作正常 record 契约。

## 固定身份

机器报告：
[`data/result-model-engine-qt6.json`](data/result-model-engine-qt6.json)，
SHA-256
`bb61f7c1bf25fa54c8f25047d9461b6184c08fe24a61fd512be423a84981ba6f`。

| Profile | Qt6 image ID | Binary SHA-256 | Cases / records |
| --- | --- | --- | ---: |
| metadata | `sha256:50a28ac93d422b86246be12da48e0c25ed71786cb8a069b32d436fcf44679cfa` | `3a24f83a064c299a9e164a8e73b1f484f28fcc66ec282610a7d56898ad3fda9c` | 4 |
| lists | `sha256:7b3f4b9f9a87a6cf07a2c9a6dafdf32cc5020071174bcb0e89f2e86842645444` | `8e8843c9fa1262a6afcd5a9bcc3dce917fbfe0aff4919ee0318c098e0e46a0fe` | 2 |
| IDs | `sha256:5a705ac19dbcff4ff3d72710dfaa4542401cb4e04414d896606e8812f2105bc4` | `48f2f815fa136ef42b06a45a13012d572249d79a404ee97ac9464e33b224429c` | 2 records |
| flags | `sha256:7476806c3f776636993bf0c48911557dcde1d677c2d960a5336ca81101153fe6` | `7a41a74417e57bd9f2acabdd2dca130ff1bc3509fe1b6d5605a52f32b49c7d03` | 4 |
| enums | `sha256:ea9e04d6ad279f7c058e58571ace05313c95ff3cb4e4c8a05d322d999810c434` | `a2f71a34656eea872a95e1061995701b1b0adc3fb5a03dec4f5694fb0cfc5afe` | 4 |

五个镜像均从
`diec-rust/upstream-oracle-cmake-qt6:74eaf505` 派生，以
`--network=none` 构建，不下载依赖；OCI revision 均为
`74eaf505c250ab47e709024e9dc41657cd8f2254`。

统一 wrapper `tools/upstream/probe_qt6_result_model.py` 动态加载五个原 Qt5
探针，替换固定 image 后仍调用原 fixture、运行和关系验证逻辑。bundle 同时
hash-bound 五个原探针、五份 Qt5 报告、两份 HostApi 报告和 Qt6
engine-contract 报告。

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-RESULT-001` scalar metadata；
- `CAP-RESULT-002` records/errors/debug/handlers lists；
- `CAP-RESULT-003` heuristic/advanced/unknown flags；
- `CAP-RESULT-004` record and parent IDs；
- `CAP-RESULT-005` raw/numeric/canonical enums；
- `CAP-RESULT-006` version/info/rule/priority metadata。

完成本批时汇总为 58 项 complete、3 项 partial、7 项 missing。后续
signature-path 与 debug-dispatch 批次已将当前汇总推进到 60/3/5，见
[`qt6-debug-dispatch-runtime-evidence.md`](qt6-debug-dispatch-runtime-evidence.md)；
`CAP-GAP-007` 仍保持开放。

## 重现

先由已有生成器分别创建 result-list、result-flag、result-enum 和 nested
corpus，然后构建五个 Qt6 Dockerfile：

```text
docker build --network=none \
  -f tools/upstream/Dockerfile.result-<profile>-harness-qt6 \
  -t diec-rust/result-<profile>-harness-qt6:74eaf505 \
  tools/upstream
```

采集：

```text
python tools/upstream/probe_qt6_result_model.py \
  --list-fixture <result-list-fixture> \
  --id-corpus <nested-corpus> \
  --flag-fixture <result-flag-fixture> \
  --enum-fixture <result-enum-fixture> \
  --raw-dir <untracked-raw> \
  --output docs/research/data/result-model-engine-qt6.json
```

能力清单生成器重新计算五份 harness output 的字段级 diff，并严格要求差异路径
只能是上述时间、UUID 和精确 parse diagnostic；修改结果而不修改 comparison
摘要同样会失败。

## 限制

- 仅覆盖 Linux amd64、Qt 6.4.2 和固定 fixture；
- 耗时与 UUID 只验证类型和关系，不固定具体值；
- parse diagnostic 是明确平台差异，Rust compatibility profile 仍需决定以
  Qt5 原文、Qt6 原文或类型化错误为目标，并通过 ADR 固定；
- 本批不覆盖 formatter 对完整 engine model 的无损表示，formatter 行已有独立
  CLI 证据。
