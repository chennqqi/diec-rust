# Upstream snapshots

本目录保存固定版本的上游参考内容和组件锁定清单，不是 diec-rust 的实现目录。

- `DIE-engine/`：主仓库 squash subtree。
- `Detect-It-Easy/`：规则和发布数据 sibling squash subtree。
- `components.lock.toml`：全部 58 个直接 gitlink，以及关键组件的角色和物化方式。

离线验证：

```sh
python3 tools/verify_upstream.py
```

Windows 也可以使用：

```powershell
python tools/verify_upstream.py
```

校验器验证：

- lock 格式及 SHA。
- lock、DIE-engine gitlink 与 `.gitmodules` 的路径集合完全一致。
- 全部 gitlink commit 和 repository URL 一致。
- CLI 依赖调研附件中的组件 commit、依赖边和证据 SHA 格式。
- subtree tree 与固定上游 commit 一致。
- `git-subtree-split` 元数据。
- 规则及相关目录 tree SHA。

工具不会访问网络或修改仓库。上游更新流程见
[`../docs/design/upstream-sync.md`](../docs/design/upstream-sync.md)。
