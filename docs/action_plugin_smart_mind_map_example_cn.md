# Open WebUI Action 插件开发范例：智绘心图

## 引言

“智绘心图” (`smart-mind-map`) 是一个功能强大的 Open WebUI Action 插件。它通过分析用户提供的文本，利用大语言模型（LLM）提取关键信息，并最终生成一个可交互的、可视化的思维导图。本文档将深入解析其源码 (`思维导图.py`)，提炼其中蕴含的插件开发知识与最佳实践，为开发者提供一个高质量的参考范例。

## 核心开发知识点

- **插件元数据定义**: 如何通过文件头注释定义插件的标题、图标、版本和描述。
- **可配置参数 (`Valves`)**: 如何为插件提供灵活的配置选项。
- **异步 `action` 方法**: 插件主入口的实现方式及其核心参数的使用。
- **实时前端交互 (`EventEmitter`)**: 如何向用户发送实时状态更新和通知。
- **与 LLM 交互**: 如何构建动态 Prompt、调用内置 LLM 服务并处理返回结果。
- **富文本 (HTML/JS) 输出**: 如何生成包含复杂前端逻辑的 HTML 内容，并将其嵌入聊天响应中。
- **健壮性设计**: 如何实现输入验证、全面的错误处理和日志记录。
- **访问 Open WebUI 核心模型**: 如何与 Open WebUI 的数据模型（如 `Users`）交互。

---

### 1. 插件元数据定义

Open WebUI 通过文件顶部的特定格式注释来识别和展示插件信息。

**代码示例 (`思维导图.py`):**
```python
"""
title: 智绘心图
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CiAgPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyIgZmlsbD0iY3VycmVudENvbG9yIi8+CiAgPGxpbmUgeDE9IjEyIiB5MT0iOSIgeDI9IjEyIiB5Mj0iNCIvPgogIDxjaXJjbGUgY3g9IjEyIiBjeT0iMyIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjEyIiB5MT0iMTUiIHgyPSIxMiIgeTI9IjIwIi8+CiAgPGNpcmNsZSBjeD0iMTIiIGN5PSIyMSIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjkiIHkxPSIxMiIgeDI9IjQiIHkyPSIxMiIvPgogIDxjaXJjbGUgY3g9IjMiIGN5PSIxMiIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjE1IiB5MT0iMTIiIHgyPSIyMCIgeTI9IjEyIi8+CiAgPGNpcmNsZSBjeD0iMjEiIGN5PSIxMiIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjEwLjUiIHkxPSྡ1LjUiIHgyPSI2IiB5Mj0iNiIvPgogIDxjaXJjbGUgY3g9IjUiIGN5PSI1Iigcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjEzLjUiIHkxPSྡ5LjUgeDI9IjE1IiB5Mj0iNiIvPgogIDxjaXJjbGUgY3g9IjE5IiBjeT0iNSIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9ྡ1LjUgeTE9ྡ3MuNSB4Mj0iNiIgeTI9IjE4Ii8+CiAgPGNpcmNsZSBjeD0iNSIgY3k9IjE5IiByPSྡ1LjUiLz4KICA8bGluZSB4MT0ྡzIuNSB5MT0ྡzIuNSB4Mj0iNSIgeTI9IjE4Ii8+CiAgPGNpcmNsZSBjeD0ྡ5IiBjeT0ྡ5IiByPSྡ1LjUiLz4KPC9zdmc+Cg==
version: 0.7.2
description: 智能分析文本内容,生成交互式思维导图,帮助用户结构化和可视化知识。
"""
```
**知识点**:
- `title`: 插件在 UI 中显示的名称。
- `icon_url`: 插件的图标，支持 base64 编码的 SVG，以实现无依赖的矢量图标。
- `version`: 插件的版本号。
- `description`: 插件的功能简介。

---

### 2. 可配置参数 (`Valves`)

通过在 `Action` 类内部定义一个 `Valves` Pydantic 模型，可以为插件创建可在 Web UI 中配置的参数。

**代码示例 (`思维导图.py`):**
```python
class Action:
    class Valves(BaseModel):
        show_status: bool = Field(
            default=True, description="是否在聊天界面显示操作状态更新。"
        )
        LLM_MODEL_ID: str = Field(
            default="gemini-2.5-flash",
            description="用于文本分析的内置LLM模型ID。",
        )
        MIN_TEXT_LENGTH: int = Field(
            default=100, description="进行思维导图分析所需的最小文本长度(字符数)。"
        )

    def __init__(self):
        self.valves = self.Valves()
```
**知识点**:
- `Valves` 类继承自 `pydantic.BaseModel`。
- 每个字段都是一个配置项，`default` 是默认值，`description` 会在 UI 中作为提示信息显示。
- 在 `__init__` 中实例化 `self.valves`，之后可以通过 `self.valves.PARAMETER_NAME` 来访问配置值。

