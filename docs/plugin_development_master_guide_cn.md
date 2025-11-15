# Open WebUI 插件开发终极指南

## Part 1: 插件开发入门

### 1.1 什么是 Open WebUI 插件 (Functions)？

在 Open WebUI 中，插件（官方称为 "Functions"）是扩展核心功能、实现高度定制化的主要方式。它们允许开发者：
-   **集成新的 AI 模型**: 通过 `Pipe` 插件接入如 Anthropic Claude、Google Gemini 或任何其他第三方 AI 服务。
-   **修改交互流程**: 通过 `Filter` 插件在请求发送给模型前或响应返回给用户后，动态地修改、增强或过滤内容。
-   **增强用户界面**: 通过 `Action` 插件在聊天消息旁添加自定义按钮，以触发特定操作，如生成图表、导出文件等。

所有插件都使用纯 Python 编写，并运行在 Open WebUI 的后端环境中，这使得它们能够无缝地访问框架的各种内部功能。

### 1.2 三种插件类型概览

Open WebUI 中有三种类型的插件，每种都有其独特的用途：

1.  **`Pipe` (管道)**: **创建自定义“模型”**
    -   **作用**: `Pipe` 插件在前端表现为一个独立的、可供选择的模型。它适用于封装复杂的工作流，例如调用外部 API（搜索、天气）、组合多个模型（“混合专家”模式），或者实现自定义的 RAG 流程。
    -   **示例**: 创建一个名为“谷歌搜索”的 `Pipe`，当用户选择这个“模型”并提问时，插件会将问题发送到 Google Search API，并将搜索结果格式化后返回。

2.  **`Filter` (过滤器)**: **修改输入和输出**
    -   **作用**: `Filter` 像一个“中间件”，挂载在模型处理流程的“入口”和“出口”。它不改变模型的本质，只修改流经它的数据。
        -   `inlet` (入口): 在请求发送给模型**前**修改 `body`。
        -   `outlet` (出口): 在模型响应完全返回**后**修改最终的 `body`。
        -   `stream` (流式): 在模型**流式**响应过程中，实时修改每一个数据块。
    -   **示例**: 创建一个自动为用户输入补充上下文信息的 `Filter`，或者一个能自动将模型输出的简体中文转换为繁体中文的 `Filter`。

3.  **`Action` (动作)**: **添加自定义按钮**
    -   **作用**: `Action` 插件会在 AI 生成的消息下方添加一个或多个可点击的按钮。用户点击按钮后，会触发插件在后端执行相应的逻辑。
    -   **示例**: 创建一个“导出为 Excel”的 `Action`，当 AI 生成了包含 Markdown 表格的回答时，用户可以点击此按钮，插件会将表格数据转换成 Excel 文件并触发浏览器下载。

---

## Part 2: 核心概念与通用技术

在深入了解每种插件的具体实现之前，我们需要掌握一些所有插件都会用到的通用核心概念。

### 2.1 `Valves` 与 `UserValves`：插件的配置系统

`Valves` 是 Open WebUI 为插件提供的一套强大而灵活的配置系统，它允许管理员和用户动态地调整插件的行为。

-   **`Valves` (管理员阀门)**:
    -   在插件的 `class` 内部定义，继承自 `pydantic.BaseModel`。
    -   管理员可以在 **管理面板 -> Functions** 中为每个插件配置这些值。
    -   它定义了插件的**全局默认行为**。

-   **`UserValves` (用户阀门)**:
    -   同样在插件 `class` 内部定义。
    -   普通用户可以在**聊天设置 -> 模型 -> 高级参数**中为**单次对话**设置这些值。
    -   它允许用户**临时覆盖**管理员的全局设置。

**关键模式：强制用户认证**
`gemini_manifold` 插件展示了一个非常高级的用法：通过 `Valves` 强制要求用户使用自己的凭证。
1.  管理员在 `Valves` 中设置 `USER_MUST_PROVIDE_AUTH_CONFIG: True`。
2.  插件逻辑会检查此项。如果为 `True`，则**强制**使用 `__user__["valves"]` 中用户自己提供的 API Key，并忽略管理员设置的全局 Key。
3.  这在团队环境中对于成本分摊和安全审计至关重要。

**代码示例:**
```python
from pydantic import BaseModel, Field
from typing import Literal

class MyFilter:
    class Valves(BaseModel):
        # 管理员设置：全局 API Key
        API_KEY: str = Field(default="", description="Admin's global API key.")
        # 管理员设置：是否强制用户使用自己的 Key
        FORCE_USER_KEY: bool = Field(default=False, description="Force users to provide their own key.")
        
    class UserValves(BaseModel):
        # 用户设置：用户自己的 API Key
        API_KEY: str = Field(default="", description="Your personal API key.")

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: dict):
        # 合并配置
        admin_valves = self.valves
        user_valves = __user__.get("valves", self.UserValves()) # 安全获取用户配置

        final_api_key = admin_valves.API_KEY
        if admin_valves.FORCE_USER_KEY:
            if user_valves.API_KEY:
                final_api_key = user_valves.API_KEY
            else:
                raise ValueError("管理员已要求您提供自己的 API Key。")
        elif user_valves.API_KEY:
            final_api_key = user_valves.API_KEY
        
        print(f"最终使用的 API Key: {final_api_key}")
        return body
```

