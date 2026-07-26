# 非格式全局 HostApi 与规则函数清单

Status: Draft

Upstream: die_script@5d82316c110abf0eb863b50bc679d330e05067b6

Rules: Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6

Last updated: 2026-07-26

## 1. 目的与边界

本文补齐格式 QObject 之外的 JavaScript global 边界，并区分三类容易混淆的名字：

- `die_script` 原生注入的 global function；
- 根 `_init` 及公共脚本定义的普通 JavaScript function；
- ECMAScript 内建和仍未解释的直接 global call。

机器清单见
[`global-host-api-inventory.json`](data/global-host-api-inventory.json)。
它不把单文件 scope analysis 的所有 undeclared identifier 都认作 HostApi，也不证明
公共脚本定义对每个调用点可达。

## 2. 固定源码、许可证与复现

主仓库 gitlink 固定 `die_script` commit
`5d82316c110abf0eb863b50bc679d330e05067b6`。实验使用临时 checkout，不向项目导入
第三方源码：

```sh
git clone --filter=blob:none --no-checkout \
  https://github.com/horsicq/die_script.git \
  /tmp/diec-rust-die-script-5d82316c
git -C /tmp/diec-rust-die-script-5d82316c \
  checkout --detach 5d82316c110abf0eb863b50bc679d330e05067b6

python tools/rules/extract_global_host_api_inventory.py \
  --die-script-root /tmp/diec-rust-die-script-5d82316c
```

提取器拒绝错误 commit、dirty checkout 和错误许可证哈希。固定 `LICENSE` SHA-256
为 `abdeb212f229d2b93a5c315763df4d7201c7d74f580ad9dc77d77dec7cbc6c69`，
内容为 MIT License。机器清单还固定 `xscriptengine.cpp`、
`die_scriptengine.cpp/.h` 和 `die_global_script.cpp/.h` 的字节数及 SHA-256。

## 3. 原生 global 声明与 Qt 注册差异

逻辑 API 以 `die_global_script.h:33-50` 的 16 个 `public slots` 为完整声明面：

| 方法 | 返回 | arity | 固定规则直接调用 |
| --- | --- | ---: | ---: |
| `includeScript` | `void` | 1 | 56 |
| `_log` | `void` | 1 | 29 |
| `_setResult` | `void` | 4 | 113 |
| `_isResultPresent` | `bool` | 2 | 11 |
| `_getNumberOfResults` | `qint32` | 1 | 30 |
| `_removeResult` | `void` | 2 | 13 |
| `_isStop` | `bool` | 0 | 1 |
| `_encodingList` | `void` | 0 | 0 |
| `_isConsoleMode` | `bool` | 0 | 0 |
| `_isLiteMode` | `bool` | 0 | 0 |
| `_isGuiMode` | `bool` | 0 | 0 |
| `_isLibraryMode` | `bool` | 0 | 0 |
| `_breakScan` | `void` | 0 | 0 |
| `_getEngineVersion` | `QString` | 0 | 0 |
| `_getOS` | `QString` | 0 | 0 |
| `_getQtVersion` | `QString` | 0 | 0 |

固定规则对其中 7 个方法有 253 次直接调用，全部只使用声明 arity；另外 9 个方法
在本规则快照中没有直接调用。

Qt 5 并不直接暴露这些 QObject slots：`die_scriptengine.h:57-71` 声明 15 个统一
接收 `QScriptContext*`/`QScriptEngine*` 的 custom wrapper，对应实现位于
`die_scriptengine.cpp:326-591`，再由第 40-54 行用 `_addFunction` 注册。三组名称
精确一致，但遗漏 `_getQtVersion`。Qt 6 `QJSEngine` 分支则在
`die_scriptengine.cpp:75-90` 通过 QObject property 注册全部 16 个 slot。
当前规则未直接调用 `_getQtVersion`，所以该差异不会影响固定规则调用覆盖，但它是
必须保留的上游可观察平台/runtime surface 差异。表中的逻辑 arity 来自 Qt 6 slot；
Qt 5 wrapper 的转换和缺参/多参行为必须按其函数体另行取证。

