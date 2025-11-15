"""
title: Async Context Compression
id: async_context_compression
author: Fu-Jie
author_url: https://github.com/Fu-Jie
funding_url: https://github.com/Fu-Jie/awesome-openwebui
description: Reduces token consumption in long conversations while maintaining coherence through intelligent summarization and message compression.
version: 1.0.1
license: MIT

═══════════════════════════════════════════════════════════════════════════════
📌 Overview
═══════════════════════════════════════════════════════════════════════════════

This filter significantly reduces token consumption in long conversations by using intelligent summarization and message compression, while maintaining conversational coherence.

Core Features:
  ✅ Automatic compression triggered by a message count threshold
  ✅ Asynchronous summary generation (does not block user response)
  ✅ Persistent storage with database support (PostgreSQL and SQLite)
  ✅ Flexible retention policy (configurable to keep first and last N messages)
  ✅ Smart summary injection to maintain context

═══════════════════════════════════════════════════════════════════════════════
🔄 Workflow
═══════════════════════════════════════════════════════════════════════════════

Phase 1: Inlet (Pre-request processing)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Receives all messages in the current conversation.
  2. Checks for a previously saved summary.
  3. If a summary exists and the message count exceeds the retention threshold:
     ├─ Extracts the first N messages to be kept.
     ├─ Injects the summary into the first message.
     ├─ Extracts the last N messages to be kept.
     └─ Combines them into a new message list: [Kept First Messages + Summary] + [Kept Last Messages].
  4. Sends the compressed message list to the LLM.

Phase 2: Outlet (Post-response processing)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Triggered after the LLM response is complete.
  2. Checks if the message count has reached the compression threshold.
  3. If the threshold is met, an asynchronous background task is started to generate a summary:
     ├─ Extracts messages to be summarized (excluding the kept first and last messages).
     ├─ Calls the LLM to generate a concise summary.
     └─ Saves the summary to the database.

═══════════════════════════════════════════════════════════════════════════════
💾 Storage
═══════════════════════════════════════════════════════════════════════════════

This filter uses a database for persistent storage, configured via the `DATABASE_URL` environment variable. It supports both PostgreSQL and SQLite.

Configuration:
  - The `DATABASE_URL` environment variable must be set.
  - PostgreSQL Example: `postgresql://user:password@host:5432/openwebui`
  - SQLite Example: `sqlite:///path/to/your/database.db`

The filter automatically selects the appropriate database driver based on the `DATABASE_URL` prefix (`postgres` or `sqlite`).

  Table Structure (`chat_summary`):
    - id: Primary Key (auto-increment)
    - chat_id: Unique chat identifier (indexed)
    - summary: The summary content (TEXT)
    - compressed_message_count: The original number of messages
    - created_at: Timestamp of creation
    - updated_at: Timestamp of last update

═══════════════════════════════════════════════════════════════════════════════
📊 Compression Example
═══════════════════════════════════════════════════════════════════════════════

Scenario: A 20-message conversation (Default settings: keep first 1, keep last 6)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Before Compression:
    Message 1: [Initial prompt + First question]
    Messages 2-14: [Historical conversation]
    Messages 15-20: [Recent conversation]
    Total: 20 full messages

  After Compression:
    Message 1: [Initial prompt + Historical summary + First question]
    Messages 15-20: [Last 6 full messages]
    Total: 7 messages

  Effect:
    ✓ Saves 13 messages (approx. 65%)
    ✓ Retains full context
    ✓ Protects important initial prompts

═══════════════════════════════════════════════════════════════════════════════
⚙️ Configuration
═══════════════════════════════════════════════════════════════════════════════

priority
  Default: 10
  Description: The execution order of the filter. Lower numbers run first.

compression_threshold
  Default: 15
  Description: When the message count reaches this value, a background summary generation will be triggered after the conversation ends.
  Recommendation: Adjust based on your model's context window and cost.

keep_first
  Default: 1
  Description: Always keep the first N messages of the conversation. Set to 0 to disable. The first message often contains important system prompts.

keep_last
  Default: 6
  Description: Always keep the last N full messages of the conversation to ensure context coherence.

summary_model
  Default: None
  Description: The LLM used to generate the summary.
  Recommendation:
    - It is strongly recommended to configure a fast, economical, and compatible model, such as `deepseek-v3`、`gemini-2.5-flash`、`gpt-4.1`。
    - If left empty, the filter will attempt to use the model from the current conversation.
  Note:
    - If the current conversation uses a pipeline (Pipe) model or a model that does not support standard generation APIs, leaving this field empty may cause summary generation to fail. In this case, you must specify a valid model.

max_summary_tokens
  Default: 4000
  Description: The maximum number of tokens allowed for the generated summary.

summary_temperature
  Default: 0.3
  Description: Controls the randomness of the summary generation. Lower values produce more deterministic output.

debug_mode
  Default: true
  Description: Prints detailed debug information to the log. Recommended to set to `false` in production.

🔧 Deployment
═══════════════════════════════════════════════════════

Docker Compose Example:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  services:
    openwebui:
      environment:
        DATABASE_URL: postgresql://user:password@postgres:5432/openwebui
      depends_on:
        - postgres

    postgres:
      image: postgres:15-alpine
      environment:
        POSTGRES_USER: user
        POSTGRES_PASSWORD: password
        POSTGRES_DB: openwebui

Suggested Filter Installation Order:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
It is recommended to set the priority of this filter relatively high (a smaller number) to ensure it runs before other filters that might modify message content. A typical order might be:

  1. Filters that need access to the full, uncompressed history (priority < 10)
     (e.g., a filter that injects a system-level prompt)
  2. This compression filter (priority = 10)
  3. Filters that run after compression (priority > 10)
     (e.g., a final output formatting filter)

═══════════════════════════════════════════════════════════════════════════════
📝 Database Query Examples
═══════════════════════════════════════════════════════════════════════════════

View all summaries:
  SELECT
    chat_id,
    LEFT(summary, 100) as summary_preview,
    compressed_message_count,
    updated_at
  FROM chat_summary
  ORDER BY updated_at DESC;

Query a specific conversation:
  SELECT *
  FROM chat_summary
  WHERE chat_id = 'your_chat_id';

Delete old summaries:
  DELETE FROM chat_summary
  WHERE updated_at < NOW() - INTERVAL '30 days';

Statistics:
  SELECT
    COUNT(*) as total_summaries,
    AVG(LENGTH(summary)) as avg_summary_length,
    AVG(compressed_message_count) as avg_msg_count
  FROM chat_summary;

═══════════════════════════════════════════════════════════════════════════════
⚠️ Important Notes
═══════════════════════════════════════════════════════════════════════════════

1. Database Permissions
   ⚠ Ensure the user specified in `DATABASE_URL` has permissions to create tables.
   ⚠ The `chat_summary` table will be created automatically on first run.

2. Retention Policy
   ⚠ The `keep_first` setting is crucial for preserving initial messages that contain system prompts. Configure it as needed.

3. Performance
   ⚠ Summary generation is asynchronous and will not block the user response.
   ⚠ There will be a brief background processing time when the threshold is first met.

4. Cost Optimization
   ⚠ The summary model is called once each time the threshold is met.
   ⚠ Set `compression_threshold` reasonably to avoid frequent calls.
   ⚠ It's recommended to use a fast and economical model to generate summaries.

5. Multimodal Support
   ✓ This filter supports multimodal messages containing images.
   ✓ The summary is generated only from the text content.
   ✓ Non-text parts (like images) are preserved in their original messages during compression.

═══════════════════════════════════════════════════════════════════════════════
🐛 Troubleshooting
═══════════════════════════════════════════════════════════════════════════════

Problem: Database connection failed
Solution:
  1. Verify that the `DATABASE_URL` environment variable is set correctly.
  2. Confirm that `DATABASE_URL` starts with either `sqlite` or `postgres`.
  3. Ensure the database service is running and network connectivity is normal.
  4. Validate the username, password, host, and port in the connection URL.
  5. Check the Open WebUI container logs for detailed error messages.

Problem: Summary not generated
Solution:
  1. Check if the `compression_threshold` has been met.
  2. Verify that the `summary_model` is configured correctly.
  3. Check the debug logs for any error messages.

Problem: Initial system prompt is lost
Solution:
  - Ensure `keep_first` is set to a value greater than 0 to preserve the initial messages containing this information.

Problem: Compression effect is not significant
Solution:
  1. Increase the `compression_threshold` appropriately.
  2. Decrease the number of `keep_last` or `keep_first`.
  3. Check if the conversation is actually long enough.


"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
import asyncio
import json
import hashlib
import os

# Open WebUI built-in imports
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users
from fastapi.requests import Request
from open_webui.main import app as webui_app

# Database imports
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class ChatSummary(Base):
    """Chat Summary Storage Table"""

    __tablename__ = "chat_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(255), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    compressed_message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Filter:
    def __init__(self):
        self.valves = self.Valves()
        self._db_engine = None
        self._SessionLocal = None
        self._init_database()

    def _init_database(self):
        """Initializes the database connection and table."""
        try:
            database_url = os.getenv("DATABASE_URL")

            if not database_url:
                print("[Database] ❌ Error: DATABASE_URL environment variable is not set. Please set this variable.")
                self._db_engine = None
                self._SessionLocal = None
                return

            db_type = None
            engine_args = {}

            if database_url.startswith("sqlite"):
                db_type = "SQLite"
                engine_args = {
                    "connect_args": {"check_same_thread": False},
                    "echo": False,
                }
            elif database_url.startswith("postgres"):
                db_type = "PostgreSQL"
                if database_url.startswith("postgres://"):
                    database_url = database_url.replace(
                        "postgres://", "postgresql://", 1
                    )
                    print("[Database] ℹ️ Automatically converted postgres:// to postgresql://")
                engine_args = {
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                    "echo": False,
                }
            else:
                print(
                    f"[Database] ❌ Error: Unsupported database type. DATABASE_URL must start with 'sqlite' or 'postgres'. Current value: {database_url}"
                )
                self._db_engine = None
                self._SessionLocal = None
                return

            # Create database engine
            self._db_engine = create_engine(database_url, **engine_args)

            # Create session factory
            self._SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self._db_engine
            )

            # Create table if it doesn't exist
            Base.metadata.create_all(bind=self._db_engine)

            print(f"[Database] ✅ Successfully connected to {db_type} and initialized the chat_summary table.")

        except Exception as e:
            print(f"[Database] ❌ Initialization failed: {str(e)}")
            self._db_engine = None
            self._SessionLocal = None

    class Valves(BaseModel):
        priority: int = Field(
            default=10, description="Priority level for the filter operations."
        )
        compression_threshold: int = Field(
            default=15, ge=0, description="The number of messages at which to trigger compression."
        )
        keep_first: int = Field(
            default=1, ge=0, description="Always keep the first N messages. Set to 0 to disable."
        )
        keep_last: int = Field(default=6, ge=0, description="Always keep the last N messages.")
        summary_model: str = Field(
            default=None,
            description="The model to use for generating the summary. If empty, uses the current conversation's model.",
        )
        max_summary_tokens: int = Field(
            default=4000, ge=1, description="The maximum number of tokens for the summary."
        )
        summary_temperature: float = Field(
            default=0.3, ge=0.0, le=2.0, description="The temperature for summary generation."
        )
        debug_mode: bool = Field(default=True, description="Enable detailed logging for debugging.")

        @model_validator(mode="after")
        def check_thresholds(self) -> "Valves":
            kept_count = self.keep_first + self.keep_last
            if self.compression_threshold <= kept_count:
                raise ValueError(
                    f"compression_threshold ({self.compression_threshold}) must be greater than "
                    f"the sum of keep_first ({self.keep_first}) and keep_last ({self.keep_last}) ({kept_count})."
                )
            return self

    def _save_summary(self, chat_id: str, summary: str, body: dict):
        """Saves the summary to the database."""
        if not self._SessionLocal:
            if self.valves.debug_mode:
                print("[Storage] Database not initialized, skipping summary save.")
            return

        try:
            session = self._SessionLocal()
            try:
                # Find existing record
                existing = (
                    session.query(ChatSummary).filter_by(chat_id=chat_id).first()
                )

                if existing:
                    # Update existing record
                    existing.summary = summary
                    existing.compressed_message_count = len(body.get("messages", []))
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new record
                    new_summary = ChatSummary(
                        chat_id=chat_id,
                        summary=summary,
                        compressed_message_count=len(body.get("messages", [])),
                    )
                    session.add(new_summary)

                session.commit()

                if self.valves.debug_mode:
                    action = "Updated" if existing else "Created"
                    print(f"[Storage] Summary has been {action.lower()} in the database (Chat ID: {chat_id})")

            finally:
                session.close()

        except Exception as e:
            print(f"[Storage] ❌ Database save failed: {str(e)}")

    def _load_summary(self, chat_id: str, body: dict) -> Optional[str]:
        """Loads the summary from the database."""
        if not self._SessionLocal:
            if self.valves.debug_mode:
                print("[Storage] Database not initialized, cannot load summary.")
            return None

        try:
            session = self._SessionLocal()
            try:
                record = (
                    session.query(ChatSummary).filter_by(chat_id=chat_id).first()
                )

                if record:
                    if self.valves.debug_mode:
                        print(f"[Storage] Loaded summary from database (Chat ID: {chat_id})")
                        print(
                            f"[Storage] Last updated: {record.updated_at}, Original message count: {record.compressed_message_count}"
                        )
                    return record.summary

            finally:
                session.close()

        except Exception as e:
            print(f"[Storage] ❌ Database read failed: {str(e)}")

        return None

    def _inject_summary_to_first_message(self, message: dict, summary: str) -> dict:
        """Injects the summary into the first message by prepending it."""
        content = message.get("content", "")
        summary_block = f"【Historical Conversation Summary】\n{summary}\n\n---\nBelow is the recent conversation:\n\n"

        # Handle different content types
        if isinstance(content, list):  # Multimodal content
            # Find the first text part and insert the summary before it
            new_content = []
            summary_inserted = False

            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "text"
                    and not summary_inserted
                ):
                    # Prepend summary to the first text part
                    new_content.append(
                        {"type": "text", "text": summary_block + part.get("text", "")}
                    )
                    summary_inserted = True
                else:
                    new_content.append(part)

            # If no text part, insert at the beginning
            if not summary_inserted:
                new_content.insert(0, {"type": "text", "text": summary_block})

            message["content"] = new_content

        elif isinstance(content, str):  # Plain text
            message["content"] = summary_block + content

        return message

    async def inlet(
        self, body: dict, __user__: Optional[dict] = None, __metadata__: dict = None
    ) -> dict:
        """
        Executed before sending to the LLM.
        Compression Strategy:
        1. Keep the first N messages.
        2. Inject the summary into the first message (if keep_first > 0).
        3. Keep the last N messages.
        """
        messages = body.get("messages", [])
        chat_id = __metadata__["chat_id"]

        if self.valves.debug_mode:
            print(f"\n{'='*60}")
            print(f"[Inlet] Chat ID: {chat_id}")
            print(f"[Inlet] Received {len(messages)} messages")

        # [Optimization] Load summary in a background thread to avoid blocking the event loop.
        if self.valves.debug_mode:
            print("[Optimization] Loading summary in a background thread to avoid blocking the event loop.")
        saved_summary = await asyncio.to_thread(self._load_summary, chat_id, body)

        total_kept_count = self.valves.keep_first + self.valves.keep_last

        if saved_summary and len(messages) > total_kept_count:
            if self.valves.debug_mode:
                print(f"[Inlet] Found saved summary, applying compression.")

            first_messages_to_keep = []

            if self.valves.keep_first > 0:
                # Copy the initial messages to keep
                first_messages_to_keep = [
                    m.copy() for m in messages[: self.valves.keep_first]
                ]
                # Inject the summary into the very first message
                first_messages_to_keep[0] = self._inject_summary_to_first_message(
                    first_messages_to_keep[0], saved_summary
                )
            else:
                # If not keeping initial messages, create a new system message for the summary
                summary_block = (
                    f"【Historical Conversation Summary】\n{saved_summary}\n\n---\nBelow is the recent conversation:\n\n"
                )
                first_messages_to_keep.append(
                    {"role": "system", "content": summary_block}
                )

            # Keep the last messages
            last_messages_to_keep = (
                messages[-self.valves.keep_last :] if self.valves.keep_last > 0 else []
            )

            # Combine: [Kept initial messages (with summary)] + [Kept recent messages]
            body["messages"] = first_messages_to_keep + last_messages_to_keep

            if self.valves.debug_mode:
                print(f"[Inlet] ✂️ Compression complete:")
                print(f"  - Original messages: {len(messages)}")
                print(f"  - Compressed to: {len(body['messages'])}")
                print(
                    f"  - Structure: [Keep first {self.valves.keep_first} (with summary)] + [Keep last {self.valves.keep_last}]"
                )
                print(f"  - Saved: {len(messages) - len(body['messages'])} messages")
        else:
            if self.valves.debug_mode:
                if not saved_summary:
                    print(f"[Inlet] No summary found, using full conversation history.")
                else:
                    print(f"[Inlet] Message count does not exceed retention threshold, no compression applied.")

        if self.valves.debug_mode:
            print(f"{'='*60}\n")

        return body

    async def outlet(
        self, body: dict, __user__: Optional[dict] = None, __metadata__: dict = None
    ) -> dict:
        """
        Executed after the LLM response is complete.
        Triggers summary generation asynchronously.
        """
        messages = body.get("messages", [])
        chat_id = __metadata__["chat_id"]

        if self.valves.debug_mode:
            print(f"\n{'='*60}")
            print(f"[Outlet] Chat ID: {chat_id}")
            print(f"[Outlet] Response complete, current message count: {len(messages)}")

        # Check if compression is needed
        if len(messages) >= self.valves.compression_threshold:
            if self.valves.debug_mode:
                print(
                    f"[Outlet] ⚡ Compression threshold reached ({len(messages)} >= {self.valves.compression_threshold})"
                )
                print(f"[Outlet] Preparing to generate summary in the background...")

            # Generate summary asynchronously in the background
            asyncio.create_task(
                self._generate_summary_async(messages, chat_id, body, __user__)
            )
        else:
            if self.valves.debug_mode:
                print(
                    f"[Outlet] Compression threshold not reached ({len(messages)} < {self.valves.compression_threshold})"
                )

        if self.valves.debug_mode:
            print(f"{'='*60}\n")

        return body

    async def _generate_summary_async(
        self, messages: list, chat_id: str, body: dict, user_data: Optional[dict]
    ):
        """
        Generates a summary asynchronously in the background.
        """
        try:
            if self.valves.debug_mode:
                print(f"\n[🤖 Async Summary Task] Starting...")

            # Messages to summarize: exclude kept initial and final messages
            if self.valves.keep_last > 0:
                messages_to_summarize = messages[
                    self.valves.keep_first : -self.valves.keep_last
                ]
            else:
                messages_to_summarize = messages[self.valves.keep_first :]

            if len(messages_to_summarize) == 0:
                if self.valves.debug_mode:
                    print(f"[🤖 Async Summary Task] No messages to summarize, skipping.")
                return

            if self.valves.debug_mode:
                print(f"[🤖 Async Summary Task] Preparing to summarize {len(messages_to_summarize)} messages.")
                print(
                    f"[🤖 Async Summary Task] Protecting: First {self.valves.keep_first} + Last {self.valves.keep_last} messages."
                )

            # Build conversation history text
            conversation_text = self._format_messages_for_summary(messages_to_summarize)

            # Call LLM to generate summary
            summary = await self._call_summary_llm(conversation_text, body, user_data)

            # [Optimization] Save summary in a background thread to avoid blocking the event loop.
            if self.valves.debug_mode:
                print("[Optimization] Saving summary in a background thread to avoid blocking the event loop.")
            await asyncio.to_thread(self._save_summary, chat_id, summary, body)

            if self.valves.debug_mode:
                print(f"[🤖 Async Summary Task] ✅ Complete! Summary length: {len(summary)} characters.")
                print(f"[🤖 Async Summary Task] Summary preview: {summary[:150]}...")

        except Exception as e:
            print(f"[🤖 Async Summary Task] ❌ Error: {str(e)}")
            import traceback

            traceback.print_exc()
            # Save a simple placeholder even on failure
            fallback_summary = (
                f"[Historical Conversation Summary] Contains content from approximately {len(messages_to_summarize)} messages."
            )
            
            # [Optimization] Save summary in a background thread to avoid blocking the event loop.
            if self.valves.debug_mode:
                print("[Optimization] Saving summary in a background thread to avoid blocking the event loop.")
            await asyncio.to_thread(self._save_summary, chat_id, fallback_summary, body)

    def _format_messages_for_summary(self, messages: list) -> str:
        """Formats messages for summarization."""
        formatted = []
        for i, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Handle multimodal content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)

            # Handle role name
            role_name = {"user": "User", "assistant": "Assistant"}.get(role, role)

            # Limit length of each message to avoid excessive length
            if len(content) > 500:
                content = content[:500] + "..."

            formatted.append(f"[{i}] {role_name}: {content}")

        return "\n\n".join(formatted)

    async def _call_summary_llm(
        self, conversation_text: str, body: dict, user_data: dict
    ) -> str:
        """
        Calls the LLM to generate a summary using Open WebUI's built-in method.
        """
        if self.valves.debug_mode:
            print(f"[🤖 LLM Call] Using Open WebUI's built-in method.")

        # Build summary prompt
        summary_prompt = f"""