---

### 3. 异步 `action` 方法

`action` 方法是插件的执行入口，它是一个异步函数，接收 Open WebUI 传入的上下文信息。

**代码示例 (`思维导图.py`):**
```python
    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __request__: Optional[Request] = None,
    ) -> Optional[dict]:
        # ... 插件逻辑 ...
        return body
```
**知识点**:
- `body`: 包含当前聊天上下文的字典，最重要的是 `body.get("messages")`，它包含了完整的消息历史。
- `__user__`: 包含当前用户信息的字典，如 `id`, `name`, `language` 等。插件中演示了如何兼容其为 `dict` 或 `list` 的情况。
- `__event_emitter__`: 一个可调用的异步函数，用于向前端发送事件，是实现实时反馈的关键。
- `__request__`: FastAPI 的 `Request` 对象，用于访问底层请求信息，例如在调用 `generate_chat_completion` 时需要传递。
- **返回值**: `action` 方法需要返回修改后的 `body` 字典，其中包含了插件生成的响应。

---

### 4. 实时前端交互 (`EventEmitter`)

使用 `__event_emitter__` 可以极大地提升用户体验，让用户了解插件的执行进度。

**代码示例 (`思维导图.py`):**
```python
# 发送通知 (Toast)
await __event_emitter__( 
    {
        "type": "notification",
        "data": {
            "type": "info",  # 'info', 'success', 'warning', 'error'
            "content": "智绘心图已启动，正在为您生成思维导图...",
        },
    }
)

# 发送状态更新 (Status Bar)
await __event_emitter__( 
    {
        "type": "status",
        "data": {
            "description": "智绘心图: 深入分析文本结构...",
            "done": False,  # False 表示进行中
            "hidden": False,
        },
    }
)

# 任务完成
await __event_emitter__( 
    {
        "type": "status",
        "data": {
            "description": "智绘心图: 绘制完成！",
            "done": True,  # True 表示已完成
            "hidden": False, # True 可以让成功状态自动隐藏
        },
    }
)
```
**知识点**:
- **通知 (`notification`)**: 在屏幕角落弹出短暂的提示信息，适合用于触发、成功或失败的即时反馈。
- **状态 (`status`)**: 在聊天输入框上方显示一个持久的状态条，适合展示多步骤任务的当前进度。`done: True` 会标记任务完成。

---

### 5. 与 LLM 交互

插件的核心功能通常依赖于 LLM。`智绘心图` 演示了如何构建一个结构化的 Prompt 并调用 LLM。

**代码示例 (`思维导图.py`):**
```python
# 1. 构建动态 Prompt
SYSTEM_PROMPT_MINDMAP_ASSISTANT = "..." # 系统指令
USER_PROMPT_GENERATE_MINDMAP = "..." # 用户指令模板

formatted_user_prompt = USER_PROMPT_GENERATE_MINDMAP.format(
    user_name=user_name,
    # ... 注入其他上下文信息
    long_text_content=long_text_content,
)

# 2. 准备 LLM 请求体
llm_payload = {
    "model": self.valves.LLM_MODEL_ID,
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT_MINDMAP_ASSISTANT},
        {"role": "user", "content": formatted_user_prompt},
    ],
    "temperature": 0.5,
    "stream": False,
}

# 3. 获取用户对象并调用 LLM
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users

user_obj = Users.get_user_by_id(user_id)
llm_response = await generate_chat_completion(
    __request__, llm_payload, user_obj
)

# 4. 处理响应
assistant_response_content = llm_response["choices"][0]["message"]["content"]
markdown_syntax = self._extract_markdown_syntax(assistant_response_content)
```
**知识点**:
- **Prompt 工程**: 将系统指令和用户指令分离。在用户指令中动态注入上下文信息（如用户名、时间、语言），可以使 LLM 的输出更具个性化和准确性。
- **调用工具**: 使用 `open_webui.utils.chat.generate_chat_completion` 是与 Open WebUI 内置 LLM 服务交互的标准方式。
- **用户上下文**: 调用 `generate_chat_completion` 需要传递 `user_obj`，这可能用于权限控制、计费或模型特定的用户标识。通过 `open_webui.models.users.Users.get_user_by_id` 获取该对象。
- **响应解析**: LLM 的响应需要被解析。该插件使用正则表达式从返回的文本中提取核心的 Markdown 内容，并提供了回退机制。

---

### 6. 富文本 (HTML/JS) 输出

Action 插件的一大亮点是能够生成 HTML，从而在聊天界面中渲染丰富的交互式内容。

