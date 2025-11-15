# Gemini Manifold 插件通用例子

## 1. 配置层叠（Valves + UserValves）

```python
from pydantic import BaseModel

class Valves(BaseModel):
    GEMINI_API_KEY: str | None = None
    USE_VERTEX_AI: bool = False
    THINKING_BUDGET: int = 8192

class UserValves(BaseModel):
    GEMINI_API_KEY: str | None = None
    THINKING_BUDGET: int | None = None


def merge_valves(default: Valves, user: UserValves | None) -> Valves:
    merged = default.model_dump()
    if user:
        for field in user.model_fields:
            value = getattr(user, field)
            if value not in (None, ""):
                merged[field] = value
    return Valves(**merged)

admin_settings = Valves(GEMINI_API_KEY="admin-key", THINKING_BUDGET=8192)
user_settings = UserValves(GEMINI_API_KEY="user-key", THINKING_BUDGET=4096)
effective = merge_valves(admin_settings, user_settings)
print(effective)
```

**场景说明：** 与 `gemini_manifold.py` 中 `Valves`/`UserValves` 合并逻辑一致，适用于需要在 admin 默认与用户覆盖之间做透明优先级控制的插件。

## 2. 异步事件与进度反馈（EventEmitter + 上传队列）

```python
import asyncio
from typing import Callable, Awaitable

class EventEmitter:
    """
    抽象事件发射器，将所有前端交互统一到异步通道中。
    """
    def __init__(self, emit: Callable[[dict], Awaitable[None]] | None = None, 
                 hide_successful_status: bool = False):
        self._emit = emit
        self.hide_successful_status = hide_successful_status

    async def emit_status(self, message: str, done: bool = False, hidden: bool = False) -> None:
        """
        发出状态消息。如果 done=True 且 hide_successful_status=True，则在前端隐藏。
        """
        if not self._emit:
            return
        
        if done and self.hide_successful_status:
            hidden = True
        
        event = {
            "type": "status",
            "data": {
                "description": message,
                "done": done,
                "hidden": hidden
            }
        }
        await self._emit(event)

    async def emit_toast(self, msg: str, toast_type: str = "info") -> None:
        """
        发出 toast 通知（弹窗）。
        """
        if not self._emit:
            return
        
        event = {
            "type": "notification",
            "data": {
                "type": toast_type,
                "content": msg
            }
        }
        await self._emit(event)

    async def emit_completion(self, content: str | None = None, done: bool = False,
                             error: str | None = None, usage: dict | None = None) -> None:
        """
        发出完成事件，可含内容、错误、使用量等信息。
        """
        if not self._emit:
            return
        
        event = {"type": "chat:completion", "data": {"done": done}}
        if content is not None:
            event["data"]["content"] = content
        if error is not None:
            event["data"]["error"] = {"detail": error}
        if usage is not None:
            event["data"]["usage"] = usage
        
        await self._emit(event)


class UploadStatusManager:
    """
    管理并发文件上传的状态，自动追踪注册与完成计数。
    """
    def __init__(self, emitter: EventEmitter, start_time: float):
        self.emitter = emitter
        self.start_time = start_time
        self.queue = asyncio.Queue()
        self.total_uploads_expected = 0
        self.uploads_completed = 0
        self.finalize_received = False
        self.is_active = False

    async def run(self) -> None:
        """
        后台任务，监听队列并发出状态更新。
        """
        import time
        
        while not (self.finalize_received and 
                   self.total_uploads_expected == self.uploads_completed):
            try:
                msg = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            msg_type = msg[0]
            
            if msg_type == "REGISTER_UPLOAD":
                self.is_active = True
                self.total_uploads_expected += 1
                await self._emit_progress_update(time.monotonic())
            elif msg_type == "COMPLETE_UPLOAD":
                self.uploads_completed += 1
                await self._emit_progress_update(time.monotonic())
            elif msg_type == "FINALIZE":
                self.finalize_received = True
            
            self.queue.task_done()

    async def _emit_progress_update(self, current_time: float) -> None:
        """发出进度更新到前端。"""
        if not self.is_active:
            return
        
        elapsed = current_time - self.start_time
        time_str = f"(+{elapsed:.2f}s)"
        
        is_done = (self.total_uploads_expected > 0 and 
                   self.uploads_completed == self.total_uploads_expected)
        
        if is_done:
            msg = f"上传完成。{self.uploads_completed} 个文件已处理。{time_str}"
        else:
            msg = f"上传中 {self.uploads_completed + 1}/{self.total_uploads_expected}… {time_str}"
        
        await self.emitter.emit_status(msg, done=is_done)


async def multi_file_upload_workflow(
    file_list: list[tuple[str, bytes]], 
    emitter: EventEmitter
) -> list[str]:
    """
    示范多文件并发上传的完整工作流。
    """
    import time
    
    start_time = time.monotonic()
    status_mgr = UploadStatusManager(emitter, start_time)
    
    # 启动后台状态管理器
    manager_task = asyncio.create_task(status_mgr.run())
    
    # 为每个文件创建上传任务
    async def upload_file(name: str, data: bytes) -> str:
        await status_mgr.queue.put(("REGISTER_UPLOAD",))
        try:
            await asyncio.sleep(0.5)  # 模拟网络延迟
            result = f"uploaded-{name}"
            await emitter.emit_toast(f"✓ 文件 {name} 上传成功", "success")
            return result
        except Exception as e:
            await emitter.emit_toast(f"✗ 文件 {name} 上传失败: {e}", "error")
            raise
        finally:
            await status_mgr.queue.put(("COMPLETE_UPLOAD",))
    
    # 并发执行所有上传
    tasks = [upload_file(name, data) for name, data in file_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 通知状态管理器完成
    await status_mgr.queue.put(("FINALIZE",))
    await manager_task
    
    # 汇总结果
    success = [r for r in results if not isinstance(r, Exception)]
    return success


# 完整使用示例
async def demo():
    async def fake_emit(payload):
        print(f"→ {payload['type']}: {payload['data']}")
    
    emitter = EventEmitter(fake_emit, hide_successful_status=False)
    
    files = [
        ("doc1.pdf", b"content1"),
        ("image.jpg", b"content2"),
        ("data.csv", b"content3"),
    ]
    
    results = await multi_file_upload_workflow(files, emitter)
    print(f"\n✓ 上传成功: {len(results)} 个文件")

asyncio.run(demo())
```

