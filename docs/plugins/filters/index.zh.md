# Filter 插件

Filter 插件会在消息发送到 LLM 之前或响应生成之后处理和修改内容。

## 什么是 Filters？

Filter 充当消息管线中的中间件：

- :material-arrow-right-bold: **Inlet**：在消息到达 LLM 前处理用户消息
- :material-arrow-left-bold: **Outlet**：在展示前处理 LLM 响应
- :material-stream: **Stream**：对流式响应进行实时处理

---

## 可用的 Filter 插件

<div class="grid cards" markdown>

- :material-arrow-collapse-vertical:{ .lg .middle } **Async Context Compression**

    ---

    通过更稳健的摘要回退和更清晰的失败提示，降低长对话的 token 消耗并保持连贯性。

    **版本：** 1.6.3

    [:octicons-arrow-right-24: 查看文档](async-context-compression.zh.md)

- :material-text-box-plus:{ .lg .middle } **Context Enhancement**

    ---

    为聊天增加额外信息，提升回复质量。

    **版本：** 0.2

    [:octicons-arrow-right-24: 查看文档](context-enhancement.md)

- :material-folder-refresh:{ .lg .middle } **Folder Memory**

    ---

    自动从文件夹内的对话中提取一致性的“项目规则”，并将其回写到文件夹的系统提示词中。

    **版本：** 0.1.0

    [:octicons-arrow-right-24: 查看文档](folder-memory.zh.md)

- :material-format-paint:{ .lg .middle } **Markdown Normalizer**

    ---

    修复 LLM 输出中常见的 Markdown 格式问题，包括 Mermaid 语法、代码块和 LaTeX 公式。

    **版本：** 1.2.8

    [:octicons-arrow-right-24: 查看文档](markdown_normalizer.zh.md)

- :material-file-shield:{ .lg .middle } **Copilot SDK 文件过滤器**

    ---

    专门用于绕过 OpenWebUI 默认 RAG 机制的过滤器，针对 GitHub Copilot SDK 模型。确保 Agent 能够接收到原始文件进行自主分析。

    **版本：** 0.1.3

    [:octicons-arrow-right-24: 查看文档](github-copilot-sdk-files-filter.zh.md)

</div>

---

## Filter 工作流程

```mermaid
graph LR
    A[User Message] --> B[Inlet Filter]
    B --> C[LLM]
    C --> D[Outlet Filter]
    D --> E[Display to User]
```

### Inlet 处理

`inlet` 方法在消息到达 LLM 前处理：

```python
async def inlet(self, body: dict, __metadata__: dict) -> dict:
    # 在发送到 LLM 前修改请求
    messages = body.get("messages", [])
    # 添加上下文、调整 prompt 等
    return body
```

### Outlet 处理

`outlet` 方法在响应生成后处理：

```python
async def outlet(self, body: dict, __metadata__: dict) -> dict:
    # 在展示前修改响应
    messages = body.get("messages", [])
    # 格式化输出、追加引用等
    return body
```

---

## 快速安装

1. 下载需要的 Filter `.py` 文件
2. 前往 **Admin Panel** → **Settings** → **Functions**
3. 上传文件并配置
4. 在聊天设置或全局启用该过滤器

---

## 开发模板

```python
"""
title: My Custom Filter
author: Your Name
version: 1.0.0
description: Description of your filter plugin
"""

from pydantic import BaseModel, Field
from typing import Optional

class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Filter priority (lower = earlier execution)"
        )
        enabled: bool = Field(
            default=True,
            description="Enable/disable this filter"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None
    ) -> dict:
        """Process messages before sending to LLM."""
        if not self.valves.enabled:
            return body
        
        # 你的 inlet 逻辑
        messages = body.get("messages", [])
        
        return body
    
    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None
    ) -> dict:
        """Process responses before displaying."""
        if not self.valves.enabled:
            return body
        
        # 你的 outlet 逻辑
        
        return body
```

更多细节见 [插件开发指南](../../development/plugin-guide.md)。
