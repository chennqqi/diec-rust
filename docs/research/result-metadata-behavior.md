# SCAN_RESULT 标量元数据行为

状态：Draft

本页固定 `CAP-RESULT-001` 的四个 `SCAN_RESULT` 标量字段及四个公共扫描入口
的文件名语义。结论绑定：

- DIE-engine：`74eaf505c250ab47e709024e9dc41657cd8f2254`
- Formats：`1151e7254fdee3c0294ff7095edbdd7bfccf8201`
- XScanEngine：`dfe4a419e4f491bb23688ba03c5a5bf39e34da83`

## 源码事实

`XScanEngine::SCAN_RESULT` 在
`XScanEngine/xscanengine.h:1041-1051` 声明 `nScanTime`、`sFileName`、`nSize`
和 `ftInit`。

四个公共入口最终都调用 `scanDevice`：

- `scanFile` 用 `QFile` 打开传入路径后调用 `scanDevice`
  （`XScanEngine/xscanengine.cpp:2555-2569`）；
- `scanMemory` 用无 `FileName` 属性的 `QBuffer` 包装字节
  （`xscanengine.cpp:2571-2586`）；
- `scanSubdevice` 用 `SubDevice` 包装给定区间后调用 `scanDevice`
  （`xscanengine.cpp:2588-2603`）；
- `scanDevice` 建立空结果并以 `bInit=true` 调用 `scanProcess`
  （`xscanengine.cpp:2538-2553`）。

顶层 `scanProcess` 在计时器启动后写入文件名和设备大小
（`xscanengine.cpp:2605-2616`），在主格式分派中写入 `ftInit`
（`xscanengine.cpp:2678-2832`），退出前用 `QElapsedTimer::elapsed()` 写入
毫秒扫描时间（`xscanengine.cpp:3032-3037`）。快速扫描的合法值可以为 0，
因此兼容测试不得要求正数，也不得把时间精确值纳入确定性差分。

`XBinary::getDeviceFileName` 先读取 QIODevice 的 `FileName` 动态属性；为空时
仅对 `QFile` 回退到 `QFile::fileName()`（`Formats/xbinary.cpp:10132-10145`）。
因此待 runtime oracle 验证的入口关系是：

| 入口 | fixture | 预期 `sFileName` |
| --- | --- | --- |
| `scanFile` | 固定 `/tmp` 路径 | 原样传入路径 |
| `scanMemory` | 裸内存 | 空字符串 |
| `scanDevice` | 显式 `FileName` 属性 | 属性值 |
| `scanSubdevice` | 有名称的父设备中的切片 | 空字符串，不继承父设备属性 |

## Runtime harness

[`result_metadata_harness_main.cpp`](../../tools/upstream/result_metadata_harness_main.cpp)
用同一份项目生成的 128-byte 最小 MSDOS 输入调用四个入口，逐 case 原样导出：

- `nScanTime`；
- `sFileName`；
- `nSize`；
- 数值 `ftInit` 及 `fileTypeIdToString(ftInit)`；
- record/error 数量和 PD success。

[`probe_result_metadata_harness.py`](../../tools/upstream/probe_result_metadata_harness.py)
执行以下强断言：

1. 四个标量字段逐 case 存在；
2. `nScanTime` 是非 bool 整数且大于等于 0，不比较入口间精确值；
3. 四个 `nSize` 都等于 128；
4. 数值 `ftInit` 在四入口一致，字符串投影均为 `MSDOS`；
5. 文件名严格符合上表，不把父设备名称传播给 subdevice；
6. 四次扫描无错误且 PD success。

构建与采集命令：

```sh
docker build \
  -f tools/upstream/Dockerfile.result-metadata-harness-qt5 \
  -t diec-rust/result-metadata-harness-qt5:74eaf505 \
  tools/upstream

python tools/upstream/probe_result_metadata_harness.py \
  --raw-dir /outside/repository/result-metadata-raw \
  --output docs/research/data/result-metadata-engine-qt5.json
```

镜像从已固定的 CMake Qt5 oracle 派生，构建阶段不访问网络；运行时使用
`--network=none`。原始 stdout/stderr 必须存放在仓库外，版本库中只保留包含
其字节数和 SHA-256 的结构化报告。

固定 Qt5 runtime 报告已经写入
[`result-metadata-engine-qt5.json`](data/result-metadata-engine-qt5.json)。
四个入口均通过全部六项关系断言，原始 stdout 为 1,876 bytes、
SHA-256 `0b70190ff72ab3c430892f6117524145c82af85a6dc30103858c01eed0fe077a`，
stderr 为空。原始流保存在仓库外；报告同时绑定 image、binary、generator 和
三层上游 commit 身份。该报告将 `CAP-RESULT-001` 的 Linux Qt5 状态提升为
runtime-observed。