**完整流程状态显示说明：**

整个异步工作流的状态显示遵循以下链路：

```text
初始化
  ↓
发出"准备请求"状态 → [emit_status] → 前端显示状态条
  ↓
启动后台 UploadStatusManager 任务
  ↓
并发执行多个上传任务
  ├─→ 任务1: REGISTER_UPLOAD → [更新计数] → emit_status("上传中 1/3…")
  ├─→ 任务2: REGISTER_UPLOAD → [更新计数] → emit_status("上传中 2/3…")
  └─→ 任务3: REGISTER_UPLOAD → [更新计数] → emit_status("上传中 3/3…")
  ↓
每个任务完成时
  ├─→ emit_toast("✓ 文件上传成功", "success") → 前端弹窗确认
  └─→ COMPLETE_UPLOAD → [更新计数] → emit_status("上传中 1/3…") 或 "上传完成"
  ↓
所有任务完成 → FINALIZE → 关闭后台管理器
  ↓
发出最终状态 → emit_status("全部完成", done=True) → 前端状态条完成
```

**关键数据流动：**

1. **EventEmitter** 负责将事件发送到前端
   - `emit_status()`: 状态条消息
   - `emit_toast()`: 弹窗通知
   - `emit_completion()`: 完成事件（含 usage 等）

2. **UploadStatusManager** 后台任务持续监听队列
   - 接收 `("REGISTER_UPLOAD",)` → 计数加 1 → 计算进度 → 更新状态显示
   - 接收 `("COMPLETE_UPLOAD",)` → 计数加 1 → 重新计算进度 → 更新状态显示
   - 接收 `("FINALIZE",)` → 退出循环 → 任务完成

3. **实时计数逻辑**

```python
已完成数 / 总数 = 进度百分比
显示: "上传中 {已完成+1}/{总数}… (+X.XXs)"
当完成数 == 总数: 显示 "上传完成。3 个文件已处理。(+2.50s)"
```

**场景说明：** 完整模拟 `gemini_manifold.py` 中 `EventEmitter` + `UploadStatusManager` 的实战设计。支持多并发任务状态跟踪、自动计数、toast 通知与后台进度汇报。适用于：

- 多文件并发上传且需要实时进度反馈的场景
- API 轮询或长流程中持续向前端汇报进展
- 需要自隐藏成功状态但保留错误警告的交互流程
- 复杂的异步任务编排与协调
- 需要细粒度时间戳与计数统计的长流程

**场景说明：** 完整模拟 `gemini_manifold.py` 中 `EventEmitter` + `UploadStatusManager` 的实战设计。支持多并发任务状态跟踪、自动计数、toast 通知与后台进度汇报。适用于：

- 多文件并发上传且需要实时进度反馈的场景
- API 轮询或长流程中持续向前端汇报进展
- 需要自隐藏成功状态但保留错误警告的交互流程
- 复杂的异步任务编排与协调
- 需要细粒度时间戳与计数统计的长流程