You are a professional conversation context compression assistant. Your task is to perform a high-fidelity compression of the [Conversation Content] below, producing a concise summary that can be used directly as context for subsequent conversation. Strictly adhere to the following requirements:

MUST RETAIN: Topics/goals, user intent, key facts and data, important parameters and constraints, deadlines, decisions/conclusions, action items and their status, and technical details like code/commands (code must be preserved as is).
REMOVE: Greetings, politeness, repetitive statements, off-topic chatter, and procedural details (unless essential). For information that has been overturned or is outdated, please mark it as "Obsolete: <explanation>" when retaining.
CONFLICT RESOLUTION: If there are contradictions or multiple revisions, retain the latest consistent conclusion and list unresolved or conflicting points under "Points to Clarify".
STRUCTURE AND TONE: Output in structured bullet points. Be logical, objective, and concise. Summarize from a third-person perspective. Use code blocks to preserve technical/code snippets verbatim.
OUTPUT LENGTH: Strictly limit the summary content to within {int(self.valves.max_summary_tokens * 3)} characters. Prioritize key information; if space is insufficient, trim details rather than core conclusions.
FORMATTING: Output only the summary text. Do not add any extra explanations, execution logs, or generation processes. You must use the following headings (if a section has no content, write "None"):
Core Theme:
Key Information:
... (List 3-6 key points)
Decisions/Conclusions:
Action Items (with owner/deadline if any):
Relevant Roles/Preferences:
Risks/Dependencies/Assumptions:
Points to Clarify:
Compression Ratio: Original ~X words → Summary ~Y words (estimate)
Conversation Content:
{conversation_text}

