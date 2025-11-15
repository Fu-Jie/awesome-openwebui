"""
title: 异步上下文压缩
id: async_context_compression
author: Fu-Jie
author_url: https://github.com/Fu-Jie
funding_url: https://github.com/Fu-Jie/awesome-openwebui
description: 通过智能摘要和消息压缩，降低长对话的 token 消耗，同时保持对话连贯性。
version: 1.0.0
license: MIT

═══════════════════════════════════════════════════════════════════════════════
📌 功能概述
═══════════════════════════════════════════════════════════════════════════════

本过滤器通过智能摘要和消息压缩技术，显著降低长对话的 token 消耗，同时保持对话连贯性。

核心特性：
  ✅ 自动触发压缩（基于消息数量阈值）
  ✅ 异步生成摘要（不阻塞用户响应）
  ✅ 数据库持久化存储（支持 PostgreSQL 和 SQLite）
  ✅ 灵活的保留策略（可配置保留对话的头部和尾部）
  ✅ 智能注入摘要，保持上下文连贯性

═══════════════════════════════════════════════════════════════════════════════
🔄 工作流程
═══════════════════════════════════════════════════════════════════════════════

阶段 1: inlet（请求前处理）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. 接收当前对话的所有消息。
  2. 检查是否存在已保存的摘要。
  3. 如果有摘要且消息数超过保留阈值：
     ├─ 提取要保留的头部消息（例如，第一条消息）。
     ├─ 将摘要注入到头部消息中。
     ├─ 提取要保留的尾部消息。
     └─ 组合成新的消息列表：[头部消息+摘要] + [尾部消息]。
  4. 发送压缩后的消息到 LLM。

阶段 2: outlet（响应后处理）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. LLM 响应完成后触发。
  2. 检查消息数是否达到压缩阈值。
  3. 如果达到阈值，则在后台异步生成摘要：
     ├─ 提取需要摘要的消息（排除保留的头部和尾部）。
     ├─ 调用 LLM 生成简洁摘要。
     └─ 将摘要保存到数据库。

═══════════════════════════════════════════════════════════════════════════════
💾 存储方案
═══════════════════════════════════════════════════════════════════════════════

本过滤器使用数据库进行持久化存储，通过 `DATABASE_URL` 环境变量进行配置，支持 PostgreSQL 和 SQLite。

配置方式：
  - 必须设置 `DATABASE_URL` 环境变量。
  - PostgreSQL 示例: `postgresql://user:password@host:5432/openwebui`
  - SQLite 示例: `sqlite:///path/to/your/database.db`

过滤器会根据 `DATABASE_URL` 的前缀（`postgres` 或 `sqlite`）自动选择合适的数据库驱动。

  表结构：
    - id: 主键（自增）
    - chat_id: 对话唯一标识（唯一索引）
    - summary: 摘要内容（TEXT）
    - compressed_message_count: 原始消息数
    - created_at: 创建时间
    - updated_at: 更新时间

═══════════════════════════════════════════════════════════════════════════════
📊 压缩效果示例
═══════════════════════════════════════════════════════════════════════════════

场景：20 条消息的对话 (默认设置: 保留前 1 条, 后 6 条)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  压缩前：
    消息 1: [初始设定 + 初始问题]
    消息 2-14: [历史对话内容]
    消息 15-20: [最近对话]
    总计: 20 条完整消息

  压缩后：
    消息 1: [初始设定 + 历史摘要 + 初始问题]
    消息 15-20: [最近 6 条完整消息]
    总计: 7 条消息

  效果：
    ✓ 节省 13 条消息（约 65%）
    ✓ 保留完整上下文信息
    ✓ 保护重要的初始设定

═══════════════════════════════════════════════════════════════════════════════
⚙️ 配置参数说明
═══════════════════════════════════════════════════════════════════════════════

priority (优先级)
  默认: 10
  说明: 过滤器执行顺序，数值越小越先执行。

compression_threshold (压缩阈值)
  默认: 15
  说明: 当消息数达到此值时，将在对话结束后触发后台摘要生成。
  建议: 根据模型上下文窗口和成本调整。

keep_first (保留初始消息数)
  默认: 1
  说明: 始终保留对话开始的 N 条消息。设置为 0 则不保留。第一条消息通常包含重要的提示或环境变量。

keep_last (保留最近消息数)
  默认: 6
  说明: 始终保留对话末尾的 N 条完整消息，以确保上下文的连贯性。

summary_model (摘要模型)
  默认: None
  说明: 用于生成摘要的 LLM 模型。
  建议:
    - 强烈建议配置一个快速且经济的兼容模型，如 `deepseek-v3`、`gemini-2.5-flash`、`gpt-4.1`。
    - 如果留空，过滤器将尝试使用当前对话的模型。
  注意:
    - 如果当前对话使用的是流水线（Pipe）模型或不直接支持标准生成API的模型，留空此项可能会导致摘要生成失败。在这种情况下，必须指定一个有效的模型。

max_summary_tokens (摘要长度)
  默认: 4000
  说明: 生成摘要时允许的最大 token 数。

summary_temperature (摘要温度)
  默认: 0.3
  说明: 控制摘要生成的随机性，较低的值会产生更确定性的输出。

debug_mode (调试模式)
  默认: true
  说明: 在日志中打印详细的调试信息。生产环境建议设为 `false`。

🔧 部署配置
═══════════════════════════════════════════════════════

Docker Compose 示例：
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

过滤器安装顺序建议：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
建议将此过滤器的优先级设置得相对较高（数值较小），以确保它在其他可能修改消息内容的过滤器之前运行。一个典型的顺序可能是：

  1. 需要访问完整、未压缩历史记录的过滤器 (priority < 10)
     (例如: 注入系统级提示的过滤器)
  2. 本压缩过滤器 (priority = 10)
  3. 在压缩后运行的过滤器 (priority > 10)
     (例如: 最终输出格式化过滤器)

═══════════════════════════════════════════════════════════════════════════════
📝 数据库查询示例
═══════════════════════════════════════════════════════════════════════════════

查看所有摘要：
  SELECT
    chat_id,
    LEFT(summary, 100) as summary_preview,
    compressed_message_count,
    updated_at
  FROM chat_summary
  ORDER BY updated_at DESC;

查询特定对话：
  SELECT *
  FROM chat_summary
  WHERE chat_id = 'your_chat_id';

删除过期摘要：
  DELETE FROM chat_summary
  WHERE updated_at < NOW() - INTERVAL '30 days';

统计信息：
  SELECT
    COUNT(*) as total_summaries,
    AVG(LENGTH(summary)) as avg_summary_length,
    AVG(compressed_message_count) as avg_msg_count
  FROM chat_summary;

═══════════════════════════════════════════════════════════════════════════════
⚠️ 注意事项
═══════════════════════════════════════════════════════════════════════════════

1. 数据库权限
   ⚠ 确保 `DATABASE_URL` 指向的用户有创建表的权限。
   ⚠ 首次运行会自动创建 `chat_summary` 表。

2. 保留策略
   ⚠ `keep_first` 配置对于保留包含提示或环境变量的初始消息非常重要。请根据需要进行配置。

3. 性能考虑
   ⚠ 摘要生成是异步的，不会阻塞用户响应。
   ⚠ 首次达到阈值时会有短暂的后台处理时间。

4. 成本优化
   ⚠ 每次达到阈值会调用一次摘要模型。
   ⚠ 合理设置 `compression_threshold` 避免频繁调用。
   ⚠ 建议使用快速且经济的模型（如 `gemini-flash`）生成摘要。

5. 多模态支持
   ✓ 本过滤器支持包含图片的多模态消息。
   ✓ 摘要仅针对文本内容生成。
   ✓ 在压缩过程中，非文本部分（如图片）会被保留在原始消息中。

═══════════════════════════════════════════════════════════════════════════════
🐛 故障排除
═══════════════════════════════════════════════════════════════════════════════

问题：数据库连接失败
解决：
  1. 确认 `DATABASE_URL` 环境变量已正确设置。
  2. 确认 `DATABASE_URL` 以 `sqlite` 或 `postgres` 开头。
  3. 确认数据库服务正在运行，并且网络连接正常。
  4. 验证连接 URL 中的用户名、密码、主机和端口是否正确。
  5. 查看 Open WebUI 的容器日志以获取详细的错误信息。

问题：摘要未生成
解决：
  1. 检查是否达到 `compression_threshold`。
  2. 查看 `summary_model` 是否配置正确。
  3. 检查调试日志中的错误信息。

问题：初始的提示或环境变量丢失
解决：
  - 确保 `keep_first` 设置为大于 0 的值，以保留包含这些信息的初始消息。

问题：压缩效果不明显
解决：
  1. 适当提高 `compression_threshold`。
  2. 减少 `keep_last` 或 `keep_first` 的数量。
  3. 检查对话是否真的很长。


"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
import asyncio
import json
import hashlib
import os

# Open WebUI 内置导入
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users
from fastapi.requests import Request
from open_webui.main import app as webui_app

# 数据库导入
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class ChatSummary(Base):
    """对话摘要存储表"""

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
        """初始化数据库连接和表"""
        try:
            database_url = os.getenv("DATABASE_URL")

            if not database_url:
                print("[数据库] ❌ 错误: DATABASE_URL 环境变量未设置。请设置该变量。")
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
                    print("[数据库] ℹ️ 已自动将 postgres:// 转换为 postgresql://")
                engine_args = {
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                    "echo": False,
                }
            else:
                print(
                    f"[数据库] ❌ 错误: 不支持的数据库类型。DATABASE_URL 必须以 'sqlite' 或 'postgres' 开头。当前值: {database_url}"
                )
                self._db_engine = None
                self._SessionLocal = None
                return

            # 创建数据库引擎
            self._db_engine = create_engine(database_url, **engine_args)

            # 创建会话工厂
            self._SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self._db_engine
            )

            # 创建表（如果不存在）
            Base.metadata.create_all(bind=self._db_engine)

            print(f"[数据库] ✅ 成功连接到 {db_type} 并初始化 chat_summary 表")

        except Exception as e:
            print(f"[数据库] ❌ 初始化失败: {str(e)}")
            self._db_engine = None
            self._SessionLocal = None

    class Valves(BaseModel):
        priority: int = Field(
            default=10, description="Priority level for the filter operations."
        )
        compression_threshold: int = Field(
            default=15, ge=0, description="触发压缩的消息数阈值"
        )
        keep_first: int = Field(
            default=1, ge=0, description="始终保留最初的 N 条消息。设置为 0 则不保留。"
        )
        keep_last: int = Field(default=6, ge=0, description="始终保留最近的 N 条完整消息。")
        summary_model: str = Field(
            default=None,
            description="用于生成摘要的模型（留空则使用当前对话的模型）",
        )
        max_summary_tokens: int = Field(
            default=4000, ge=1, description="摘要的最大 token 数"
        )
        summary_temperature: float = Field(
            default=0.3, ge=0.0, le=2.0, description="摘要生成的温度参数"
        )
        debug_mode: bool = Field(default=True, description="调试模式，打印详细日志")

        @model_validator(mode="after")
        def check_thresholds(self) -> "Valves":
            kept_count = self.keep_first + self.keep_last
            if self.compression_threshold <= kept_count:
                raise ValueError(
                    f"compression_threshold ({self.compression_threshold}) 必须大于 "
                    f"keep_first ({self.keep_first}) 和 keep_last ({self.keep_last}) 的总和 ({kept_count})。"
                )
            return self

    def _save_summary(self, chat_id: str, summary: str, body: dict):
        """保存摘要到数据库"""
        if not self._SessionLocal:
            if self.valves.debug_mode:
                print("[存储] 数据库未初始化，跳过保存摘要")
            return

        try:
            session = self._SessionLocal()
            try:
                # 查找现有记录
                existing = (
                    session.query(ChatSummary).filter_by(chat_id=chat_id).first()
                )

                if existing:
                    # 更新现有记录
                    existing.summary = summary
                    existing.compressed_message_count = len(body.get("messages", []))
                    existing.updated_at = datetime.utcnow()
                else:
                    # 创建新记录
                    new_summary = ChatSummary(
                        chat_id=chat_id,
                        summary=summary,
                        compressed_message_count=len(body.get("messages", [])),
                    )
                    session.add(new_summary)

                session.commit()

                if self.valves.debug_mode:
                    action = "更新" if existing else "创建"
                    print(f"[存储] 摘要已{action}到数据库 (Chat ID: {chat_id})")

            finally:
                session.close()

        except Exception as e:
            print(f"[存储] ❌ 数据库保存失败: {str(e)}")

    def _load_summary(self, chat_id: str, body: dict) -> Optional[str]:
        """从数据库加载摘要"""
        if not self._SessionLocal:
            if self.valves.debug_mode:
                print("[加载] 数据库未初始化，无法加载摘要")
            return None

        try:
            session = self._SessionLocal()
            try:
                record = (
                    session.query(ChatSummary).filter_by(chat_id=chat_id).first()
                )

                if record:
                    if self.valves.debug_mode:
                        print(f"[加载] 从数据库加载摘要 (Chat ID: {chat_id})")
                        print(
                            f"[加载] 更新时间: {record.updated_at}, 原消息数: {record.compressed_message_count}"
                        )
                    return record.summary

            finally:
                session.close()

        except Exception as e:
            print(f"[加载] ❌ 数据库读取失败: {str(e)}")

        return None

    def _inject_summary_to_first_message(self, message: dict, summary: str) -> dict:
        """将摘要注入到第一条消息中（追加到内容前面）"""
        content = message.get("content", "")
        summary_block = f"【历史对话摘要】\n{summary}\n\n---\n以下是最近的对话：\n\n"

        # 处理不同内容类型
        if isinstance(content, list):  # 多模态内容
            # 查找第一个文本部分并在其前面插入摘要
            new_content = []
            summary_inserted = False

            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "text"
                    and not summary_inserted
                ):
                    # 在第一个文本部分前插入摘要
                    new_content.append(
                        {"type": "text", "text": summary_block + part.get("text", "")}
                    )
                    summary_inserted = True
                else:
                    new_content.append(part)

            # 如果没有文本部分，在开头插入
            if not summary_inserted:
                new_content.insert(0, {"type": "text", "text": summary_block})

            message["content"] = new_content

        elif isinstance(content, str):  # 纯文本
            message["content"] = summary_block + content

        return message

    async def inlet(
        self, body: dict, __user__: Optional[dict] = None, __metadata__: dict = None
    ) -> dict:
        """
        在发送到 LLM 之前执行
        压缩策略：
        1. 保留最初的 N 条消息
        2. 将摘要注入到第一条消息前面 (如果 keep_first > 0)
        3. 保留最近的 N 条消息
        """
        messages = body.get("messages", [])
        chat_id = __metadata__["chat_id"]

        if self.valves.debug_mode:
            print(f"\n{'='*60}")
            print(f"[Inlet] Chat ID: {chat_id}")
            print(f"[Inlet] 收到 {len(messages)} 条消息")

        # [优化] 在后台线程中加载摘要，以避免阻塞事件循环
        if self.valves.debug_mode:
            print("[优化] 正在后台线程中加载摘要，以避免阻塞事件循环。")
        saved_summary = await asyncio.to_thread(self._load_summary, chat_id, body)

        total_kept_count = self.valves.keep_first + self.valves.keep_last

        if saved_summary and len(messages) > total_kept_count:
            if self.valves.debug_mode:
                print(f"[Inlet] 找到已保存的摘要，准备应用压缩")

            first_messages_to_keep = []

            if self.valves.keep_first > 0:
                # 复制要保留的初始消息
                first_messages_to_keep = [
                    m.copy() for m in messages[: self.valves.keep_first]
                ]
                # 将摘要注入到第一条消息中
                first_messages_to_keep[0] = self._inject_summary_to_first_message(
                    first_messages_to_keep[0], saved_summary
                )
            else:
                # 如果不保留初始消息，则创建一个新的系统消息来存放摘要
                summary_block = (
                    f"【历史对话摘要】\n{saved_summary}\n\n---\n以下是最近的对话：\n\n"
                )
                first_messages_to_keep.append(
                    {"role": "system", "content": summary_block}
                )

            # 保留最近的消息
            last_messages_to_keep = (
                messages[-self.valves.keep_last :] if self.valves.keep_last > 0 else []
            )

            # 组合：[保留的初始消息（含摘要）] + [保留的最近消息]
            body["messages"] = first_messages_to_keep + last_messages_to_keep

            if self.valves.debug_mode:
                print(f"[Inlet] ✂️ 压缩完成:")
                print(f"  - 原始消息: {len(messages)} 条")
                print(f"  - 压缩后: {len(body['messages'])} 条")
                print(
                    f"  - 结构: [保留前 {self.valves.keep_first} 条(带摘要)] + [保留后 {self.valves.keep_last} 条]"
                )
                print(f"  - 节省: {len(messages) - len(body['messages'])} 条消息")
        else:
            if self.valves.debug_mode:
                if not saved_summary:
                    print(f"[Inlet] 未找到摘要，使用完整对话历史")
                else:
                    print(f"[Inlet] 消息数量未超过保留阈值，不压缩")

        if self.valves.debug_mode:
            print(f"{'='*60}\n")

        return body

    async def outlet(
        self, body: dict, __user__: Optional[dict] = None, __metadata__: dict = None
    ) -> dict:
        """
        在 LLM 响应完成后执行
        异步触发摘要生成（不阻塞当前响应）
        """
        messages = body.get("messages", [])
        chat_id = __metadata__["chat_id"]

        if self.valves.debug_mode:
            print(f"\n{'='*60}")
            print(f"[Outlet] Chat ID: {chat_id}")
            print(f"[Outlet] 响应完成，当前 {len(messages)} 条消息")

        # 检查是否需要压缩
        if len(messages) >= self.valves.compression_threshold:
            if self.valves.debug_mode:
                print(
                    f"[Outlet] ⚡ 触发压缩阈值 ({len(messages)} >= {self.valves.compression_threshold})"
                )
                print(f"[Outlet] 准备在后台生成摘要...")

            # 在后台异步生成摘要（不等待完成）
            asyncio.create_task(
                self._generate_summary_async(messages, chat_id, body, __user__)
            )
        else:
            if self.valves.debug_mode:
                print(
                    f"[Outlet] 未触发压缩阈值 ({len(messages)} < {self.valves.compression_threshold})"
                )

        if self.valves.debug_mode:
            print(f"{'='*60}\n")

        return body

    async def _generate_summary_async(
        self, messages: list, chat_id: str, body: dict, user_data: Optional[dict]
    ):
        """
        异步生成摘要（后台执行，不阻塞响应）
        """
        try:
            if self.valves.debug_mode:
                print(f"\n[🤖 异步摘要任务] 开始...")

            # 需要压缩的消息：排除保留的初始和末尾消息
            if self.valves.keep_last > 0:
                messages_to_summarize = messages[
                    self.valves.keep_first : -self.valves.keep_last
                ]
            else:
                messages_to_summarize = messages[self.valves.keep_first :]

            if len(messages_to_summarize) == 0:
                if self.valves.debug_mode:
                    print(f"[🤖 异步摘要任务] 没有需要摘要的消息，跳过")
                return

            if self.valves.debug_mode:
                print(f"[🤖 异步摘要任务] 准备摘要 {len(messages_to_summarize)} 条消息")
                print(
                    f"[🤖 异步摘要任务] 保护: 前 {self.valves.keep_first} 条 + 后 {self.valves.keep_last} 条"
                )

            # 构建对话历史文本
            conversation_text = self._format_messages_for_summary(messages_to_summarize)

            # 调用 LLM 生成摘要
            summary = await self._call_summary_llm(conversation_text, body, user_data)

            # [优化] 在后台线程中保存摘要，以避免阻塞事件循环
            if self.valves.debug_mode:
                print("[优化] 正在后台线程中保存摘要，以避免阻塞事件循环。")
            await asyncio.to_thread(self._save_summary, chat_id, summary, body)

            if self.valves.debug_mode:
                print(f"[🤖 异步摘要任务] ✅ 完成！摘要长度: {len(summary)} 字符")
                print(f"[🤖 异步摘要任务] 摘要预览: {summary[:150]}...")

        except Exception as e:
            print(f"[🤖 异步摘要任务] ❌ 错误: {str(e)}")
            import traceback

            traceback.print_exc()
            # 即使失败也设置一个简单的占位符
            fallback_summary = (
                f"[历史对话概要] 包含约 {len(messages_to_summarize)} 条消息的内容。"
            )
            # [优化] 在后台线程中保存摘要，以避免阻塞事件循环
            if self.valves.debug_mode:
                print("[优化] 正在后台线程中保存摘要，以避免阻塞事件循环。")
            await asyncio.to_thread(self._save_summary, chat_id, fallback_summary, body)

    def _format_messages_for_summary(self, messages: list) -> str:
        """格式化消息用于摘要"""
        formatted = []
        for i, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 处理多模态内容
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)

            # 处理角色名称
            role_name = {"user": "用户", "assistant": "助手"}.get(role, role)

            # 限制每条消息的长度，避免过长
            if len(content) > 500:
                content = content[:500] + "..."

            formatted.append(f"[{i}] {role_name}: {content}")

        return "\n\n".join(formatted)

    async def _call_summary_llm(
        self, conversation_text: str, body: dict, user_data: dict
    ) -> str:
        """
        使用 Open WebUI 内置方法调用 LLM 生成摘要
        """
        if self.valves.debug_mode:
            print(f"[🤖 LLM 调用] 使用 Open WebUI 内置方法")

        # 构建摘要提示词
        summary_prompt = f"""