## 3. 文件缓存 + 幂等上传（xxHash + deterministic 名称）

```python
import xxhash

def content_hash(data: bytes) -> str:
    return xxhash.xxh64(data).hexdigest()

cache: dict[str, str] = {}

def deterministic_name(hash_val: str) -> str:
    return f"files/owui-v1-{hash_val}"

async def maybe_upload(data: bytes):
    h = content_hash(data)
    if h in cache:
        print("cache hit", cache[h])
        return cache[h]
    name = deterministic_name(h)
    cache[h] = name
    print("uploading", name)
    return name
    ```

    **场景说明：** 简化版 `FilesAPIManager` 热/暖/冷路径，适合需要避免重复上传、并希望后端能通过 deterministic 名称恢复文件状态的场景。


## 4. 统一响应处理（流式 + 非流式适配）

```python
from typing import AsyncGenerator

class UnifiedResponseProcessor:
    async def process_stream(
        self, response_stream: AsyncGenerator, is_stream: bool = True
    ) -> AsyncGenerator:
        """
        处理流式或一次性响应，统一返回 AsyncGenerator。
        """
        try:
            async for chunk in response_stream:
                # 处理单个 chunk
                processed = await self._process_chunk(chunk)
                if processed:
                    yield {"choices": [{"delta": processed}]}
        except Exception as e:
            yield {"choices": [{"delta": {"content": f"Error: {e}"}}]}
        finally:
            yield "data: [DONE]"

    async def _process_chunk(self, chunk):
        # 简化处理逻辑
        return {"content": str(chunk)}

# 使用示例
async def main():
    processor = UnifiedResponseProcessor()
    async def fake_stream():
        for i in range(3):
            yield f"chunk-{i}"
    async for item in processor.process_stream(fake_stream()):
        print(item)
```

**场景说明：** 对应 `gemini_manifold.py` 中 `_unified_response_processor` 的核心思想——无论前端是否启用流式，插件内部都用统一的 AsyncGenerator 处理，避免代码分支。适用于需要兼容流式与非流式响应的任何插件。

## 5. 特殊标签禁用（防止前端解析干扰）

```python
import re

ZWS = "\u200b"  # 零宽空格
SPECIAL_TAGS = ["think", "details", "thinking", "reason"]

def disable_special_tags(text: str) -> tuple[str, int]:
    """
    在特殊标签前插入零宽空格，防止前端 HTML 解析器处理它们。
    """
    if not text:
        return "", 0

    TAG_REGEX = re.compile(
        r"<(/?(" + "|".join(re.escape(tag) for tag in SPECIAL_TAGS) + r"))"
    )
    modified, count = TAG_REGEX.subn(rf"<{ZWS}\1", text)
    return modified, count

def enable_special_tags(text: str) -> str:
    """
    移除零宽空格，恢复原始标签，用于模型理解上下文。
    """
    if not text:
        return ""
    REVERSE_REGEX = re.compile(
        r"<" + ZWS + r"(/?(" + "|".join(re.escape(tag) for tag in SPECIAL_TAGS) + r"))"
    )
    return REVERSE_REGEX.sub(r"<\1", text)

# 使用示例
original = "<think>这是思考内容</think>"
disabled, count = disable_special_tags(original)
print(f"禁用前: {original}")
print(f"禁用后: {disabled}")
print(f"修改数: {count}")
```

**场景说明：** 当模型可能生成会被前端 HTML 解析器误触发的标签（如 `<think>` 推理块）时，通过注入零宽空格破坏标签结构，再在需要时恢复。这是 `gemini_manifold.py` 中保护前端的一种防御手段，对任何可能含有模型生成 HTML 的插件都有借鉴价值。

## 6. 统一异常处理与用户反馈

```python
class PluginException(Exception):
    """插件统一异常基类。"""
    pass

class APIError(PluginException):
    """API 调用异常。"""
    pass

class FileUploadError(PluginException):
    """文件上传异常。"""
    pass

class EventEmitterForErrors:
    def __init__(self):
        self.event_queue = []

    async def emit_error(self, error_msg: str, is_toast: bool = True):
        """
        发出错误事件，同时记录日志。
        """
        event = {"type": "error", "data": {"detail": error_msg}}
        if is_toast:
            event["data"]["toast_type"] = "error"
        self.event_queue.append(event)
        print(f"[ERROR] {error_msg}")

async def call_api_with_fallback(api_key: str, emitter: EventEmitterForErrors):
    """
    调用 API 并完整处理异常。
    """
    try:
        # 模拟 API 调用
        if not api_key:
            raise ValueError("API key 未提供")
        # 成功处理
        return {"status": "ok"}
    except ValueError as e:
        await emitter.emit_error(f"参数错误: {e}")
        raise APIError(f"API 调用失败: {e}") from e
    except Exception as e:
        await emitter.emit_error(f"意外错误: {e}", is_toast=True)
        raise PluginException(f"插件异常: {e}") from e

# 使用示例
import asyncio
emitter = EventEmitterForErrors()
try:
    result = asyncio.run(call_api_with_fallback("", emitter))
except PluginException as e:
    print(f"捕获到插件异常: {e}")
```

