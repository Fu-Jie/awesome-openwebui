"""
title: Example Filter
author: open-webui
author_url: https://github.com/open-webui
funding_url: https://github.com/open-webui
version: 0.1
"""

from pydantic import BaseModel, Field
from typing import Optional
import re


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )

    def __init__(self):
        # Indicates custom file handling logic. This flag helps disengage default routines in favor of custom
        # implementations, informing the WebUI to defer file-related operations to designated methods within this class.
        # Alternatively, you can remove the files directly from the body in from the inlet hook
        # self.file_handler = True

        # Initialize 'valves' with specific configurations. Using 'Valves' instance helps encapsulate settings,
        # which ensures settings are managed cohesively and not confused with operational flags like 'file_handler'.
        self.valves = self.Valves()
        pass

    def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        # Modify the request body or validate it before processing by the chat completion API.
        # This function is the pre-processor for the API where various checks on the input can be performed.
        # It can also modify the request before sending it to the API.
        messages = body.get("messages", [])
        self.insert_user_env_info(__metadata__, messages)
        if "测试系统提示词" in str(messages):
            messages.insert(0, {"role": "system", "content": "你是一个大数学家"})
            print("XXXXX" * 100)
            print(body)
        self.change_web_search(body, __user__)
        body = self.inlet_chat_id(__model__, __metadata__, body)

        return body

    def inlet_chat_id(self, model: dict, metadata: dict, body: dict):
        if "openai" in model:
            base_model_id = model["openai"]["id"]

        else:
            base_model_id = model["info"]["base_model_id"]

        base_model = model["id"] if base_model_id is None else base_model_id
        if base_model.startswith("cfchatqwen"):
            # pass
            body["chat_id"] = metadata["chat_id"]

        if base_model.startswith("webgemini"):
            body["chat_id"] = metadata["chat_id"]
            if not model["id"].startswith("webgemini"):
                body["custom_model_id"] = model["id"]

        # print("我是 body *******************", body)
        return body

    def change_web_search(self, body, __user__):
        features = body.get("features", {})
        web_search_enabled = (
            features.get("web_search", False) if isinstance(features, dict) else False
        )
        if isinstance(__user__, (list, tuple)):
            user_email = __user__[0].get("email", "用户") if __user__[0] else "用户"
        elif isinstance(__user__, dict):
            user_email = __user__.get("email", "用户")
        model_name = body.get("model")
        if web_search_enabled:
            if model_name in ["qwen-max-latest", "qwen-max", "qwen-plus-latest"]:
                body.setdefault("enable_search", True)
                features["web_search"] = False
            if "search" in model_name or "搜索" in model_name:
                features["web_search"] = False
            if model_name.startswith("cfdeepseek-deepseek") and not model_name.endswith(
                "search"
            ):
                body["model"] = body["model"] + "-search"
                features["web_search"] = False
            if model_name.startswith("cfchatqwen") and not model_name.endswith(
                "search"
            ):
                body["model"] = body["model"] + "-search"
                features["web_search"] = False
            if model_name.startswith("gemini-2.5") and "search" not in model_name:
                body["model"] = body["model"] + "-search"
                features["web_search"] = False
            if user_email == "yi204o@qq.com":
                features["web_search"] = False

    def insert_user_env_info(self, __metadata__, messages, model_match_tags=None):
        """
        无论模型标签，始终在第一条用户消息内容前注入用户环境变量Markdown说明，并处理各种输入类型。
        如果消息中已存在环境变量信息，则更新为最新数据而不是重复添加。
        支持纯文本消息、图片消息或图文混合消息。
        """
        variables = __metadata__.get("variables", {})
        if not messages or messages[0]["role"] != "user":
            return

        if variables:
            # 构建环境变量的Markdown文本
            variable_markdown = (
                "## 用户环境变量\n"
                "以下信息为用户的环境变量，可用于为用户提供更个性化的服务或满足特定需求时作为参考：\n"
                f"- **用户姓名**：{variables.get('{{USER_NAME}}', '')}\n"
                f"- **当前日期时间**：{variables.get('{{CURRENT_DATETIME}}', '')}\n"
                f"- **当前星期**：{variables.get('{{CURRENT_WEEKDAY}}', '')}\n"
                f"- **当前时区**：{variables.get('{{CURRENT_TIMEZONE}}', '')}\n"
                f"- **用户语言**：{variables.get('{{USER_LANGUAGE}}', '')}\n"
            )

            content = messages[0]["content"]
            # 环境变量部分的匹配模式
            env_var_pattern = r"(## 用户环境变量\n以下信息为用户的环境变量，可用于为用户提供更个性化的服务或满足特定需求时作为参考：\n.*?用户语言.*?\n)"
            # 处理不同内容类型
            if isinstance(content, list):  # 多模态内容(可能包含图片和文本)
                # 查找第一个文本类型的内容
                text_index = -1
                for i, part in enumerate(content):
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_index = i
                        break

                if text_index >= 0:
                    # 存在文本内容，检查是否已存在环境变量信息
                    text_part = content[text_index]
                    text_content = text_part.get("text", "")

                    if re.search(env_var_pattern, text_content, flags=re.DOTALL):
                        # 已存在环境变量信息，更新为最新数据
                        text_part["text"] = re.sub(
                            env_var_pattern,
                            variable_markdown,
                            text_content,
                            flags=re.DOTALL,
                        )
                    else:
                        # 不存在环境变量信息，添加到开头
                        text_part["text"] = f"{variable_markdown}\n{text_content}"

                    content[text_index] = text_part
                else:
                    # 没有文本内容(例如只有图片)，添加新的文本项
                    content.insert(
                        0, {"type": "text", "text": f"{variable_markdown}\n"}
                    )

                messages[0]["content"] = content

            elif isinstance(content, str):  # 纯文本内容
                # 检查是否已存在环境变量信息
                if re.search(env_var_pattern, content, flags=re.DOTALL):
                    # 已存在，更新为最新数据
                    messages[0]["content"] = re.sub(
                        env_var_pattern, variable_markdown, content, flags=re.DOTALL
                    )
                else:
                    # 不存在，添加到开头
                    messages[0]["content"] = f"{variable_markdown}\n{content}"

            else:  # 其他类型内容
                # 转换为字符串并处理
                str_content = str(content)
                # 检查是否已存在环境变量信息
                if re.search(env_var_pattern, str_content, flags=re.DOTALL):
                    # 已存在，更新为最新数据
                    messages[0]["content"] = re.sub(
                        env_var_pattern, variable_markdown, str_content, flags=re.DOTALL
                    )
                else:
                    # 不存在，添加到开头
                    messages[0]["content"] = f"{variable_markdown}\n{str_content}"

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify or analyze the response body after processing by the API.
        # This function is the post-processor for the API, which can be used to modify the response
        # or perform additional checks and analytics.
        # print(f"outlet:{__name__}")
        # print(f"outlet:body:{body}")
        # print(f"outlet:user:{__user__}")
        return body
