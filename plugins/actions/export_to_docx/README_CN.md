# 📝 导出为 Word (增强版)

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v0.5.1 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

将对话导出为 Word (.docx)，支持**代码语法高亮**、**原生数学公式**、**Mermaid 图表**、**引用参考**和**增强表格格式**。

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) ，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## 🔥 v0.5.0 更新内容

- 🔠 **标题级别字体自定义**: 新增 `一级标题西文字体`、`一级标题中文字体`、`二级标题西文字体`、`二级标题中文字体` 阀门 — 可为 H1 和 H2 独立配置字体，不再与正文字体绑定。
- ⬆️ **相对标题算法**: 当内容没有 H1 时，自动提升标题级别（如 `## → #`），确保文档层级结构正确。
- 🧹 **元数据清理**: Word 文档属性（`author`、`last_modified_by` 等）现在使用真实用户名，不再暴露 `python-docx` 库指纹。
- 🎨 **标题样式修复**: 清除了 Word 主题字体继承（`w:asciiTheme`、`w:eastAsiaTheme`），涵盖 Title、Heading 1-9 和默认样式，防止 Word 覆盖自定义字体（如宋体回退问题）。移除了标题样式上多余的下划线和边框。

## ✨ 核心特性

- 🚀 **一键导出**: 在聊天界面添加"导出为 Word"动作按钮。
- 📄 **Markdown 转换**: 完整支持 Markdown 语法（标题、粗体、斜体、代码、表格、列表）。
- 🎨 **代码语法高亮**: 使用 Pygments 库高亮代码块（支持 500+ 种语言）。
- 🔢 **原生数学公式**: LaTeX 公式（`$$...$$`、`\[...\]`、`$...$`）转换为可编辑的 Word 公式。
- 📊 **Mermaid 图表**: 流程图和时序图渲染为文档中的图片。
- 📚 **引用与参考**: 自动生成参考资料章节，支持可点击的引用链接。
- 🧹 **移除思考过程**: 自动移除 AI 思考块（`<think>`、`<analysis>`）。
- 📋 **增强表格**: 智能列宽、对齐、表头跨页重复。
- 💬 **引用块支持**: Markdown 引用块渲染为带左侧边框的灰色斜体样式。
- 🌐 **多语言支持**: 正确处理中文和英文文本。

## 🚀 使用方法

1. **安装**: 在 Open WebUI 社区搜索 "导出为 Word" 并安装。
2. **触发**: 在任意对话中，点击"导出为 Word"动作按钮。
3. **下载**: .docx 文件将自动下载到你的设备。

## ⚙️ 配置参数 (Valves)

| 参数 | 默认值 | 说明 |
| :--- | :--- | :--- |
| **文档标题来源** | `chat_title` | `chat_title`（对话标题）、`ai_generated`（AI 生成）、`markdown_title`（Markdown 标题）|
| **最大嵌入图片大小MB** | `20` | 嵌入图片的最大大小 (MB) |
| **界面语言** | `zh` | `en`（英语）或 `zh`（中文）|
| **英文字体** | `Calibri` | 英文字体名称 |
| **中文字体** | `SimSun` | 中文字体名称 |
| **代码字体** | `Consolas` | 代码块字体名称 |
| **一级标题西文字体** | `Aptos Display` | H1 西文字体名称 |
| **一级标题中文字体** | `SimHei` | H1 中文字体名称 |
| **二级标题西文字体** | `Calibri Light` | H2 西文字体名称 |
| **二级标题中文字体** | `SimHei` | H2 中文字体名称 |
| **表头背景色** | `F2F2F2` | 表头背景色（十六进制）|
| **表格隔行背景色** | `FBFBFB` | 表格隔行背景色（十六进制）|
| **Mermaid_PNG缩放比例** | `3.0` | Mermaid 图片分辨率倍数 |
| **启用数学公式** | `True` | 启用 LaTeX 公式转换 |

## ⭐ 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

## 🛠️ 支持的 Markdown 语法

| 语法 | Word 效果 |
| :--- | :--- |
| `# 标题1` 到 `###### 标题6` | 标题级别 1-6 |
| `**粗体**` 或 `__粗体__` | 粗体文本 |
| `*斜体*` 或 `_斜体_` | 斜体文本 |
| `` `行内代码` `` | 等宽字体 + 灰色背景 |
| ` ``` 代码块 ``` ` | **语法高亮**的代码块 |
| `> 引用文本` | 带左侧边框的灰色斜体文本 |
| `[链接](url)` | 蓝色下划线链接文本 |
| `~~删除线~~` | 删除线文本 |
| `- 项目` 或 `* 项目` | 无序列表 |
| `1. 项目` | 有序列表 |
| Markdown 表格 | **增强表格**（智能列宽）|
| `$$LaTeX$$` 或 `\[LaTeX\]` | **原生 Word 公式**（块级）|
| `$LaTeX$` 或 `\(LaTeX\)` | **原生 Word 公式**（行内）|
| ` ```mermaid ... ``` ` | **Mermaid 图表**（图片形式）|
| `[1]` 引用标记 | **可点击链接**到参考资料 |

## 📦 依赖

- `python-docx==1.1.2` - Word 文档生成
- `Pygments>=2.15.0` - 语法高亮
- `latex2mathml` - LaTeX 转 MathML
- `mathml2omml` - MathML 转 Office Math (OMML)

## 故障排除 (Troubleshooting) ❓

- **插件不工作？**: 请检查是否在模型设置中启用了该过滤器/动作。
- **调试日志**: 请查看浏览器控制台 (F12) 获取详细日志（如果可用）。
- **错误信息**: 如果看到错误，请复制完整的错误信息并报告。
- **提交 Issue**: 如果遇到任何问题，请在 GitHub 上提交 Issue：[OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## 📝 更新日志

完整历史请查看 GitHub 项目： [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