### 2.2 核心方法参数详解

插件的每个核心方法（如 `inlet`, `pipe`, `action`）都会接收一系列由 Open WebUI 框架传入的、以 `__` 包裹的特殊参数。这些参数是插件获取上下文、与系统交互的生命线。

-   **`body: dict`**:
    -   **功能**: 前端发送的原始请求体，是插件最主要的操作对象。
    -   **核心字段**: `messages`, `model`, `stream`, `features` (前端UI的功能开关), `metadata`。

-   **`__user__: dict`**:
    -   **功能**: 当前用户的详细信息。
    -   **核心字段**: `id`, `name`, `email`, `role` (admin/user), `language`, 以及 `valves` (用户的 `UserValves` 配置)。

-   **`__metadata__: dict`**:
    -   **功能**: 关于本次请求的元数据，是插件获取额外上下文和进行内部通信的关键。
    -   **核心字段**:
        -   `chat_id`, `message_id`: 用于唯一标识对话和消息。
        -   `features`: 一个专为插件间通信设计的字典，`Filter` 可在此设置标志，供后续的 `Pipe` 读取。
        -   `variables`: **（非常实用）** 一个由 Open WebUI 自动填充的字典，包含了丰富的即用型环境变量，如 `{{USER_NAME}}`, `{{CURRENT_DATETIME}}` 等。`inject_env` 插件的核心就是利用此字典。

-   **`__model__: dict`**:
    -   **功能**: 当前所选模型的完整信息，比 `body["model"]` 更详细。
    -   **核心字段**: `id`, `name`, `info.base_model_id` (对于自定义模型，指向其基础模型)。这对于根据模型“家族”编写逻辑非常有用。

-   **`__request__: Request`**:
    -   **功能**: FastAPI 的原始请求对象。
    -   **核心用途**: `__request__.app.state` 是一个在单次 HTTP 请求生命周期内持续存在的共享状态对象。高级插件模式（如 `Pipe` 与 `Filter` 协同）用它来实现跨阶段的数据传递。

-   **`__files__: list`**:
    -   **功能**: 一个列表，包含了用户在聊天中上传的**文件**（不包括图片，图片在 `body['messages']` 中以 base64 形式存在）。
    -   **内容**: 列表中的每一项都是一个字典，包含了文件的 `id`, `filename`, `path` (服务器上的真实路径) 等元数据。

### 2.3 事件系统：与前端的实时交互

插件可以通过 `__event_emitter__` 和 `__event_call__` 与前端浏览器进行实时、动态的交互。

-   **`__event_emitter__` (单向事件发射器)**:
    -   **功能**: 以“即发即忘”(fire-and-forget)的方式向前端发送**标准事件**，用于显示通知和状态更新。
    -   **常用事件类型**:
        -   `notification`: 在屏幕角落显示一个短暂的弹窗通知。
        -   `status`: 更新输入框上方的状态条。
        -   `chat:message:delta`: 向当前消息流式追加内容。
        -   `chat:message`: 完全替换当前消息的内容。
        -   `chat:title`: 更新对话标题。

-   **`__event_call__` (双向事件调用)**:
    -   **功能**: 发送一个事件到前端，并**暂停**后端执行，直到收到前端（通常是用户）的响应。
    -   **常用事件类型**:
        -   `confirmation`: 显示一个“确认/取消”对话框，返回用户的选择 (`True`/`False`)。
        -   `input`: 显示一个输入框，返回用户输入的内容。
        -   `execute`: **在用户的浏览器中执行任意 JavaScript 代码**。这是一个极其强大的功能。

**`execute` 事件实战：触发文件下载**
`export_to_excel` 插件展示了 `execute` 的标准用法：
1.  后端生成 Excel 文件并保存在临时目录。
2.  将文件内容读取为字节，并进行 Base64 编码。
3.  构建一段 JavaScript 代码，该代码的作用是：解码 Base64 -> 创建 Blob -> 创建隐藏的 `<a>` 标签 -> 模拟点击以下载文件。
4.  通过 `__event_call__` 将这段 JS 代码发送到前端执行。
5.  后端删除临时文件。

```python
# 伪代码
js_code = f"const data = atob('{base64_string}'); ..."
await __event_call__({"type": "execute", "data": {"code": js_code}})
```

### 2.4 与 Open WebUI 后端模块交互

插件可以导入并使用 Open WebUI 框架内部的模块，以访问数据库或使用通用功能。

-   **`from open_webui.models import Users, Chats, Files, Functions`**:
    -   这些是数据库 ORM 模型，用于直接查询 `users`, `chats`, `files`, `functions` 表。
    -   **注意**: 这些是**同步**方法，在 `async` 函数中必须用 `await asyncio.to_thread(...)` 调用。