## 4. 根规则框架不是 native HostApi

固定 `db/_init` 通过 `includeScript` 加载 `_debug`、`_runtime_helpers` 和
`language`，随后定义 `meta`、兼容别名 `init` 和 `result`。这三个名字不是 C++
注入方法。根初始化链一共定义 8 个顶层函数：

| 函数 | 定义参数数 | 规则直接调用 |
| --- | ---: | ---: |
| `_debug` | 1 | 1 |
| `_error` | 1 | 12 |
| `_isLangDetected` | 0 | 8 |
| `_isLangPresent` | 1 | 10 |
| `_setLang` | 2 | 13 |
| `init` | 0 | 0 |
| `meta` | 6 | 2,156 |
| `result` | 0 | 2,165 |

普通 JavaScript 调用允许少传或多传参数。例如 `meta` 的 2,156 次调用分别使用
0、1、2 个实参；缺少的参数由函数体处理。`_setLang` 也有 11 次一参数调用。
Rust runtime 必须先按真实 include/init 生命周期加载这些函数，不能把它们硬编码成
native HostApi 或按 Rust 函数签名做严格 arity 拒绝。

## 5. 全规则直接 global call 分类

规则 AST 清单现在额外保存顶层 function declaration、函数值 `var` 和简单全局赋值
定义。固定规则实际得到 183 个顶层函数名、2,371 次定义；本快照全部是 function
declaration。

71 个 undeclared direct-call 名、7,834 次调用已按源码分类：

| 分类 | 名称 | 调用 |
| --- | ---: | ---: |
| 规则顶层函数候选 | 55 | 7,223 |
| ECMAScript global | 7 | 356 |
| native engine global | 7 | 253 |
| 未分类 | 2 | 2 |

“规则顶层函数候选”是全仓库 union，只说明存在同名顶层定义；是否在调用前通过
init/include 可达仍需生命周期实验。

两个未分类调用都具有明确的固定源码拼写证据：

- `db/Binary/debug_data_debugData.1.sg:58` 调用 `get_DWRAF_vi(...)`，规则集没有
  同名定义；
- `db/Binary/audio_WEM.1.sg:55` 调用 `xma2_pase_xma2_chunk(...)`，它先
  `includeScript("vgmcodingutils")`，但该脚本在第 14 行定义的是
  `xma2_parse_xma2_chunk(...)`。

两者不得被兼容层静默补成别名。当前只证明执行到表达式时会查找未定义 global；
分支可达性、Qt 异常文本和上层扫描行为仍需 oracle fixture。

## 6. 对实现与测试的约束

- Rust `HostApi` 的非格式 native surface 以 16 个 slot 为声明基线，并显式记录
  Qt 5 的 `_getQtVersion` omission；
- `meta`、`result`、语言 helper 和 prototype 扩展必须来自原样规则脚本及真实
  init/include 生命周期；
- 未声明直接调用不得自动变成 permissive stub；未分类项必须产生兼容诊断；
- 规则同步时必须重生成规则语法和本清单，评审 native 注册、顶层定义、分类及
  arity 变化；
- 后续 Qt/QuickJS 对照必须覆盖 native 返回值、字符串转换、结果去重/删除、停止
  状态、include 失败和异常传播，而不只验证函数名存在。

## 7. 尚未完成

- 16 个 native global 的 Qt 5/Qt 6 参数转换、返回值、副作用和异常 fixture；
- 两个拼写错误分支的可达语料、Qt 异常及扫描器传播行为；
- 55 个跨文件规则函数候选的逐调用 include 可达性证明；
- 1,408 个 undeclared global symbol 中非直接调用的读取、写入、隐式 global 和
  动态属性访问分类；
- 用完整 native/global/format HostApi 逐规则执行并与固定 Qt oracle 差分。
