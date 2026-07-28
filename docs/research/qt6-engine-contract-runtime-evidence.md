# Linux Qt6 引擎契约运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Linux amd64 Qt6 oracle 在与 Qt5 完全相同的项目生成 fixture 上运行
37-case engine harness。Qt6 的 23 条确定性关系、fixture manifest 和七个上游
源码文件的审计投影与固定 Qt5 报告完全一致。

本轮完整覆盖：

- `scanFile`、`scanMemory`、`scanDevice`、`scanSubdevice` 四个入口；
- direct device 与 subdevice 的分块读取、短读、read/seek error、sequential、
  初始位置和范围边界；
- signature name 的精确匹配、大小写、缺失名称和 deep gate；
- callback 首/中/末停止、同步外部停止、规则内 break、预停止和 fresh-state
  恢复；
- record 的插入顺序、启用排序后的类型优先级和规则 metadata。

Qt6 harness exit 0，stderr 为空。随机 record ID 不做原始值比较，只由既有
唯一性和父子不变量验证；其余确定性关系逐字段与 Qt5 相等。

## 固定身份

机器报告：
[`data/engine-contract-linux-qt6.json`](data/engine-contract-linux-qt6.json)。
对照报告：
[`data/engine-contract-linux-qt5.json`](data/engine-contract-linux-qt5.json)。

| 项目 | 值 |
| --- | --- |
| Qt6 image | `diec-rust/engine-contract-harness-qt6:74eaf505` |
| Qt6 image ID | `sha256:ffd09170f4c37a49bffff6a3c3c59469c19caabf6aa9c78f0981e1bd95591a6b` |
| OCI revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Platform | `linux-amd64-qt6` |
| Harness binary | `/opt/die-build/src/console/diec-engine-contract-harness` |
| Harness binary SHA-256 | `8d4011ace3a8392f601b974f45aaeb0ad8b0115d89adc03090e1abedb1cfcfa9` |
| Harness source SHA-256 | `55efa51a59ada97064169df8f65f776d74176d859e2b8457d6a051d1bd0f29c6` |
| Fixture manifest SHA-256 | `535d96510e1a807a07af752ed60b0239bdbb91331ce51b1f89d2be043d07f23e` |
| Cases / relationships | `37 / 23` |
| Raw stdout | `59410` bytes / `a5e3b09f7d5ae5fb0dc3812b18c4ad157bbee30a2c0bf1c42b93f62d92760a81` |
| Raw stderr | `0` bytes / SHA-256 of empty input |

Qt6 Dockerfile 从固定
`diec-rust/upstream-oracle-cmake-qt6:74eaf505` 派生，只替换 console main
并链接同一 Qt6 构建对象。构建使用 `--network=none`，没有下载新依赖。
薄 wrapper
`tools/upstream/probe_qt6_engine_contract.py` hash-bound 原
`probe_engine_contract.py`，只替换 image/Dockerfile 身份和报告 metadata，
没有复制或修改 37-case 验证逻辑。

## 能力影响

以下能力提升为 Linux Qt6 `evidence_complete`：

- `CAP-ENG-IN-001` public entry points；
- `CAP-ENG-IN-002` device/subdevice I/O；
- `CAP-RULE-006` signature-name filtering；
- `CAP-RULE-009` cancellation；
- `CAP-RULE-012` result ordering。

完成本批时汇总为 47 项 complete、10 项 partial、11 项 missing。后续规则
编排、result-model、signature-path 与 debug-dispatch 批次已将当前汇总推进到
60/3/5，见
[`qt6-debug-dispatch-runtime-evidence.md`](qt6-debug-dispatch-runtime-evidence.md)；
`CAP-GAP-007` 仍保持开放。

## 重现

```text
python tools/corpus/generate_rule_orchestration_fixture.py <fixture>

docker build --network=none \
  -f tools/upstream/Dockerfile.engine-contract-harness-qt6 \
  -t diec-rust/engine-contract-harness-qt6:74eaf505 \
  tools/upstream

python tools/upstream/probe_qt6_engine_contract.py \
  --fixture-dir <fixture> \
  --raw-dir <untracked-raw> \
  --output docs/research/data/engine-contract-linux-qt6.json
```

能力清单生成器额外要求固定 image/revision、37-case catalog、23 条关系全部为
true，并要求 Qt5/Qt6 的 relationship、fixture manifest 和 source audit 三个
确定性投影完全相等。任一报告或本地探针变化还会导致来源 SHA-256 改变。

## 限制

- 仅覆盖 Linux amd64、Qt 6.4.2 和固定上游 commit，不外推到其他 Qt minor
  或平台；
- Qt5 文档列出的 callback exception、未同步数据竞争、超大范围和并发修改等
  未定义或未覆盖边界仍然存在；
- 本轮只关闭五个完整能力行；规则编排已由后续批次覆盖，database cache、
  signature path、dispatch/nested 和 result-model harness 仍待完成。
