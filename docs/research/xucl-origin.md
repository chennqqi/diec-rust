# XArchive 内嵌 XUCL 的 UCL 1.03 来源与许可证追溯

Status: In Review

Upstream: `horsicq/DIE-engine@74eaf505c250ab47e709024e9dc41657cd8f2254`

Last updated: 2026-07-29

## 结论

固定 XArchive `0fcd4e8d3e9933baac3b12246d82ac026557ffd0` 中的
`Algos/xucldecoder.cpp` 与 `Algos/xucldecoder_acc.h` 可技术追溯到 Markus
Oberhumer 发布的官方 UCL 1.03 归档：

- 官方归档 SHA-1 与作者发布页公布值一致：
  `5847003d136fbbca1334dd5de10554c76c755f7c`；
- 归档 SHA-256 固定为
  `b865299ffd45d73412293369c9754b07637680e5c826915f097577cd27350348`；
- 两个内嵌文件合计 36,567 个 C token；12-token shingle 覆盖 94.76%，
  64-token shingle 覆盖 89.08%，分别具有 35 和 30 个唯一来源文件；
- `xucldecoder.cpp` 自报 UCL 1.03，并在第 842 行要求查阅
  `ACC_LICENSE`；`xucldecoder_acc.h` 大量映射官方 `acc/*`，但省略了官方
  `acc/acc.h` 的版权、GPL 与 `ACC_LICENSE` 提示头；
- 官方 UCL 源文件头声明 GNU GPL version 2 or any later version；
  `COPYING` 与 `acc/ACC_LICENSE` 均为相同的 GPL version 2 正文。因此机器报告
  将技术 SPDX 表达式分类为 `GPL-2.0-or-later`。

机器证据位于 [`data/xucl-origin.json`](data/xucl-origin.json)。这关闭了
`PRODUCT-LICENSE-GAP-001` 的“官方版本、内容来源和缺失许可证正文是什么”技术
子问题，但不是复制、翻译或发布批准：未发现 XArchive 保存特殊/商业授权证据，
MIT/GPL 组合仍须发布/法律责任人书面评审，`P0-BLOCK-004` 继续 Open。

## 固定来源

| 项目 | 固定值 |
| --- | --- |
| UCL 作者发布页 | `https://www.oberhumer.com/opensource/ucl/` |
| 官方归档 | `https://www.oberhumer.com/opensource/ucl/download/ucl-1.03.tar.gz` |
| 版本/发布日期 | `1.03` / `2004-07-20` |
| 归档大小 | 534,881 bytes |
| 归档 SHA-1 | `5847003d136fbbca1334dd5de10554c76c755f7c` |
| 归档 SHA-256 | `b865299ffd45d73412293369c9754b07637680e5c826915f097577cd27350348` |
| 归档 regular files | 622 |
| 索引的 `.c/.h/.ch` | 62 |

归档的 `include/ucl/uclconf.h` 明确声明 `UCL_VERSION_STRING "1.03"` 和
`UCL_VERSION_DATE "Jul 20 2004"`。根 `README` 却仍显示 `Version 1.02`；
审计器将这个上游残留不一致作为必须成立的固定事实记录，版本判断以作者发布页、
归档文件名和版本头为准，不用 README 单独推断。

## 内容映射

| 内嵌文件 | SHA-256 | 12-token 覆盖 | 64-token 覆盖 |
| --- | --- | ---: | ---: |
| `Algos/xucldecoder.cpp` | `f2f2fe4e11beaa122c2474a44c7c1c97242e9d211eacc15d0c7f3c646b2a45cf` | 93.30% | 85.37% |
| `Algos/xucldecoder_acc.h` | `f53d934a8efdb4f1b483e7fddf5ffe749d6914a2830bbaf7d68428b91fecc669` | 97.42% | 95.81% |
| **合并** | — | **94.76%** | **89.08%** |

唯一来源包括 `include/ucl/ucl.h`、`include/ucl/uclconf.h`、
`src/n2b_d.c`、`src/n2d_d.c`、`src/n2e_d.c`、`src/ucl_init.c`、
`src/ucl_crc.c` 以及 `acc/acc.h`、`acc_auto.h`、`acc_chk.ch` 等。
报告保存全部来源路径、内容 hash 和唯一 matching-window 计数。

shingle 覆盖证明大规模内容来源，不证明逐字节相同，也不能替代法律判断。未覆盖
token 可能来自聚合、重命名、包装或修改；不能据覆盖率推断这些差异获得了额外授权。

## 许可证证据与约束

官方归档内的证据已逐文件 hash-bound：

| 文件 | SHA-256 | 作用 |
| --- | --- | --- |
| `README` | `179c5419b5604bda56868a1ad40741e4ce1a4a2fbffe9729202d01200acdaf20` | 声明 UCL 按 GNU GPL 分发 |
| `COPYING` | `70439f6e2b47057a408d2390ed6663b9875f5a08066a06a060a357ef1df89a8c` | GPL version 2 正文 |
| `acc/ACC_LICENSE` | `70439f6e2b47057a408d2390ed6663b9875f5a08066a06a060a357ef1df89a8c` | 与 COPYING 逐字节相同 |
| `src/n2_99.ch` | `c39464853f36ddd4bf32ca44fc8083ce47987096bbf5b08a0e6e40e83eeacfae` | GPL-2.0-or-later 文件头 |
| `src/n2b_d.c` | `35fe4158db0b223f81c5a89441a6bb5b4e2bd7c79f845f00b43c21d973eca819` | GPL-2.0-or-later 文件头 |

因此当前约束是：

- 未取得并评审不同的书面授权前，按 `GPL-2.0-or-later` 技术证据处理；
- 获准分发时至少恢复精确 UCL 1.03 `COPYING`/`ACC_LICENSE`、版权和来源归属；
- MIT/GPL 组合评审完成前，不复制或翻译该 XUCL 实现到 Rust；
- 优先评估许可证清晰、行为可差分验证的独立实现；替换不能降低能力兼容要求。

## 复现

官方归档仅作为外部 hash-bound 输入，不提交到仓库。先从固定 URL 获取并验证
SHA-1/SHA-256，再运行禁网、只读挂载的固定 image：

```powershell
curl.exe -L `
  https://www.oberhumer.com/opensource/ucl/download/ucl-1.03.tar.gz `
  -o I:\tmp\ucl-1.03.tar.gz

python tools\upstream\audit_xucl_origin.py `
  --archive I:\tmp\ucl-1.03.tar.gz `
  --output docs\research\data\xucl-origin.json

python -m unittest discover -s tools\tests -p test_xucl_origin.py
```

审计器拒绝归档 hash、tar 路径、主仓库/XArchive commit、component lock、前置
product report、许可证文本、版本宏、覆盖阈值或 image revision 漂移。机器报告
不保存本机路径、容器源码路径或采集时间，可逐字节重复生成。

## 尚未完成

- 发布/法律责任人对 XArchive MIT 外层与 UCL GPL 派生内容的书面组合结论；
- 是否存在未进入固定仓库的特殊、商业或其他书面授权证据；
- 最终 Rust 方案选择：独立实现、兼容替代或在明确授权条件下复用；
- Windows、macOS、其他构建配置与最终发布包的许可证/SBOM/NOTICE 闭包。
