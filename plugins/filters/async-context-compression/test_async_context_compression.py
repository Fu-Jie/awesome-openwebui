import asyncio
import importlib.util
import os
import sys
import types
import unittest


PLUGIN_PATH = os.path.join(os.path.dirname(__file__), "async_context_compression.py")
MODULE_NAME = "async_context_compression_under_test"


def _ensure_module(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


def _install_dependency_stubs() -> None:
    pydantic_module = _ensure_module("pydantic")
    sqlalchemy_module = _ensure_module("sqlalchemy")
    sqlalchemy_orm_module = _ensure_module("sqlalchemy.orm")
    sqlalchemy_engine_module = _ensure_module("sqlalchemy.engine")

    class DummyBaseModel:
        def __init__(self, **kwargs):
            annotations = getattr(self.__class__, "__annotations__", {})
            for field_name in annotations:
                if field_name in kwargs:
                    value = kwargs[field_name]
                else:
                    value = getattr(self.__class__, field_name, None)
                setattr(self, field_name, value)

    def dummy_field(default=None, **kwargs):
        return default

    class DummyMetadata:
        def create_all(self, *args, **kwargs):
            return None

    def dummy_declarative_base():
        class DummyBase:
            metadata = DummyMetadata()

        return DummyBase

    def dummy_sessionmaker(*args, **kwargs):
        return lambda: None

    class DummyEngine:
        pass

    def dummy_column(*args, **kwargs):
        return None

    def dummy_type(*args, **kwargs):
        return None

    def dummy_inspect(*args, **kwargs):
        return types.SimpleNamespace(has_table=lambda *a, **k: False)

    pydantic_module.BaseModel = DummyBaseModel
    pydantic_module.Field = dummy_field
    sqlalchemy_module.Column = dummy_column
    sqlalchemy_module.String = dummy_type
    sqlalchemy_module.Text = dummy_type
    sqlalchemy_module.DateTime = dummy_type
    sqlalchemy_module.Integer = dummy_type
    sqlalchemy_module.inspect = dummy_inspect
    sqlalchemy_orm_module.declarative_base = dummy_declarative_base
    sqlalchemy_orm_module.sessionmaker = dummy_sessionmaker
    sqlalchemy_engine_module.Engine = DummyEngine


def _install_openwebui_stubs() -> None:
    _ensure_module("open_webui")
    _ensure_module("open_webui.utils")
    chat_module = _ensure_module("open_webui.utils.chat")
    _ensure_module("open_webui.models")
    users_module = _ensure_module("open_webui.models.users")
    models_module = _ensure_module("open_webui.models.models")
    chats_module = _ensure_module("open_webui.models.chats")
    main_module = _ensure_module("open_webui.main")
    _ensure_module("fastapi")
    fastapi_requests = _ensure_module("fastapi.requests")

    async def generate_chat_completion(*args, **kwargs):
        return {}

    class DummyUsers:
        pass

    class DummyModels:
        @staticmethod
        def get_model_by_id(model_id):
            return None

    class DummyChats:
        @staticmethod
        def get_chat_by_id(chat_id):
            return None

    class DummyRequest:
        def __init__(self, *args, **kwargs):
            pass

    chat_module.generate_chat_completion = generate_chat_completion
    users_module.Users = DummyUsers
    models_module.Models = DummyModels
    chats_module.Chats = DummyChats
    main_module.app = object()
    fastapi_requests.Request = DummyRequest


_install_dependency_stubs()
_install_openwebui_stubs()
spec = importlib.util.spec_from_file_location(MODULE_NAME, PLUGIN_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = module
assert spec.loader is not None
spec.loader.exec_module(module)
module.Filter._init_database = lambda self: None


class TestAsyncContextCompression(unittest.TestCase):
    def setUp(self):
        self.filter = module.Filter()

    def test_inlet_logs_tool_trimming_outcome_when_no_oversized_outputs(self):
        self.filter.valves.show_debug_log = True
        self.filter.valves.enable_tool_output_trimming = True

        logged_messages = []

        async def fake_log(message, log_type="info", event_call=None):
            logged_messages.append(message)

        async def fake_user_context(__user__, __event_call__):
            return {"user_language": "en-US"}

        async def fake_event_call(_payload):
            return True

        self.filter._log = fake_log
        self.filter._get_user_context = fake_user_context
        self.filter._get_chat_context = lambda body, metadata=None: {
            "chat_id": "",
            "message_id": "",
        }
        self.filter._get_latest_summary = lambda chat_id: None

        body = {
            "params": {"function_calling": "native"},
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [{"id": "call_1", "type": "function"}],
                    "content": "",
                },
                {"role": "tool", "content": "short result"},
                {"role": "assistant", "content": "Final answer"},
            ],
        }

        asyncio.run(self.filter.inlet(body, __event_call__=fake_event_call))

        self.assertTrue(
            any("Tool trimming check:" in message for message in logged_messages)
        )
        self.assertTrue(
            any(
                "no oversized native tool outputs were found" in message
                for message in logged_messages
            )
        )

    def test_inlet_logs_tool_trimming_skip_reason_when_disabled(self):
        self.filter.valves.show_debug_log = True
        self.filter.valves.enable_tool_output_trimming = False

        logged_messages = []

        async def fake_log(message, log_type="info", event_call=None):
            logged_messages.append(message)

        async def fake_user_context(__user__, __event_call__):
            return {"user_language": "en-US"}

        async def fake_event_call(_payload):
            return True

        self.filter._log = fake_log
        self.filter._get_user_context = fake_user_context
        self.filter._get_chat_context = lambda body, metadata=None: {
            "chat_id": "",
            "message_id": "",
        }
        self.filter._get_latest_summary = lambda chat_id: None

        body = {"messages": [], "params": {"function_calling": "native"}}

        asyncio.run(self.filter.inlet(body, __event_call__=fake_event_call))

        self.assertTrue(
            any("Tool trimming skipped: tool trimming disabled" in message for message in logged_messages)
        )

    def test_normalize_native_tool_call_ids_keeps_links_aligned(self):
        long_tool_call_id = "call_abcdefghijklmnopqrstuvwxyz_1234567890abcd"
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": long_tool_call_id,
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"},
                    }
                ],
                "content": "",
            },
            {
                "role": "tool",
                "tool_call_id": long_tool_call_id,
                "content": "tool result",
            },
        ]

        normalized_count = self.filter._normalize_native_tool_call_ids(messages)

        normalized_id = messages[0]["tool_calls"][0]["id"]
        self.assertEqual(normalized_count, 1)
        self.assertLessEqual(len(normalized_id), 40)
        self.assertNotEqual(normalized_id, long_tool_call_id)
        self.assertEqual(messages[1]["tool_call_id"], normalized_id)

    def test_trim_native_tool_outputs_restores_real_behavior(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [{"id": "call_1", "type": "function"}],
                "content": "",
            },
            {"role": "tool", "content": "x" * 1600},
            {"role": "assistant", "content": "Final answer"},
        ]

        trimmed_count, trim_debug = self.filter._trim_native_tool_outputs(
            messages, "en-US"
        )

        self.assertEqual(trimmed_count, 1)
        self.assertIsNone(trim_debug)
        self.assertEqual(messages[1]["content"], "... [Content collapsed] ...")
        self.assertTrue(messages[1]["metadata"]["is_trimmed"])
        self.assertTrue(messages[2]["metadata"]["tool_outputs_trimmed"])
        self.assertIn("Final answer", messages[2]["content"])
        self.assertIn("Tool outputs trimmed", messages[2]["content"])

    def test_trim_native_tool_outputs_supports_embedded_tool_call_cards(self):
        messages = [
            {
                "role": "assistant",
                "content": (
                    '<details type="tool_calls" done="true" id="call-1" '
                    'name="execute_code" arguments="&quot;{}&quot;" '
                    f'result="&quot;{"x" * 1600}&quot;">\n'
                    "<summary>Tool Executed</summary>\n"
                    "</details>\n"
                    "Final answer"
                ),
            }
        ]

        trimmed_count, trim_debug = self.filter._trim_native_tool_outputs(
            messages, "en-US"
        )

        self.assertEqual(trimmed_count, 1)
        self.assertIsNone(trim_debug)
        self.assertIn(
            'result="&quot;... [Content collapsed] ...&quot;"',
            messages[0]["content"],
        )
        self.assertNotIn("x" * 200, messages[0]["content"])
        self.assertTrue(messages[0]["metadata"]["tool_outputs_trimmed"])

    def test_function_calling_mode_reads_params_fallback(self):
        self.assertEqual(
            self.filter._get_function_calling_mode(
                {"params": {"function_calling": "native"}}
            ),
            "native",
        )

    def test_function_calling_mode_infers_native_from_message_shape(self):
        self.assertEqual(
            self.filter._get_function_calling_mode(
                {
                    "messages": [
                        {
                            "role": "assistant",
                            "tool_calls": [{"id": "call_1", "type": "function"}],
                            "content": "",
                        },
                        {"role": "tool", "content": "tool result"},
                    ]
                }
            ),
            "native",
        )

    def test_trim_native_tool_outputs_handles_pending_tool_chain(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [{"id": "call_1", "type": "function"}],
                "content": "",
            },
            {"role": "tool", "content": "x" * 1600},
        ]

        trimmed_count, trim_debug = self.filter._trim_native_tool_outputs(
            messages, "en-US"
        )

        self.assertEqual(trimmed_count, 1)
        self.assertIsNone(trim_debug)
        self.assertEqual(messages[1]["content"], "... [Content collapsed] ...")
        self.assertTrue(messages[1]["metadata"]["is_trimmed"])

    def test_target_progress_uses_original_history_coordinates(self):
        self.filter.valves.keep_last = 2
        summary_message = self.filter._build_summary_message(
            "older summary", "en-US", 6
        )
        messages = [
            {"role": "system", "content": "System prompt"},
            summary_message,
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 2"},
        ]

        self.assertEqual(self.filter._get_original_history_count(messages), 10)
        self.assertEqual(self.filter._calculate_target_compressed_count(messages), 8)

    def test_load_full_chat_messages_rebuilds_active_history_branch(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    chat={
                        "history": {
                            "currentId": "m3",
                            "messages": {
                                "m1": {
                                    "id": "m1",
                                    "role": "user",
                                    "content": "Question",
                                },
                                "m2": {
                                    "id": "m2",
                                    "role": "assistant",
                                    "content": "Tool call",
                                    "tool_calls": [{"id": "call_1"}],
                                    "parentId": "m1",
                                },
                                "m3": {
                                    "id": "m3",
                                    "role": "tool",
                                    "content": "Tool result",
                                    "tool_call_id": "call_1",
                                    "parentId": "m2",
                                },
                            },
                        }
                    }
                )

        original_chats = module.Chats
        module.Chats = FakeChats
        try:
            messages = self.filter._load_full_chat_messages("chat-1")
        finally:
            module.Chats = original_chats

        self.assertEqual([message["id"] for message in messages], ["m1", "m2", "m3"])
        self.assertEqual(messages[2]["role"], "tool")

    def test_outlet_unfolds_compact_tool_details_view(self):
        compact_messages = [
            {"role": "user", "content": "U1"},
            {
                "role": "assistant",
                "content": (
                    '<details type="tool_calls" done="true" id="call-1" '
                    'name="search_notes" arguments="&quot;{}&quot;" '
                    f'result="&quot;{"x" * 3000}&quot;">\n'
                    "<summary>Tool Executed</summary>\n"
                    "</details>\n"
                    "Answer 1"
                ),
            },
            {"role": "user", "content": "U2"},
            {
                "role": "assistant",
                "content": (
                    '<details type="tool_calls" done="true" id="call-2" '
                    'name="merge_notes" arguments="&quot;{}&quot;" '
                    f'result="&quot;{"y" * 4000}&quot;">\n'
                    "<summary>Tool Executed</summary>\n"
                    "</details>\n"
                    "Answer 2"
                ),
            },
        ]

        async def fake_user_context(__user__, __event_call__):
            return {"user_language": "en-US"}

        async def noop_log(*args, **kwargs):
            return None

        create_task_called = False

        def fake_create_task(coro):
            nonlocal create_task_called
            create_task_called = True
            coro.close()
            return None

        self.filter._get_user_context = fake_user_context
        self.filter._get_chat_context = lambda body, metadata=None: {
            "chat_id": "chat-1",
            "message_id": "msg-1",
        }
        self.filter._should_skip_compression = lambda body, model: False
        self.filter._log = noop_log

        # Set a low threshold so the task is guaranteed to trigger
        self.filter.valves.compression_threshold_tokens = 100

        original_create_task = asyncio.create_task
        asyncio.create_task = fake_create_task
        try:
            asyncio.run(
                self.filter.outlet(
                    {"model": "test-model", "messages": compact_messages},
                    __event_call__=None,
                )
            )
        finally:
            asyncio.create_task = original_create_task

        self.assertTrue(create_task_called)

    def test_estimate_messages_tokens_counts_output_text_parts(self):
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "abcd" * 25}],
            }
        ]

        self.assertEqual(
            self.filter._estimate_messages_tokens(messages),
            module._estimate_text_tokens("abcd" * 25),
        )

    def test_unfold_messages_keeps_plain_assistant_output_when_expand_is_not_richer(self):
        misc_module = _ensure_module("open_webui.utils.misc")
        misc_module.convert_output_to_messages = lambda output, raw=True: [
            {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Plain reply"}],
            }
        ]

        messages = [
            {
                "id": "assistant-1",
                "role": "assistant",
                "content": "Plain reply",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Plain reply"}],
                    }
                ],
            }
        ]

        unfolded = self.filter._unfold_messages(messages)

        self.assertEqual(len(unfolded), 1)
        self.assertEqual(unfolded[0]["id"], "assistant-1")
        self.assertEqual(unfolded[0]["content"], "Plain reply")
        self.assertNotIn("output", unfolded[0])

    def test_summary_save_progress_matches_final_prompt_shrink(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200

        captured = {}
        events = []

        async def mock_emitter(event):
            events.append(event)

        async def mock_summary_llm(
            new_conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = new_conversation_text
            return "new summary"

        def mock_save_summary(chat_id, summary, compressed_count):
            captured["chat_id"] = chat_id
            captured["summary"] = summary
            captured["compressed_count"] = compressed_count

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = mock_summary_llm
        self.filter._save_summary = mock_save_summary
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 1200
        }
        self.filter._format_messages_for_summary = lambda messages: "\n".join(
            msg["content"] for msg in messages
        )
        self.filter._build_summary_prompt = (
            lambda conversation_text, previous_summary=None: conversation_text
        )
        self.filter._count_tokens = lambda text: len(text)

        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Q" * 100},
            {"role": "assistant", "content": "A" * 100},
            {"role": "user", "content": "B" * 100},
            {"role": "assistant", "content": "C" * 100},
            {"role": "user", "content": "Question 3"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=5,
                lang="en-US",
                __event_emitter__=mock_emitter,
                __event_call__=None,
            )
        )

        self.assertEqual(captured["chat_id"], "chat-1")
        self.assertEqual(captured["summary"], "new summary")
        self.assertEqual(captured["compressed_count"], 3)
        self.assertEqual(captured["conversation_text"], f"{'Q' * 100}\n{'A' * 100}")
        self.assertTrue(any(event["type"] == "status" for event in events))

    def test_generate_summary_async_drops_previous_summary_when_prompt_still_oversized(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200

        captured = {}

        async def mock_summary_llm(
            new_conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = new_conversation_text
            captured["previous_summary"] = previous_summary
            return "new summary"

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = mock_summary_llm
        self.filter._save_summary = lambda *args: None
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 1200
        }
        self.filter._format_messages_for_summary = lambda messages: "\n".join(
            msg["content"] for msg in messages
        )
        self.filter._build_summary_prompt = (
            lambda conversation_text, previous_summary=None: (
                (previous_summary or "") + "\n" + conversation_text
            )
        )
        self.filter._count_tokens = lambda text: len(text)
        self.filter._load_summary = lambda chat_id, body: "P" * 220

        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Q" * 60},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=2,
                lang="en-US",
                __event_emitter__=None,
                __event_call__=None,
            )
        )

        self.assertEqual(captured["conversation_text"], "Q" * 60)
        self.assertIsNone(captured["previous_summary"])

    def test_call_summary_llm_silently_handles_provider_error_dict_by_default(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.show_debug_log = False

        async def fake_generate_chat_completion(request, payload, user):
            return {"error": {"message": "context too long", "code": 400}}

        async def noop_log(*args, **kwargs):
            return None

        frontend_calls = []

        async def fake_event_call(payload):
            frontend_calls.append(payload)
            return True

        original_generate = module.generate_chat_completion
        original_get_user = getattr(module.Users, "get_user_by_id", None)

        module.generate_chat_completion = fake_generate_chat_completion
        module.Users.get_user_by_id = staticmethod(
            lambda user_id: types.SimpleNamespace(email="user@example.com")
        )
        self.filter._log = noop_log
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 8192
        }
        self.filter._build_summary_prompt = (
            lambda conversation_text, previous_summary=None: conversation_text
        )

        try:
            summary = asyncio.run(
                self.filter._call_summary_llm(
                    "conversation",
                    {"model": "fake-summary-model"},
                    {"id": "user-1"},
                    __event_call__=fake_event_call,
                )
            )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        self.assertEqual(summary, "")
        self.assertTrue(frontend_calls)
        self.assertEqual(frontend_calls[0]["type"], "execute")
        self.assertIn("console.error", frontend_calls[0]["data"]["code"])
        self.assertIn("context too long", frontend_calls[0]["data"]["code"])

    def test_call_summary_llm_raises_provider_error_dict_when_fail_mode_is_raise(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.show_debug_log = False
        self.filter.valves.SUMMARY_FAIL_MODE = "raise"

        async def fake_generate_chat_completion(request, payload, user):
            return {"error": {"message": "context too long", "code": 400}}

        async def noop_log(*args, **kwargs):
            return None

        frontend_calls = []

        async def fake_event_call(payload):
            frontend_calls.append(payload)
            return True

        original_generate = module.generate_chat_completion
        original_get_user = getattr(module.Users, "get_user_by_id", None)

        module.generate_chat_completion = fake_generate_chat_completion
        module.Users.get_user_by_id = staticmethod(
            lambda user_id: types.SimpleNamespace(email="user@example.com")
        )
        self.filter._log = noop_log
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 8192
        }
        self.filter._build_summary_prompt = (
            lambda conversation_text, previous_summary=None: conversation_text
        )

        try:
            with self.assertRaises(Exception) as exc_info:
                asyncio.run(
                    self.filter._call_summary_llm(
                        "conversation",
                        {"model": "fake-summary-model"},
                        {"id": "user-1"},
                        __event_call__=fake_event_call,
                    )
                )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        self.assertIn(
            "Upstream provider error: context too long", str(exc_info.exception)
        )
        self.assertNotIn(
            "LLM response format incorrect or empty", str(exc_info.exception)
        )
        self.assertTrue(frontend_calls)
        self.assertEqual(frontend_calls[0]["type"], "execute")
        self.assertIn("console.error", frontend_calls[0]["data"]["code"])
        self.assertIn("context too long", frontend_calls[0]["data"]["code"])

    def test_generate_summary_async_status_guides_user_to_browser_console(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.show_debug_log = False

        events = []
        frontend_calls = []

        async def fake_summary_llm(*args, **kwargs):
            raise Exception("boom details")

        async def fake_emitter(event):
            events.append(event)

        async def fake_event_call(payload):
            frontend_calls.append(payload)
            return True

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = fake_summary_llm
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 1200
        }
        self.filter._format_messages_for_summary = lambda messages: "\n".join(
            msg["content"] for msg in messages
        )
        self.filter._build_summary_prompt = (
            lambda conversation_text, previous_summary=None: conversation_text
        )
        self.filter._count_tokens = lambda text: len(text)

        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Q" * 40},
            {"role": "assistant", "content": "A" * 40},
            {"role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=2,
                lang="en-US",
                __event_emitter__=fake_emitter,
                __event_call__=fake_event_call,
            )
        )

        self.assertTrue(frontend_calls)
        self.assertIn("console.error", frontend_calls[0]["data"]["code"])
        self.assertIn("boom details", frontend_calls[0]["data"]["code"])
        status_descriptions = [
            event["data"]["description"]
            for event in events
            if event.get("type") == "status"
        ]
        self.assertTrue(
            any("Check browser console (F12) for details" in text for text in status_descriptions)
        )

    def test_check_and_generate_summary_async_forces_frontend_and_status_on_pre_summary_error(
        self,
    ):
        self.filter.valves.show_debug_log = False

        events = []
        frontend_calls = []

        async def fake_emitter(event):
            events.append(event)

        async def fake_event_call(payload):
            frontend_calls.append(payload)
            return True

        async def noop_log(*args, **kwargs):
            return None

        def fail_estimate(_messages):
            raise Exception("pre summary boom")

        self.filter._log = noop_log
        self.filter._estimate_messages_tokens = fail_estimate
        self.filter._get_model_thresholds = lambda model_id: {
            "compression_threshold_tokens": 100,
            "max_context_tokens": 1000,
        }

        asyncio.run(
            self.filter._check_and_generate_summary_async(
                chat_id="chat-1",
                model="fake-model",
                body={"messages": [{"role": "user", "content": "Hello"}]},
                user_data={"id": "user-1"},
                target_compressed_count=1,
                lang="en-US",
                __event_emitter__=fake_emitter,
                __event_call__=fake_event_call,
            )
        )

        self.assertTrue(frontend_calls)
        self.assertIn("console.error", frontend_calls[0]["data"]["code"])
        self.assertIn("pre summary boom", frontend_calls[0]["data"]["code"])
        status_descriptions = [
            event["data"]["description"]
            for event in events
            if event.get("type") == "status"
        ]
        self.assertTrue(
            any("Check browser console (F12) for details" in text for text in status_descriptions)
        )

    def test_external_reference_message_detection_matches_injected_marker(self):
        message = {
            "role": "assistant",
            "content": "External refs",
            "metadata": {
                "is_summary": True,
                "is_external_references": True,
                "source": "external_references",
            },
        }

        self.assertTrue(self.filter._is_external_reference_message(message))

    def test_handle_external_chat_references_falls_back_when_summary_llm_errors(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 4096

        async def fake_summary_llm(*args, **kwargs):
            raise Exception("reference summary failed")

        self.filter._call_summary_llm = fake_summary_llm
        self.filter._load_summary_record = lambda chat_id: None
        self.filter._load_full_chat_messages = lambda chat_id: [
            {"role": "user", "content": "Referenced question"},
            {"role": "assistant", "content": "Referenced answer"},
        ]
        self.filter._format_messages_for_summary = (
            lambda messages: "Referenced conversation body"
        )
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 5001
        }
        self.filter._estimate_messages_tokens = lambda messages: 5000

        body = {
            "model": "main-model",
            "messages": [{"role": "user", "content": "Current prompt"}],
            "metadata": {
                "files": [
                    {
                        "type": "chat",
                        "id": "chat-ref-1",
                        "name": "Referenced Chat",
                    }
                ]
            },
        }

        result = asyncio.run(
            self.filter._handle_external_chat_references(
                body,
                user_data={"id": "user-1"},
            )
        )

        self.assertIn("__external_references__", result)
        self.assertIn(
            "Referenced conversation body",
            result["__external_references__"]["content"],
        )

    def test_generate_referenced_summaries_background_uses_model_context_window_fallback(
        self,
    ):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 0
        self.filter.valves.max_summary_tokens = 64

        captured = {}
        truncate_calls = []

        async def fake_summary_llm(
            new_conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = new_conversation_text
            return "cached summary"

        async def noop_log(*args, **kwargs):
            return None

        self.filter._call_summary_llm = fake_summary_llm
        self.filter._log = noop_log
        self.filter._save_summary = lambda *args: None
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 5000
        }
        self.filter._truncate_messages_for_summary = (
            lambda messages, max_tokens: truncate_calls.append(max_tokens) or "truncated"
        )

        conversation_text = "x" * 600

        asyncio.run(
            self.filter._generate_referenced_summaries_background(
                [
                    {
                        "chat_id": "chat-ref-ctx",
                        "title": "Referenced Chat",
                        "conversation_text": conversation_text,
                        "covers_full_history": True,
                        "covered_message_count": 1,
                    }
                ],
                user_data={"id": "user-1"},
            )
        )

        self.assertEqual(captured["conversation_text"], conversation_text)
        self.assertEqual(truncate_calls, [])

    def test_generate_referenced_summaries_background_uses_summary_llm_signature(self):
        self.filter.valves.summary_model = "fake-summary-model"

        captured = {}

        async def fake_summary_llm(
            new_conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = new_conversation_text
            captured["body"] = body
            captured["user_data"] = user_data
            captured["request"] = __request__
            captured["previous_summary"] = previous_summary
            return "cached reference summary"

        def fake_save_summary(chat_id, summary, compressed_count):
            captured["saved"] = (chat_id, summary, compressed_count)

        async def noop_log(*args, **kwargs):
            return None

        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._log = noop_log

        request = object()

        asyncio.run(
            self.filter._generate_referenced_summaries_background(
                [
                    {
                        "chat_id": "chat-ref-1",
                        "title": "Referenced Chat",
                        "conversation_text": "Full referenced conversation",
                        "covers_full_history": True,
                        "covered_message_count": 3,
                    }
                ],
                user_data={"id": "user-1"},
                __request__=request,
            )
        )

        self.assertEqual(captured["conversation_text"], "Full referenced conversation")
        self.assertEqual(captured["body"]["model"], "fake-summary-model")
        self.assertEqual(captured["user_data"], {"id": "user-1"})
        self.assertIs(captured["request"], request)
        self.assertIsNone(captured["previous_summary"])
        self.assertEqual(
            captured["saved"], ("chat-ref-1", "cached reference summary", 3)
        )

    def test_generate_referenced_summaries_background_skips_progress_save_for_truncation(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 100

        saved_calls = []
        captured = {}

        async def fake_summary_llm(
            new_conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = new_conversation_text
            return "ephemeral summary"

        async def noop_log(*args, **kwargs):
            return None

        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = lambda *args: saved_calls.append(args)
        self.filter._log = noop_log
        self.filter._load_full_chat_messages = lambda chat_id: [
            {"role": "user", "content": "msg 1"},
            {"role": "assistant", "content": "msg 2"},
        ]
        self.filter._format_messages_for_summary = lambda messages: "x" * 600
        self.filter._truncate_messages_for_summary = (
            lambda messages, max_tokens: "tail only"
        )

        asyncio.run(
            self.filter._generate_referenced_summaries_background(
                [{"chat_id": "chat-ref-2", "title": "Large Referenced Chat"}],
                user_data={"id": "user-1"},
            )
        )

        self.assertEqual(captured["conversation_text"], "tail only")
        self.assertEqual(saved_calls, [])


if __name__ == "__main__":
    unittest.main()