**场景说明：** 对应 `gemini_manifold.py` 中 `GenaiApiError`、`FilesAPIError` 等定制异常。通过分层异常类和统一的 emit_error 机制，确保所有错误都能被前端看到，同时便于调试和日志分析。

## 7. 后处理与数据回写（Usage + Grounding）

```python
from datetime import datetime

class PostProcessor:
    def __init__(self, request_state):
        self.state = request_state

    async def emit_usage(self, prompt_tokens: int, completion_tokens: int):
        """
        发出 Token 使用情况。
        """
        total = prompt_tokens + completion_tokens
        elapsed = datetime.now().timestamp()
        usage_data = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
            "completion_time": elapsed,
        }
        print(f"Usage: {usage_data}")
        return usage_data

    async def emit_grounding(self, chat_id: str, message_id: str, grounding_metadata):
        """
        将 grounding 数据存入应用状态，供 Filter 或后续步骤使用。
        """
        key = f"grounding_{chat_id}_{message_id}"
        self.state[key] = grounding_metadata
        print(f"存储 grounding 数据到 {key}")

    async def emit_status(self, message: str, done: bool = False):
        """
        发出最终状态。
        """
        status_event = {
            "type": "status",
            "data": {"description": message, "done": done}
        }
        print(f"Status: {status_event}")

# 使用示例
async def main():
    state = {}  # 模拟 request.app.state
    processor = PostProcessor(state)
    
    await processor.emit_usage(prompt_tokens=50, completion_tokens=100)
    await processor.emit_grounding(
        chat_id="chat_123",
        message_id="msg_456",
        grounding_metadata={"sources": ["source1", "source2"]}
    )
    await processor.emit_status("Response finished", done=True)
    print("\n最终状态:", state)

asyncio.run(main())
```

**场景说明：** 模拟 `gemini_manifold.py` 中 `_do_post_processing` 的职责——在主响应流完成后，将 usage、grounding、状态等元数据通过独立通道发出。这种分离确保前端能获得完整信息，同时不阻塞流式响应。

## 8. 日志与数据截断（Loguru + 自动截断）

```python
import json
from functools import wraps

class PluginLogger:
    def __init__(self, max_payload_length: int = 256):
        self.max_length = max_payload_length

    def truncate_payload(self, data: any) -> str:
        """
        将复杂数据序列化并截断。
        """
        try:
            serialized = json.dumps(data, default=str)
            if len(serialized) > self.max_length:
                return serialized[:self.max_length] + "[...]"
            return serialized
        except Exception as e:
            return f"<Serialization Error: {e}>"

    def log_with_payload(self, level: str, message: str, payload: any = None):
        """
        记录带有 payload 的日志，自动截断。
        """
        log_line = f"[{level}] {message}"
        if payload is not None:
            truncated = self.truncate_payload(payload)
            log_line += f" - {truncated}"
        print(log_line)

# 使用示例
logger = PluginLogger(max_payload_length=100)
logger.log_with_payload("DEBUG", "API Response", 
                        payload={"data": "x" * 200, "status": "ok"})
logger.log_with_payload("INFO", "File uploaded",
                        payload={"file_id": "abc123", "size": 1024})
```

**场景说明：** 对应 `gemini_manifold.py` 中自定义 loguru handler 与 `_truncate_long_strings` 的逻辑。当插件需要调试复杂 API 响应或大型 payload 时，通过自动截断避免日志爆炸，同时保留关键信息。

## 9. 联网搜索功能与源引用显示

