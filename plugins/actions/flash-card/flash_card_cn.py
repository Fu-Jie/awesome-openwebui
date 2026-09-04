"""
title: 闪记卡 (Flash Card)
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
version: 0.2.6
required_open_webui_version: 0.11.0
openwebui_id: 4a31eac3-a3c4-4c30-9ca5-dab36b5fac65
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5Z29uIHBvaW50cz0iMTIgMiAyIDcgMTIgMTIgMjIgNyAxMiAyIi8+PHBvbHlsaW5lIHBvaW50cz0iMiAxNyAxMiAyMiAyMiAxNyIvPjxwb2x5bGluZSBwb2ludHM9IjIgMTIgMTIgMTcgMjIgMTIiLz48L3N2Zz4=
description: 快速将文本提炼为精美的学习记忆卡片，支持核心要点提取与分类。
"""

from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any, List
import json
import logging
import re
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users
import asyncio
from inspect import iscoroutinefunction


async def _call_db(method, *args, **kwargs):
    if iscoroutinefunction(method):
        return await method(*args, **kwargs)
    res = method(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HTML_WRAPPER_TEMPLATE = """
<!-- OPENWEBUI_PLUGIN_OUTPUT -->
<!DOCTYPE html>
<html lang="{user_language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            margin: 0; 
            padding: 10px; 
            background-color: transparent; 
        }
        #main-container { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 20px; 
            align-items: flex-start; 
            width: 100%;
        }
        .plugin-item { 
            flex: 1 1 400px; /* 默认宽度，允许伸缩 */
            min-width: 300px; 
            background: white; 
            border-radius: 12px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
            overflow: hidden; 
            border: 1px solid #e5e7eb; 
            transition: all 0.3s ease;
        }
        .plugin-item:hover {
            box-shadow: 0 10px 15px rgba(0,0,0,0.1);
        }
        @media (max-width: 768px) { 
            .plugin-item { flex: 1 1 100%; } 
        }
        /* STYLES_INSERTION_POINT */
    </style>
</head>
<body>
    <div id="main-container">
        <!-- CONTENT_INSERTION_POINT -->
    </div>
    <!-- SCRIPTS_INSERTION_POINT -->
</body>
</html>
"""


class Action:
    class Valves(BaseModel):
        MODEL_ID: str = Field(
            default="",
            description="用于生成卡片内容的模型 ID。如果为空，则使用当前模型。",
        )
        MIN_TEXT_LENGTH: int = Field(
            default=50, description="生成闪记卡所需的最小文本长度（字符数）。"
        )
        LANGUAGE: str = Field(
            default="zh", description="卡片内容的目标语言 (例如 'zh', 'en')。"
        )
        SHOW_STATUS: bool = Field(
            default=True, description="是否在聊天界面显示状态更新。"
        )
        SHOW_DEBUG_LOG: bool = Field(
            default=False,
            description="是否在浏览器控制台打印调试日志。",
        )
        CLEAR_PREVIOUS_HTML: bool = Field(
            default=False,
            description="是否强制清除旧的插件结果（如果为 True，则不合并，直接覆盖）。",
        )
        MESSAGE_COUNT: int = Field(
            default=1,
            description="用于生成的最近消息数量。设置为1仅使用最后一条消息，更大值可包含更多上下文。",
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_user_context(self, __user__: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """安全提取用户上下文信息，支持多种输入格式。"""
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        return {
            "user_id": user_data.get("id", "unknown_user"),
            "user_name": user_data.get("name", "用户"),
            "user_language": user_data.get("language", "zh-CN"),
        }

    def _get_chat_context(
        self, body: dict, __metadata__: Optional[dict] = None
    ) -> Dict[str, str]:
        """
        统一提取聊天上下文信息 (chat_id, message_id)。
        优先从 body 中提取，其次从 metadata 中提取。
        """
        chat_id = ""
        message_id = ""

        # 1. 尝试从 body 获取
        if isinstance(body, dict):
            chat_id = body.get("chat_id", "")
            message_id = body.get("id", "")  # message_id 在 body 中通常是 id

            # 再次检查 body.metadata
            if not chat_id or not message_id:
                body_metadata = body.get("metadata", {})
                if isinstance(body_metadata, dict):
                    if not chat_id:
                        chat_id = body_metadata.get("chat_id", "")
                    if not message_id:
                        message_id = body_metadata.get("message_id", "")

        # 2. 尝试从 __metadata__ 获取 (作为补充)
        if __metadata__ and isinstance(__metadata__, dict):
            if not chat_id:
                chat_id = __metadata__.get("chat_id", "")
            if not message_id:
                message_id = __metadata__.get("message_id", "")

        return {
            "chat_id": str(chat_id).strip(),
            "message_id": str(message_id).strip(),
        }

    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Any:
        logger.info(f"Action: {__name__} 触发")

        if not __event_emitter__:
            return body

        # Get messages based on MESSAGE_COUNT
        messages = body.get("messages", [])
        if not messages:
            return body

        # Get last N messages based on MESSAGE_COUNT
        message_count = min(self.valves.MESSAGE_COUNT, len(messages))
        recent_messages = messages[-message_count:]

        # Aggregate content from selected messages with labels
        aggregated_parts = []
        for i, msg in enumerate(recent_messages, 1):
            text_content = self._extract_text_content(msg.get("content"))
            if text_content:
                role = msg.get("role", "unknown")
                role_label = (
                    "用户"
                    if role == "user"
                    else "助手" if role == "assistant" else role
                )
                aggregated_parts.append(f"{text_content}")

        if not aggregated_parts:
            return body

        target_message = "\n\n---\n\n".join(aggregated_parts)

        # Check text length
        text_length = len(target_message)
        if text_length < self.valves.MIN_TEXT_LENGTH:
            await self._emit_notification(
                __event_emitter__,
                f"文本内容过短 ({text_length} 字符)，建议至少 {self.valves.MIN_TEXT_LENGTH} 字符。",
                "warning",
            )
            return body

        # Notify user that we are generating the card
        await self._emit_notification(__event_emitter__, "⚡ 正在生成闪记卡...", "info")
        await self._emit_status(__event_emitter__, "⚡ 闪记卡: 开始生成...", done=False)

        try:
            # 1. Extract information using LLM
            await self._emit_status(
                __event_emitter__, "⚡ 闪记卡: 正在调用 AI 模型分析内容...", done=False
            )

            user_ctx = self._get_user_context(__user__)
            user_id = user_ctx["user_id"]
            user_obj = await _call_db(Users.get_user_by_id, user_id)

            target_model = (
                self.valves.MODEL_ID if self.valves.MODEL_ID else body.get("model")
            )

            system_prompt = f"""
你是一个闪记卡生成专家，专注于创建适合学习和记忆的知识卡片。你的任务是将文本提炼成简洁、易记的学习卡片。

请提取以下字段，并以 JSON 格式返回：
1. "title": 创建一个简短、精准的标题（3-8 个词），突出核心概念
2. "summary": 用一句话总结核心要义（10-25 个词），要通俗易懂、便于记忆
3. "key_points": 列出 3-5 个关键记忆点（每个 5-15 个词）
    - 每个要点应该是独立的知识点
    - 使用简洁、口语化的表达
    - 避免冗长的句子
4. "tags": 列出 2-4 个分类标签（每个 1-3 个词）
5. "category": 选择一个主分类（如：概念、技能、事实、方法等）

目标语言: {self.valves.LANGUAGE}

重要原则：
- **极简主义**: 每个要点都要精炼到极致
- **记忆优先**: 内容要便于记忆和回忆
- **核心聚焦**: 只提取最核心的知识点
- **口语化**: 使用通俗易懂的语言
- 只返回 JSON 对象，不要包含 markdown 格式
            """

            prompt = f"请将以下文本提炼成一张学习记忆卡片：\n\n{target_message}"

            payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            }

            response = await generate_chat_completion(__request__, payload, user_obj)
            content = response["choices"][0]["message"]["content"]

            await self._emit_status(
                __event_emitter__, "⚡ 闪记卡: AI 分析完成，正在解析数据...", done=False
            )

            # Parse JSON
            try:
                # simple cleanup in case of markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                card_data = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}, content: {content}")
                await self._emit_status(
                    __event_emitter__, "❌ 闪记卡: 数据解析失败", done=True
                )
                await self._emit_notification(
                    __event_emitter__, "❌ 生成卡片数据失败，请重试。", "error"
                )
                return body

            # 2. Generate HTML components
            await self._emit_status(
                __event_emitter__, "⚡ 闪记卡: 正在渲染卡片...", done=False
            )
            card_content, card_style = self.generate_html_card_components(card_data)

            # 3. Append to message
            # Extract existing HTML if any
            existing_html_block = ""
            match = re.search(
                r"```html\s*(<!-- OPENWEBUI_PLUGIN_OUTPUT -->[\s\S]*?)```",
                body["messages"][-1]["content"],
            )
            if match:
                existing_html_block = match.group(1)

            if self.valves.CLEAR_PREVIOUS_HTML:
                body["messages"][-1]["content"] = self._remove_existing_html(
                    body["messages"][-1]["content"]
                )
                final_html = self._merge_html(
                    "", card_content, card_style, "", self.valves.LANGUAGE
                )
            else:
                if existing_html_block:
                    body["messages"][-1]["content"] = self._remove_existing_html(
                        body["messages"][-1]["content"]
                    )
                    final_html = self._merge_html(
                        existing_html_block,
                        card_content,
                        card_style,
                        "",
                        self.valves.LANGUAGE,
                    )
                else:
                    final_html = self._merge_html(
                        "", card_content, card_style, "", self.valves.LANGUAGE
                    )

            await self._emit_status(
                __event_emitter__, "✅ 闪记卡: 生成完成！", done=True
            )
            await self._emit_notification(
                __event_emitter__, "⚡ 闪记卡生成成功！", "success"
            )

            # OpenWebUI >= 0.11 processes Action results through
            # process_tool_result(). Only an inline HTMLResponse is emitted as
            # a Rich UI embed; mutating body["messages"] is not persisted or
            # rendered by the current Action pipeline.
            return HTMLResponse(
                content=final_html,
                headers={"Content-Disposition": "inline"},
            )

        except Exception as e:
            logger.error(f"Error generating knowledge card: {e}")
            await self._emit_status(__event_emitter__, "❌ 闪记卡: 生成失败", done=True)
            await self._emit_notification(
                __event_emitter__, f"❌ 生成知识卡片时出错: {str(e)}", "error"
            )
            return body

    async def _emit_status(self, emitter, description: str, done: bool = False):
        """发送状态更新事件。"""
        if self.valves.SHOW_STATUS and emitter:
            await emitter(
                {"type": "status", "data": {"description": description, "done": done}}
            )

    async def _emit_notification(self, emitter, content: str, ntype: str = "info"):
        """发送通知事件 (info/success/warning/error)。"""
        if emitter:
            await emitter(
                {"type": "notification", "data": {"type": ntype, "content": content}}
            )

    async def _emit_debug_log(self, emitter, title: str, data: dict):
        """在浏览器控制台打印结构化调试日志"""
        if not self.valves.SHOW_DEBUG_LOG or not emitter:
            return

        try:
            import json

            js_code = f"""
                (async function() {{
                    console.group("🛠️ {title}");
                    console.log({json.dumps(data, ensure_ascii=False)});
                    console.groupEnd();
                }})();
            """

            await emitter({"type": "execute", "data": {"code": js_code}})
        except Exception as e:
            print(f"Error emitting debug log: {e}")

    def _remove_existing_html(self, content: str) -> str:
        """移除内容中已有的插件生成 HTML 代码块 (通过标记识别)。"""
        pattern = r"```html\s*<!-- OPENWEBUI_PLUGIN_OUTPUT -->[\s\S]*?```"
        return re.sub(pattern, "", content).strip()

    def _extract_text_content(self, content) -> str:
        """从消息内容中提取文本，支持多模态消息格式"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # 多模态消息: [{"type": "text", "text": "..."}, {"type": "image_url", ...}]
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        return str(content) if content else ""

    def _merge_html(
        self,
        existing_html_code: str,
        new_content: str,
        new_styles: str = "",
        new_scripts: str = "",
        user_language: str = "zh-CN",
    ) -> str:
        """
        将新内容合并到现有的 HTML 容器中，或者创建一个新的容器。
        """
        if (
            "<!-- OPENWEBUI_PLUGIN_OUTPUT -->" in existing_html_code
            and "<!-- CONTENT_INSERTION_POINT -->" in existing_html_code
        ):
            base_html = existing_html_code
            base_html = re.sub(r"^```html\s*", "", base_html)
            base_html = re.sub(r"\s*```$", "", base_html)
        else:
            base_html = HTML_WRAPPER_TEMPLATE.replace("{user_language}", user_language)

        wrapped_content = f'<div class="plugin-item">\n{new_content}\n</div>'

        if new_styles:
            base_html = base_html.replace(
                "/* STYLES_INSERTION_POINT */",
                f"{new_styles}\n/* STYLES_INSERTION_POINT */",
            )

        base_html = base_html.replace(
            "<!-- CONTENT_INSERTION_POINT -->",
            f"{wrapped_content}\n<!-- CONTENT_INSERTION_POINT -->",
        )

        if new_scripts:
            base_html = base_html.replace(
                "<!-- SCRIPTS_INSERTION_POINT -->",
                f"{new_scripts}\n<!-- SCRIPTS_INSERTION_POINT -->",
            )

        return base_html.strip()

    def generate_html_card_components(self, data):
        # Enhanced CSS with premium styling
        style = """
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            
            .knowledge-card-container {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                display: flex;
                justify-content: center;
                margin: 30px 0;
                padding: 0 10px;
            }
            
            .knowledge-card {
                width: 100%;
                max-width: 500px;
                border-radius: 20px;
                overflow: hidden;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 3px;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
            }
            
            .knowledge-card:hover {
                transform: translateY(-8px) scale(1.02);
                box-shadow: 0 25px 50px -12px rgba(102, 126, 234, 0.4);
            }
            
            .knowledge-card::before {
                content: '';
                position: absolute;
                top: -2px;
                left: -2px;
                right: -2px;
                bottom: -2px;
                background: linear-gradient(135deg, #667eea, #764ba2, #f093fb, #4facfe);
                border-radius: 20px;
                opacity: 0;
                transition: opacity 0.4s ease;
                z-index: -1;
                filter: blur(10px);
            }
            
            .knowledge-card:hover::before {
                opacity: 0.7;
                animation: glow 2s ease-in-out infinite;
            }
            
            @keyframes glow {
                0%, 100% { opacity: 0.5; }
                50% { opacity: 0.8; }
            }
            
            .card-inner {
                background: #ffffff;
                border-radius: 18px;
                overflow: hidden;
            }
            
            .card-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 32px 28px;
                position: relative;
                overflow: hidden;
            }
            
            .card-header::before {
                content: '';
                position: absolute;
                top: -50%;
                right: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                animation: rotate 15s linear infinite;
            }
            
            @keyframes rotate {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .card-category {
                font-size: 0.7em;
                text-transform: uppercase;
                letter-spacing: 2px;
                opacity: 0.95;
                margin-bottom: 10px;
                font-weight: 700;
                display: inline-block;
                padding: 4px 12px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                backdrop-filter: blur(10px);
            }
            
            .card-title {
                font-size: 1.75em;
                font-weight: 800;
                margin: 0;
                line-height: 1.3;
                position: relative;
                z-index: 1;
                letter-spacing: -0.5px;
            }
            
            .card-body {
                padding: 28px;
                color: #1a1a1a;
                background: linear-gradient(to bottom, #ffffff 0%, #fafafa 100%);
            }
            
            .card-summary {
                font-size: 1.05em;
                color: #374151;
                margin-bottom: 24px;
                line-height: 1.7;
                border-left: 5px solid #764ba2;
                padding: 16px 20px;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
                border-radius: 0 12px 12px 0;
                font-weight: 500;
                position: relative;
                overflow: hidden;
            }
            
            .card-summary::before {
                content: '"';
                position: absolute;
                top: -10px;
                left: 10px;
                font-size: 4em;
                color: rgba(118, 75, 162, 0.1);
                font-family: Georgia, serif;
                font-weight: bold;
            }
            
            .card-section-title {
                font-size: 0.85em;
                font-weight: 700;
                color: #764ba2;
                margin-bottom: 14px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .card-section-title::before {
                content: '';
                width: 4px;
                height: 16px;
                background: linear-gradient(to bottom, #667eea, #764ba2);
                border-radius: 2px;
            }
            
            .card-points {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            
            .card-points li {
                margin-bottom: 14px;
                padding: 12px 16px 12px 44px;
                position: relative;
                line-height: 1.6;
                color: #374151;
                background: #ffffff;
                border-radius: 10px;
                transition: all 0.3s ease;
                border: 1px solid #e5e7eb;
                font-weight: 500;
            }
            
            .card-points li:hover {
                transform: translateX(5px);
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
                border-color: #764ba2;
                box-shadow: 0 4px 12px rgba(118, 75, 162, 0.1);
            }
            
            .card-points li::before {
                content: '✓';
                color: #ffffff;
                background: linear-gradient(135deg, #667eea, #764ba2);
                font-weight: bold;
                position: absolute;
                left: 12px;
                top: 50%;
                transform: translateY(-50%);
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                font-size: 0.85em;
                box-shadow: 0 2px 8px rgba(118, 75, 162, 0.3);
            }
            
            .card-footer {
                padding: 20px 28px;
                background: linear-gradient(to right, #f8fafc 0%, #f1f5f9 100%);
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                border-top: 2px solid #e5e7eb;
                align-items: center;
            }
            
            .card-tag-label {
                font-size: 0.75em;
                font-weight: 700;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-right: 4px;
            }
            
            .card-tag {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 600;
                transition: all 0.3s ease;
                border: 2px solid transparent;
                cursor: default;
                letter-spacing: 0.3px;
            }
            
            .card-tag:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                border-color: rgba(255, 255, 255, 0.3);
            }
            
            /* Dark mode support */
            @media (prefers-color-scheme: dark) {
                .card-inner {
                    background: #1e1e1e;
                }
                
                .card-body {
                    background: linear-gradient(to bottom, #1e1e1e 0%, #252525 100%);
                    color: #e5e7eb;
                }
                
                .card-summary {
                    background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
                    color: #d1d5db;
                }
                
                .card-summary::before {
                    color: rgba(118, 75, 162, 0.2);
                }
                
                .card-points li {
                    color: #d1d5db;
                    background: #2d2d2d;
                    border-color: #404040;
                }
                
                .card-points li:hover {
                    background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
                    border-color: #667eea;
                }
                
                .card-footer {
                    background: linear-gradient(to right, #252525 0%, #2d2d2d 100%);
                    border-top-color: #404040;
                }
                
                .card-tag-label {
                    color: #9ca3af;
                }
            }
            
            /* Mobile responsive */
            @media (max-width: 640px) {
                .knowledge-card {
                    max-width: 100%;
                }
                
                .card-header {
                    padding: 24px 20px;
                }
                
                .card-title {
                    font-size: 1.5em;
                }
                
                .card-body {
                    padding: 20px;
                }
                
                .card-footer {
                    padding: 16px 20px;
                }
            }
        """

        # Generate tags HTML
        tags_html = ""
        if "tags" in data and data["tags"]:
            for tag in data["tags"]:
                tags_html += f'<div class="card-tag"><span class="card-tag-label">#</span>{tag}</div>'

        # Generate key points HTML
        points_html = ""
        if "key_points" in data and data["key_points"]:
            for point in data["key_points"]:
                points_html += f"<li>{point}</li>"

        # Build the card HTML structure
        content = f"""
        <div class="knowledge-card-container">
            <div class="knowledge-card">
                <div class="card-inner">
                    <div class="card-header">
                        <div class="card-category">{data.get('category', 'Knowledge')}</div>
                        <h2 class="card-title">{data.get('title', 'Flash Card')}</h2>
                    </div>
                    <div class="card-body">
                        <div class="card-summary">
                            {data.get('summary', '')}
                        </div>
                        
                        <div class="card-section-title">KEY POINTS</div>
                        <ul class="card-points">
                            {points_html}
                        </ul>
                    </div>
                    <div class="card-footer">
                        {tags_html}
                    </div>
                </div>
            </div>
        </div>
        """

        return content, style
