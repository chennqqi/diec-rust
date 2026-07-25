# 上游同步设计

Status: Accepted  
Last updated: 2026-07-25

## 目标

在本仓库中保留可审计的 DIE-engine 上游快照，并能够在上游更新后：

- 查看主仓库发生了哪些变化。
- 获取新的 submodule gitlink SHA。
- 判断规则、扫描引擎、格式解析器和 CLI 是否需要同步。
- 在升级兼容基线前运行差分测试。

## 决策

将 `horsicq/DIE-engine` 以 squash subtree 导入：

```text
upstream/DIE-engine/
```

配置只读语义的远端名称：

```text
upstream-die -> https://github.com/horsicq/DIE-engine.git
```

新 clone 需要执行：

```sh
git remote add upstream-die https://github.com/horsicq/DIE-engine.git
git remote set-url --push upstream-die DISABLED
```

初始 subtree 固定到：

```text
74eaf505c250ab47e709024e9dc41657cd8f2254
```

subtree 内容仅作为上游参考与变更跟踪来源，不直接成为 diec-rust 的编译输入。

当前导入提交记录：

| Item | Value |
| --- | --- |
| Local merge commit | `5f39bfba` |
| Squashed subtree commit | `438a02af` |
| `git-subtree-split` | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Tree entries | 621 |
| Nested gitlinks | 58 |

## 重要限制

DIE-engine 使用 58 个 git submodule。Git subtree 导入主仓库时：

- 顶层普通文件会进入 `upstream/DIE-engine/`。
- submodule 路径只保存 gitlink SHA。
- `Detect-It-Easy/db`、`XScanEngine`、`Formats`、`die_script` 等 submodule 内容不会随主 subtree 展开。
- subtree 内的 `.gitmodules` 只是上游证据，不能自动管理这些嵌套 gitlink。

因此，不能把“DIE-engine subtree 已更新”解释为“规则和核心组件内容已更新”。

## 组件锁定清单

后续同步工具应生成机器可读 lock manifest，至少记录：

```text
component
repository URL
commit SHA
upstream gitlink path
content role
license
local materialization strategy
```

Phase 0 期间继续以 [`../research/upstream-baseline.md`](../research/upstream-baseline.md) 记录核心组件 SHA。正式同步工具建立后，文档引用生成的 lock manifest，不再人工重复全部 SHA。

## 更新流程

更新前先只获取远端：

```sh
git fetch upstream-die master
```

比较当前基线和候选版本：

```sh
git diff --submodule=log \
  74eaf505c250ab47e709024e9dc41657cd8f2254..upstream-die/master
```

调研并确定新的固定 SHA 后，执行：

```sh
git subtree pull \
  --prefix=upstream/DIE-engine \
  upstream-die <new-fixed-sha> \
  --squash
```

随后必须：

1. 比较 `.gitmodules` 和所有 gitlink。
2. 更新组件 lock manifest。
3. 单独同步受影响的规则或核心组件内容。
4. 更新 `docs/research/upstream-baseline.md`。
5. 运行规则完整性、构建和差分测试。
6. 以独立提交记录上游升级，禁止混入功能修改。

禁止直接对 `upstream/DIE-engine/` 做项目实现修改。若需要研究性注释，写入 `docs/research/`；若必须维护上游补丁，将补丁保存为独立、可重放的 patch，并记录原因。

## 组件内容的后续方案

以下方案留待 Phase 0 评审：

- 对 `Detect-It-Easy`、`XScanEngine`、`Formats`、`die_script` 等关键仓库分别建立 sibling subtree。
- 仅 vendor 运行所需规则，并用同步工具从固定 component SHA 复制和校验。
- 将完整 recursive checkout 保留在 CI/cache 外部，只在本仓库提交 lock manifest。

选择标准：

- 规则必须保持原始字节与文件名。
- 本仓库大小和 clone 成本可控。
- 上游升级 diff 可审计。
- 不要求使用者理解或初始化嵌套 git submodule。
- 构建和发布不依赖网络。

## 为什么使用 squash

主仓库有大量与 GUI 和 submodule bump 相关的历史。Squash subtree：

- 保留每次同步对应的上游 SHA。
- 让本仓库历史集中在兼容基线升级。
- 避免导入全部上游提交历史。

代价是不能在本仓库直接逐提交遍历上游历史；需要时通过 `upstream-die` remote 查询。
