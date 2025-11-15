# Open WebUI 插件开发核心模块指南

## 引言

在开发 Open WebUI 插件（无论是 `Pipe`、`Filter` 还是 `Action`）时，框架本身提供了一系列核心模块和上下文参数，用于与 Open WebUI 的后端数据和功能进行交互。理解并善用这些模块和参数是构建强大、稳定插件的关键。

本文档旨在汇总分析现有高级插件（如 `Gemini Manifold`, `Async Context Compression`, `Inject Env` 等）中所使用的 `open_webui` 核心功能，为开发者提供一份清晰、实用的“SDK”指南。

## ⚠️ 重要提示：同步与异步

Open WebUI 的插件运行在 `asyncio` 事件循环中（`pipe`, `inlet`, `outlet`, `action` 都是 `async` 函数）。然而，大部分数据库和文件系统相关的核心模块方法（如 `Chats.get_chat_by_id`, `Files.get_file_by_id`, `Storage.upload_file`）都是**同步阻塞**的。

为了避免阻塞服务器的主事件循环，**必须**使用 `asyncio.to_thread` 来包装这些同步调用。

**错误示范 (会阻塞服务):**
```python
# ❌ 错误
chat = Chats.get_chat_by_id_and_user_id(chat_id, user_id)
```

**正确示范 (在线程池中运行):**
```python
import asyncio

# ✓ 正确
chat = await asyncio.to_thread(
    Chats.get_chat_by_id_and_user_id,
    chat_id,
    user_id
)
```

---

## 1. 插件核心方法参数详解

Open WebUI 的插件（`Pipe`, `Filter`, `Action`）通过其核心方法（`pipe`, `inlet`, `outlet`, `action`）接收一系列标准化的参数，这些参数是插件与外界交互的入口。

```python
async def inlet(
    self,
    body: dict,
    __user__: Optional[dict] = None,
    __metadata__: Optional[dict] = None,
    __model__: Optional[dict] = None,
    __request__: Optional[Request] = None,
    # ... 其他参数
) -> dict:
```

### 1.1 `body: dict`

-   **功能**: 代表前端发送过来的原始请求体，是插件最主要的操作对象。
-   **核心字段**:
    -   `body["messages"]`: 一个列表，包含了到当前回合为止的对话历史。插件可以读取、修改或替换它。
    -   `body["model"]`: 当前请求希望使用的模型 ID。插件可以修改它来实现“模型重定向”。
    -   `body["stream"]`: 布尔值，指示前端是否期望流式响应。
    -   `body["features"]`: 一个字典，包含了用户在前端 UI 上开启的各项功能开关，如 `{"web_search": True}`。

### 1.2 `__user__: dict`

-   **功能**: 包含了当前发起请求的用户的详细信息。
-   **核心字段**:
    -   `__user__["id"]`: 用户唯一 ID。
    -   `__user__["name"]`: 用户名。
    -   `__user__["email"]`: 用户邮箱。
    -   `__user__["language"]`: 用户的界面语言偏好（如 `zh-CN`）。
    -   `__user__["valves"]`: 一个字典，包含了该用户为本次请求设置的、用于覆盖插件默认配置的 `UserValves`。

### 1.3 `__metadata__: dict`

-   **功能**: 包含了关于本次请求的元数据，是插件获取额外上下文和进行内部通信的关键。
-   **核心字段**:
    -   `__metadata__["chat_id"]`: 当前对话的唯一 ID。
    -   `__metadata__["message_id"]`: 当前消息的唯一 ID。
    -   `__metadata__["features"]`: 一个专为插件间通信设计的字典。`Filter` 可以在这里设置一些标志，供后续的 `Pipe` 读取。
    -   `__metadata__["variables"]`: **（非常实用）** 一个由 Open WebUI 自动填充的字典，包含了丰富的即用型环境变量。

**`variables` 字典详解**:
`inject_env` 插件展示了如何利用此字典为对话注入上下文。
```python
variables = __metadata__.get("variables", {})
variable_markdown = (
    "## 用户环境变量\n"
    f"- **用户姓名**：{variables.get('{{USER_NAME}}', '')}\n"
    f"- **当前日期时间**：{variables.get('{{CURRENT_DATETIME}}', '')}\n"
    f"- **当前星期**：{variables.get('{{CURRENT_WEEKDAY}}', '')}\n"
    f"- **当前时区**：{variables.get('{{CURRENT_TIMEZONE}}', '')}\n"
    f"- **用户语言**：{variables.get('{{USER_LANGUAGE}}', '')}\n"
)
```

### 1.4 `__model__: dict`

-   **功能**: 包含了当前请求所选模型的完整信息，比 `body["model"]` 更详细。
-   **核心字段**:
    -   `__model__["id"]`: 模型的完整 ID。
    -   `__model__["info"]["base_model_id"]`: 对于自定义模型，这指向它的基础模型 ID。这对于根据模型“家族”（如都属于 `qwen` 系列）来编写逻辑非常有用。