你是一个专业的对话上下文压缩助手。你的任务是将下面的【对话内容】进行高保真压缩，输出一段可直接作为后续对话上下文使用的精炼摘要。严格遵守以下要求：

必须保留：主题/目标、用户意图、关键事实与数据、重要参数与限制、时间节点、决策/结论、待办事项与状态、代码/命令等技术细节（代码须保留原样）。
删除：寒暄、客套、重复表述、与任务无关的闲聊、过程性细节（如非必要可省略）。对已被推翻或过时的信息，保留时请标注“已废弃：<说明>”。
冲突处理：若存在矛盾或多次修改，保留最新一致结论，并在“需澄清处”中列出未决或冲突点。
结构与语气：按结构化要点输出，逻辑连贯、用词客观简洁、以第三方视角概括，中文输出。遇到技术/代码片段须用代码块保留原样。
输出长度：摘要内容严格控制在 {int(self.valves.max_summary_tokens * 3)} 字符以内。优先保证关键信息，不足则删减细节而非核心结论。
格式约束：仅输出摘要文本，不要附加任何额外说明、执行日志或生成过程。须使用以下标题（若某项无内容写“无”）：
核心主题：
关键信息：
…（要点列举，3-6 条为宜）
决策/结论：
待跟进项（含负责人/截止时间若有）：
相关角色/偏好：
风险/依赖/假设：
需澄清处：
压缩率：原文约X字 → 摘要约Y字（估算）
对话内容：
{conversation_text}