Please directly output the compressed summary that meets the above requirements (summary text only).
"""
        # Determine the model to use
        model = self.valves.summary_model or body.get("model", "")

        if self.valves.debug_mode:
            print(f"[🤖 LLM Call] Model: {model}")

        # Build payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": summary_prompt}],
            "stream": False,
            "max_tokens": self.valves.max_summary_tokens,
            "temperature": self.valves.summary_temperature,
        }

        try:
            # Get user object
            user_id = user_data.get("id") if user_data else None
            if not user_id:
                raise ValueError("Could not get user ID")

            # [Optimization] Get user object in a background thread to avoid blocking the event loop.
            if self.valves.debug_mode:
                print("[Optimization] Getting user object in a background thread to avoid blocking the event loop.")
            user = await asyncio.to_thread(Users.get_user_by_id, user_id)

            if not user:
                raise ValueError(f"Could not find user: {user_id}")

            if self.valves.debug_mode:
                print(f"[🤖 LLM Call] User: {user.email}")
                print(f"[🤖 LLM Call] Sending request...")

            # Create Request object
            request = Request(scope={"type": "http", "app": webui_app})

            # Call generate_chat_completion
            response = await generate_chat_completion(request, payload, user)

            if not response or "choices" not in response or not response["choices"]:
                raise ValueError("LLM response is not in the correct format or is empty")

            summary = response["choices"][0]["message"]["content"].strip()

            if self.valves.debug_mode:
                print(f"[🤖 LLM Call] ✅ Successfully received summary.")

            return summary

        except Exception as e:
            error_message = f"An error occurred while calling the LLM ({model}) to generate a summary: {str(e)}"
            if not self.valves.summary_model:
                error_message += (
                    "\n[Hint] You did not specify a summary_model, so the filter attempted to use the current conversation's model. "
                    "If this is a pipeline (Pipe) model or an incompatible model, please specify a compatible summary model (e.g., 'gemini-2.5-flash') in the configuration."
                )

            if self.valves.debug_mode:
                print(f"[🤖 LLM Call] ❌ {error_message}")

            raise Exception(error_message)
