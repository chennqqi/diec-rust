# 需求分析摘要 003 — 2026-07-31

## Phase 1 关闭与 Phase 2 启动

### 状态转换
- P0-BLOCK-005 macOS基线已由其他 Agent 完成（17 candidate reports in docs/research/data/macos-qt5/）
- Phase 1 全部退出条件满足：CI/规则同步/差分框架/macOS基线
- ROADMAP Phase 1 -> DONE, Phase 2 -> IN PROGRESS

### Phase 2 首批：受控字节读取层
- 范围决策：首批实现 ByteSource/ByteView 具体实现（用户选择）
- ADR 0013 fail-closed 要求：short read/EOF/seek error 必须返回 typed error，不复制未初始化尾部、不补零、不无限重试

### IoError 扩展
- 新增 ShortRead{offset,expected,actual}：精确报告短读位置和字节数
- 新增 NotSeekable：拒绝 sequential/non-seekable source 进入随机访问 parser
- 新增 InvalidArgument：处理 C/FFI 负值、零 size subdevice、溢出范围

### ByteSource 实现
- MemorySource<'a>：借用 slice，零拷贝零分配
- OwnedSource：Arc<[u8]>，cheap clone，适合解压缓冲
- FileSource：seek+read，open 时读 metadata.len()，Arc<File> 可共享
- ChunkedSource<'a>：测试用，每次 read_at 最多返回 chunk_size 字节，验证 read_exact_at 正进展循环
- EmptySource：测试用，总是返回 0 字节

### read_exact_at 语义
- 预检查 end = offset + out.len() 不越过 source.len()，否则 ShortRead{actual:0}
- 正进展循环：每次 read_at 返回 n>0 则继续，n==0 立即 ShortRead
- 零长度 out 直接 Ok(())，不触碰 source

### ByteView typed reads
- read_u8/u16_le/u16_be/u32_le/u32_be/u64_le/u64_be
- view 边界裁剪：read_at 不越过 view [start,end)，read_exact_at 检查 available < needed 则 ShortRead
- subview checked arithmetic：abs_start = range.start + offset，溢出返回 None

### 测试覆盖
- 35 新增测试：ByteRange 溢出/零长度、MemorySource full/partial/EOF/empty、read_exact short/overflow、ChunkedSource 分块循环、OwnedSource clone、ByteView subview/boundary/typed、FileSource open/read
- 总计 37 diec-core 测试通过
