# 上游 main/extra/custom 数据库层行为

Status: Draft

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Component:
`horsicq/XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

Last updated: 2026-07-27

## 1. 范围

本文固定三类规则数据库同时存在时的：

- 加载开关与 materialized record 集合；
- main、extra、custom 跨层顺序；
- 三层存在相同 signature filename 时是否覆盖或去重；
- 数据库加载后，扫描时 extra/custom 开关是否继续过滤 records；
- signature priority 与扫描结果顺序的关系。

项目生成 fixture 清单为
[`data/database-layer-fixture.json`](data/database-layer-fixture.json)，
Qt5 engine harness 的完整机器报告为
[`data/database-layers-engine-qt5.json`](data/database-layers-engine-qt5.json)。
fixture 只包含九条项目生成规则和一个 benign Binary 输入，不含上游规则或第三方
样本字节。

## 2. 固定源码语义

固定 `XScanEngine::loadDatabase(SCAN_OPTIONS*)` 先调用 `initDatabase()` 清空
records，再依次：

1. 加载 main；
2. `bUseExtraDatabase=true` 时加载 extra；
3. `bUseCustomDatabase=true` 时加载 custom。

每个目录层单独建立 `listNewRecords`，以 `sort_signature_prio` 排序后 append 到
`m_listSignatures`。比较器先按 file type，再从形如 `name.5.sg` 的倒数第二段
提取字符串 priority，最后按完整 signature filename。成功加载目录后不会对三层
合并结果做一次全局 priority sort，所以正常目录路径形成
`main → extra → custom` 三个连续块。

`SIGNATURE_RECORD` 保存 `databaseType`。加载器没有按 filename/path 去重或覆盖的
逻辑。`DiE_Script::_shouldExecuteSignature()` 对 main 恒允许；extra/custom record
还分别检查扫描时的 `bUseExtraDatabase`/`bUseCustomDatabase`。因此这两个选项既
控制相应层是否被加载，也能过滤已经 materialized 的 records。

源码位置：

- `XScanEngine/xscanengine.cpp`：
  `sort_signature_prio()`、`loadDatabase(SCAN_OPTIONS*)`、
  `loadDatabase(path, DT, ...)`；
- `XScanEngine/xscanengine.h`：`DT` 与 `SIGNATURE_RECORD`；
- `die_script/die_script.cpp`：`_shouldExecuteSignature()`。

上述组件源码由固定 CMake oracle 镜像提供，身份和 source harness SHA-256 均绑定
在机器报告中。

## 3. 确定性 fixture

生成命令：

```text
python tools/corpus/generate_database_layer_fixture.py <fixture-dir>
```

main、extra、custom 每层都有相同三个 filename，但脚本写入不同 detection name：

| Filename | Priority | Main | Extra | Custom |
| --- | ---: | --- | --- | --- |
| `layer-low.1.sg` | `1` | `MainLow` | `ExtraLow` | `CustomLow` |
| `shared.5.sg` | `5` | `MainShared` | `ExtraShared` | `CustomShared` |
| `layer-high.9.sg` | `9` | `MainHigh` | `ExtraHigh` | `CustomHigh` |

三层的 `shared.5.sg` 名称完全相同，内容不同。生成器测试要求两次生成的 manifest
和每个文件逐字节相同，并与版本化清单一致。

## 4. 可重复 engine 实验

专用 harness 只替换 console `main`，链接固定 Qt5 CMake 镜像中的未修改 engine
objects。构建和采集：

```text
docker build --network none \
  --build-arg BASE_IMAGE=diec-rust/upstream-oracle-cmake:74eaf505 \
  -f tools/upstream/Dockerfile.database-layers-harness-qt5 \
  -t diec-rust/upstream-database-layers-harness:74eaf505 \
  tools/upstream

