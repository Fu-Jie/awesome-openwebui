# 智能信息图

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v1.6.0 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

基于 AntV Infographic 引擎的 Open WebUI 插件，能够将长文本内容一键转换为专业、美观的信息图表。

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/tools/batch-install-plugins)，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## 🔥 最新更新 v1.6.0

- 🌐 **智能语言检测**：自动从浏览器准确识别当前界面语言设置。
- 🗣️ **上下文感知生成**：生成的信息图内容现在严格跟随用户输入内容的语言（例如：输入日语 -> 生成日语信息图）。
- 🐛 **问题修复**：修复了界面语言与生成内容语言不同步的问题。

## ✨ 核心特性

- 🚀 **智能转换**：自动分析文本核心逻辑，提取关键点并生成结构化图表。
- 🎨 **70+ 专业模板**：内置多种 AntV 官方模板，包括列表、树图、路线图、时间线、对比图、SWOT、象限图及统计图表等。
- 🔍 **自动图标匹配**：内置图标搜索逻辑，支持 Iconify 图标和 unDraw 插图自动匹配。
- 📥 **多格式导出**：支持一键下载为 **SVG**、**PNG** 或 **独立 HTML** 文件。
- 🌈 **高度自定义**：支持深色/浅色模式，自动适配主题颜色，主标题加粗突出，卡片布局精美。
- 📱 **响应式设计**：生成的图表在桌面端和移动端均有良好的展示效果。

## 🚀 使用方法

1. **安装插件**：在 Open WebUI 插件市场搜索并安装。
2. **触发生成**：在对话框中输入一段长文本，点击输入框旁边的 **Action 按钮**（📊 图标）。
3. **AI 处理**：AI 会自动分析文本并生成对应的信息图语法。
4. **预览与下载**：在渲染区域预览效果，满意后点击下方的下载按钮保存。

## ⚙️ 配置参数 (Valves)

在插件设置界面，你可以调整以下参数来优化生成效果：

| 参数名称 | 默认值 | 说明 |
| :--- | :--- | :--- |
| **显示状态 (SHOW_STATUS)** | `True` | 是否在聊天界面实时显示 AI 分析和生成的进度状态。 |
| **模型 ID (MODEL_ID)** | `空` | 指定用于文本分析的 LLM 模型。留空则默认使用当前对话的模型。 |
| **最小文本长度 (MIN_TEXT_LENGTH)** | `100` | 触发分析所需的最小字符数，防止对过短的对话误操作。 |
| **清除旧结果 (CLEAR_PREVIOUS_HTML)** | `False` | 每次生成是否清除之前的图表。若为 `False`，新图表将追加在下方。 |
| **上下文消息数 (MESSAGE_COUNT)** | `1` | 用于分析的最近消息条数。增加此值可让 AI 参考更多对话背景。 |
| **输出模式 (OUTPUT_MODE)** | `image` | `image` 为静态图片嵌入（默认，兼容性好），`html` 为交互式图表。 |

## ⭐ 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

## 🛠️ 支持的模板类型

| 分类 | 模板名称 | 适用场景 |
| :--- | :--- | :--- |
| **时序与流程** | `sequence-timeline-simple`, `sequence-roadmap-vertical-simple`, `sequence-snake-steps-compact-card` | 时间线、路线图、步骤说明 |
| **列表与网格** | `list-grid-candy-card-lite`, `list-row-horizontal-icon-arrow`, `list-column-simple-vertical-arrow` | 功能亮点、要点列举、清单 |
| **对比与分析** | `compare-binary-horizontal-underline-text-vs`, `compare-swot`, `quadrant-quarter-simple-card` | 优劣势对比、SWOT 分析、象限图 |
| **层级与结构** | `hierarchy-tree-tech-style-capsule-item`, `hierarchy-structure` | 组织架构、层级关系 |
| **图表与数据** | `chart-column-simple`, `chart-bar-plain-text`, `chart-line-plain-text`, `chart-wordcloud` | 数据趋势、比例分布、数值对比 |

## 故障排除 (Troubleshooting) ❓

- **插件不工作？**: 请检查是否在模型设置中启用了该过滤器/动作。
- **调试日志**: 在 Valves 中启用 `SHOW_STATUS` 以查看进度更新。
- **错误信息**: 如果看到错误，请复制完整的错误信息并报告。
- **提交 Issue**: 如果遇到任何问题，请在 GitHub 上提交 Issue：[OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## 更新日志

完整历史请查看 GitHub 项目： [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)

## 📝 语法示例 (高级用户)

你也可以直接输入以下语法让 AI 渲染：

```infographic
infographic list-grid
data
  title 🚀 插件优势
  desc 为什么选择智能信息图插件
  items
    - label 极速生成
      desc 秒级完成文本到图表的转换
    - label 视觉精美
      desc 采用 AntV 专业设计规范
```
