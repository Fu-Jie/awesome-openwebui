import asyncio
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from fastapi import Request

from open_webui.models.chats import Chats


class Filter:
    class Valves(BaseModel):
        # 注入的系统消息的前缀
        CONTEXT_PREFIX: str = Field(
            default="下面是多个匿名AI模型给出的回答，使用<response>标签包裹：\n\n",
            description="Prefix for the injected system message containing the raw merged context.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True
        self.type = "filter"
        self.name = "合并回答"
        self.description = "在用户提问时，自动注入之前多个模型回答的上下文。"

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
            user_message_count = sum(
                1 for msg in messages_map.values() if msg.get("role") == "user"
            )

            # If there are less than 2 user messages, there's no previous turn to merge.
            if user_message_count < 2:
                print(
                    f"DEBUG: Filter '{self.name}' skipped: Not enough user messages in history to have a previous turn (found {user_message_count}, required >= 2)."
                )
                return body

        except Exception as e:
            print(
                f"ERROR: Filter '{self.name}' failed to get chat history from DB: {e}"
            )
            return body

        # This filter rebuilds the entire chat history to consolidate all multi-response turns.

        # 1. Get all messages from history and sort by timestamp
        all_messages = list(messages_map.values())
        all_messages.sort(key=lambda x: x.get("timestamp", 0))

        # 2. Pre-group all assistant messages by their parentId for efficient lookup
        assistant_groups = {}
        for msg in all_messages:
            if msg.get("role") == "assistant":
                parent_id = msg.get("parentId")
                if parent_id:
                    if parent_id not in assistant_groups:
                        assistant_groups[parent_id] = []
                    assistant_groups[parent_id].append(msg)

        final_messages = []
        processed_parent_ids = set()

        # 3. Iterate through the sorted historical messages to build the final, clean list
        for msg in all_messages:
            msg_id = msg.get("id")
            role = msg.get("role")
            parent_id = msg.get("parentId")

            if role == "user":
                # Add user messages directly
                final_messages.append(msg)

            elif role == "assistant":
                # If this assistant's parent group has already been processed, skip it
                if parent_id in processed_parent_ids:
                    continue

                # Process the group of siblings for this parent_id
                if parent_id in assistant_groups:
                    siblings = assistant_groups[parent_id]

                    # Only perform a merge if there are multiple siblings
                    if len(siblings) > 1:
                        print(
                            f"DEBUG: Found a group of {len(siblings)} siblings for parent_id {parent_id}. Merging..."
                        )

                        # --- MERGE LOGIC ---
                        merged_content = None
                        merged_message_id = None
                        # Sort siblings by timestamp before processing
                        siblings.sort(key=lambda s: s.get("timestamp", 0))
                        merged_message_timestamp = siblings[0].get("timestamp", 0)

                        # Case A: Check for system pre-merged content (merged.status: true and content not empty)
                        merged_content_msg = next(
                            (
                                s
                                for s in siblings
                                if s.get("merged", {}).get("status")
                                and s.get("merged", {}).get("content")
                            ),
                            None,
                        )

                        if merged_content_msg:
                            merged_content = merged_content_msg["merged"]["content"]
                            merged_message_id = merged_content_msg["id"]
                            merged_message_timestamp = merged_content_msg.get(
                                "timestamp", merged_message_timestamp
                            )
                            print(
                                f"DEBUG: Using pre-merged content from message ID: {merged_message_id}"
                            )
                        else:
                            # Case B: Manually merge content
                            combined_content = []
                            first_sibling_id = None
                            counter = 0

                            for s in siblings:
                                if not first_sibling_id:
                                    first_sibling_id = s["id"]

                                content = s.get("content", "")
                                if (
                                    content
                                    and content
                                    != "The requested model is not supported."
                                ):
                                    response_id = chr(ord("a") + counter)
                                    combined_content.append(
                                        f'<response id="{response_id}">\n{content}\n</response>'
                                    )
                                    counter += 1

                            if combined_content:
                                merged_content = "\n\n".join(combined_content)
                                merged_message_id = first_sibling_id or parent_id

                        if merged_content:
                            merged_message = {
                                "id": merged_message_id,
                                "parentId": parent_id,
                                "role": "assistant",
                                "content": f"{self.valves.CONTEXT_PREFIX}{merged_content}",
                                "timestamp": merged_message_timestamp,
                            }
                            final_messages.append(merged_message)
                    else:
                        # If there's only one sibling, add it directly
                        final_messages.append(siblings[0])

                    # Mark this group as processed
                    processed_parent_ids.add(parent_id)

        # 4. The new user message from the current request is not in the historical messages_map,
        # so we need to append it to our newly constructed message list.
        if body.get("messages"):
            new_user_message_from_body = body["messages"][-1]
            # Ensure we don't add a historical message that might be in the body for context
            if new_user_message_from_body.get("id") not in messages_map:
                final_messages.append(new_user_message_from_body)

        # 5. Replace the original message list with the new, cleaned-up list
        body["messages"] = final_messages
        print(
            f"DEBUG: Rebuilt message history with {len(final_messages)} messages, consolidating all multi-response turns."
        )

        print(f"*********** Filter '{self.name}' finished successfully ***********")
        return body