python tools/upstream/probe_database_layers.py \
  --image diec-rust/upstream-database-layers-harness:74eaf505 \
  --binary /opt/die-build/src/console/diec-database-layers-harness \
  --expected-revision 74eaf505c250ab47e709024e9dc41657cd8f2254 \
  --fixture-dir <fixture-dir> \
  --repetitions 2 \
  --output docs/research/data/database-layers-engine-qt5.json
```

容器禁用网络，限制为 2 CPU、1 GiB memory、256 PIDs，并只读挂载 fixture。
镜像 ID 为
`sha256:0b5f10b2e0fad5fbfaa14601afd2635032426008da96a92cdc3cb1fc95137468`。
两次运行的 exit、stdout 和 stderr 逐字节相同；stderr 为空，报告
`passed=true`、`failures=[]`。

## 5. 结果

### 5.1 加载开关

| Load options | Records | Database-type blocks |
| --- | ---: | --- |
| main only | 3 | main |
| main + extra | 6 | main, extra |
| main + custom | 6 | main, custom |
| all layers | 9 | main, extra, custom |

四次 `loadDatabase()` 都返回 true，且没有取消。全层 record 的精确顺序为：

```text
main:   layer-low.1.sg, shared.5.sg, layer-high.9.sg
extra:  layer-low.1.sg, shared.5.sg, layer-high.9.sg
custom: layer-low.1.sg, shared.5.sg, layer-high.9.sg
```

因此同名 `shared.5.sg` 在三层各保留一条；extra/custom 不覆盖 main，也不互相
覆盖，三层总计三条同名 record。

### 5.2 已加载 record 的运行时过滤

harness 先启用全部层加载九条 records，再只改变扫描 options：

| Scan options | Detection names |
| --- | --- |
| main only | `MainLow`, `MainShared`, `MainHigh` |
| main + extra | 上述 main 三条，再接 extra 三条 |
| main + custom | 上述 main 三条，再接 custom 三条 |
| all layers | main 三条、extra 三条、custom 三条 |

所有 scan error 列表为空。该实验把“没有加载该层”和“层已加载但 scan 时关闭”
区分开，证明 `_shouldExecuteSignature()` 的 database type gate 可达。

`bIsSort=true` 的本 fixture 仍得到相同顺序，因为九个 `_setResult()` 记录的结果
priority 相同；上游 result comparator 只比较 `SCANSTRUCT.nPrio`。这只固定当前
输入的原始结果，不能外推相同 priority 的 `std::sort` 顺序在其他平台或构建中
稳定。

## 6. 对 Rust 设计与差分的约束

- database 不是按 filename 构造的覆盖 map；内部模型必须允许跨层同名 records，
  并为每条保存 layer、原始 path、file type、priority 和稳定 source identity；
- legacy 顺序是各层内部 priority/name 排序，再按
  `main → extra → custom` 拼接；不能把三层合并后做全局 priority sort；
- extra/custom enablement 必须有单一语义来源，database build 和 scan request
  不能各自实现不一致的过滤逻辑；
- 现代 strict API 可以报告跨层 duplicate，但默认不能静默丢弃其中任意一条；
- canonical result 需要保留 rule provenance，CLI renderer 再决定是否隐藏；
- differential normalization 不得按 signature filename 去重，也不得把 detection
  名称排序后当作等价，因为原始执行顺序可能影响共享 JavaScript global state；
- 相同比较 key 的上游 C++ sort 没有稳定 tie-breaker。Rust 必须定义确定顺序，
  同时将无法跨平台证明的 legacy tie 归为明确 compatibility risk。

## 7. 尚未覆盖

- 同一层内完全相同 filename（ZIP duplicate records）与跨层组合后的 tie；
- main/extra/custom 混用 directory 与 ZIP 时的跨层顺序；
- 各层 `_init`、include 和共享 global state 的交互；
- 不同 file type、deep/heuristic 规则与 database type gate 的组合；
- Qt6、Windows 和 macOS 的相同实验；
- GUI 对层开关和动态数据库更新的行为。
