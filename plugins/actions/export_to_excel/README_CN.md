# 📊 导出为 Excel

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v0.3.11 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

将对话历史直接导出为 Excel (.xlsx) 文件。

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) ，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## v0.3.11 最新更新

- **OpenWebUI >= 0.9.0 / v0.10.1 上的异步 DB 兼容性**：`_call_db` 现在用 `iscoroutinefunction` + `asyncio.iscoroutine` 检测 DB 方法是否为异步，不再依赖 `_owui_version_ge("0.9.0")`。在隔离的插件沙箱里版本导入有时会回退到 `"0.0.0"`，此前会导致异步 DB 方法被同步调用。本版本解决 `RuntimeWarning: coroutine '_call_db' was never awaited` 和 `AttributeError: 'coroutine' object has no attribute 'params'/'email'`。OpenWebUI < 0.9.0 上行为不变。

## 🔥 v0.3.10 更新内容

- 🛠️ **Open WebUI 0.10.x 兼容性修复（关键）**: OWUI 0.10 将助手回复迁移到结构化 `output` 字段，`content` 变空，导致导出报错 "No tables found to export!"。现在通过 `ChatMessages` + `convert_output_to_messages` 用 OpenWebUI 原生方式恢复每条目标消息的文本（排除推理内容），使表格提取和 AI 标题生成能再次读取到真实内容。**要求 OWUI ≥ 0.10.2。**
- 📏 **文件名长度限制**: 过长的对话标题可能超过操作系统文件名限制（"File name too long"）。工作簿文件名现在会被清理并限制到安全长度。

<details>
<summary>v0.3.9 更新内容</summary>

- 📏 **可配置行高**：新增 `ROW_HEIGHT` 配置项，可控制数据行高度。设为 `0`（默认）根据内容自动调整，或设置固定值（如 `20`）以获得紧凑的单行显示。
- 📐 **可配置列宽**：新增 `COLUMN_WIDTH` 配置项，可控制列宽。设为 `0`（默认）根据内容自动调整，或设置固定值（如 `15`）以获得统一的紧凑列宽。

</details>

## ✨ 核心特性

- 🚀 **一键导出**：在聊天界面添加“导出为 Excel”按钮。
- 🧠 **自动表头提取**：智能识别聊天内容中的表格标题。
- 📊 **多表支持**：支持单次对话中的多个表格。

## 🚀 使用方法

1. **安装**：在 Open WebUI 社区搜索“导出为 Excel”并安装。
2. **触发**：在任意对话中，点击“导出为 Excel”动作按钮。
3. **下载**：.xlsx 文件将自动下载到你的设备。

## ⚙️ 配置参数 (Valves)

| 参数 | 默认值 | 描述 |
| :--- | :--- | :--- |
| `TITLE_SOURCE` | `chat_title` | 文件名来源：`chat_title`、`ai_generated`、`markdown_title`。 |
| `EXPORT_SCOPE` | `last_message` | 导出范围：`last_message` 或 `all_messages`。 |
| `MODEL_ID` | `""` | AI 标题生成的模型 ID。为空则使用当前对话模型。 |
| `SHOW_STATUS` | `True` | 是否显示操作状态更新。 |
| `SHOW_DEBUG_LOG` | `False` | 是否在浏览器控制台输出调试日志 (F12)。 |
| `ROW_HEIGHT` | `0` | 数据行固定行高（点数）。`0` = 根据内容自动调整。例如设置 `20` 为紧凑行高。 |
| `COLUMN_WIDTH` | `0` | 所有数据列固定列宽（字符数）。`0` = 根据内容自动调整。例如设置 `15` 为统一紧凑列宽。 |

## ⭐ 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

## 故障排除 (Troubleshooting) ❓

- **插件不工作？**: 请检查是否在模型设置中启用了该过滤器/动作。
- **调试日志**: 如需排查，启用 `SHOW_STATUS` 并查看浏览器控制台 (F12)。
- **错误信息**: 如果看到错误，请复制完整的错误信息并报告。
- **提交 Issue**: 如果遇到任何问题，请在 GitHub 上提交 Issue：[OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## 更新日志

完整历史请查看 GitHub 项目： [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)# 导出为 Excel

此插件允许你直接从聊天界面将对话历史导出为 Excel (.xlsx) 文件。

## v0.3.6 更新内容

- **OpenWebUI 风格主题**：现代深灰表头 (#1f2937)，搭配浅灰斑马纹，提升可读性。
- **斑马纹效果**：隔行变色（#ffffff / #f3f4f6），方便视觉扫描。
- **智能数据类型转换**：自动将列转换为数字或日期类型，无法转换时保持字符串。
- **全单元格粗体/斜体**：支持 Excel 中的全单元格 Markdown 粗体 (`**text**`) 和斜体 (`*text*`) 格式。
- **部分 Markdown 清理**：自动移除部分 Markdown 格式符号（如 `部分**加粗**文本` → `部分加粗文本`），使 Excel 输出更整洁。
- **导出范围**: 新增 `EXPORT_SCOPE` 配置项，可选择导出"最后一条消息"（默认）或"所有消息"中的表格。
- **智能 Sheet 命名**: 根据 Markdown 标题、AI 标题（如启用）或消息索引（如 `消息1-表1`）自动命名 Sheet。
- **多表格支持**: 优化了对单条或多条消息中包含多个表格的处理。
- **智能文件名生成**：支持根据对话标题、AI 总结或 Markdown 标题生成文件名。
- **配置选项**：新增 `TITLE_SOURCE` 设置，用于控制文件名生成策略。
- **AI 标题生成**：新增 `MODEL_ID` 设置用于指定 AI 标题生成模型，并支持生成进度通知。

## 功能特点

- **一键导出**：在聊天界面添加"导出为 Excel"按钮。
- **自动表头提取**：智能识别聊天内容中的表格标题。
- **多表支持**：支持处理单次对话中的多个表格。

## 配置

- **标题来源 (Title Source)**：选择文件名的生成方式：
  - `chat_title`：使用对话标题（默认）。
  - `ai_generated`：使用 AI 根据内容生成简洁标题。
  - `markdown_title`：提取 Markdown 内容中的第一个 H1/H2 标题。

## 使用方法

1. 安装插件。
2. 在任意对话中，点击"导出为 Excel"按钮。
3. 文件将自动下载到你的设备。

## 作者

Fu-Jie
GitHub: [Fu-Jie/openwebui-extensions](https://github.com/Fu-Jie/openwebui-extensions)

## 许可证

MIT License
