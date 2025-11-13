"""
title: Smart Mind Map
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CiAgPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyIgZmlsbD0iY3VycmVudENvbG9yIi8+CiAgPGxpbmUgeDE9IjEyIiB5MT0iOSIgeDI9IjEyIiB5Mj0iNCIvPgogIDxjaXJjbGUgY3g9IjEyIiBjeT0iMyIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjEyIiB5MT0iMTUiIHgyPSIxMiIgeTI9IjIwIi8+CiAgPGNpcmNsZSBjeD0iMTIiIGN5PSIyMSIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjkiIHkxPSIxMiIgeDI9IjQiIHkyPSIxMiIvPgogIDxjaXJjbGUgY3g9IjMiIGN5PSIxMiIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjE1IiB5MT0iMTIiIHgyPSIyMCIgeTI9IjEyIi8+CiAgPGNpcmNsZSBjeD0iMjEiIGN5PSIxMiIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjEwLjUiIHkxPSIxMC41IiB4Mj0iNiIgeTI9IjYiLz4KICA8Y2lyY2xlIGN4PSI1IiBjeT0iNSIgcj0iMS41Ii8+CiAgPGxpbmUgeDE9IjEzLjUiIHkxPSIxMC41IiB4Mj0iMTgiIHkyPSI2Ii8+CiAgPGNpcmNsZSBjeD0iMTkiIGN5PSI1IiByPSIxLjUiLz4KICA8bGluZSB4MT0iMTAuNSIgeTE9IjEzLjUiIHgyPSI2IiB5Mj0iMTgiLz4KICA8Y2lyY2xlIGN4PSI1IiBjeT0iMTkiIHI9IjEuNSIvPgogIDxsaW5lIHgxPSIxMy41IiB5MT0iMTMuNSIgeDI9IjE4IiB5Mj0iMTgiLz4KICA8Y2lyY2xlIGN4PSIxOSIgY3k9IjE5IiByPSIxLjUiLz4KPC9zdmc+
version: 0.7.2
description: Intelligently analyzes text content and generates interactive mind maps to help users structure and visualize knowledge.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import time
import re
from fastapi import Request
from datetime import datetime
import pytz

from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_MINDMAP_ASSISTANT = """
你是一个专业的思维导图生成助手,能够高效地分析用户提供的长篇文本,并将其核心主题、关键概念、分支和子分支结构化为标准的Markdown列表语法,以便Markmap.js进行渲染。

请严格遵循以下指导原则:
-   **语言**: 所有输出必须使用用户指定的语言。
-   **格式**: 你的输出必须严格为Markdown列表格式,并用```markdown 和 ``` 包裹。
    -   使用 `#` 定义中心主题(根节点)。
    -   使用 `-` 和两个空格的缩进表示分支和子分支。
-   **内容**:
    -   识别文本的中心主题作为 `#` 标题。
    -   识别主要概念作为一级列表项。
    -   识别支持性细节或子概念作为嵌套的列表项。
    -   节点内容应简洁明了,避免冗长。
-   **只输出Markdown语法**: 不要包含任何额外的寒暄、解释或引导性文字。
-   **如果文本过短或无法生成有效导图**: 请输出一个简单的Markdown列表,表示无法生成,例如:
    ```markdown
    # 无法生成思维导图
    - 原因: 文本内容不足或不明确
    ```
"""

USER_PROMPT_GENERATE_MINDMAP = """
请分析以下长篇文本,并将其核心主题、关键概念、分支和子分支结构化为标准的Markdown列表语法,以供Markmap.js渲染。

---
**用户上下文信息:**
用户姓名: {user_name}
当前日期时间: {current_date_time_str}
当前星期: {current_weekday}
当前时区: {current_timezone_str}
用户语言: {user_language}
---

