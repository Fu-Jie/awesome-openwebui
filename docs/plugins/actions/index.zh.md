# Action 插件

Action 插件会在聊天界面的消息下方添加自定义按钮，让你一键触发特定功能。

## 什么是 Actions？

Actions 是交互式插件，能够：

- :material-gesture-tap: 在消息操作栏添加按钮
- :material-export: 生成并导出内容（思维导图、图表、文件等）
- :material-api: 与外部服务和 API 交互
- :material-animation-play: 创建可视化或交互内容

---

## 可用的 Action 插件

<div class="grid cards" markdown>

- :material-brain:{ .lg .middle } **Smart Mind Map**

    ---

    智能分析文本并生成交互式、精美的思维导图。

    **版本：** 1.0.0

    [:octicons-arrow-right-24: 查看文档](smart-mind-map.md)

- :material-chart-bar:{ .lg .middle } **Smart Infographic**

    ---

    使用 AntV 可视化引擎，将文本转成专业的信息图。

    **版本：** 1.6.0

    [:octicons-arrow-right-24: 查看文档](smart-infographic.md)

- :material-card-text:{ .lg .middle } **Flash Card（闪记卡）**

    ---

    快速生成精美的学习记忆卡片，非常适合学习和快速记忆。

    **版本：** 0.2.4

    [:octicons-arrow-right-24: 查看文档](flash-card.md)

- :material-file-excel:{ .lg .middle } **Export to Excel**

    ---

    将聊天记录导出为 Excel 电子表格，方便分析或归档。

    **版本：** 0.3.7

    [:octicons-arrow-right-24: 查看文档](export-to-excel.md)

- :material-file-word-box:{ .lg .middle } **Word 导出 (格式增强)**

    ---

    将当前对话导出为完美格式的 Word 文档，支持**代码语法高亮**、**原生数学公式**、**Mermaid 图表**、**引用资料**以及**增强表格**渲染。

    **版本：** 0.4.4

    [:octicons-arrow-right-24: 查看文档](export-to-word.md)

- :material-brain:{ .lg .middle } **精读 (Deep Dive)**

    ---

    全方位的思维透镜 —— 全景 → 脉络 → 洞察 → 路径。支持主题自适应。

    **版本：** 1.0.0

    [:octicons-arrow-right-24: 查看文档](deep-dive.zh.md)

</div>

---

## 快速安装

1. 下载需要的 `.py` 插件文件
2. 前往 **Admin Panel** → **Settings** → **Functions**
3. 上传文件并完成配置
4. 在聊天消息中使用对应的 Action 按钮

---

## 开发模板

想要自己编写 Action 插件？可以参考下面的模板：

```python
"""
title: My Custom Action
author: Your Name
version: 1.0.0
description: Description of your action plugin
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class Action:
    class Valves(BaseModel):
        # 在这里添加你的配置项
        show_status: bool = Field(
            default=True,
            description="Show status updates during processing"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Optional[dict]:
        """
        当用户点击 Action 按钮时触发的主方法。
        
        Args:
            body: 包含会话数据的消息体
            __user__: 当前用户信息
            __event_emitter__: 用于发送通知或状态更新
            __request__: FastAPI 请求对象
        
        Returns:
            修改后的 body 字典或 None
        """
        # 发送状态更新
        if __event_emitter__ and self.valves.show_status:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Processing...", "done": False}
            })
        
        # 插件逻辑
        messages = body.get("messages", [])
        if messages:
            last_message = messages[-1].get("content", "")
            # 在这里处理消息...
        
        # 完成状态
        if __event_emitter__ and self.valves.show_status:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Done!", "done": True}
            })
        
        return body
```

更多详情可查看 [插件开发指南](../../development/plugin-guide.md)。
