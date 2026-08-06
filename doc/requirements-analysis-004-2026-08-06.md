# 需求分析摘要 004

## 2026-08-06: GUI 主题自动跟随系统
- 需求：die-gui 增加自动跟随系统主题，并设为默认
- 分析：当前默认暗色，新增 `system` 主题后系统为亮色时显示亮色主题
- 落地：在 ROADMAP.md Phase 8 7B 主题样式下新增条目
- Phase 规划：7B-8 主题样式（与上游 1:1 对齐），7B-8-1 自动跟随系统（默认），对齐上游 QSS 主题 `orange_fix` / `Fusion` 与 `View` → `STYLE` 默认行为

## 2026-08-06: GUI Advanced 模式完善
- 需求：可拖拽分割条、签名语法高亮、Type/Flags 下拉框
- 分析：上游 DIEWidgetAdvanced 使用 QSplitter + die_highlighter + comboBoxType/comboBoxFlags
- 落地：SplitPane.tsx（拖拽分割条）、SignatureHighlighter.tsx（regex tokenizer）、AdvancedToolbar（Type/Flags 下拉+复选框）
- 验证：Playwright 自动测试全部通过

## 2026-08-06: GUI 7A/7B 功能对齐
- 需求：Recent files、全屏、复制/清除/保存结果、上下文菜单、Databases 下拉、主题切换、快捷键
- 分析：对比 ROADMAP 7A/7B 功能清单，识别出 7 项缺失功能
- 落地：工具栏新增 5 按钮（Copy/Clear/Save/Recent/Fullscreen）+ Settings 主题/语言下拉 + 6 个全局快捷键 + 右键上下文菜单 + Database 下拉 + write_text_file 后端命令
- 验证：Playwright 自动测试覆盖所有新功能，主题切换（System/Dark/Light）CSS 类正确应用，快捷键（F11/Escape）响应正确，上下文菜单 3 选项显示正确

## 2026-08-06: GUI 7B 签名浏览器增强 + 7C 扩展功能
- 需求：签名浏览器搜索/编辑/运行/调试/Profiling + 内存映射视图 + 归档视图 + 数据转换器
- 分析：SignatureBrowser 原为只读查看，需增强为编辑+执行；7C 三项扩展功能需新建组件
- 落地：SignatureBrowser 重写（搜索+编辑+Run/Debug+Profiling）、MemoryMapViewer（区段可视化）、ArchiveViewer（ZIP 树形浏览+list_archive 命令）、DataConverter（6种格式实时转换）；run_signature 从 stub 实现为全量扫描+过滤
- 验证：Playwright 测试 DataConverter（"Hello" hex→6种格式全部正确）、MemMap/Archive 空状态正确、SignatureBrowser 搜索框+Run/Debug 按钮渲染正确