**长篇文本内容:**
Use code with caution.
Python
{long_text_content}
"""

HTML_TEMPLATE_MINDMAP = """
<!DOCTYPE html>
<html lang="{user_language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智绘心图: 思维导图</title>
    <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
    <script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.17"></script>
    <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.17"></script>
    <style>
        :root {
            --primary-color: #1e88e5;
            --secondary-color: #43a047;
            --background-color: #f4f6f8;
            --card-bg-color: #ffffff;
            --text-color: #263238;
            --muted-text-color: #546e7a;
            --border-color: #e0e0e0;
            --header-gradient: linear-gradient(135deg, var(--secondary-color), var(--primary-color));
            --shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
            --border-radius: 12px;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        body {
            font-family: var(--font-family);
            line-height: 1.7;
            color: var(--text-color);
            margin: 0;
            padding: 24px;
            background-color: var(--background-color);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        .container {
            max-width: 1280px;
            margin: 20px auto;
            background: var(--card-bg-color);
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            overflow: hidden;
            border: 1px solid var(--border-color);
        }
        .header {
            background: var(--header-gradient);
            color: white;
            padding: 32px 40px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2em;
            font-weight: 600;
            text-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .user-context {
            font-size: 0.85em;
            color: var(--muted-text-color);
            background-color: #eceff1;
            padding: 12px 20px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
        }
        .user-context span { margin: 4px 10px; }
        .content-area { 
            padding: 30px 40px;
        }
        .markmap-container {
            position: relative;
            background-color: #fff;
            background-image: radial-gradient(var(--border-color) 0.5px, transparent 0.5px);
            background-size: 20px 20px;
            border-radius: var(--border-radius);
            padding: 24px;
            min-height: 700px;
            display: flex;
            justify-content: center;
            align-items: center;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        .download-area {
            text-align: center;
            padding-top: 30px;
            margin-top: 30px;
            border-top: 1px solid var(--border-color);
        }
        .download-btn {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            margin: 0 10px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .download-btn.secondary {
            background-color: var(--secondary-color);
        }
        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }
        .download-btn.copied {
            background-color: #2e7d32; /* A darker green for success */
        }
        .footer {
            text-align: center;
            padding: 24px;
            font-size: 0.85em;
            color: #90a4ae;
            background-color: #eceff1;
        }
        .footer a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        .error-message {
            color: #c62828;
            background-color: #ffcdd2;
            border: 1px solid #ef9a9a;
            padding: 20px;
            border-radius: var(--border-radius);
            font-weight: 500;
            font-size: 1.1em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 智绘心图</h1>
        </div>
        <div class="user-context">
            <span><strong>用户:</strong> {user_name}</span>
            <span><strong>分析时间:</strong> {current_date_time_str}</span>
            <span><strong>星期:</strong> {current_weekday_zh}</span>
        </div>
        <div class="content-area">
            <div class="markmap-container" id="markmap-container-{unique_id}"></div>
            <div class="download-area">
                <button id="download-svg-btn-{unique_id}" class="download-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span class="btn-text">复制 SVG 代码</span>
                </button>
                <button id="download-md-btn-{unique_id}" class="download-btn secondary">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                    <span class="btn-text">复制 Markdown</span>
                </button>
            </div>
        </div>
        <div class="footer">
            <p>© {current_year} 智绘心图 • 渲染引擎由 <a href="https://markmap.js.org/" target="_blank">Markmap</a> 提供</p>
        </div>
    </div>
    
    <script type="text/template" id="markdown-source-{unique_id}">{markdown_syntax}</script>

    <script>
      (function() {
        const renderMindmap = () => {
            const uniqueId = "{unique_id}";
            const containerEl = document.getElementById('markmap-container-' + uniqueId);
            if (!containerEl || containerEl.dataset.markmapRendered) return;

            const sourceEl = document.getElementById('markdown-source-' + uniqueId);
            if (!sourceEl) return;

            const markdownContent = sourceEl.textContent.trim();
            if (!markdownContent) {
                containerEl.innerHTML = '<div class="error-message">⚠️ 无法加载思维导图: 缺少有效内容。</div>';
                return;
            }

            try {
                const svgEl = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                svgEl.style.width = '100%';
                svgEl.style.height = '700px';
                containerEl.innerHTML = ''; 
                containerEl.appendChild(svgEl);

                const { Transformer, Markmap } = window.markmap;
                const transformer = new Transformer();
                const { root } = transformer.transform(markdownContent);
                
                const style = (id) => `${id} text { font-size: 16px !important; }`;

                const options = { 
                    autoFit: true,
                    style: style
                };
                Markmap.create(svgEl, options, root);
                
                containerEl.dataset.markmapRendered = 'true';
                
                attachDownloadHandlers(uniqueId);

            } catch (error) {
                console.error('Markmap rendering error:', error);
                containerEl.innerHTML = '<div class="error-message">⚠️ 思维导图渲染失败!<br>原因: ' + error.message + '</div>';
            }
        };

        const attachDownloadHandlers = (uniqueId) => {
            const downloadSvgBtn = document.getElementById('download-svg-btn-' + uniqueId);
            const downloadMdBtn = document.getElementById('download-md-btn-' + uniqueId);
            const containerEl = document.getElementById('markmap-container-' + uniqueId);

            const showFeedback = (button, isSuccess) => {
                const buttonText = button.querySelector('.btn-text');
                const originalText = buttonText.textContent;
                
                button.disabled = true;
                if (isSuccess) {
                    buttonText.textContent = '✅ 已复制!';
                    button.classList.add('copied');
                } else {
                    buttonText.textContent = '❌ 复制失败';
                }

                setTimeout(() => {
                    buttonText.textContent = originalText;
                    button.disabled = false;
                    button.classList.remove('copied');
                }, 2500);
            };

            const copyToClipboard = (content, button) => {
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(content).then(() => {
                        showFeedback(button, true);
                    }, () => {
                        showFeedback(button, false);
                    });
                } else {
                    // Fallback for older/insecure contexts
                    const textArea = document.createElement('textarea');
                    textArea.value = content;
                    textArea.style.position = 'fixed';
                    textArea.style.opacity = '0';
                    document.body.appendChild(textArea);
                    textArea.focus();
                    textArea.select();
                    try {
                        document.execCommand('copy');
                        showFeedback(button, true);
                    } catch (err) {
                        showFeedback(button, false);
                    }
                    document.body.removeChild(textArea);
                }
            };

            if (downloadSvgBtn) {
                downloadSvgBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    const svgEl = containerEl.querySelector('svg');
                    if (svgEl) {
                        const svgData = new XMLSerializer().serializeToString(svgEl);
                        copyToClipboard(svgData, downloadSvgBtn);
                    }
                });
            }

            if (downloadMdBtn) {
                downloadMdBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    const markdownContent = document.getElementById('markdown-source-' + uniqueId).textContent;
                    copyToClipboard(markdownContent, downloadMdBtn);
                });
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', renderMindmap);
        } else {
            renderMindmap();
        }
      })();
    </script>
</body>
</html>
"""


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
        self.weekday_map = {
            "Monday": "星期一",
            "Tuesday": "星期二",
            "Wednesday": "星期三",
            "Thursday": "星期四",
            "Friday": "星期五",
            "Saturday": "星期六",
            "Sunday": "星期日",
        }

    def _extract_markdown_syntax(self, llm_output: str) -> str:
        match = re.search(r"```markdown\s*(.*?)\s*```", llm_output, re.DOTALL)
        if match:
            extracted_content = match.group(1).strip()
        else:
            logger.warning(
                "LLM输出未严格遵循预期Markdown格式，将整个输出作为摘要处理。"
            )
            extracted_content = llm_output.strip()
        return extracted_content.replace("</script>", "<\\/script>")

    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __request__: Optional[Request] = None,
    ) -> Optional[dict]:
        logger.info("Action: 智绘心图 (v12 - Final Feedback Fix) started")

        if isinstance(__user__, (list, tuple)):
            user_language = (
                __user__[0].get("language", "zh-CN") if __user__ else "zh-CN"
            )
            user_name = __user__[0].get("name", "用户") if __user__[0] else "用户"
            user_id = (
                __user__[0]["id"]
                if __user__ and "id" in __user__[0]
                else "unknown_user"
            )
        elif isinstance(__user__, dict):
            user_language = __user__.get("language", "zh-CN")
            user_name = __user__.get("name", "用户")
            user_id = __user__.get("id", "unknown_user")

        try:
            shanghai_tz = pytz.timezone("Asia/Shanghai")
            current_datetime_shanghai = datetime.now(shanghai_tz)
            current_date_time_str = current_datetime_shanghai.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            current_weekday_en = current_datetime_shanghai.strftime("%A")
            current_weekday_zh = self.weekday_map.get(current_weekday_en, "未知星期")
            current_year = current_datetime_shanghai.strftime("%Y")
            current_timezone_str = "Asia/Shanghai"
        except Exception as e:
            logger.warning(f"获取时区信息失败: {e}，使用默认值。")
            now = datetime.now()
            current_date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            current_weekday_zh = "未知星期"
            current_year = now.strftime("%Y")
            current_timezone_str = "未知时区"

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "notification",
                    "data": {
                        "type": "info",
                        "content": "智绘心图已启动，正在为您生成思维导图...",
                    },
                }
            )

        messages = body.get("messages")
        if (
            not messages
            or not isinstance(messages, list)
            or not messages[-1].get("content")
        ):
            error_message = "无法获取有效的用户消息内容。"
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "notification",
                        "data": {"type": "error", "content": error_message},
                    }
                )
            return {
                "messages": [{"role": "assistant", "content": f"❌ {error_message}"}]
            }

        parts = re.split(r"```html.*?```", messages[-1]["content"], flags=re.DOTALL)
        long_text_content = ""
        if parts:
            for part in reversed(parts):
                if part.strip():
                    long_text_content = part.strip()
                    break

        if not long_text_content:
            long_text_content = messages[-1]["content"].strip()

        if len(long_text_content) < self.valves.MIN_TEXT_LENGTH:
            short_text_message = f"文本内容过短({len(long_text_content)}字符)，无法进行有效分析。请提供至少{self.valves.MIN_TEXT_LENGTH}字符的文本。"
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "notification",
                        "data": {"type": "warning", "content": short_text_message},
                    }
                )
            return {
                "messages": [
                    {"role": "assistant", "content": f"⚠️ {short_text_message}"}
                ]
            }

        if self.valves.show_status and __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "智绘心图: 深入分析文本结构...",
                        "done": False,
                        "hidden": False,
                    },
                }
            )

        try:
            unique_id = f"id_{int(time.time() * 1000)}"

            formatted_user_prompt = USER_PROMPT_GENERATE_MINDMAP.format(
                user_name=user_name,
                current_date_time_str=current_date_time_str,
                current_weekday=current_weekday_zh,
                current_timezone_str=current_timezone_str,
                user_language=user_language,
                long_text_content=long_text_content,
            )

            llm_payload = {
                "model": self.valves.LLM_MODEL_ID,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_MINDMAP_ASSISTANT},
                    {"role": "user", "content": formatted_user_prompt},
                ],
                "temperature": 0.5,
                "stream": False,
            }
            user_obj = Users.get_user_by_id(user_id)
            if not user_obj:
                raise ValueError(f"无法获取用户对象，用户ID: {user_id}")

            llm_response = await generate_chat_completion(
                __request__, llm_payload, user_obj
            )

            if (
                not llm_response
                or "choices" not in llm_response
                or not llm_response["choices"]
            ):
                raise ValueError("LLM响应格式不正确或为空。")

            assistant_response_content = llm_response["choices"][0]["message"][
                "content"
            ]
            markdown_syntax = self._extract_markdown_syntax(assistant_response_content)

            final_html_content = (
                HTML_TEMPLATE_MINDMAP.replace("{unique_id}", unique_id)
                .replace("{user_language}", user_language)
                .replace("{user_name}", user_name)
                .replace("{current_date_time_str}", current_date_time_str)
                .replace("{current_weekday_zh}", current_weekday_zh)
                .replace("{current_year}", current_year)
                .replace("{markdown_syntax}", markdown_syntax)
            )

            html_embed_tag = f"```html\n{final_html_content}\n```"
            body["messages"][-1]["content"] = f"{long_text_content}\n\n{html_embed_tag}"

            if self.valves.show_status and __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "智绘心图: 绘制完成！",
                            "done": True,
                            "hidden": False,
                        },
                    }
                )
                await __event_emitter__(
                    {
                        "type": "notification",
                        "data": {
                            "type": "success",
                            "content": f"思维导图已生成，{user_name}！",
                        },
                    }
                )
            logger.info("Action: 智绘心图 (v12) completed successfully")

        except Exception as e:
            error_message = f"智绘心图处理失败: {str(e)}"
            logger.error(f"智绘心图错误: {error_message}", exc_info=True)
            user_facing_error = f"抱歉，智绘心图在处理时遇到错误: {str(e)}。\n请检查Open WebUI后端日志获取更多详情。"
            body["messages"][-1][
                "content"
            ] = f"{long_text_content}\n\n❌ **错误:** {user_facing_error}"

            if __event_emitter__:
                if self.valves.show_status:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": "智绘心图: 处理失败。",
                                "done": True,
                                "hidden": False,
                            },
                        }
                    )
                await __event_emitter__(
                    {
                        "type": "notification",
                        "data": {
                            "type": "error",
                            "content": f"智绘心图生成失败, {user_name}！",
                        },
                    }
                )

        return body
