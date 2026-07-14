# Export to Word（导出为 Word）

<span class="category-badge action">Action</span>
<span class="version-badge">v0.5.3</span>

将当前对话导出为完美格式的 Word 文档，支持**代码语法高亮**、**原生数学公式**、**Mermaid 图表**、**引用资料**以及**增强表格**渲染。

---

## 概览

Export to Word 插件会把聊天消息从 Markdown 转成精致的 Word 文档。它完整支持标题、列表、表格、代码块和引用，同时兼顾中英文显示效果。

## 功能特性

- :material-file-word-box: **一键导出**：在聊天界面添加"导出为 Word"动作按钮。
- :material-format-bold: **Markdown 转换**：将 Markdown 语法转换为 Word 格式（标题、粗体、斜体、代码、表格、列表）。
- :material-code-tags: **代码语法高亮**：使用 Pygments 库为代码块添加语法高亮（支持 500+ 种语言）。
- :material-sigma: **原生数学公式**：LaTeX 公式（`$$...$$`、`\[...\]`、`$...$`、`\(...\)`）转换为可编辑的 Word 公式。
- :material-graph: **Mermaid 图表**：Mermaid 流程图和时序图渲染为文档中的图片。
- :material-book-open-page-variant: **引用与参考**：自动从 OpenWebUI 来源生成参考资料章节，支持可点击的引用链接。
- :material-brain-off: **移除思考过程**：自动移除 AI 思考块（`<think>`、`<analysis>`）。
- :material-table: **增强表格**：智能列宽、列对齐（`:---`、`---:`、`:---:`）、表头跨页重复。
- :material-format-quote-close: **引用块支持**：Markdown 引用块渲染为带左侧边框的灰色斜体样式。
- :material-translate: **多语言支持**：正确处理中文和英文文本，无乱码问题。
- :material-file-document-outline: **智能文件名**：可配置标题来源（对话标题、AI 生成或 Markdown 标题）。

---

## 配置

您可以通过插件设置中的 **Valves** 按钮配置以下选项：

| Valve | 说明 | 默认值 |
| :--- | :--- | :--- |
| `文档标题来源` | 文档标题/文件名的来源。选项：`chat_title` (对话标题), `ai_generated` (AI 生成), `markdown_title` (Markdown 标题) | `chat_title` |
| `最大嵌入图片大小MB` | 嵌入图片的最大大小 (MB)。 | `20` |
| `界面语言` | 界面语言。选项：`en` (英语), `zh` (中文)。 | `zh` |
| `英文字体` | 英文字体名称。 | `Calibri` |
| `中文字体` | 中文字体名称。 | `SimSun` |
| `代码字体` | 代码字体名称。 | `Consolas` |
| `一级标题西文字体` | H1 西文字体名称。 | `Aptos Display` |
| `一级标题中文字体` | H1 中文字体名称。 | `SimHei` |
| `二级标题西文字体` | H2 西文字体名称。 | `Calibri Light` |
| `二级标题中文字体` | H2 中文字体名称。 | `SimHei` |
| `表头背景色` | 表头背景色（十六进制，不带#）。 | `F2F2F2` |
| `表格隔行背景色` | 表格隔行背景色（十六进制，不带#）。 | `FBFBFB` |
| `Mermaid_JS地址` | Mermaid.js 库的 URL。 | `https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.min.js` |
| `JSZip库地址` | JSZip 库的 URL（用于 DOCX 操作）。 | `https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js` |
| `Mermaid_PNG缩放比例` | Mermaid PNG 生成缩放比例（分辨率）。 | `3.0` |
| `Mermaid显示比例` | Mermaid 在 Word 中的显示比例（视觉大小）。 | `1.0` |
| `Mermaid布局优化` | 优化 Mermaid 布局: 自动将 LR (左右) 转换为 TD (上下)。 | `False` |
| `Mermaid背景色` | Mermaid 图表背景色（如 `white`, `transparent`）。 | `transparent` |
| `启用Mermaid图注` | 启用/禁用 Mermaid 图表的图注。 | `True` |
| `Mermaid图注样式` | Mermaid 图注的段落样式名称。 | `Caption` |
| `Mermai5.0 更新内容

- 🔠 **标题级别字体自定义**: 新增 `一级标题西文字体`、`一级标题中文字体`、`二级标题西文字体`、`二级标题中文字体` 阀门 — 可为 H1 和 H2 独立配置字体，不再与正文字体绑定。
- ⬆️ **相对标题算法**: 当内容没有 H1 时，自动提升标题级别（如 `## → #`），确保文档层级结构正确。
- 🧹 **元数据清理**: Word 文档属性（`author`、`last_modified_by` 等）现在使用真实用户名，不再暴露 `python-docx` 库指纹。
- 🎨 **标题样式修复**: 清除了 Word 主题字体继承（`w:asciiTheme`、`w:eastAsiaTheme`），涵盖 Title、Heading 1-9 和默认样式，防止 Word 覆盖自定义字体（如宋体回退问题）。移除了标题样式上多余的下划线和边框
- 🧹 **内容清理加强**: 增强了对 `<details>` 块（通常包含工具调用或思考过程）的清理，确保最终文档整洁。
- 📄 **文档格式标准化**: 采用了专业的文档排版标准（兼容中文 GB/T 规范），标题居中加粗，各级标题使用标准字号和间距。
- 🔠 **字体渲染修复**: 修复了 CJK 字符在 Word 中回退到 MS Gothic 的问题；现在正确使用配置的中文字体（例如宋体）。
- ⚙️ **标题对齐配置**: 新增 `标题对齐方式` Valve，支持配置文档标题的对齐方式（左对齐、居中、右对齐）。

