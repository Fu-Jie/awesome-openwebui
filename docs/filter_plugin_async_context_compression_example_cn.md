# Open WebUI Filter 插件开发范例：异步上下文压缩

## 引言

“异步上下文压缩” (`async-context-compression`) 是一个功能先进的 Open WebUI `Filter` 插件。它旨在通过在后台异步地对长对话历史进行智能摘要，来显著减少发送给大语言模型（LLM）的 Token 数量，从而在节约成本的同时保持对话的连贯性。

本文档将深入剖析其源码，提炼其作为高级 `Filter` 插件所展示的设计模式与开发技巧，特别是关于**异步处理**、**数据库集成**和**复杂消息流控制**等方面。

## 核心开发知识点

-   **Filter 插件结构 (`inlet` / `outlet`)**: 掌握过滤器在请求生命周期中的两个核心切入点。
-   **异步后台任务**: 如何使用 `asyncio.create_task` 执行耗时操作而不阻塞用户响应。
-   **数据库持久化**: 如何使用 SQLAlchemy 与数据库（PostgreSQL/SQLite）集成，实现数据的持久化存储。
-   **高级 `Valves` 配置**: 如何使用 Pydantic 的 `@model_validator` 实现复杂的跨字段配置验证。
-   **复杂消息体处理**: 如何安全地操作和修改包含多模态内容的消息结构。
-   **从插件内部调用 LLM**: 在插件中调用 LLM 服务以实现“插件调用插件”的元功能。
-   **环境变量依赖与初始化**: 如何处理对外部环境变量的依赖，并在插件初始化时进行安全配置。

---

### 1. Filter 插件结构 (`inlet` / `outlet`)

`Filter` 插件通过 `inlet` 和 `outlet` 两个方法，在请求发送给 LLM **之前**和 LLM 响应返回 **之后**对消息进行处理。

-   `inlet(self, body: dict, ...)`: 在请求发送前执行。此插件用它来检查是否存在历史摘要，如果存在，则用摘要替换部分历史消息，从而“压缩”上下文。
-   `outlet(self, body: dict, ...)`: 在收到 LLM 响应后执行。此插件用它来判断对话是否达到了需要生成摘要的长度阈值，如果是，则触发一个后台任务来生成新的摘要，以供**下一次**对话使用。

这种“读旧，写新”的异步策略是该插件的核心设计。

**代码示例 (`async_context_compression.py`):**
```python
class Filter:
    def inlet(self, body: dict, ...) -> dict:
        """
        在发送到 LLM 之前执行。
        应用已有的摘要来压缩本次请求的上下文。
        """
        # 1. 从数据库加载已保存的摘要
        saved_summary = self._load_summary(chat_id, body)
        
        # 2. 如果摘要存在且消息足够长
        if saved_summary and len(messages) > total_kept_count:
            # 3. 替换中间的消息为摘要
            body["messages"] = compressed_messages
        
        return body

    async def outlet(self, body: dict, ...) -> dict:
        """
        在 LLM 响应完成后执行。
        检查是否需要为下一次请求生成新的摘要。
        """
        # 1. 检查消息总数是否达到阈值
        if len(messages) >= self.valves.compression_threshold:
            # 2. 创建一个异步后台任务来生成摘要，不阻塞当前响应
            asyncio.create_task(
                self._generate_summary_async(...)
            )
            
        return body
```
**知识点**:
- `inlet` 和 `outlet` 分别作用于请求流的不同阶段，实现了功能的解耦。
- `inlet` 负责**消费**摘要，`outlet` 负责**生产**摘要，两者通过数据库解耦。

---

### 2. 异步后台任务

对于耗时操作（如调用 LLM 生成摘要），为了不让用户等待，必须采用异步后台处理。这是高级插件必备的技巧。

**代码示例 (`async_context_compression.py`):**
```python
# 在 outlet 方法中
async def outlet(self, ...):
    if len(messages) >= self.valves.compression_threshold:
        # 核心：创建一个后台任务，并立即返回，不等待其完成
        asyncio.create_task(
            self._generate_summary_async(messages, chat_id, body, __user__)
        )
    return body

# 后台任务的具体实现
async def _generate_summary_async(self, ...):
    """
    在后台异步生成摘要。
    """
    try:
        # 1. 提取需要被摘要的消息
        messages_to_summarize = ...
        
        # 2. 将消息格式化为纯文本
        conversation_text = self._format_messages_for_summary(messages_to_summarize)

        # 3. 调用 LLM 生成摘要
        summary = await self._call_summary_llm(conversation_text, body, user_data)

        # 4. 将新摘要存入数据库
        self._save_summary(chat_id, summary, body)
    except Exception as e:
        # 错误处理
        ...
```
**知识点**:
- `asyncio.create_task()`: 这是实现“即发即忘”(fire-and-forget)模式的关键。它将一个协程（`_generate_summary_async`）提交到事件循环中运行，而当前函数（`outlet`）可以继续执行并立即返回，从而确保了前端的快速响应。
- **健壮性**: 后台任务必须有自己独立的 `try...except` 块，以防止其内部的失败影响到主程序的稳定性。

---

### 3. 数据库持久化 (SQLAlchemy)