```python
from typing import TypedDict

class SearchSource(TypedDict):
    title: str
    url: str
    snippet: str

class GroundingMetadata(TypedDict):
    search_queries: list[str]  # 使用的搜索查询
    sources: list[SearchSource]  # 检索到的源

class SearchableResponseBuilder:
    """
    当启用联网搜索功能时，构建含有搜索信息的响应。
    对应 gemini_manifold.py 中依据 features["google_search_tool"] 的逻辑。
    """
    def __init__(self, enable_search: bool = False, emitter = None):
        self.enable_search = enable_search
        self.emitter = emitter
        self.grounding_metadata: GroundingMetadata | None = None

    async def build_response_with_search(self, 
                                         query: str, 
                                         use_search: bool = True) -> tuple[str, GroundingMetadata | None]:
        """
        构建响应，如果启用搜索则收集源信息。
        """
        if not (self.enable_search and use_search):
            # 未启用搜索，直接返回响应
            return "这是直接回答，无搜索", None
        
        # 模拟搜索过程
        search_results = await self._perform_search(query)
        
        # 构建 grounding 元数据
        self.grounding_metadata = {
            "search_queries": [query],
            "sources": search_results
        }
        
        # 构建含源引用的响应
        response_with_sources = await self._format_response_with_citations(
            query, search_results
        )
        
        return response_with_sources, self.grounding_metadata

    async def _perform_search(self, query: str) -> list[SearchSource]:
        """
        模拟调用 Google Search API（实际中由 gemini_manifold.py 的 tool 层处理）。
        """
        # 模拟搜索结果
        results = [
            {
                "title": "Open WebUI 官方文档",
                "url": "https://docs.openwebui.com",
                "snippet": "Open WebUI 是一个开源的大语言模型管理平台..."
            },
            {
                "title": "Open WebUI GitHub 仓库",
                "url": "https://github.com/open-webui/open-webui",
                "snippet": "开源代码库，包含所有源码和插件..."
            },
            {
                "title": "Open WebUI 社区论坛",
                "url": "https://community.openwebui.com",
                "snippet": "用户交流和问题解答社区..."
            }
        ]
        
        if self.emitter:
            await self.emitter.emit_toast(
                f"✓ 已搜索: '{query}' 找到 {len(results)} 个结果",
                "success"
            )
        
        return results

    async def _format_response_with_citations(self, 
                                              query: str, 
                                              sources: list[SearchSource]) -> str:
        """
        将搜索结果格式化为含有源引用的响应。
        """
        response = f"关于 '{query}' 的搜索结果：\n\n"
        
        for idx, source in enumerate(sources, 1):
            response += f"[{idx}] **{source['title']}**\n"
            response += f"    URL: {source['url']}\n"
            response += f"    摘要: {source['snippet']}\n\n"
        
        response += "---\n\n根据上述源的信息，可以得出以下结论：\n"
        response += "Open WebUI 是一个功能丰富的平台，提供了完整的文档、源码和社区支持。"
        
        return response

    def extract_sources_for_frontend(self) -> list[dict]:
        """
        提取 grounding 元数据中的源，用于前端显示为 'sources' 字段。
        对应 gemini_manifold.py 中 emit_completion(sources=...) 的数据。
        """
        if not self.grounding_metadata:
            return []
        
        sources_for_ui = []
        for source in self.grounding_metadata["sources"]:
            sources_for_ui.append({
                "title": source["title"],
                "url": source["url"],
                "description": source["snippet"]
            })
        
        return sources_for_ui


async def demo_search_workflow():
    """
    演示启用联网搜索时的完整工作流。
    """
    class FakeEmitter:
        async def emit_toast(self, msg, ttype):
            print(f"[{ttype.upper()}] {msg}")
        
        async def emit_status(self, msg, done=False):
            print(f"[STATUS] {msg} (done={done})")
    
    emitter = FakeEmitter()
    
    # 创建搜索构建器，启用联网搜索
    builder = SearchableResponseBuilder(enable_search=True, emitter=emitter)
    
    # 步骤 1: 用户提问
    user_query = "Open WebUI 的插件开发最佳实践"
    await emitter.emit_status(f"处理查询: {user_query}")
    
    # 步骤 2: 构建响应并收集源
    response_text, grounding = await builder.build_response_with_search(user_query)
    
    # 步骤 3: 提取源引用供前端使用
    sources_for_ui = builder.extract_sources_for_frontend()
    
    # 步骤 4: 构建完整的 completion 事件
    completion_event = {
        "type": "chat:completion",
        "data": {
            "content": response_text,
            "sources": sources_for_ui,  # 前端将在消息下方显示这些源
            "done": True
        }
    }
    
    print("\n=== 最终响应 ===")
    print(f"内容:\n{response_text}")
    print(f"\n源信息 (供前端显示):")
    for source in sources_for_ui:
        print(f"  - {source['title']}: {source['url']}")
    
    print(f"\n完整事件数据:")
    import json
    print(json.dumps(completion_event, ensure_ascii=False, indent=2))

asyncio.run(demo_search_workflow())
```

**实现细节说明：**

联网搜索功能的完整链路（对应 `gemini_manifold.py`）：

