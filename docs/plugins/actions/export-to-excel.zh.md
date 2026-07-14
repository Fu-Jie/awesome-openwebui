# Export to Excel（导出到 Excel）

<span class="category-badge action">Action</span>
<span class="version-badge">v0.3.11</span>

将聊天记录导出为 Excel 表格，便于分析、归档和分享。


### v0.3.11 最新更新

- **OpenWebUI >= 0.9.0 / v0.10.1 上的异步 DB 兼容性**：`_call_db` 现在用 `iscoroutinefunction` + `asyncio.iscoroutine` 检测 DB 方法是否为异步，不再依赖 `_owui_version_ge("0.9.0")`。在隔离的插件沙箱里版本导入有时会回退到 `"0.0.0"`，此前会导致异步 DB 方法被同步调用。本版本解决 `RuntimeWarning: coroutine '_call_db' was never awaited` 和 `AttributeError: 'coroutine' object has no attribute 'params'/'email'`。OpenWebUI < 0.9.0 上行为不变。

### v0.3.9 更新内容
- 📏 **可配置行高**：新增 `ROW_HEIGHT` 配置项，可控制数据行高度。设为 `0`（默认）根据内容自动调整，或设置固定值（如 `20`）以获得紧凑的单行显示。
- 📐 **可配置列宽**：新增 `COLUMN_WIDTH` 配置项，可控制列宽。设为 `0`（默认）根据内容自动调整，或设置固定值（如 `15`）以获得统一的紧凑列宽。

---


## 概览

Export to Excel 插件可以把你的聊天记录下载为 Excel 文件，适用于：

- 归档重要对话
- 分析聊天数据
- 与同事共享对话内容
- 将 AI 辅助的研究整理成文档

## 功能特性

- :material-file-excel: **Excel 导出**：标准 `.xlsx` 格式
- :material-table: **格式化输出**：整洁的表格结构
- :material-download: **一键下载**：即时生成文件
- :material-history: **完整历史**：导出完整会话内容

## 配置

- **标题来源 (Title Source)**：选择文件名的生成方式：
  - `chat_title`：使用对话标题（默认）。
  - `ai_generated`：使用 AI 根据内容生成简洁标题。
  - `markdown_title`：提取 Markdown 内容中的第一个 H1/H2 标题。
- **列宽 (COLUMN_WIDTH)**：所有数据列固定列宽（字符数）。`0`（默认）根据内容自动调整，设置如 `15` 可获得统一的紧凑列宽。
- **行高 (ROW_HEIGHT)**：数据行固定行高（点数）。`0`（默认）根据内容自动调整，设置如 `20` 可获得紧凑的单行显示。

---

## 安装

1. 下载插件文件：[`export_to_excel.py`](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_excel)
2. 上传到 OpenWebUI：**Admin Panel** → **Settings** → **Functions**
3. 启用插件

---

## 使用方法

1. 打开想要导出的对话
2. 点击消息操作栏中的 **Export** 按钮
3. Excel 文件会自动下载

---

## 导出格式

生成的 Excel 文件包含：

| 列 | 说明 |
|--------|-------------|
| Timestamp | 消息发送时间 |
| Role | 角色（用户 / 助手） |
| Content | 消息文本内容 |
| Model | 使用的模型（助手消息） |

---

## 运行要求

!!! note "前置条件"
    - OpenWebUI v0.3.0 及以上
    - 无需额外 Python 依赖（使用内置库）

---

## 源码

[:fontawesome-brands-github: 在 GitHub 查看](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_excel){ .md-button }