请直接输出符合上述要求的压缩摘要（仅摘要文本）。
"""
        # 确定使用的模型
        model = self.valves.summary_model or body.get("model", "")

        if self.valves.debug_mode:
            print(f"[🤖 LLM 调用] 模型: {model}")

        # 构建 payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": summary_prompt}],
            "stream": False,
            "max_tokens": self.valves.max_summary_tokens,
            "temperature": self.valves.summary_temperature,
        }

        try:
            # 获取用户对象
            user_id = user_data.get("id") if user_data else None
            if not user_id:
                raise ValueError("无法获取用户 ID")

            # [优化] 在后台线程中获取用户对象，以避免阻塞事件循环
            if self.valves.debug_mode:
                print("[优化] 正在后台线程中获取用户对象，以避免阻塞事件循环。")
            user = await asyncio.to_thread(Users.get_user_by_id, user_id)
            
            if not user:
                raise ValueError(f"无法找到用户: {user_id}")

            if self.valves.debug_mode:
                print(f"[🤖 LLM 调用] 用户: {user.email}")
                print(f"[🤖 LLM 调用] 发送请求...")

            # 创建 Request 对象
            request = Request(scope={"type": "http", "app": webui_app})

            # 调用 generate_chat_completion
            response = await generate_chat_completion(request, payload, user)

            if not response or "choices" not in response or not response["choices"]:
                raise ValueError("LLM 响应格式不正确或为空")

            summary = response["choices"][0]["message"]["content"].strip()

            if self.valves.debug_mode:
                print(f"[🤖 LLM 调用] ✅ 成功获取摘要")

            return summary

        except Exception as e:
            error_message = f"调用 LLM ({model}) 生成摘要时发生错误: {str(e)}"
            if not self.valves.summary_model:
                error_message += (
                    "\n[提示] 您没有指定摘要模型 (summary_model)，因此尝试使用当前对话的模型。"
                    "如果这是一个流水线（Pipe）模型或不兼容的模型，请在配置中指定一个兼容的摘要模型（如 'gemini-2.5-flash'）。"
                )

            if self.valves.debug_mode:
                print(f"[🤖 LLM 调用] ❌ {error_message}")

            raise Exception(error_message)