```text
1. 前端请求时，features 包含 "google_search_tool": true
                    ↓
2. Pipe.pipe() 检测到 features["google_search_tool"]
                    ↓
3. 在 _build_gen_content_config() 中：
   gen_content_conf.tools.append(
       types.Tool(google_search=types.GoogleSearch())
   )
                    ↓
4. 将 config 传给 Google Gemini API
                    ↓
5. API 自动执行搜索并返回搜索结果
                    ↓
6. 获取 response.candidates[0].grounding_metadata
   ├─ 包含搜索查询
   ├─ 包含检索到的源（标题、URL、摘要）
   └─ 包含段落级的源匹配信息
                    ↓
7. 在 _do_post_processing() 中：
   将 grounding_metadata 存入 request.app.state
   供后续 Filter 使用
                    ↓
8. 在响应流中通过 emit_completion(sources=...)
   将源引用发送到前端
                    ↓
9. 前端在消息下方显示：
   [1] 源标题 (链接)
   [2] 源标题 (链接)
   ...
```

**关键实现要点：**

| 步骤 | 职责 | 代码位置 |
|------|------|---------|
| **检测开关** | 检查 `features["google_search_tool"]` | `_build_gen_content_config()` |
| **配置工具** | 将 `google_search` 添加到 tools 列表 | `gen_content_conf.tools.append()` |
| **执行搜索** | Google API 自动执行，返回 grounding_metadata | API 响应处理 |
| **提取源** | 从 grounding_metadata 提取源信息 | `_do_post_processing()` |
| **存储状态** | 将 grounding 存入 `request.app.state` | `_add_grounding_data_to_state()` |
| **发送前端** | 通过 `emit_completion(sources=...)` 发送 | `_unified_response_processor()` |
| **显示引用** | 前端渲染源链接和摘要 | 前端 UI 逻辑 |

**场景说明：** 展示如何在启用联网搜索时收集、处理和展示搜索源。适用于：

- 需要集成搜索功能的插件
- 需要展示信息来源的智能应用
- 需要追踪 API 调用的溯源场景
- 需要构建可引用的 LLM 应用

## 总结与最佳实践

| 哲学 | 核心机制 | 使用场景 |
|------|---------|----------|
| **配置层叠** | Valves + UserValves 合并 | Admin 全局设置 + 用户按需覆盖 |
| **异步反馈** | EventEmitter + Queue | 长流程中持续向前端汇报状态 |
| **资源复用** | xxHash + 缓存 + Stateless GET | 避免重复上传，快速恢复 |
| **统一处理** | AsyncGenerator + 适配器 | 流式和非流式响应一致处理 |
| **安全防护** | 特殊标签注入 ZWS | 防止模型生成的 HTML 破坏前端 |
| **异常管理** | 分层异常 + emit_error | 所有错误对前端可见 |
| **后处理** | Usage/Grounding 在 response 后 | 非阻塞式补充元数据 |
| **日志控制** | 自动截断 + 多级别 | 避免日志爆炸，便于调试 |
| **搜索集成** | grounding_metadata 提取 + 源展示 | 联网搜索时收集并显示信息来源 |

## 补充：响应格式与引用解析

### 一、源（Source）的数据结构

当启用联网搜索时，Google Gemini API 返回的 `grounding_metadata` 包含搜索源信息，对应以下结构：

```python
# Google API 返回的 grounding_metadata 格式
{
    "search_queries": ["用户的搜索查询"],
    "web_search_results": [
        {
            "uri": "https://example.com/page1",
            "title": "网页标题",
            "snippet": "网页摘要文本...",
            "display_uri": "example.com",
        },
        # ... 更多搜索结果
    ],
    "grounding_supports": [
        {
            "segment": {
                "start_index": 0,
                "end_index": 145,
                "text": "模型回答中被引用的这段文本"
            },
            "supporting_segments": [
                {
                    "segment": {
                        "text": "网页中的相关内容"
                    },
                    "uri": "https://example.com/page1"
                }
            ],
            "confidence_scores": [0.95]
        }
    ]
}
```

### 二、引用标记的格式

**API 返回的响应中引用标记格式：**

Google Gemini API 在响应文本中自动插入引用标记：

```text
根据搜索结果[1]，Open WebUI 是一个开源平台[2]。用户可以通过插件[1][2]
扩展功能。

[1] https://docs.openwebui.com - Open WebUI 官方文档
[2] https://github.com/open-webui/open-webui - GitHub 仓库
```

**引用标记特征：**

- 格式：`[N]` 其中 N 是数字索引（1-based）
- 位置：内联在文本中，跟在被引用的短语后
- 对应关系：`[1]` → `web_search_results[0]`，`[2]` → `web_search_results[1]` 等

### 三、前端显示的 sources 格式

`emit_completion(sources=...)` 发送给前端的数据格式：