### 用户级配置 (UserValves)

用户可以在个人设置中覆盖以下配置：

- `文档标题来源`
- `界面语言`
- `英文字体`, `中文字体`, `代码字体`
- `表头背景色`, `表格隔行背景色`
- `Mermaid_...` (部分 Mermaid 设置)
- `启用数学公式`, `启用行内公式`

---

## 安装

1. 下载插件文件：[`export_to_word.py`](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_docx)
2. 上传到 OpenWebUI：**Admin Panel** → **Settings** → **Functions**
3. 启用插件

---

## 使用方法

1. 打开想要导出的对话
2. 点击消息操作栏的 **Export to Word** 按钮
3. `.docx` 文件会自动下载

---

## 支持的 Markdown 语法

| 语法 | Word 效果 |
| :--- | :--- |
| `# 标题1` 到 `###### 标题6` | 标题级别 1-6 |
| `**粗体**` / `__粗体__` | 粗体文本 |
| `*斜体*` / `_斜体_` | 斜体文本 |
| `***粗斜体***` | 粗体 + 斜体 |
| `` `行内代码` `` | 等宽字体 + 灰色背景 |
| <code>``` 代码块 ```</code> | 语法高亮代码块 |
| `> 引用文本` | 左侧边框的灰色斜体 |
| `[链接](url)` | 蓝色下划线链接 |
| `~~删除线~~` | 删除线 |
| `- 项目` / `* 项目` | 无序列表 |
| `1. 项目` | 有序列表 |
| Markdown 表格 | **增强表格**（智能列宽） |
| `---` / `***` | 水平分割线 |
| `$$LaTeX$$` 或 `\[LaTeX\]` | **原生 Word 公式**（块级） |
| `$LaTeX$` 或 `\(LaTeX\)` | **原生 Word 公式**（行内） |
| ` ```mermaid ... ``` ` | **Mermaid 图表**（图片形式） |
| `[1]` 引用标记 | **可点击链接**到参考资料 |

---

## 运行要求

!!! note "前置条件"
    - `python-docx==1.1.2`（文档生成）
    - `Pygments>=2.15.0`（语法高亮）
    - `latex2mathml`（LaTeX 转 MathML）
    - `mathml2omml`（MathML 转 Office Math）

---
5.0
## 源码

[:fontawesome-brands-github: View on GitHub](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_docx){ .md-button }
**Author:** [Fu-Jie](https://github.com/Fu-Jie) | **Version:** 0.4.4 | **Project:** [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
