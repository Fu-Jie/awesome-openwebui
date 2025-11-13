"""
title: AI Agent Pipe
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CiAgPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyIvPgogIDxwYXRoIGQ9Im0xMiA5IDAgNSIvPgogIDxwYXRoIGQ9Im0xMiAxNSAwIDUiLz4KICA8cGF0aCBkPSJtOSA5IDMgMyIvPgogIDxwYXRoIGQ9Im0xNSA5LTMgMyIvPgogIDxwYXRoIGQ9Im05IDE1IDMgMyIvPgogIDxwYXRoIGQ9Im0xNSAxNUwzIDMiLz4KPC9zdmc+
version: 1.0.0
description: AI代理管道插件，让AI响应以代理模式进行多步骤分析和工具使用。
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import json
from fastapi import Request

from open_webui.utils.chat import generate_chat_completion

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Pipe:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the pipe operations."
        )
        enable_agent_mode: bool = Field(
            default=True, description="Enable agent mode for all responses."
        )
        pass

    def __init__(self):
        self.valves = self.Valves()
        pass

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = {},
        __event_emitter__=None,
        __event_call__=None,
        __model__=None,
        __request__: Request = None,
    ) -> Optional[dict]:
        """
        AI Agent Pipe - Transform LLM responses into agent-style multi-step analysis
        """
        logger.info("AI Agent Pipe processing response")

        if not self.valves.enable_agent_mode:
            return body

        # 获取原始响应
        messages = body.get("messages", [])
        if not messages:
            return body

        # 获取最后一条用户消息和AI响应
        user_message = None
        ai_response = None

        for msg in reversed(messages):
            if msg.get("role") == "user" and not user_message:
                user_message = msg.get("content", "")
            elif msg.get("role") == "assistant" and not ai_response:
                ai_response = msg.get("content", "")

        if not user_message or not ai_response:
            return body

        # 系统提示：让AI重新分析并以代理模式格式化响应
        system_prompt = """
你是一个AI代理分析器。你的任务是将普通的AI响应转换为结构化的代理式分析格式。

请分析用户的问题和AI的原始响应，然后以JSON格式重新组织：

{
  "original_response": "原始AI响应",
  "agent_analysis": {
    "problem_identification": "问题识别",
    "step_by_step_reasoning": ["步骤1", "步骤2", "步骤3"],
    "tool_recommendations": ["工具1", "工具2"],
    "solution_summary": "解决方案总结"
  }
}

如果原始响应已经是结构化的，保持其结构但添加代理分析层。
        """

        analysis_prompt = f"""
用户问题：{user_message}

AI原始响应：{ai_response}

请将上述内容转换为代理式分析格式。
        """

        try:
            # 调用LLM进行代理式分析
            response = await generate_chat_completion(
                model=__model__,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": analysis_prompt}
                ],
                user=__user__,
            )

            # 解析分析结果
            analysis_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            try:
                analysis_result = json.loads(analysis_content)

                # 构建增强的响应
                enhanced_response = f"""
## 🤖 AI代理分析结果

### 📝 原始响应
{analysis_result.get('original_response', ai_response)}

### 🔍 代理分析

**问题识别：**
{analysis_result.get('agent_analysis', {}).get('problem_identification', '无法解析')}

**逐步推理：**
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(analysis_result.get('agent_analysis', {}).get('step_by_step_reasoning', [])))}

**推荐工具：**
{chr(10).join(f"• {tool}" for tool in analysis_result.get('agent_analysis', {}).get('tool_recommendations', []))}

**解决方案总结：**
{analysis_result.get('agent_analysis', {}).get('solution_summary', '无法解析')}
                """

                # 更新消息中的AI响应
                for msg in messages:
                    if msg.get("role") == "assistant":
                        msg["content"] = enhanced_response
                        break

                body["messages"] = messages

            except json.JSONDecodeError:
                # 如果解析失败，添加简单的代理格式
                enhanced_response = f"""
## 🤖 AI代理响应

### 原始回答
{ai_response}

### 代理分析
此响应已通过AI代理管道处理，提供多角度分析和工具建议。
                """

                for msg in messages:
                    if msg.get("role") == "assistant":
                        msg["content"] = enhanced_response
                        break

                body["messages"] = messages

        except Exception as e:
            logger.error(f"Error in AI Agent Pipe: {str(e)}")
            # 如果出错，返回原始body
            pass

        return body