**代码示例:**
```python
# 检查模型是否属于某个系列
base_model_id = __model__.get("info", {}).get("base_model_id")
if base_model_id and base_model_id.startswith("cfchatqwen"):
    # 执行针对通义千问模型的特定逻辑
    body["chat_id"] = __metadata__["chat_id"]
```

### 1.5 `__request__: Request`

-   **功能**: FastAPI 的原始请求对象。
-   **核心用途**:
    -   `__request__.app.state`: 这是一个在单次 HTTP 请求生命周期内持续存在的共享状态对象。高级插件模式（如 `Pipe` 与 `Filter` 协同）用它来实现跨阶段的数据传递。例如，`Pipe` 插件可以将处理结果（如搜索元数据）存入 `state`，供后续的 `Filter` 在 `outlet` 阶段读取。

### 1.6 前端交互参数

插件可以通过 `__event_emitter__` 和 `__event_call__` 这两个特殊的参数与前端浏览器进行实时、动态的交互。

#### 1.6.1 `__event_emitter__` - 发送标准事件

-   **路径**: 作为 `pipe`, `inlet`, `outlet`, `action` 方法的参数传入。
-   **功能**: 向前端发送预定义的标准事件，用于显示通知（Toast）和状态更新。这是向用户提供实时反馈的标准方式。
-   **使用场景**:
    -   `{"type": "notification", "data": {...}}`: 在屏幕角落显示一个短暂的弹窗通知，适合用于操作开始、成功、失败等即时性反馈。
    -   `{"type": "status", "data": {...}}`: 在聊天输入框上方显示或更新一个状态条，适合用于展示多步骤、耗时任务的当前进度。

**代码示例:**
```python
# 发送通知 (Toast)
await __event_emitter__(
    {
        "type": "notification",
        "data": {
            "type": "info",  # 'info', 'success', 'warning', 'error'
            "content": "插件已启动，正在处理您的请求...",
        },
    }
)
```

#### 1.6.2 `__event_call__` - 执行前端代码

-   **路径**: 作为 `action` 方法的参数传入。
-   **功能**: **在用户的浏览器中执行任意 JavaScript 代码**。这是一个极其强大的功能，允许插件实现标准事件无法完成的复杂前端交互。
-   **核心方法**: `async __event_call__({"type": "execute", "data": {"code": "..."}})`
-   **使用场景**:
    -   **触发文件下载**: 如 `export_to_excel` 插件所示，将后端生成的文件内容（以 base64 编码）发送到前端，然后用 JS 创建一个 Blob 并模拟点击下载链接。
    -   **与浏览器 API 交互**: 例如，将内容复制到剪贴板 (`navigator.clipboard.writeText(...)`)，调用 Web Speech API 朗读文本等。
    -   **执行复杂的 DOM 操作**或调用前端页面中已有的某个特定 JS 函数。

**代码示例 (触发文件下载):**
```python
import base64

# 1. 在后端准备好文件内容
with open(excel_file_path, "rb") as file:
    file_content = file.read()
    base64_blob = base64.b64encode(file_content).decode("utf-8")

# 2. 构建将在浏览器中执行的 JavaScript 代码
js_code = f"""
try {{
    const base64Data = "{base64_blob}";
    const binaryData = atob(base64Data);
    // ... JS 解码并创建下载链接的代码 ...
}} catch (error) {{
    console.error('触发下载时出错:', error);
}}
"""

# 3. 通过 __event_call__ 发送执行指令
if __event_call__:
    await __event_call__({
        "type": "execute",
        "data": { "code": js_code },
    })
```
**安全提示**: 由于 `__event_call__` 可以执行任意 JS 代码，因此插件开发者必须确保所执行的代码是安全可靠的，避免引入跨站脚本（XSS）等安全风险。

---

## 2. 模型交互 (`open_webui.models`)

`open_webui.models` 提供了与数据库表进行交互的 ORM 模型类。

### 2.1 `Users` - 用户模型

-   **路径**: `from open_webui.models.users import Users`
-   **功能**: 用于获取当前用户的详细信息。
-   **核心方法**: `Users.get_user_by_id(user_id: str) -> User | None`
-   **使用场景**:
    -   在调用 `generate_chat_completion` 时，需要传递 `user` 对象作为参数。
    -   获取用户的姓名、邮箱、语言偏好等信息，用于构建个性化的 Prompt 或响应。

**代码示例:**
```python
from open_webui.models.users import Users

# __user__ 是插件方法传入的字典，包含 'id'
user_id = __user__.get("id")
user_obj = Users.get_user_by_id(user_id)
```

### 2.2 `Chats` - 对话历史模型

-   **路径**: `from open_webui.models.chats import Chats`
-   **功能**: 访问和管理特定对话的完整历史记录。
-   **核心方法**: `Chats.get_chat_by_id_and_user_id(id: str, user_id: str) -> Chat | None`
-   **使用场景**:
    -   获取包含完整元数据（如文件、引用来源）的消息历史。
    -   在需要对历史消息进行复杂分析或修改时。

