import asyncio
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from fastapi import Request

from open_webui.models.chats import Chats

class Filter:
    class Valves(BaseModel):
        # 注入的系统消息的前缀
        CONTEXT_PREFIX: str = Field(
            default="**背景知识**：为了更好地回答您的新问题，请参考上一轮对话中多个AI模型给出的回答：\n\n",
            description="Prefix for the injected system message containing the raw merged context."
        )

    def __init__(self):
        self.valves = self.Valves()
        self.type = "filter"
        self.name = "auto_context_merger"
        self.description = "Automatically injects the context of previous multi-model answers when a follow-up question is asked."

    async def inlet(self, body: Dict, __user__: Dict, __metadata__: Dict, __request__: Request, __event_emitter__):
        """
        此方法是过滤器的入口点。它会检查上一回合是否为多模型响应，
        如果是，则将这些响应直接格式化，并将格式化后的上下文作为系统消息注入到当前请求中。
        """
        print(f"*********** Filter '{self.name}' triggered ***********")
        chat_id = __metadata__.get("chat_id")
        if not chat_id:
            print(f"DEBUG: Filter '{self.name}' skipped: chat_id not found in metadata.")
            return body
        
        print(f"DEBUG: Chat ID found: {chat_id}")

        # 1. 从数据库获取完整的聊天历史
        try:
            chat = await asyncio.to_thread(Chats.get_chat_by_id, chat_id)
            
            # 根据 chats.py 源码，历史记录在 chat.chat['history'] 中
            if not chat or not hasattr(chat, 'chat') or not chat.chat.get("history") or not chat.chat.get("history").get("messages"):
                print(f"DEBUG: Filter '{self.name}' skipped: Chat history not found or empty for chat_id: {chat_id}")
                return body
            
            messages_map = chat.chat["history"]["messages"]
            print(f"DEBUG: Successfully loaded {len(messages_map)} messages from history.")
        except Exception as e:
            print(f"ERROR: Filter '{self.name}' failed to get chat history from DB: {e}")
            return body

        # 2. 分析历史，判断上一回合是否为多模型响应
        if not body.get("messages"):
            print(f"DEBUG: Filter '{self.name}' skipped: 'messages' array is empty in the request body.")
            return body
            
        current_user_message_id = body["messages"][-1].get("id")
        if not current_user_message_id:
            print(f"DEBUG: Filter '{self.name}' skipped: current_user_message_id not found in the last message of request body.")
            return body
        
        print(f"DEBUG: Current user message ID: {current_user_message_id}")

        parent_id = messages_map.get(current_user_message_id, {}).get("parentId")
        if not parent_id:
            print(f"DEBUG: Filter '{self.name}' skipped: parent_id not found for message '{current_user_message_id}'. This might be the first turn.")
            return body
        
        print(f"DEBUG: Parent message ID: {parent_id}")

        # 父消息（上一回合的AI回答）
        parent_message = messages_map.get(parent_id)
        if not parent_message:
            print(f"DEBUG: Filter '{self.name}' skipped: parent_message with id '{parent_id}' not found in history map.")
            return body

        # 祖父消息（上一回合的用户问题）
        grandparent_id = parent_message.get("parentId")
        if not grandparent_id:
            print(f"DEBUG: Filter '{self.name}' skipped: grandparent_id not found for message '{parent_id}'.")
            return body
        
        print(f"DEBUG: Grandparent message ID: {grandparent_id}")
        
        grandparent_message = messages_map.get(grandparent_id)
        if not grandparent_message or grandparent_message.get("role") != "user":
            print(f"DEBUG: Filter '{self.name}' skipped: grandparent_message with id '{grandparent_id}' is not a user message.")
            return body

        # 找到所有与父消息同级的AI回答（即上一回合的所有AI回答）
        sibling_assistant_messages = [
            msg for msg_id, msg in messages_map.items()
            if msg.get("parentId") == grandparent_id and msg.get("role") == "assistant"
        ]

        # 如果上一回合只有一个或没有AI回答，则不执行任何操作
        if len(sibling_assistant_messages) <= 1:
            print(f"DEBUG: Filter '{self.name}' skipped: Found {len(sibling_assistant_messages)} sibling assistant responses (required > 1).")
            return body
        
        print(f"DEBUG: Found {len(sibling_assistant_messages)} messages to merge for user query: '{str(grandparent_message.get('content', ''))[:70]}...'")

        # 3. 直接格式化响应
        await __event_emitter__({
            "type": "status",
            "data": {"description": f"检测到多模型历史，正在格式化 {len(sibling_assistant_messages)} 条上下文...", "done": False}
        })
        
        formatted_responses = []
        for msg in sibling_assistant_messages:
            # 尝试获取更友好的模型名称
            model_name = msg.get("modelName", msg.get("model", "未知模型"))
            content = msg.get("content", "[无内容]")
            formatted_responses.append(f"**来自模型 '{model_name}' 的回答是：**\n{content}")
        
        raw_merged_context = "\n\n---\n\n".join(formatted_responses)

        await __event_emitter__({
            "type": "status",
            "data": {"description": "上下文格式化完成。", "done": True}
        })

        # 4. 注入上下文到当前请求
        # 在当前用户问题之前插入格式化后的系统消息
        new_system_message = {
            "role": "system",
            "content": f"{self.valves.CONTEXT_PREFIX}{raw_merged_context}"
        }
        
        print(f"DEBUG: Injecting system message with merged context.")
        
        # 找到当前用户消息在body["messages"]中的位置
        current_user_message_index = -1
        for i, msg in enumerate(body["messages"]):
            if msg.get("id") == current_user_message_id:
                current_user_message_index = i
                break
        
        if current_user_message_index != -1:
            body["messages"].insert(current_user_message_index, new_system_message)
        else:
            # 如果找不到，作为安全兜底，加在倒数第二的位置
            body["messages"].insert(-1, new_system_message)
            print(f"WARN: Could not find current message ID in body, inserting context at second to last position.")

        print(f"*********** Filter '{self.name}' finished successfully ***********")
        return body

