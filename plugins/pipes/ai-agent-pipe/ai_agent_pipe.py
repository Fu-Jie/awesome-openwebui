"""
title: AI Agent Pipe
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CiAgPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyIvPgogIDxwYXRoIGQ9Im0xMiA5IDAgNSIvPgogIDxwYXRoIGQ9Im0xMiAxNSAwIDUiLz4KICA8cGF0aCBkPSJtOSA5IDMgMyIvPgogIDxwYXRoIGQ9Im0xNSA5LTMgMyIvPgogIDxwYXRoIGQ9Im05IDE1IDMgMyIvPgogIDxwYXRoIGQ9Im0xNSAxNUwzIDMiLz4KPC9zdmc+
version: 1.0.0
description: AI代理管道插件，让AI响应展示完整的代理工作流程，包括多轮思考、工具调用和迭代分析。
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

        # 系统提示：让AI模拟完整的代理工作流程
        system_prompt = """
你是一个高级AI代理，能够进行多轮思考、工具调用和迭代分析。请模拟一个完整的代理工作流程，包括：

1. **初始分析**：理解用户问题
2. **多轮思考**：进行深入分析和推理
3. **工具调用**：选择并使用适当的工具
4. **结果处理**：分析工具返回的结果
5. **最终总结**：提供完整的解决方案

请以JSON格式返回完整的代理工作流程：

{
  "agent_workflow": [
    {
      "step": 1,
      "type": "thinking",
      "content": "初始思考内容"
    },
    {
      "step": 2,
      "type": "tool_call",
      "tool_name": "工具名称",
      "tool_input": "工具输入参数",
      "reasoning": "为什么使用这个工具"
    },
    {
      "step": 3,
      "type": "tool_result",
      "tool_output": "工具返回的结果",
      "analysis": "对结果的分析"
    },
    {
      "step": 4,
      "type": "thinking",
      "content": "基于工具结果的进一步思考"
    },
    {
      "step": 5,
      "type": "tool_call",
      "tool_name": "另一个工具",
      "tool_input": "新的工具输入",
      "reasoning": "继续深入分析"
    }
  ],
  "final_answer": "最终的完整答案",
  "tools_used": ["使用的工具列表"],
  "confidence_level": "置信度评估"
}

至少包含3-5个步骤的完整工作流程，展示出代理的思考过程和工具使用。
        """

        analysis_prompt = f"""
用户问题：{user_message}

请作为AI代理完整解决这个问题。展示你的思考过程、工具使用和最终答案。

模拟可用的工具：
- web_search: 网络搜索工具
- code_analyzer: 代码分析工具
- data_processor: 数据处理工具
- knowledge_base: 知识库查询工具
- calculator: 计算工具
- file_reader: 文件读取工具

请进行多轮思考和工具调用来彻底解决这个问题。
        """

        try:
            # 调用LLM进行代理式分析
            response = await generate_chat_completion(
                model=__model__,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": analysis_prompt},
                ],
                user=__user__,
            )

            # 解析分析结果
            analysis_content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            try:
                analysis_result = json.loads(analysis_content)

                # 构建增强的响应，展示完整的代理工作流程
                workflow_steps = analysis_result.get("agent_workflow", [])

                workflow_display = ""
                for step in workflow_steps:
                    step_num = step.get("step", 0)
                    step_type = step.get("type", "unknown")

                    if step_type == "thinking":
                        workflow_display += f"""
### 🤔 思考步骤 {step_num}
{step.get('content', '')}
"""
                    elif step_type == "tool_call":
                        workflow_display += f"""
### 🛠️ 工具调用 {step_num}
**工具：** {step.get('tool_name', '')}
**输入：** {step.get('tool_input', '')}
**原因：** {step.get('reasoning', '')}
"""
                    elif step_type == "tool_result":
                        workflow_display += f"""
### 📊 工具结果 {step_num}
**输出：** {step.get('tool_output', '')}
**分析：** {step.get('analysis', '')}
"""

                enhanced_response = f"""
## 🤖 AI代理完整工作流程

### 🎯 问题
{user_message}

{workflow_display}

### 🎉 最终答案
{analysis_result.get('final_answer', '无法获取最终答案')}

### 📋 使用工具
{chr(10).join(f"• {tool}" for tool in analysis_result.get('tools_used', []))}

### 📊 置信度
{analysis_result.get('confidence_level', '未评估')}
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
此响应已通过AI代理管道处理，包含多轮思考和工具调用模拟。
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
