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
            description="Prefix for the injected system message containing the raw merged context.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.type = "filter"
        self.name = "auto_context_merger"
        self.description = "Automatically injects the context of previous multi-model answers when a follow-up question is asked."

    async def inlet(
        self,
        body: Dict,
        __user__: Dict,
        __metadata__: Dict,
        __request__: Request,
        __event_emitter__,
    ):
        """
        此方法是过滤器的入口点。它会检查上一回合是否为多模型响应，
        如果是，则将这些响应直接格式化，并将格式化后的上下文作为系统消息注入到当前请求中。
        """
        print(f"*********** Filter '{self.name}' triggered ***********")
        chat_id = __metadata__.get("chat_id")
        if not chat_id:
            print(
                f"DEBUG: Filter '{self.name}' skipped: chat_id not found in metadata."
            )
            return body

        print(f"DEBUG: Chat ID found: {chat_id}")

        # 1. 从数据库获取完整的聊天历史
        try:
            chat = await asyncio.to_thread(Chats.get_chat_by_id, chat_id)

            # 根据 chats.py 源码，历史记录在 chat.chat['history'] 中
            if (
                not chat
                or not hasattr(chat, "chat")
                or not chat.chat.get("history")
                or not chat.chat.get("history").get("messages")
            ):
                print(
                    f"DEBUG: Filter '{self.name}' skipped: Chat history not found or empty for chat_id: {chat_id}"
                )
                return body

            messages_map = chat.chat["history"]["messages"]
            print(
                f"DEBUG: Successfully loaded {len(messages_map)} messages from history."
            )

            # Count the number of user messages in the history
            user_message_count = sum(1 for msg in messages_map.values() if msg.get("role") == "user")

            # If there are less than 2 user messages, there's no previous turn to merge.
            if user_message_count < 2:
                print(f"DEBUG: Filter '{self.name}' skipped: Not enough user messages in history to have a previous turn (found {user_message_count}, required >= 2).")
                return body

        except Exception as e:
            print(
                f"ERROR: Filter '{self.name}' failed to get chat history from DB: {e}"
            )
            return body

        # 2. 分析历史，判断上一回合是否为多模型响应
        if not body.get("messages"):
            print(
                f"DEBUG: Filter '{self.name}' skipped: 'messages' array is empty in the request body."
            )
            return body

        new_user_message = body["messages"][-1]
        new_user_message_id = new_user_message.get("id")

        print(f"DEBUG: New user message ID (from body): {new_user_message_id}")

        # Find the last user message in the historical messages_map (this is the grandparent_id)
        grandparent_id = None
        grandparent_message = None
        last_user_message_timestamp = 0

        for msg_id, msg in messages_map.items():
            if (
                msg.get("role") == "user"
                and msg.get("timestamp", 0) > last_user_message_timestamp
            ):
                grandparent_id = msg_id
                grandparent_message = msg
                last_user_message_timestamp = msg.get("timestamp", 0)

        if not grandparent_id:
            print(
                f"DEBUG: Filter '{self.name}' skipped: No user messages found in history to determine previous turn."
            )
            return body

        print(
            f"DEBUG: Grandparent message ID (last user message in history): {grandparent_id}"
        )

        # Now, grandparent_id is the ID of the last user message in the history.
        # We need to find all AI responses that are children of this user message.
        sibling_assistant_messages = [
            msg
            for msg_id, msg in messages_map.items()
            if msg.get("parentId") == grandparent_id and msg.get("role") == "assistant"
        ]

        # Sort sibling assistant messages by timestamp to ensure "top to bottom" order
        sibling_assistant_messages.sort(key=lambda msg: msg.get("timestamp", 0))

        # If there's only one or no AI response for the last user message, do nothing
        if len(sibling_assistant_messages) <= 1:
            print(
                f"DEBUG: Filter '{self.name}' skipped: Found {len(sibling_assistant_messages)} sibling assistant responses for the last user message (required > 1)."
            )
            return body
        
        # Check if all sibling assistant messages are complete and have content
        all_siblings_ready = True
        print("DEBUG: Checking sibling assistant messages for completion...")
        for msg in sibling_assistant_messages:
            is_done = msg.get("done", False)
            has_content = bool(msg.get("content", "").strip())
            print(f"DEBUG: Checking sibling message ID {msg.get('id')}: done={is_done}, has_content={has_content}")
            if not (is_done and has_content):
                all_siblings_ready = False
        
        if not all_siblings_ready:
            print(f"DEBUG: Filter '{self.name}' skipped: Not all sibling assistant responses from the previous turn are complete or have content.")
            return body

        print(
            f"DEBUG: Found {len(sibling_assistant_messages)} messages to merge for user query: '{str(grandparent_message.get('content', ''))[:70]}...'"
        )

        # 3. 直接格式化响应
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": f"检测到多模型历史，正在格式化 {len(sibling_assistant_messages)} 条上下文...",
                    "done": False,
                },
            }
        )

        merged_content = None
        merged_message_id = None
        merged_message_timestamp = sibling_assistant_messages[0].get("timestamp", 0)

        # Case A: Check for system pre-merged content (merged.status: true and content not empty)
        merged_content_msg = next(
            (s for s in sibling_assistant_messages if s.get('merged', {}).get('status') and s.get('merged', {}).get('content')), 
            None
        )

        if merged_content_msg:
            merged_content = merged_content_msg['merged']['content']
            merged_message_id = merged_content_msg['id']
            merged_message_timestamp = merged_content_msg.get('timestamp', merged_message_timestamp)
            print(f"DEBUG: Using pre-merged content from message ID: {merged_message_id}")
        else:
            # Case B: Manually merge all sibling assistant messages' content
            combined_content = []
            first_sibling_id = None
            counter = 0
            
            for s in sibling_assistant_messages:
                if not first_sibling_id:
                    first_sibling_id = s['id']
                    
                content = s.get('content', '')
                
                # Filter out empty or error content
                if content and content != "The requested model is not supported.":
                    # Convert counter to a letter (a, b, c, ...) for the ID
                    response_id = chr(ord('a') + counter)
                    combined_content.append(f"<response id=\"{response_id}\">\n{content}\n</response>")
                    counter += 1
            
            if combined_content:
                merged_content = "\n\n".join(combined_content)
                merged_message_id = first_sibling_id or grandparent_id # Use first sibling's ID or grandparent's ID as fallback
                print(f"DEBUG: Manually merged content with XML tags. New message ID will be: {merged_message_id}")
        
        if not merged_content:
            print("DEBUG: No valid content to merge after checking pre-merged and manual merge.")
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "没有有效内容可合并。", "done": True},
                }
            )
            return body

        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "上下文格式化完成。", "done": True},
            }
        )

        # 4. 注入上下文到当前请求
        # 将合并后的助手消息注入到当前请求中，并替换掉旧的同级助手消息
        new_assistant_message = {
            "id": merged_message_id, # Assign the determined ID
            "parentId": grandparent_id,
            "role": "assistant",
            "content": f"{self.valves.CONTEXT_PREFIX}{merged_content}",
            "timestamp": merged_message_timestamp
        }

        print(f"DEBUG: Injecting merged assistant message and replacing old siblings.")

        # Find and remove old sibling assistant messages from the body
        sibling_ids_to_remove = {msg.get("id") for msg in sibling_assistant_messages}
        insertion_index = -1
        indices_to_remove = []

        for i, msg in enumerate(body["messages"]):
            if msg.get("id") in sibling_ids_to_remove:
                indices_to_remove.append(i)
                if insertion_index == -1:
                    # Store the index of the first sibling to insert the merged message at
                    insertion_index = i
        
        # If old siblings were found in the body, replace them
        if insertion_index != -1:
            # Remove old siblings in reverse order to not mess up indices
            for i in sorted(indices_to_remove, reverse=True):
                del body["messages"][i]
            
            # Insert the new merged message at the position of the first old sibling
            body["messages"].insert(insertion_index, new_assistant_message)
            print(f"DEBUG: Replaced {len(indices_to_remove)} sibling messages with a single merged message.")
        else:
            # If no old siblings were found in the body, fall back to inserting before the current user message
            current_user_message_index = -1
            if new_user_message_id:
                for i, msg in enumerate(body["messages"]):
                    if msg.get("id") == new_user_message_id:
                        current_user_message_index = i
                        break
            else:
                current_user_message_index = len(body["messages"]) - 1

            if current_user_message_index != -1:
                body["messages"].insert(current_user_message_index, new_assistant_message)
                print(f"DEBUG: No old siblings found in body. Inserted merged message at index {current_user_message_index}.")
            else:
                body["messages"].append(new_assistant_message)
                print(f"DEBUG: No old siblings found in body. Appended merged message at the end.")
        
        print(f"*********** Filter '{self.name}' finished successfully ***********")
        return body