**代码示例 (`思维导图.py`):**
```python
# 1. 定义 HTML 模板
HTML_TEMPLATE_MINDMAP = """
<!DOCTYPE html>
<html>
<head>
    <!-- 引入 Markmap.js 等外部库 -->
    <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.17"></script>
    <style>...</style>
</head>
<body>
    <!-- 动态内容占位符 -->
    <div id="markmap-container-{unique_id}"></div>
    <script type="text/template" id="markdown-source-{unique_id}">{markdown_syntax}</script>
    <script>
      // 嵌入的 JavaScript 逻辑
      (function() {
        const uniqueId = "{unique_id}";
        // ... 渲染逻辑、事件处理 ...
      })();
    </script>
</body>
</html>
"""

# 2. 注入动态内容
final_html_content =
    HTML_TEMPLATE_MINDMAP.replace("{unique_id}", unique_id)
    .replace("{markdown_syntax}", markdown_syntax)
    # ... 替换其他占位符

# 3. 嵌入到聊天响应中
html_embed_tag = f"```html\n{final_html_content}\n```"
body["messages"][-1]["content"] = f"{long_text_content}\n\n{html_embed_tag}"
```
**知识点**:
- **HTML 模板**: 将静态 HTML/CSS/JS 代码定义为模板字符串，使用占位符（如 `{unique_id}`）来注入动态数据。
- **嵌入 JS**: 可以在 HTML 中直接嵌入 JavaScript 代码，用于处理前端交互逻辑，如渲染图表、绑定按钮事件等。`智绘心图` 的 JS 代码负责调用 Markmap.js 库来渲染思维导图，并实现了“复制 SVG”和“复制 Markdown”的按钮功能。
- **唯一 ID**: 使用 `unique_id` 是一个好习惯，可以防止在同一页面上多次使用该插件时发生 DOM 元素 ID 冲突。
- **响应格式**: 最终的 HTML 内容需要被包裹在 ````html\n...\n```` 代码块中，Open WebUI 的前端会自动识别并渲染它。
- **内容追加**: 插件将生成的 HTML 追加到原始用户输入之后，而不是替换它，保留了上下文。

---

### 7. 健壮性设计

一个生产级的插件必须具备良好的健壮性。

**代码示例 (`思维导图.py`):**
```python
# 输入验证
if len(long_text_content) < self.valves.MIN_TEXT_LENGTH:
    # ... 返回警告信息 ...
    return {"messages": [...]}

# 完整的异常捕获
try:
    # ... 核心逻辑 ...
except Exception as e:
    error_message = f"智绘心图处理失败: {str(e)}"
    logger.error(f"智绘心图错误: {error_message}", exc_info=True)
    
    # 向前端发送错误通知
    if __event_emitter__:
        await __event_emitter__(...)
    
    # 在聊天中显示错误信息
    body["messages"][-1]["content"] = f"❌ **错误:** {user_facing_error}"

# 日志记录
import logging
logger = logging.getLogger(__name__)
logger.info("Action started")
logger.error("Error occurred", exc_info=True)
```
**知识点**:
- **输入验证**: 在执行核心逻辑前，对输入（如文本长度）进行检查，可以避免不必要的资源消耗和潜在错误。
- **`try...except` 块**: 将主要逻辑包裹在 `try` 块中，并捕获 `Exception`，确保任何意外失败都能被优雅地处理。
- **用户友好的错误反馈**: 在 `except` 块中，不仅要记录详细的错误日志（`logger.error`），还要通过 `EventEmitter` 和聊天消息向用户提供清晰、可操作的错误提示。
- **日志**: 使用 `logging` 模块记录关键步骤和错误信息，是调试和监控插件运行状态的重要手段。`exc_info=True` 会记录完整的堆栈跟踪。

---

### 总结

`智绘心图` 插件是一个优秀的 Open WebUI Action 开发学习案例。它全面展示了如何利用 Action 插件的各项功能，构建一个交互性强、用户体验好、功能完整且健壮的 AI 应用。

**最佳实践总结**:
- **明确元数据**: 为你的插件提供清晰的 `title`, `icon`, `description`。
- **提供配置**: 使用 `Valves` 让插件更灵活。
- **善用反馈**: 积极使用 `EventEmitter` 提供实时状态和通知。
- **结构化 Prompt**: 精心设计的 Prompt 是高质量输出的保证。
- **拥抱富文本**: 利用 HTML 和 JS 创造丰富的交互体验。
- **防御性编程**: 始终考虑输入验证和错误处理。
- **详细日志**: 记录日志是排查问题的关键。

通过学习和借鉴`智绘心图`的设计模式，开发者可以更高效地构建出属于自己的高质量 Open WebUI 插件。