为了在不同对话回合乃至服务重启后都能保留摘要，插件集成了数据库。

**代码示例 (`async_context_compression.py`):**
```python
# 1. 依赖环境变量
database_url = os.getenv("DATABASE_URL")

# 2. 定义数据模型
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class ChatSummary(Base):
    __tablename__ = "chat_summary"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String(255), unique=True, index=True)
    summary = Column(Text)
    # ... 其他字段

# 3. 初始化数据库连接
def _init_database(self):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # ... 错误处理 ...
        return
    
    # 根据 URL 前缀选择驱动 (PostgreSQL/SQLite)
    if database_url.startswith("sqlite"): ...
    elif database_url.startswith("postgres"): ...

    self._db_engine = create_engine(database_url, ...)
    self._SessionLocal = sessionmaker(bind=self._db_engine)
    Base.metadata.create_all(bind=self._db_engine) # 自动建表

# 4. 封装 CRUD 操作
def _save_summary(self, chat_id: str, summary: str, body: dict):
    session = self._SessionLocal()
    try:
        # ... 查询、更新或创建记录 ...
        session.commit()
    finally:
        session.close()
```
**知识点**:
- **配置驱动**: 插件依赖 `DATABASE_URL` 环境变量，并在 `_init_database` 中进行解析，实现了对不同数据库（PostgreSQL, SQLite）的兼容。
- **ORM 模型**: 使用 SQLAlchemy 的声明式基类定义 `ChatSummary` 表结构，使数据库操作对象化，更易于维护。
- **自动建表**: `Base.metadata.create_all()` 会在插件首次运行时自动检查并创建不存在的表，简化了部署。
- **会话管理**: 使用 `sessionmaker` 创建会话，并通过 `try...finally` 确保会话在使用后被正确关闭，这是管理数据库连接的标准实践。

---

### 4. 高级 `Valves` 配置

除了简单的默认值，`Valves` 还可以通过 Pydantic 的验证器实现更复杂的逻辑。

**代码示例 (`async_context_compression.py`):**
```python
from pydantic import model_validator

class Valves(BaseModel):
    compression_threshold: int = Field(...)
    keep_first: int = Field(...)
    keep_last: int = Field(...)
    # ... 其他配置

    @model_validator(mode="after")
    def check_thresholds(self) -> "Valves":
        kept_count = self.keep_first + self.keep_last
        if self.compression_threshold <= kept_count:
            raise ValueError(
                f"compression_threshold ({self.compression_threshold}) 必须大于 "
                f"keep_first 和 keep_last 的总和。"
            )
        return self
```
**知识点**:
- `@model_validator(mode="after")`: 这个装饰器允许你在所有字段都已赋值**之后**，执行一个自定义的验证函数。
- **跨字段验证**: 该插件用它来确保 `compression_threshold` 必须大于 `keep_first` 和 `keep_last` 之和，保证了插件逻辑的正确性，避免了无效配置。

---

### 5. 复杂消息体处理

Open WebUI 的消息体 `content` 可能是简单的字符串，也可能是用于多模态的列表。插件必须能稳健地处理这两种情况。

**代码示例 (`async_context_compression.py`):**
```python
def _inject_summary_to_first_message(self, message: dict, summary: str) -> dict:
    content = message.get("content", "")
    summary_block = f"【历史对话摘要】\n{summary}\n..."

    if isinstance(content, list):  # 多模态内容
        new_content = []
        summary_inserted = False
        for part in content:
            if part.get("type") == "text" and not summary_inserted:
                # 将摘要追加到第一个文本部分的前面
                new_content.append({"type": "text", "text": summary_block + part.get("text", "")})
                summary_inserted = True
            else:
                new_content.append(part)
        message["content"] = new_content
    elif isinstance(content, str):  # 纯文本
        message["content"] = summary_block + content

    return message
```
**知识点**:
- **类型检查**: 通过 `isinstance(content, list)` 判断消息是否为多模态类型。
- **安全注入**: 在处理多模态列表时，代码会遍历所有 `part`，找到第一个文本部分进行注入，同时保持其他部分（如图片）不变。这确保了插件的兼容性和稳定性。

---

### 总结

`异步上下文压缩` 插件是学习如何构建生产级 Open WebUI `Filter` 的绝佳案例。它不仅展示了 `Filter` 的基本用法，更深入地探讨了在 Web 服务中至关重要的**异步处理**和**持久化存储**。

**高级实践总结**:
- **分离读写**: 利用 `inlet` 和 `outlet` 的生命周期，结合数据库，实现异步的“读写分离”模式。
- **非阻塞设计**: 通过 `asyncio.create_task` 将耗时操作移出主请求/响应循环，保证用户体验的流畅性。
- **外部依赖管理**: 优雅地处理对环境变量和数据库的依赖，并在初始化时提供清晰的日志和错误提示。
- **健壮配置**: 利用模型验证器 (`@model_validator`) 防止用户设置出不符合逻辑的参数。
- **兼容性处理**: 在操作消息体时，充分考虑多模态等复杂数据结构，确保插件的广泛适用性。

通过研究此插件，开发者可以掌握构建需要与外部服务（如数据库）交互、执行复杂后台任务的高级 `Filter` 的核心技能。
