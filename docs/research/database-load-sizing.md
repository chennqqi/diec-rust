# 数据库加载规模与资源边界

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-30

## 1. 目的与边界

本文为目录、ZIP、embedded bundle 和项目自有 cache 的统一
`DatabaseLimits` 提供可重复 sizing。机器报告为
[`data/database-load-sizing.json`](data/database-load-sizing.json)。

报告固定规则组件
`Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6`，并绑定：

- 完整 `db`、`db_extra`、`db_custom` 资产与许可证清单；
- Linux Qt5 双 oracle 的 17-case ZIP database 结果；
- 三层加载、同名规则保留和 runtime gate 的 engine 结果；
- 19-case cache miss/hit/corrupt/cancel/permission/concurrency 结果。

它不证明候选值已适合生产，也不把未来上游或用户数据库的规模限制为当前固定
bundle。

## 2. 固定 bundle 观察值

| 观察量 | 值 |
| --- | ---: |
| source/layer 数 | 3 |
| 全部文件数 | 2,268 |
| 全部文件 bytes | 2,909,316 |
| program 文件数 | 2,235 |
| program bytes | 2,902,881 |
| 最大单文件 | 603,640 bytes |
| 最大 source-relative UTF-8 path | 55 bytes |
| 最大 bundle-relative UTF-8 path | 64 bytes |
| source-relative path 累计 | 59,879 bytes |
| 最大 path components | 3 |

最大文件是 `db/Binary/audio.1.sg`。三个 source 分别包含
2,124/142/2 个文件和 2,832,469/76,651/196 bytes。枚举拒绝 symlink，并对
每个 source 内的 POSIX 风格相对路径排序；资产计数和 bytes 必须与已固定的
license inventory 精确相等。

## 3. 规范 ZIP_STORED 模型

仓库没有一个与三棵当前规则树同时固定的正式发布 database archive，不能用
221-byte 单规则 fixture 推断全库上限。报告因此只建立确定性、无压缩的容器尺寸
模型：

```text
sum(file_bytes + 76 + 2 * utf8_path_bytes) + 22
```

其中每项包含 30-byte local header、46-byte central record 和两份 filename，
末尾包含 22-byte EOCD；没有 extra field、comment、data descriptor 或 ZIP64。
这是一种合法 `ZIP_STORED` 表示的精确尺寸，不依赖 zlib 版本。

| source | 文件 bytes | 规范 stored ZIP bytes |
| --- | ---: | ---: |
| `db` | 2,832,469 | 3,105,701 |
| `db_extra` | 76,651 | 95,361 |
| `db_custom` | 196 | 446 |
| 合计 | 2,909,316 | 3,201,508 |

该模型不是所有 ZIP 编码的上界。extra/comment、ZIP64、未知 compression ratio
仍必须由独立 hard limits 和 `limit-1/exact/+1` 覆盖。

## 4. 候选 profile

Modern 候选把各观察值乘 8 后向上取二次幂；legacy-high 使用 64 倍。cache
bytes 取相应 total-entry ceiling 的两倍，为 record framing、path 和 metadata
保留空间。两者都保持 `review_candidate_not_admitted`。

| Counter | Modern | Legacy-high |
| --- | ---: | ---: |
| maximum sources | 32 | 256 |
| maximum entries/cache records | 32,768 | 262,144 |
| maximum single entry bytes | 8,388,608 | 67,108,864 |
| maximum total entry bytes | 33,554,432 | 268,435,456 |
| maximum single/total container bytes | 33,554,432 | 268,435,456 |
| maximum single logical path bytes | 512 | 4,096 |
| maximum total logical path bytes | 524,288 | 4,194,304 |
| maximum cache bytes | 67,108,864 | 536,870,912 |

这些值是设计评审输入，不是上游行为。上游 ZIP 使用 `getRecords(-1)`，cache
整文件 `readAll()` 并按不可信 record count `reserve()`；Rust 实现必须在读取、
分配和 materialize 前 reserve，而不是复刻无界行为。

## 5. 加载不变量

- directory、ZIP、embedded、cache hit 和 fallback 使用同一组计数器；
- container bytes 在整文件读取前 reserve；
- entry count、logical path bytes、声明和实际 entry bytes 在 materialize 前
  reserve；
- cache decode、database build 和 publish 事务化；失败、取消或 limit reached
  不泄漏部分 records，不发布 cache；
- 未知语法、损坏 archive/cache 和不支持的压缩产生明确诊断；
- cache miss/fallback 不重置预算，legacy-high 不被任何 adapter 默认选择。

## 6. 复现与未覆盖

```powershell
python tools\rules\analyze_database_load_sizing.py --check
python tools\tests\test_database_load_sizing.py
```

尚未闭合：

- 完整固定 bundle 的真实 cache 序列化 overhead；
- ZIP extra/comment、ZIP64、compression ratio 和声明长度欺骗；
- production CPU、峰值内存及 modern/legacy-high 的跨平台边界；
- future/custom database 的规模分布。

因此本报告只能关闭“database load 完全没有非零候选”的缺口，不能让统一资源
策略或 Phase 0 门禁变为 admitted。
