# 文档索引

项目文档按内容性质分开维护，避免将调研正文堆积在根目录文件中。

## 目录

- [`research/`](research/)：对上游的事实调查、源码分析和可重复实验。
- [`design/`](design/)：基于调研结论形成的架构与接口设计。
- [`design/decisions/`](design/decisions/)：Architecture Decision Records。

根目录文档各自只承担一个职责：

- [`../README.md`](../README.md)：项目目标、范围和导航。
- [`../ROADMAP.md`](../ROADMAP.md)：阶段、交付物、门禁和状态。
- [`../AGENTS.md`](../AGENTS.md)：开发与评审约束。

## 文档证据要求

- 上游结论注明仓库、commit SHA 和源码路径/行号或符号名。
- 实验注明环境、命令、输入、原始输出位置和预期结果。
- 尚未验证的内容明确标记为“假设”或“待验证”，不得写成事实。
- 调研材料与设计决策分开：调研回答“上游现在如何工作”，设计回答“本项目决定如何实现”。
- 影响公共 API、兼容性、依赖或长期维护成本的决策必须建立 ADR。
- 大型原始输出、二进制语料和构建产物不进入文档目录；文档只记录可复现方法、摘要、哈希和受控存储位置。

## 状态标记

文档顶部应包含：

```text
Status: Draft | In Review | Accepted | Superseded
Upstream: <repository>@<commit>
Last updated: YYYY-MM-DD
```

不适用上游版本的设计文档可以省略 `Upstream`，但应链接其依赖的调研文档。