```python
sources = [
    {
        "title": "Open WebUI 官方文档",
        "uri": "https://docs.openwebui.com",
        "snippet": "Open WebUI 是一个开源的大语言模型管理平台...",
        "display_uri": "docs.openwebui.com",
    },
    {
        "title": "Open WebUI GitHub 仓库",
        "uri": "https://github.com/open-webui/open-webui",
        "snippet": "开源代码库，包含所有源码和插件...",
        "display_uri": "github.com",
    }
]
```

**前端如何渲染：**

1. **识别内联引用标记** → 将 `[1]` 链接到 `sources[0]`

2. **在消息下方显示源面板**，通常格式为：

   ```text
   [1] Open WebUI 官方文档 (docs.openwebui.com)
   [2] Open WebUI GitHub 仓库 (github.com)
   ```

3. **点击引用标记** → 高亮对应的源，显示摘要

4. **点击源链接** → 在新标签页打开 URL

### 四、完整数据流转

```text
1. 用户启用搜索功能 (features["google_search_tool"] = true)
           ↓
2. Pipe 配置 API：gen_content_conf.tools.append(
       types.Tool(google_search=types.GoogleSearch())
   )
           ↓
3. Google Gemini API 执行搜索，返回：
   - 文本响应（含内联 [N] 标记）
   - grounding_metadata（含搜索结果和支撑段落）
           ↓
4. gemini_manifold.py _process_part() 处理：
   - 提取文本响应
   - 通过 _disable_special_tags() 处理特殊标签
   - 返回结构化 chunk: {"content": "文本[1][2]..."}
           ↓
5. _do_post_processing() 后处理：
   - 提取 candidate.grounding_metadata
   - 存入 request.app.state[f"grounding_{chat_id}_{message_id}"]
   - 提取 web_search_results → sources 列表
           ↓
6. emit_completion(content="...", sources=[...])
   - 发送完整内容给前端
   - 同时发送 sources 列表
           ↓
7. 前端渲染：
   - 消息体显示文本和 [1][2] 引用标记
   - 底部显示 sources 面板
   - 用户可交互查看源信息
```

### 五、可能需要移除的引用标记

在某些情况下（如用户编辑消息），需要调用 `_remove_citation_markers()` 移除不再有效的引用标记：

```python
# 源数据结构（来自 grounding_metadata）
source = {
    "uri": "https://example.com",
    "title": "Page Title",
    "metadata": [
        {
            "supports": [
                {
                    "segment": {
                        "start_index": 10,
                        "end_index": 50,
                        "text": "这是被引用的文本片段"
                    },
                    "grounding_chunk_indices": [0, 1]  # 对应 [1], [2]
                }
            ]
        }
    ]
}

# 方法会找到 "这是被引用的文本片段[1][2]" 并删除 [1][2]
cleaned_text = _remove_citation_markers(response_text, [source])
```

### 六、关键要点

**✓ 引用的识别规则：**

- 文本内联的 `[数字]` 是引用标记
- 必须对应 sources 列表中的同序号元素
- 通常由 API 自动生成和嵌入

**✗ 常见问题：**

- 删除源但保留标记 → 前端会显示孤立的 `[N]`
- 修改文本后标记位置错误 → 需要重新生成
- 混合多个搜索结果 → 确保索引连续且不重叠

### 七、Chat/Completions 接口的响应格式

当直接通过 Open WebUI 的 `chat/completions` API 调用 pipe 时，响应应采用以下格式返回引用信息。

**流式响应（streaming=true）：**

Pipe 返回 `AsyncGenerator[dict]`，每个 dict 按以下顺序发送：

```python
# 流式块（多次）
{
    "choices": [
        {
            "delta": {
                "content": "根据搜索结果[1]，Open WebUI..."
            }
        }
    ]
}

# 完成标记
"data: [DONE]"

# 后续元数据通过 event_emitter 事件发送
# 1. emit_status - 状态更新消息
# 2. emit_toast - 弹窗通知（如错误或成功提示）
# 3. emit_usage - Token 使用量数据
# 4. emit_completion(sources=[...]) - 发送最终的源信息列表
```

**关键特性：**

- 文本内容通过 `{"choices": [{"delta": {"content": "..."}}]}` 流式返回
- 引用标记 `[1][2]` 直接包含在内容文本中
- 源信息通过 `emit_completion(sources=[...])` 以事件形式发送到前端
- 完成后发送 `"data: [DONE]"` 标记

**非流式响应（streaming=false）：**

整个响应通过适配器转换为单次 AsyncGenerator：

```python
async def single_item_stream(response):
    yield response

# 输出结果类似流式，但内容全部在一个块中
{
    "choices": [
        {
            "delta": {
                "content": "完整的回答文本[1][2]..."
            }
        }
    ]
}

"data: [DONE]"
```

