# XScanEngine HostApi 声明与规则覆盖

Status: Draft

Upstream: XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83

Rules: Detect-It-Easy@c2c17dfa5ea4e078ba31eab55d87430c96622fb6

Last updated: 2026-07-26

## 1. 目的与边界

本文从固定 XScanEngine C++ 头文件提取 Qt script 格式宿主的声明面，并与固定规则
实际调用的第一层 `receiver.method(...)` 和公共脚本扩展做集合差分。它回答：

- 30 个 `*_Script` 类各自声明和继承哪些 `public slots`；
- 参数文本、默认参数及最小/最大 C++ 声明 arity；
- 固定规则观察到的方法和 arity 是否有 C++ 声明或公共脚本定义；
- 哪些调用仍需要 Qt 运行时实验。

它不证明 QtScript/QJSEngine 的类型转换、重载选择、额外参数、返回值、异常或方法
副作用。文本声明匹配不能代替行为 fixture。

## 2. 固定源码与许可证

XScanEngine 在主 subtree 中是未物化 gitlink；锁文件将其标为
`external-research-checkout`。本实验只把固定 commit checkout 到临时目录，不向
项目导入第三方源码：

```sh
git clone --filter=blob:none --no-checkout \
  https://github.com/horsicq/XScanEngine.git \
  /tmp/diec-rust-xscanengine-dfe4a419
git -C /tmp/diec-rust-xscanengine-dfe4a419 \
  checkout --detach dfe4a419e4f491bb23688ba03c5a5bf39e34da83
```

生成器会拒绝其他 `HEAD`，并要求 `LICENSE` SHA-256 精确等于
`ac4f868b0034a4047dd1394409e412a25b03013a42f75f20fb0a4f9b4692a827`；
该文件为 MIT License。30 个 `modules/*_script.h` 的路径、字节数和 SHA-256
保存在
[`host-api-inventory.json`](data/host-api-inventory.json)，按文件名顺序的
header manifest SHA-256 为
`63eb6f8c1520ae0f8e75f9f5e419f5c4be555a74d4ca6acddb621432896f2ec9`。

复现：

```sh
python tools/rules/extract_host_api_inventory.py \
  --xscanengine-root /tmp/diec-rust-xscanengine-dfe4a419 \
  --rule-inventory docs/research/data/rule-syntax-inventory.json \
  --output docs/research/data/host-api-inventory.json
```

## 3. C++ 声明结果

固定源码包含 30 个 `*_Script` 类、337 个直接 `public slots` 方法、0 个
`Q_PROPERTY`。先前调研写成 338，是因为人工统计把
`pe_script.h` 中已注释的 `isExportFunctionPresentExp` 当成了声明；机器提取后
`PE_Script` 是 87 个直接方法而非 88 个。

继承展开保持原始类来源，不把 override 去重：

- `Binary_Script`：155 个直接/有效方法；
- `MSDOS_Script`：13 个直接、168 个含继承方法；
- `PE_Script`：87 个直接、255 个含继承方法；
- `ELF_Script`：26 个直接、181 个含继承方法；
- `Archive_Script`：2 个直接、157 个含继承方法；
- `APK_Script`：2 个直接、161 个含继承方法。

其余 24 个类的父类、lineage、直接和有效方法数均保存在机器清单。声明记录包含
返回类型、参数类型/名称/default、`virtual`、`const`、源码路径和行号。

## 4. 规则侧调用边界修正

规则语法清单现在只把第一层成员调用认作 HostApi：

```text
PE.compare(...)                    HostApi 候选
MSDOS.addressToOffset.apply(...)   apply 属于函数对象，不是 MSDOS slot
```

更深链仍保存在通用 member 清单。按此边界，固定规则有 16,499 次第一层宿主调用、
429 个 receiver/method 组合、464 个 arity 形状；动态 computed 第一层方法名为
0。

规则公共脚本还定义了 13 个第一层函数扩展：

- `db/archive-file`：`Archive.add`、`Archive.contents`；
- `db/MSDOS/_init`：5 个方法，包括覆盖 C++ 零参数方法的
  `getEntryPointOffset(nOffset)`；
- `db/PE/_init`：6 个方法，包括 `getEntryPointSignature` 和四个 `*Exp` helper。

JavaScript 函数允许少传或多传参数，因此这些扩展作为独立覆盖层；不能把它们伪造为
C++ slot。

## 5. 联合覆盖结果

464 个观察 arity 形状中：

| 覆盖来源 | arity 形状 |
| --- | ---: |
| C++ 声明及默认参数范围 | 444 |
| 公共 JavaScript 扩展（含同名 shadowing） | 16 |
| 仍未覆盖 | 4 |
| **总计** | **464** |

剩余四项为：

| 调用 | 观察次数 | 固定声明/定义结论 |
| --- | ---: | --- |
| `PE.getEPSignature(…, …)` | 1 | C++ slot 和 2235 个规则/公共脚本中均无定义；同一 `_init` 只有 `getEntryPointSignature` |
| `X.SA` 三参数 | 2 | C++ 声明范围 1..2 |
| `X.SC` 四参数 | 1 | C++ 声明范围 1..3 |
| `X.U8` 二参数 | 5 | C++ 声明范围 1..1 |

`PE.getEPSignature` 很可能是
`db_extra/PE/sfx_CipherWall.1.sg:8` 的上游命名错误，但在 Qt oracle 证明实际异常
和分支可达性前只记为“未解析”，不自行修正规则。

三个 `X` 方法的额外实参集中出现在 Binary 规则。普通 JavaScript 会忽略多余参数，
但 QObject slot wrapper 是否一致、是否产生 overload/转换差异必须由固定 Qt 5/Qt 6
实验确认；当前不能把它们算作兼容通过。

## 6. 对实现和测试的约束

- Rust `HostApi` 不能只复制 337 个直接方法；必须按 30 类继承展开，并单独加载
  13 个规则脚本扩展；
- 默认参数必须在 JavaScript 边界模拟，不能依赖 Rust 函数默认值；
- `File`/`X` 是随 file type 绑定的别名，当前机器对照使用所有格式类 union，
  正式实现必须按真实 init/lifecycle 绑定具体对象；
- 未知方法、未覆盖 arity 和类型转换失败必须产生可定位 diagnostic；
- 上游同步时，header manifest、slot、default、inheritance、脚本扩展或规则 arity
  任一变化都必须重新生成并评审；
- `getEPSignature` 和三个额外参数形状必须加入 Qt 5/Qt 6 conformance oracle。

## 7. 尚未完成

- 337 个 C++ slot 的参数/返回 Qt 类型转换和异常行为 fixture；
- 继承 override、默认参数和额外实参的 Qt 5/Qt 6 对照；
- `File`/`X` 在每种 file type/init/include 生命周期中的精确 identity；
- `_setResult`、`meta`、`result` 等非格式对象 global HostApi 的源码声明清单；
- 用完整 HostApi 逐规则执行并对比固定上游结果。
