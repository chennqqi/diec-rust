# Runtime 规则资产许可证与归属审计

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 范围与结论

本文只审计固定 `diec` CLI 实际加载并且 Rust 项目计划 1:1 同步的
`Detect-It-Easy/db`、`db_extra`、`db_custom` 三棵 runtime 资产树。YARA、
PEiD、SearchSignatures、`dbs_min` 和 `dbs_special` 不在本文范围；其中前三类的
独立证据见 [`rule-asset-provenance.md`](rule-asset-provenance.md)。

固定三棵树共有 2,268 个文件、2,909,316 bytes：

- 2,175 个 `.sg` 和 60 个无扩展程序，共 2,235 个规则程序、
  2,902,881 bytes；该数量与 runtime 全库 isolated-eval 口径完全相同；
- 2 个 `.ini`、3 个 `.json`、6 个 `.txt` 和 22 个 PNG，共 33 个随规则分发
  的 metadata/visual 资产；
- 全部文件进入 path/length/content/hash 组合 tree digest，没有按扩展名或
  文本可见性遗漏分发输入。

`Detect-It-Easy` 根 `LICENSE` 是 MIT License，SHA-256 为
`be0fe2d727cd0a754fb0b2fdc579ead8f19ef575840b4daef221be201701eaad`。
规则文本中严格许可标记只有
`db/PE/__GenericHeuristicAnalysis_By_DosX.7.sg:73` 的一条显式 MIT 声明；
没有发现严格的 GPL、Apache、BSD 或 SPDX 标记。

这些事实仍不足以关闭许可证门禁。后续
[`runtime-png-provenance.md`](runtime-png-provenance.md) 已把 22 个 PNG 收窄到
两个原仓库来源 commit、一个 R100 rename、两个 C100 copy、20 个唯一 blob
及有效 PNG metadata，但根 MIT 和 Git author 仍不能由技术审计自动转换为
“每个 artwork 来源均完成法律确认”；Author 和 URL 注释也不能证明
第三方内容的许可证。机器报告因此固定
`legal_review_complete = false`，`P0-BLOCK-004` 继续 Open。

## 固定身份

| 项目 | 值 |
| --- | --- |
| Detect-It-Easy commit | `c2c17dfa5ea4e078ba31eab55d87430c96622fb6` |
| component lock SHA-256 | `9fabcaf6a0062fcae7007ea5af13a98876e8a6e08b3e2e4727fdff06d974c63c` |
| combined tree SHA-256 | `20f2b74effc2bdaf069e3b2e13060432b8890d38364511f5cde56a337348bfda` |
| machine report | [`data/runtime-rule-assets-license.json`](data/runtime-rule-assets-license.json) |
| generator | [`audit_runtime_rule_assets.py`](../../tools/upstream/audit_runtime_rule_assets.py) |

tree digest 对按 UTF-8 bytes 排序后的每个相对路径依次加入：

```text
path || NUL || u64_be(length) || content || raw_sha256(content)
```

这不是 Git tree object ID；算法显式加入路径、长度、内容和单文件 hash，便于在
subtree、归档或 release staging 目录中使用相同方式复算。

## 三层清单

| Tree | Files | Bytes | Tree SHA-256 |
| --- | ---: | ---: | --- |
| `db` | 2,124 | 2,832,469 | `8000138ce96a6a892aaa3cba8dee60960694c42dcfa24b3787f02c25858f1650` |
| `db_extra` | 142 | 76,651 | `77c4e0da796baa9a71ec1a699a37e61ed73783c0d3dc5d49044185dc80a38ec1` |
| `db_custom` | 2 | 196 | `36c10cd4d87826c78f07a0c801c1ae374f4b6364936056d44a045e9150ba5815` |

`db_custom` 为空规则模板树仍属于 CLI 默认数据库路径；不能因为没有 `.sg` 就从
发布物身份中删除。PNG 也不由规则 runtime 执行，但如果项目原样分发完整 runtime
树，它们仍是许可证/SBOM 输入。

## 可见归属信号

生成器只把行首 `Author:`/`Authors:` 当作作者标记，不从检测结果字符串推断作者：

- 2,101 个文件含作者标记；
- 原始写法形成 65 个唯一作者字符串；
- 7 个文件的注释行含 copyright 文本；
- URL 只按 hostname 汇总，不将链接目标自动当作复制来源；
- 一条语法畸形 URL 被显式计为 `<invalid-url>`，不会使审计中止或被静默丢弃。

作者字符串保持上游写法；例如同一作者可能有空格、括号或联系信息差异。本报告
不擅自规范化/合并，因为这会丢失归属证据。机器报告只保存每个作者对应的文件数
和排序路径清单 SHA-256，不复制 2,101 条路径到文档。

## 二进制资产

22 个非文本文件全部具有 PNG signature；本报告保存每个相对路径、长度和
SHA-256。后续离线 Git/PNG 审计已证明它们全部与固定原仓库 blob 逐字节相等，
由 DosX 身份在两个 2025-07-26 commit 中引入，来源时根目录已有 MIT LICENSE；
全部为有效 16×16 RGBA8 PNG，只有三条 paint.net Software metadata，没有嵌入
许可或创作者信息。完整证据和三种历史口径见
[`runtime-png-provenance.md`](runtime-png-provenance.md)。

这些证据回答当前字节、首次引入历史和仓库级许可上下文，但不能证明底层 artwork
原创/授权。后续发布方案可以选择：

1. 如果 CLI/runtime 只需要规则程序和必要 metadata，先用可重复运行实验证明 PNG
   不可达，再通过 ADR 定义精确最小分发树；
2. 如果承诺 1:1 分发完整 `db*` 树，则由发布/法律责任人评审已固定 PNG 历史，
   并在 NOTICE/SBOM 中保留必要归属；
3. 不能在未记录行为/分发差异的情况下静默删除或替换 PNG。

## 复现

```powershell
python tools/upstream/audit_runtime_rule_assets.py
python tools/tests/test_audit_runtime_rule_assets.py
```

生成器完全离线，只读取固定 subtree 与 `components.lock.toml`。回归测试会：

- 重新扫描全部 2,268 个文件，并要求与提交报告逐字段相等；
- 将 component/rules commit、lock hash 和根 LICENSE hash 绑定；
- 将 2,235/2,902,881 与规则 runtime 全库口径交叉验证；
- 逐个复算 22 个 PNG 的长度/hash/signature；
- 独立 PNG 历史测试逐个复算 Git blob、chunk CRC、metadata、commit/policy/
  LICENSE 身份和 C100/R100 chain；
- 固定显式许可 marker、作者/版权计数和四条限制；
- 要求 `legal_review_complete` 保持 false，防止技术报告被误当成批准。

## 尚未关闭

- 根 MIT 对全部历史贡献及 22 个 PNG artwork 的书面适用性评审；当前 PNG
  Git/blob 历史已固定，但不等于底层创作来源获确认；
- 上游完整历史中非 maintainer 贡献的许可/贡献约定；
- 最终 Rust release 是分发完整 `db*` 还是经 ADR 证明的最小 runtime asset set；
- NOTICE、SBOM、source offer/attribution 的最终内容；
- 发布/法律责任人的书面结论。

在这些证据完成前，本报告只收窄 `P0-BLOCK-004`，不关闭它。