### 八、sources 数据的发送方式

#### 方式 1：通过 EventEmitter 事件发送（推荐）

```python
await event_emitter.emit_completion(
    content=None,  # 内容已通过 delta 发送
    sources=[
        {
            "title": "Open WebUI 官方文档",
            "uri": "https://docs.openwebui.com",
            "snippet": "Open WebUI 是一个开源的大语言模型管理平台...",
            "display_uri": "docs.openwebui.com",
        },
        {
            "title": "Open WebUI GitHub 仓库",
            "uri": "https://github.com/open-webui/open-webui",
            "snippet": "开源代码库，包含所有源码和插件...",
            "display_uri": "github.com",
        }
    ],
    done=True
)
```

这会产生事件：

```python
{
    "type": "chat:completion",
    "data": {
        "done": True,
        "sources": [
            {"title": "...", "uri": "...", ...},
            {"title": "...", "uri": "...", ...}
        ]
    }
}
```

#### 方式 2：通过应用状态存储（Companion Filter 读取）

gemini_manifold 的 `_add_grounding_data_to_state()` 将 grounding_metadata 存入：

```python
request.app.state[f"grounding_{chat_id}_{message_id}"] = grounding_metadata_obj
```

Companion Filter 或其他处理组件可以读取这个状态并从中提取源信息。

#### 方式 3：直接在响应文本中（最简单）

如果只需要在文本中显示源链接，可以让 API 返回：

```text
根据搜索结果[1]，Open WebUI 是一个开源平台[2]。

[1] https://docs.openwebui.com - Open WebUI 官方文档
[2] https://github.com/open-webui/open-webui - GitHub 仓库
```

前端将识别 `[N]` 标记并自动提取为引用。

### 九、完整的 pipe 返回规范

**Pipe 方法签名：**

```python
async def pipe(
    self,
    body: dict,  # 请求体：模型、消息、流式标志等
    __user__: dict,  # 用户信息
    __request__: Request,  # FastAPI Request
    __event_emitter__: Callable[[Event], Awaitable[None]] | None,  # 事件发射器
    __metadata__: dict,  # 元数据：特性、任务类型等
) -> AsyncGenerator[dict, None] | str:
    ...
    return self._unified_response_processor(...)
```

**返回的 AsyncGenerator 应产生的消息序列：**

```text
1. {"choices": [{"delta": {"content": "流式文本块..."}}]}  ← 多次
2. {"choices": [{"delta": {"content": "[1][2]..."}}]}  ← 最后的内容块
3. "data: [DONE]"  ← 完成标记
4. (事件发送阶段) emit_status, emit_toast, emit_usage, emit_completion(sources=[...])
```

**事件发送（通过 EventEmitter）：**

这些不是 AsyncGenerator 的产出，而是通过 `__event_emitter__` 回调发送：

```python
# 在处理过程中发送状态
await event_emitter.emit_status("处理中...", done=False)

# 发送错误或成功提示
event_emitter.emit_toast("✓ 完成", "success")

# 发送 Token 使用量
await event_emitter.emit_usage({
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "completion_time": 2.34
})

# 发送最终的源信息和其他元数据
await event_emitter.emit_completion(
    sources=[...],
    usage={...},
    done=True
)
```

### 十、实现 Pipe 时的源处理清单

当你实现一个支持搜索的 pipe 时，确保：

**✓ 流式响应部分：**

- [ ] 文本包含内联的 `[1]`, `[2]` 等引用标记
- [ ] 每个块通过 `yield {"choices": [{"delta": {"content": "..."}}]}` 返回
- [ ] 最后一块完成后发送 `yield "data: [DONE]"`

**✓ 元数据部分：**

- [ ] 调用 `emit_status()` 显示处理进度
- [ ] 调用 `emit_toast()` 通知成功或错误
- [ ] 调用 `emit_usage()` 发送 Token 使用量
- [ ] 调用 `emit_completion(sources=[...])` 发送源列表

**✓ 源数据结构：**

- [ ] 每个源包含 `title`, `uri`, `snippet`, `display_uri`
- [ ] 源的顺序与文本中 `[N]` 的顺序一一对应
- [ ] 使用 `emit_completion(sources=[...], done=True)` 标记完成

**✗ 常见错误：**

- [ ] ❌ 只返回文本，不发送源信息
- [ ] ❌ 源数据格式不完整或字段错误
- [ ] ❌ 源顺序与引用标记不匹配
- [ ] ❌ 混合了内容和元数据返回方式

> 这些示例可直接集成进团队的插件开发指南或代码模板库，新插件可参考对应场景快速实现相关功能。