**代码示例:**
```python
from open_webui.models.chats import Chats
import asyncio

# 必须在线程中调用
chat_model = await asyncio.to_thread(
    Chats.get_chat_by_id_and_user_id,
    chat_id,
    user_id
)
```

### 2.3 `Files` & `FileForm` - 文件元数据模型

-   **路径**: `from open_webui.models.files import Files, FileForm`
-   **功能**: 管理与 Open WebUI 文件库相关的元数据。
-   **核心方法**:
    -   `Files.get_file_by_id(file_id: str) -> FileModel | None`
    -   `Files.insert_new_file(user_id: str, file_form: FileForm) -> FileModel | None`
-   **使用场景**:
    -   查询已上传文件的物理路径和 MIME 类型。
    -   将插件生成的新文件注册到数据库中。

**代码示例:**
```python
from open_webui.models.files import Files, FileForm
import asyncio

# 查询文件
file_model = await asyncio.to_thread(Files.get_file_by_id, file_id)

# 注册新文件
new_file_form = FileForm(...)
await asyncio.to_thread(Files.insert_new_file, user_id, new_file_form)
```

### 2.4 `Functions` - 插件管理模型

-   **路径**: `from open_webui.models.functions import Functions`
-   **功能**: 查询已安装的 `Pipe`, `Filter`, `Action` 的信息。
-   **核心方法**: `Functions.get_function_by_id(function_id: str) -> Function | None`
-   **使用场景**:
    -   **依赖检查**: 检查另一个“伴侣”插件是否已安装并启用。

**代码示例:**
```python
from open_webui.models.functions import Functions

# 这是一个同步操作，无需 to_thread
function_model = Functions.get_function_by_id("my_companion_plugin_id")
if function_model and function_model.is_active:
    print("依赖插件已启用。")
```

---

## 3. 核心工具 (`open_webui.utils`)

`open_webui.utils` 提供了一系列高层级的辅助函数。

### 3.1 `generate_chat_completion` - LLM 调用工具

-   **路径**: `from open_webui.utils.chat import generate_chat_completion`
-   **功能**: 这是从插件内部调用 LLM 的**标准**和**推荐**方式。
-   **核心方法**: `async generate_chat_completion(request: Request, payload: dict, user: User) -> dict`
-   **使用场景**: 当插件需要“思考”或根据上下文生成内容时。
-   **关键参数**: `request`, `payload`, `user`。

**代码示例:**
```python
from open_webui.utils.chat import generate_chat_completion

# 在能直接访问 __request__ 的地方
llm_response = await generate_chat_completion(__request__, llm_payload, user_obj)
```

### 3.2 `pop_system_message` - 系统消息提取工具

-   **路径**: `from open_webui.utils.misc import pop_system_message`
-   **功能**: 从消息列表中分离出第一条系统消息。
-   **核心方法**: `pop_system_message(messages: list) -> tuple[dict | None, list]`
-   **使用场景**: 在将对话历史发送给不支持 `system` role 的 LLM 前，需要先将系统提示提取出来。

**代码示例:**
```python
from open_webui.utils.misc import pop_system_message

system_message, remaining_messages = pop_system_message(body.get("messages", []))
```

---

## 4. 文件存储 (`open_webui.storage.provider`)

### 4.1 `Storage` - 物理文件处理器

-   **路径**: `from open_webui.storage.provider import Storage`
-   **功能**: 负责将文件内容（字节流）写入到 Open WebUI 配置的存储后端。
-   **核心方法**: `Storage.upload_file(file: BinaryIO, filename: str) -> tuple[bytes, str]`
-   **使用场景**: 当插件**生成**了一个新文件并需要将其持久化时。通常与 `Files.insert_new_file` 配合使用。

**代码示例:**
```python
from open_webui.storage.provider import Storage
import io, asyncio

image_file = io.BytesIO(image_bytes)
# 必须在线程中调用
_, storage_path = await asyncio.to_thread(Storage.upload_file, image_file, "my_image.png")
```

---

## 5. Web 框架集成 (`open_webui.main`)

### 5.1 `app as webui_app` - FastAPI 应用实例

-   **路径**: `from open_webui.main import app as webui_app`
-   **功能**: 代表 Open WebUI 后端的 FastAPI 主应用实例。
-   **使用场景**: 一个特殊的用例，用于在无法直接访问 `__request__` 上下文的后台任务中，为了调用 `generate_chat_completion` 而“伪造”一个 `Request` 对象。

**代码示例:**
```python
from fastapi.requests import Request
from open_webui.main import app as webui_app

# 在后台任务中创建一个 Request 上下文
background_request = Request(scope={"type": "http", "app": webui_app})
```
这个技巧使得在任何地方（即使是脱离了原始请求生命周期的后台任务）都能方便地复用 `generate_chat_completion` 这一强大的工具函数。


