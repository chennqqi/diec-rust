# Runtime PNG 历史来源与 Metadata 审计

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-28

## 范围与结论

本文只审计固定 `Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`
runtime `db/_icons` 中、已由
[`runtime-rule-assets-license.md`](runtime-rule-assets-license.md) 固定字节身份的
22 个 PNG。审计完全离线，直接遍历本地 Git 对象中的原仓库路径和 commit
ancestry，不从 subtree merge commit 猜测来源。

22 个当前路径可追溯到两个原仓库提交：

| Commit | 时间 | Author/Committer | 资产引入数 | Subject |
| --- | --- | --- | ---: | --- |
| `62432a2608cf114a8ae881fbad40bb8e2e3335fc` | 2025-07-26T01:49:24+03:00 | `DosX <collab@kay-software.ru>` | 18 | `Add icon images for various detection types` |
| `ae8ec5903a3bf1c3c6c4e674a37b84e7e97dc91a` | 2025-07-26T13:11:05+03:00 | `DosX <collab@kay-software.ru>` | 4 | `Add new icon files and rename library icon` |

两次提交的 author 与 committer 身份/时间相同，都是固定 component commit 的祖先；
当时仓库根 `LICENSE` 均声明 MIT，SHA-256
`5203a1e5b50c6fcaf9127174aecf01fb179a296a85cb963735b3895693f887ad`，
copyright 年份为 2012–2025。固定 component commit 的 MIT LICENSE 后来把年份
更新为 2012–2026，SHA-256
`be0fe2d727cd0a754fb0b2fdc579ead8f19ef575840b4daef221be201701eaad`；
两者不是同一 blob。
两次提交均无 GPG signature 和 `Signed-off-by` trailer。

这些事实显著收窄了“PNG 历史未知”，但不证明底层 artwork 是提交者原创，也不把
根 MIT 自动转换为每个 PNG 的法律结论。机器报告继续固定
`legal_review_complete = false`，`P0-BLOCK-004` 保持 Open。

机器报告：
[`runtime-png-history.json`](data/runtime-png-history.json)，SHA-256
`379b713476e3289ea369372d1c77aba7f0c574255d07b3d53168cf5cd242ef3b`。

## 三种历史口径

Git rename/copy detection 会改变“首次出现”的含义，报告因此同时保存三种计数：

| 口径 | 首个 commit | 第二个 commit | 解释 |
| --- | ---: | ---: | --- |
| asset introduction | 18 | 4 | rename 继续原资产；copy 创建新资产 |
| current path first | 17 | 5 | `library, module.png` 当前路径在 rename 时出现 |
| blob lineage first | 20 | 2 | C100 copy 继续追溯相同 blob 的更早来源 |

具体关系：

- `db/_icons/library.png` 在第二个提交以 `R100` 改名为
  `db/_icons/library, module.png`，内容未变；
- `archive.png` 是 `other.png` 的 `C100` copy；
- `package.png` 是 `tool.png` 的 `C100` copy；
- 22 个路径只有 20 个唯一 Git blob；
- history 中没有任何 add 后的 `M` 内容修改。

报告保留每个资产的 `changes_newest_first`，不会把 Git 的相似度判断简化成未经
说明的“首次贡献”。

## PNG 结构与嵌入 Metadata

审计器独立解析所有 PNG chunk 并复算 CRC：

- 全部为 16×16、8-bit RGBA、non-interlaced；
- 全部 chunk CRC 有效，IEND 后无额外 bytes；
- 19 个文件的 chunk 序列为 `IHDR/pHYs/IDAT/IEND`；
- `image.png`、`package.png`、`tool.png` 另有
  `sRGB/gAMA/tEXt`；
- 三条 tEXt 仅为 `Software=paint.net 4.0.3` 一条和
  `Software=paint.net 4.0.2` 两条；
- 没有 PNG text chunk 包含 license、copyright、author、creator、source 或
  SPDX 归属词。

`paint.net` metadata 只说明编码工具字符串，不能作为 artwork 来源或许可证明。

## 贡献政策边界

两个图标来源 commit 的 tree 中没有 CLA、DCO、CONTRIBUTING 或 CONTRIBUTORS
候选文件。固定 component commit 后来包含
`CONTRIBUTING.md`，其 blob SHA-256 为
`c207432fced507cc5f0c2cb428a6346f7422016f6a62ab46fb8d1e944db90f9d`；
文本描述 issue/PR/测试流程，但没有：

- 贡献许可授予或 copyright 条款；
- Contributor License Agreement；
- Developer Certificate of Origin；
- `Signed-off-by` 要求。

因此不能用后来加入的 PR 流程文件反推 2025-07-26 两次提交的许可承诺。

## 固定与验证内容

报告和测试绑定：

- component lock 与固定 Detect-It-Easy commit；
- 原 runtime asset 报告 SHA-256；
- 22 个 subtree 文件与固定原仓库 commit blob 逐字节相等；
- 每个文件的 SHA-256、Git blob OID、IHDR、chunk/CRC、text metadata；
- 每个路径的 `--follow -M` change chain；
- 两个 commit 的 parent、author、committer、时间、subject、message hash、
  signature/sign-off 状态和当时根 LICENSE blob；
- contribution policy 在 origin/pinned tree 的差异；
- 18/4、17/5、20/2 三种历史计数，以及 C100/R100/无 M 事实。

任何当前字节、Git 对象、history status、metadata、LICENSE 或政策文件变化都会
使审计测试失败。

## 复现

```powershell
python tools\upstream\audit_runtime_png_history.py
python tools\tests\test_audit_runtime_png_history.py
```

该工具不访问网络；完整原始 Git history 必须已随 subtree component 对象存在于
本地 object database。

## 尚未关闭

- 需要上游/贡献者或法律评审确认 artwork 的原创/授权来源和根 MIT 的适用性；
- 未查询 GitHub PR、issue、review、账号签名或网页端贡献条款；这些属于外部
  forge evidence，后续获取时必须固定 URL/ID/时间并保存可审计摘要；
- 最终发布是否包含 PNG，仍取决于最小 runtime asset set 的行为证明和 ADR；
- NOTICE/SBOM 中对 DosX、hors 及 PNG 的最终归属文本尚未评审；
- 没有 release owner 或 legal approver 的书面结论。

本报告只关闭“当前字节没有原始 Git 历史证据”这一技术缺口，不关闭许可证门禁。
