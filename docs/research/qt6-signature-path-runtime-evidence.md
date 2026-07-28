# Linux Qt6 Signature file path 运行证据

Status: In Review
Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`
Last updated: 2026-07-28

## 结论

固定 Linux amd64 Qt6 private-entry harness 在与 Qt5 相同的七用例 fixture 上
得到完全相同的 harness output、11 条关系和原始 stdout：

- 空 filter 执行 main/extra 两层同 basename 规则；
- main/extra 的精确绝对路径各只选择对应规则；
- missing、大小写变化、含 `..` 的字符串和 basename-only 均匹配零条规则；
- filter 原样传递，不做 canonicalization、case folding 或 basename fallback。

两侧 stdout 都是 3837 bytes，SHA-256 都为
`1ef8d0913678d60050c0e99573fa9a07781b8292ec4c961f7164a740f7a563be`；
exit 0、stderr 为空。

该能力仍不是公共扫描 API。harness 仅用 translation-unit-local
`#define private public` 调用真实 `DiE_Script::processDetect()`，没有修改
上游对象或复制 comparator。

## 固定身份

机器报告：
[`data/signature-path-engine-qt6.json`](data/signature-path-engine-qt6.json)，
SHA-256
`f83535e9579c286bb545659539ef3809e39d300e57e239649fe35e72a00e3014`。
Qt5 对照：
[`data/signature-path-engine-qt5.json`](data/signature-path-engine-qt5.json)。

| 项目 | Qt6 值 |
| --- | --- |
| Image | `diec-rust/signature-path-harness-qt6:74eaf505` |
| Image ID | `sha256:df9be77359a4b9eb877ddf03c247ab553385b35b103d617655f973e916a333fd` |
| Revision | `74eaf505c250ab47e709024e9dc41657cd8f2254` |
| Binary | `/opt/die-build/src/console/diec-signature-path-harness` |
| Binary SHA-256 | `3628a994502a923e6de9e3329cf238c4d9d862d97f68cecfad4ea6d435eeb810` |
| Cases / relationships | `7 / 11` |

Qt6 Dockerfile 从固定 CMake Qt6 oracle 派生，以 `--network=none` 构建。
薄 wrapper `tools/upstream/probe_qt6_signature_path_harness.py` hash-bound 并调用
原 Qt5 探针逻辑，只替换 image、Dockerfile 和报告 metadata。

## 能力影响

`CAP-RULE-007` 提升为 Linux Qt6 `evidence_complete`。当前汇总为
59 项 complete、3 项 partial、6 项 missing；9 项仍需闭环，
`CAP-GAP-007` 保持开放。

## 重现

```text
python tools/corpus/generate_signature_path_fixture.py <fixture>

docker build --network=none \
  -f tools/upstream/Dockerfile.signature-path-harness-qt6 \
  -t diec-rust/signature-path-harness-qt6:74eaf505 \
  tools/upstream

python tools/upstream/probe_qt6_signature_path_harness.py \
  --fixture-dir <fixture> \
  --raw-dir <untracked-raw> \
  --output docs/research/data/signature-path-engine-qt6.json
```

能力清单生成器要求固定 image/revision、七用例、11 条关系全 true，并要求
Qt5/Qt6 的完整 harness output、relationships 和 fixture identity 完全一致。

## 限制

- 仅覆盖 Linux amd64、Qt 6.4.2 和固定组件 commit；
- public Rust/CLI/C ABI 是否暴露该上游私有 filter 仍是设计决策；
- Windows/macOS 路径字符串来源和大小写文件系统行为不能由本实验外推。