-   **`from open_webui.storage.provider import Storage`**:
    -   用于物理文件操作，主要是 `Storage.upload_file()`。
    -   同样是**同步**方法，需要 `asyncio.to_thread`。

-   **`from open_webui.utils.chat import generate_chat_completion`**:
    -   **功能**: 从插件内部调用 LLM 的**标准**和**推荐**方式。
    -   **签名**: `async def generate_chat_completion(request: Request, payload: dict, user: User)`
    -   这是一个 `async` 函数，可以直接 `await`。

-   **`from open_webui.utils.misc import pop_system_message`**:
    -   一个便捷的同步工具函数，用于从消息列表中分离出 `system` 角色的消息。

---

## Part 3: 插件类型深度解析与高级模式

### 3.1 `Filter` 插件高级模式

-   **模式 1: 上下文注入与幂等性**
    -   **案例**: `inject_env.py`
    -   **技巧**: 在 `inlet` 中，使用 `__metadata__["variables"]` 获取环境变量，并将其注入到第一条用户消息中。关键在于，注入前先用 `re.search` 检查是否已存在，如果存在则用 `re.sub` 更新，保证了操作的**幂等性**。同时，通过 `isinstance` 判断消息 `content` 类型，兼容了纯文本和多模态消息。

-   **模式 2: 功能拦截与模型重定向**
    -   **案例**: `inject_env.py`, `gemini_manifold_companion.py`
    -   **技巧**: 在 `inlet` 中拦截前端的功能开关（如 `body["features"]["web_search"] = True`），先将其设为 `False` 以阻止默认行为，然后通过两种方式之一实现自定义逻辑：
        1.  **参数翻译**: 添加一个后端 `Pipe` 认识的私有参数（如 `body.setdefault("enable_search", True)`）。
        2.  **模型重定向**: 直接修改 `body["model"]` 的值（如 `my-model` -> `my-model-search`），将请求路由到另一个支持搜索的模型上。

-   **模式 3: 异步后台任务与数据库**
    -   **案例**: `async-context-compression.py`
    -   **技巧**: 在 `outlet` 中，当满足某个条件（如对话长度超限）时，使用 `asyncio.create_task()` 启动一个**后台任务**来执行耗时操作（调用 LLM 生成摘要）。主流程无需等待，立即返回，保证了前端的快速响应。后台任务完成后，通过 SQLAlchemy 将结果存入数据库，供下一次对话使用。

-   **模式 4: Pipe-Filter 协同通信**
    -   **案例**: `gemini_manifold_companion.py`
    -   **技巧**: `Pipe` 和 `Filter` 可以通过 `__request__.app.state` 这个共享对象进行通信。`Pipe` 在执行完毕后，可以将一些处理结果（如搜索引用元数据）存入 `state`。随后运行的 `Filter` 在 `outlet` 阶段可以从 `state` 中读出这些数据，并进行进一步的处理（如在最终响应中插入引用标记）。

### 3.2 `Action` 插件高级模式

-   **模式 1: 富文本 (HTML/JS) 输出**
    -   **案例**: `smart_mind_map.py`
    -   **技巧**: `Action` 可以返回一个包含了完整 HTML、CSS 和 JavaScript 的字符串，并用 ` ```html ... ``` ` 包裹。Open WebUI 前端会自动渲染这个 HTML 块，从而实现思维导图、图表等丰富的交互式可视化。

-   **模式 2: 文件生成与下载**
    -   **案例**: `export_to_excel.py`
    -   **技巧**: 这是从后端向用户提供生成文件的标准模式。流程是：在服务器临时目录生成文件 -> Base64 编码 -> 通过 `__event_call__` 的 `execute` 事件将编码字符串和下载用的 JS 代码发往前端 -> 前端执行 JS 触发下载 -> 后端删除临时文件。

### 3.3 `Pipe` 插件高级模式

-   **模式 1: 高性能文件处理与缓存**
    -   **案例**: `gemini_manifold.py`
    -   **技巧**: `FilesAPIManager` 展示了一套企业级的文件处理方案。它使用 `xxhash` 实现**内容寻址**，避免重复上传。通过**三级缓存**（内存、无状态GET、上传）最大化效率。并使用 `asyncio.Lock` 解决了并发上传的竞态问题。

-   **模式 2: 并发与进度管理**
    -   **案例**: `gemini_manifold.py`
    -   **技巧**: `GeminiContentBuilder` 使用 `asyncio.gather` 并发处理所有消息中的文件。同时，`UploadStatusManager` 通过 `asyncio.Queue` 作为生产者-消费者队列，从各个上传任务中收集进度，并向前端提供统一的、实时的进度反馈。

## 结论

Open WebUI 的插件系统远不止是简单的 API 调用。通过组合使用框架提供的上下文参数、核心模块以及 Python 强大的异步和第三方库生态，开发者可以构建出功能极其强大、体验流畅且高度定制化的 AI 应用。

希望这份终极指南能为您在 Open WebUI 的插件开发之旅上提供清晰的指引和深刻的启发。
