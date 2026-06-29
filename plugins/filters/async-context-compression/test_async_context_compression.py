import asyncio
import importlib
import importlib.util
import json
import os
import sys
import types
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone


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

    class DummyMetaData:
        pass

    class DummyTable:
        def __init__(self, *args, **kwargs):
            pass

        def drop(self, *args, **kwargs):
            return None

    class DummyIndex:
        def __init__(self, name, *args, **kwargs):
            self.name = name

        def create(self, *args, **kwargs):
            return None

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
    sqlalchemy_module.Index = DummyIndex
    sqlalchemy_module.MetaData = DummyMetaData
    sqlalchemy_module.Table = DummyTable
    sqlalchemy_module.inspect = dummy_inspect
    sqlalchemy_orm_module.declarative_base = dummy_declarative_base
    sqlalchemy_orm_module.sessionmaker = dummy_sessionmaker
    sqlalchemy_engine_module.Engine = DummyEngine


def _install_openwebui_stubs() -> None:
    _ensure_module("open_webui")
    _ensure_module("open_webui.utils")
    chat_module = _ensure_module("open_webui.utils.chat")
    misc_module = _ensure_module("open_webui.utils.misc")
    _ensure_module("open_webui.models")
    users_module = _ensure_module("open_webui.models.users")
    models_module = _ensure_module("open_webui.models.models")
    chats_module = _ensure_module("open_webui.models.chats")
    main_module = _ensure_module("open_webui.main")
    _ensure_module("fastapi")
    fastapi_requests = _ensure_module("fastapi.requests")

    async def generate_chat_completion(*args, **kwargs):
        return {}

    def convert_output_to_messages(output, raw=False):
        return deepcopy(output) if isinstance(output, list) else []

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
    misc_module.convert_output_to_messages = convert_output_to_messages
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


def _load_module_with_real_sqlalchemy(module_name: str):
    sqlalchemy_module_names = [
        name
        for name in sys.modules
        if name == "sqlalchemy" or name.startswith("sqlalchemy.")
    ]
    saved_modules = {name: sys.modules.get(name) for name in sqlalchemy_module_names}
    for name in sqlalchemy_module_names:
        sys.modules.pop(name, None)

    real_sqlalchemy = importlib.import_module("sqlalchemy")
    real_sqlalchemy_orm = importlib.import_module("sqlalchemy.orm")
    real_sqlalchemy_engine = importlib.import_module("sqlalchemy.engine")

    real_spec = importlib.util.spec_from_file_location(module_name, PLUGIN_PATH)
    real_module = importlib.util.module_from_spec(real_spec)
    sys.modules[module_name] = real_module

    def restore_sqlalchemy_stubs():
        for loaded_name in list(sys.modules):
            if loaded_name == "sqlalchemy" or loaded_name.startswith("sqlalchemy."):
                sys.modules.pop(loaded_name, None)
        for saved_name, saved_module in saved_modules.items():
            if saved_module is not None:
                sys.modules[saved_name] = saved_module

    sys.modules["sqlalchemy"] = real_sqlalchemy
    sys.modules["sqlalchemy.orm"] = real_sqlalchemy_orm
    sys.modules["sqlalchemy.engine"] = real_sqlalchemy_engine
    try:
        assert real_spec.loader is not None
        real_spec.loader.exec_module(real_module)
    except Exception:
        restore_sqlalchemy_stubs()
        raise
    return real_module, real_sqlalchemy, restore_sqlalchemy_stubs


def _messages_with_ids(ids):
    messages = []
    for index, message_id in enumerate(ids):
        numeric_id = "".join(ch for ch in message_id if ch.isdigit())
        role_index = int(numeric_id) if numeric_id else index
        messages.append(
            {
                "id": message_id,
                "role": "user" if role_index % 2 == 0 else "assistant",
                "content": f"message {message_id}",
            }
        )
    return messages


def _snapshot(summary, refs, protected_head_count=0):
    refs_payload = refs
    if protected_head_count > 0:
        refs_payload = {
            "refs": refs,
            "protected_head_count": protected_head_count,
        }
    return types.SimpleNamespace(
        summary=summary,
        compressed_message_count=len(refs),
        covered_message_refs_json=json.dumps(
            refs_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        covered_refs_hash="hash",
        branch_tip_id=refs[-1]["id"] if refs else None,
        updated_at=None,
        created_at=None,
    )


def _live_refs_by_id(filter_instance, messages):
    refs = filter_instance._message_refs_for_prefix(messages, len(messages)) or []
    return {ref["id"]: ref for ref in refs}


class _GeneratedBranchGraph:
    """Deterministic OpenWebUI-like branch tree for compression tests."""

    def __init__(self, filter_instance):
        self.filter = filter_instance
        self.branches = {}
        self.deleted_ids = set()

    def add_branch(self, name, ids, prefix_branch=None, through_id=None):
        if prefix_branch is None:
            messages = _messages_with_ids(ids)
        else:
            prefix = self.branch(prefix_branch)
            try:
                through_index = next(
                    index
                    for index, message in enumerate(prefix)
                    if message.get("id") == through_id
                )
            except StopIteration as exc:
                raise AssertionError(f"Unknown fork point: {through_id}") from exc
            messages = prefix[: through_index + 1] + _messages_with_ids(ids)
        self.branches[name] = [deepcopy(message) for message in messages]
        return self

    def branch(self, name):
        return [deepcopy(message) for message in self.branches[name]]

    def edit_message(self, branch_name, message_id, **updates):
        for message in self.branches[branch_name]:
            if message.get("id") == message_id:
                message.update(updates)
                return self
        raise AssertionError(f"Unknown message for edit: {message_id}")

    def delete_message(self, message_id):
        self.deleted_ids.add(message_id)
        return self

    def summary_row(self, summary, branch_name, covered_count, sequence=0):
        refs = self.filter._message_refs_for_prefix(
            self.branch(branch_name), covered_count
        )
        row = _snapshot(summary, refs)
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(
            seconds=sequence
        )
        row.created_at = timestamp
        row.updated_at = timestamp
        return row

    def live_refs_by_id(self):
        live_messages_by_id = {}
        for messages in self.branches.values():
            for message in messages:
                message_id = message.get("id")
                if message_id in self.deleted_ids:
                    continue
                live_messages_by_id[message_id] = deepcopy(message)
        refs = [
            self.filter._message_ref(message)
            for message in live_messages_by_id.values()
        ]
        return {ref["id"]: ref for ref in refs if ref is not None}


class _FakeBranchSummaryStore:
    def __init__(self, filter_instance, graph):
        self.filter = filter_instance
        self.graph = graph
        self.rows = []
        self.saved_calls = []
        self._sequence = 0

    def add(self, row):
        self.rows.append(row)
        return row

    async def load(self, chat_id, messages, require_full_coverage=False):
        return self.filter._select_applicable_summary_snapshot(
            list(self.rows),
            messages,
            require_full_coverage=require_full_coverage,
            live_message_refs_by_id=self.graph.live_refs_by_id(),
        )

    async def save(
        self,
        chat_id,
        summary,
        compressed_count,
        covered_message_refs=None,
        source_current_id=None,
        protected_head_count=0,
    ):
        self.saved_calls.append(
            {
                "chat_id": chat_id,
                "summary": summary,
                "compressed_count": compressed_count,
                "covered_message_refs": covered_message_refs,
                "source_current_id": source_current_id,
                "protected_head_count": protected_head_count,
            }
        )
        if not covered_message_refs:
            return False
        self._sequence += 1
        row = _snapshot(summary, covered_message_refs, protected_head_count)
        timestamp = datetime(2026, 1, 2, tzinfo=timezone.utc) + timedelta(
            seconds=self._sequence
        )
        row.created_at = timestamp
        row.updated_at = timestamp
        row.compressed_message_count = compressed_count
        row.branch_tip_id = source_current_id
        self.rows.append(row)
        return True


def _run_forced_branch_compression(
    filter_instance,
    graph,
    store,
    branch_name,
    target_compressed_count,
    summary,
):
    captured = {}

    async def noop(*args, **kwargs):
        return None

    async def fake_summary_llm(
        conversation_text,
        body,
        user_data,
        event_call=None,
        request=None,
        previous_summary=None,
    ):
        captured["conversation_text"] = conversation_text
        captured["previous_summary"] = previous_summary
        return summary

    filter_instance.valves.keep_last = 0
    filter_instance.valves.summary_model = "fake-summary-model"
    filter_instance.valves.summary_model_max_context = 10000
    filter_instance.valves.max_summary_tokens = 100
    filter_instance._log = noop
    filter_instance._load_applicable_summary_snapshot = store.load
    filter_instance._save_summary = store.save
    filter_instance._call_summary_llm = fake_summary_llm
    filter_instance._estimate_messages_tokens = lambda messages: 100
    filter_instance._calculate_messages_tokens = lambda messages: 100
    filter_instance._get_model_thresholds = lambda model_id: {
        "compression_threshold_tokens": 100,
        "max_context_tokens": 1000,
    }

    saved_before = len(store.saved_calls)
    asyncio.run(
        filter_instance._check_and_generate_summary_async(
            chat_id="chat-branch",
            model="test-model",
            body={
                "model": "test-model",
                "messages": graph.branch(branch_name),
            },
            user_data={"id": "user-1"},
            target_compressed_count=target_compressed_count,
            lang="en-US",
        )
    )
    if len(store.saved_calls) != saved_before + 1:
        raise AssertionError(
            f"Expected forced compression for {branch_name} to save exactly one "
            f"summary row; saved {len(store.saved_calls) - saved_before}"
        )
    return captured, store.saved_calls[-1]


class TestAsyncContextCompression(unittest.TestCase):
    def setUp(self):
        misc_module = _ensure_module("open_webui.utils.misc")
        misc_module.convert_output_to_messages = (
            lambda output, raw=False: deepcopy(output)
            if isinstance(output, list)
            else []
        )
        self.filter = module.Filter()

    def test_build_summary_prompt_defaults_to_balanced_style(self):
        prompt = self.filter._build_summary_prompt("latest conversation")

        self.assertIn("Active style: `balanced`", prompt)
        self.assertIn(
            "Balance compactness and continuity.",
            prompt,
        )

    def test_build_summary_prompt_supports_aggressive_style(self):
        self.filter.valves.compression_style = "aggressive"

        prompt = self.filter._build_summary_prompt("latest conversation")

        self.assertIn("Active style: `aggressive`", prompt)
        self.assertIn(
            "Prioritize minimum token usage.",
            prompt,
        )
        self.assertIn(
            "Merge similar items aggressively",
            prompt,
        )

    def test_build_summary_prompt_supports_faithful_style(self):
        self.filter.valves.compression_style = "faithful"

        prompt = self.filter._build_summary_prompt("latest conversation")

        self.assertIn("Active style: `faithful`", prompt)
        self.assertIn(
            "Prioritize recall over brevity.",
            prompt,
        )
        self.assertIn(
            "Do not collapse multiple important concrete points into a vague abstraction",
            prompt,
        )

    def test_build_summary_prompt_falls_back_to_balanced_for_unknown_style(self):
        self.filter.valves.compression_style = "verbose"

        prompt = self.filter._build_summary_prompt("latest conversation")

        self.assertIn("Active style: `balanced`", prompt)
        self.assertNotIn("Active style: `verbose`", prompt)

    def test_build_summary_message_marks_summary_state_as_historical(self):
        summary_message = self.filter._build_summary_message(
            "<working_memory><current_goal>old task</current_goal></working_memory>",
            "en-US",
            1,
        )

        self.assertIn(
            "describe historical state at the summarized point only",
            summary_message["content"],
        )
        self.assertIn(
            "must not override later messages",
            summary_message["content"],
        )

    def test_build_summary_message_injects_safety_guard_for_all_locales(self):
        # The main chat summary path now relies on the localized
        # ``summary_prompt_prefix`` (which carries the safety note) instead of
        # an extra English guard. Verify every locale ships a localized safety
        # note in its prefix and that the English guard is no longer injected.
        def _core_sentence(guard_text: str) -> str:
            # Strip the leading "Label: " / "Label：" prefix to get the core
            # localized safety sentence that must also appear in the prefix.
            if "：" in guard_text:
                return guard_text.split("：", 1)[1]
            return guard_text.split(": ", 1)[1] if ": " in guard_text else guard_text

        for lang in module.TRANSLATIONS:
            with self.subTest(lang=lang):
                summary_message = self.filter._build_summary_message(
                    "<working_memory><current_goal>old task</current_goal></working_memory>",
                    lang,
                    1,
                )

                # English guard prefix must not leak into the main path.
                self.assertNotIn(
                    "Summary safety: Any goals, open loops, or tool state",
                    summary_message["content"],
                )
                # The localized core safety sentence (shared between the guard
                # dictionary and the locale prefix) must be present.
                guard_core = _core_sentence(
                    module.SUMMARY_INJECTION_SAFETY_GUARD_LOCALES[lang]
                )
                self.assertIn(guard_core, summary_message["content"])

    def test_build_summary_message_strips_next_reply_guidance_from_injected_context(
        self,
    ):
        stale_summary = """<working_memory>
  <current_goal>构建「以旧换新」市场进入战略框架</current_goal>
  <open_loops>
    <item>旧任务仍未完成</item>
  </open_loops>
  <next_reply_guidance>
    <item>继续输出四项以旧换新任务清单</item>
  </next_reply_guidance>
</working_memory>"""

        summary_message = self.filter._build_summary_message(
            stale_summary,
            "zh-CN",
            3,
        )

        self.assertIn("历史状态", summary_message["content"])
        self.assertIn("构建「以旧换新」市场进入战略框架", summary_message["content"])
        self.assertIn("旧任务仍未完成", summary_message["content"])
        self.assertNotIn("next_reply_guidance", summary_message["content"])
        self.assertNotIn("继续输出四项以旧换新任务清单", summary_message["content"])

    def test_referenced_summary_content_strips_next_reply_guidance(self):
        referenced_summary = """<working_memory>
  <current_goal>old referenced goal</current_goal>
  <next_reply_guidance>
    <item>continue old referenced task</item>
  </next_reply_guidance>
</working_memory>"""

        content = self.filter._build_referenced_summary_content(
            referenced_summary,
            "verified_reference_summary",
        )

        self.assertIn("<verified_reference_summary>", content)
        self.assertIn("Summary safety: Any goals, open loops, or tool state", content)
        self.assertIn("old referenced goal", content)
        self.assertNotIn("next_reply_guidance", content)
        self.assertNotIn("continue old referenced task", content)

    def test_mixed_referenced_summary_content_guards_partial_summary(self):
        ref_messages = [
            {"id": "ref-1", "role": "user", "content": "Referenced question"},
            {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
        ]
        refs = self.filter._message_refs_for_prefix(ref_messages, 1)
        snapshot = _snapshot(
            """<working_memory>
  <current_goal>partial referenced goal</current_goal>
  <next_reply_guidance>
    <item>old partial instruction</item>
  </next_reply_guidance>
</working_memory>""",
            refs,
        )

        content = self.filter._build_mixed_referenced_chat_content(
            snapshot,
            ref_messages,
            1,
        )

        self.assertIn("<verified_earlier_summary>", content)
        self.assertIn("Summary safety: Any goals, open loops, or tool state", content)
        self.assertIn("partial referenced goal", content)
        self.assertIn("Referenced answer", content)
        self.assertNotIn("next_reply_guidance", content)
        self.assertNotIn("old partial instruction", content)

    def test_generated_referenced_summary_content_guards_generated_summary(self):
        content = self.filter._build_generated_referenced_summary_content_from_text(
            """<working_memory>
  <current_goal>generated referenced goal</current_goal>
  <next_reply_guidance>
    <item>old generated instruction</item>
  </next_reply_guidance>
</working_memory>""",
            "Latest referenced tail",
        )

        self.assertIn("<generated_reference_summary>", content)
        self.assertIn("Summary safety: Any goals, open loops, or tool state", content)
        self.assertIn("generated referenced goal", content)
        self.assertIn("Latest referenced tail", content)
        self.assertNotIn("next_reply_guidance", content)
        self.assertNotIn("old generated instruction", content)

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

    def test_message_ref_uses_id_and_payload_fingerprint(self):
        message = {"id": "m1", "role": "user", "content": "hello"}
        original_ref = self.filter._message_ref(message)

        message["content"] = "edited"
        edited_ref = self.filter._message_ref(message)

        self.assertEqual(original_ref["id"], "m1")
        self.assertEqual(edited_ref["id"], "m1")
        self.assertNotEqual(original_ref["fingerprint"], edited_ref["fingerprint"])

    def test_message_refs_for_prefix_allows_marker_overlap_with_kept_head(self):
        raw_messages = _messages_with_ids(["m0", "m1", "m2", "m3", "m4"])
        covered_refs = self.filter._message_refs_for_prefix(raw_messages, 3)
        summary_message = self.filter._build_summary_message(
            "older summary",
            "en-US",
            3,
            covered_refs,
            protected_head_count=1,
        )
        summary_view = [raw_messages[0], summary_message] + raw_messages[3:]

        refs = self.filter._message_refs_for_prefix(summary_view, 5)

        self.assertEqual(
            [ref["id"] for ref in refs],
            ["m0", "m1", "m2", "m3", "m4"],
        )

    def test_message_refs_for_prefix_allows_reinjected_marker_after_raw_prefix(self):
        raw_messages = _messages_with_ids(["m0", "m1", "m2", "m3", "m4", "m5"])
        covered_refs = self.filter._message_refs_for_prefix(raw_messages, 4)
        summary_message = self.filter._build_summary_message(
            "older summary",
            "en-US",
            4,
            covered_refs,
        )
        reinjected_view = raw_messages[:4] + [summary_message] + raw_messages[4:]

        refs = self.filter._message_refs_for_prefix(reinjected_view, 6)

        self.assertEqual(
            [ref["id"] for ref in refs],
            ["m0", "m1", "m2", "m3", "m4", "m5"],
        )

    def test_snapshot_selection_rejects_snapshot_when_protected_head_is_not_kept(self):
        messages = _messages_with_ids(["m0", "m1", "m2"])
        refs = self.filter._message_refs_for_prefix(messages, 2)
        self.filter.valves.keep_first = 0

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("summary needs protected head", refs, protected_head_count=1)],
            messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, messages),
        )

        self.assertIsNone(selected)

    def test_history_graph_refs_fail_closed_for_malformed_live_node(self):
        refs = self.filter._history_graph_refs_by_id(
            {
                "m1": {"role": "user", "content": "Question"},
                "m2": "malformed live node",
            }
        )

        self.assertIsNone(refs)

    def test_snapshot_selection_rejects_snapshot_with_live_sibling_refs(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(
            [
                "m0",
                "m1",
                "m2",
                "m3",
                "m4",
                "m5",
                "m6",
                "m7",
                "new_m8",
                "new_m9",
                "new_m10",
            ]
        )
        old_branch_messages = _messages_with_ids(
            [
                "m0",
                "m1",
                "m2",
                "m3",
                "m4",
                "m5",
                "m6",
                "m7",
                "old_m8",
                "old_m9",
                "old_m10",
            ]
        )
        old_refs = self.filter._message_refs_for_prefix(old_branch_messages, 11)
        live_messages = current_messages + old_branch_messages[8:]

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("old branch summary", old_refs)],
            current_messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, live_messages),
        )

        self.assertIsNone(selected)

    def test_snapshot_selection_rejects_unmatched_refs_without_full_graph(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(["m1", "m2", "m3p", "m4p", "m5p"])
        old_branch_messages = _messages_with_ids(["m1", "m2", "m3", "m4", "m5"])
        old_refs = self.filter._message_refs_for_prefix(old_branch_messages, 5)

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("old branch summary", old_refs)],
            current_messages,
        )

        self.assertIsNone(selected)

    def test_snapshot_selection_uses_matching_common_prefix_snapshot(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(
            [
                "m0",
                "m1",
                "m2",
                "m3",
                "m4",
                "m5",
                "m6",
                "m7",
                "new_m8",
                "new_m9",
                "new_m10",
            ]
        )
        old_branch_messages = _messages_with_ids(
            [
                "m0",
                "m1",
                "m2",
                "m3",
                "m4",
                "m5",
                "m6",
                "m7",
                "old_m8",
                "old_m9",
                "old_m10",
            ]
        )
        old_refs = self.filter._message_refs_for_prefix(old_branch_messages, 11)
        prefix_refs = self.filter._message_refs_for_prefix(current_messages, 8)
        live_messages = current_messages + old_branch_messages[8:]

        selected = self.filter._select_applicable_summary_snapshot(
            [
                _snapshot("old branch summary", old_refs),
                _snapshot("shared prefix summary", prefix_refs),
            ],
            current_messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, live_messages),
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.summary, "shared prefix summary")

    def test_snapshot_selection_requires_full_coverage_for_referenced_chat(self):
        self.filter.valves.keep_last = 1
        messages = _messages_with_ids(["m0", "m1", "m2"])
        partial_refs = self.filter._message_refs_for_prefix(messages, 2)
        full_refs = self.filter._message_refs_for_prefix(messages, 3)
        full_with_deleted_refs = self.filter._message_refs_for_prefix(
            _messages_with_ids(["m0", "deleted_m1", "m1", "m2"]),
            4,
        )
        partial_snapshot = _snapshot("partial referenced chat summary", partial_refs)
        full_snapshot = _snapshot("full referenced chat summary", full_refs)
        full_with_deleted_snapshot = _snapshot(
            "full referenced chat summary with deleted message",
            full_with_deleted_refs,
        )

        current_chat_selected = self.filter._select_applicable_summary_snapshot(
            [full_snapshot],
            messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, messages),
        )
        self.assertIsNone(current_chat_selected)

        referenced_chat_selected = self.filter._select_applicable_summary_snapshot(
            [partial_snapshot, full_with_deleted_snapshot, full_snapshot],
            messages,
            require_full_coverage=True,
            live_message_refs_by_id=_live_refs_by_id(self.filter, messages),
        )

        self.assertIs(referenced_chat_selected, full_snapshot)

        selected_with_deleted_only = self.filter._select_applicable_summary_snapshot(
            [partial_snapshot, full_with_deleted_snapshot],
            messages,
            require_full_coverage=True,
            live_message_refs_by_id=_live_refs_by_id(self.filter, messages),
        )
        self.assertIs(selected_with_deleted_only, full_with_deleted_snapshot)

    def test_inlet_uses_matching_prefix_snapshot_and_keeps_new_branch_tail(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(
            [
                "m0",
                "m1",
                "m2",
                "m3",
                "m4",
                "m5",
                "m6",
                "m7",
                "new_m8",
                "new_m9",
                "new_m10",
            ]
        )
        old_branch_messages = _messages_with_ids(
            [
                "m0",
                "m1",
                "m2",
                "m3",
                "m4",
                "m5",
                "m6",
                "m7",
                "old_m8",
                "old_m9",
                "old_m10",
            ]
        )
        old_refs = self.filter._message_refs_for_prefix(old_branch_messages, 11)
        prefix_refs = self.filter._message_refs_for_prefix(current_messages, 8)
        live_messages = current_messages + old_branch_messages[8:]
        snapshots = [
            _snapshot("old branch summary", old_refs),
            _snapshot("shared prefix summary", prefix_refs),
        ]

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
        ):
            return self.filter._select_applicable_summary_snapshot(
                snapshots,
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, live_messages),
            )

        async def noop(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        body = {
            "chat_id": "chat-1",
            "model": "test-model",
            "messages": current_messages,
        }

        result = asyncio.run(self.filter.inlet(body))
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 4)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("shared prefix summary", final_messages[0]["content"])
        self.assertNotIn("old branch summary", final_messages[0]["content"])
        self.assertEqual(
            [message["id"] for message in final_messages[1:]],
            ["new_m8", "new_m9", "new_m10"],
        )
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7"],
        )

    def test_inlet_uses_only_latest_matching_snapshot_for_current_branch(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids([f"m{i}" for i in range(18)])
        snapshots = [
            _snapshot(
                "summary 1-5",
                self.filter._message_refs_for_prefix(current_messages, 5),
            ),
            _snapshot(
                "summary 1-10",
                self.filter._message_refs_for_prefix(current_messages, 10),
            ),
            _snapshot(
                "summary 1-15",
                self.filter._message_refs_for_prefix(current_messages, 15),
            ),
        ]

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
        ):
            return self.filter._select_applicable_summary_snapshot(
                snapshots,
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, current_messages),
            )

        async def noop(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        body = {
            "chat_id": "chat-1",
            "model": "test-model",
            "messages": current_messages,
        }

        result = asyncio.run(self.filter.inlet(body))
        final_messages = result["messages"]
        summary_messages = [
            message
            for message in final_messages
            if self.filter._is_summary_message(message)
        ]

        self.assertEqual(len(summary_messages), 1)
        self.assertIn("summary 1-15", summary_messages[0]["content"])
        self.assertNotIn("summary 1-10", summary_messages[0]["content"])
        self.assertNotIn("summary 1-5", summary_messages[0]["content"])
        self.assertEqual(
            [message["id"] for message in final_messages[1:]],
            ["m15", "m16", "m17"],
        )
        self.assertEqual(
            [
                ref["id"]
                for ref in summary_messages[0]["metadata"]["covered_message_refs"]
            ],
            [f"m{i}" for i in range(15)],
        )

    def test_generated_branch_graph_models_non_aligned_fork(self):
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("main", [f"m{i}" for i in range(1, 11)])
        graph.add_branch("branch-b", ["b8", "b9"], "main", "m7")

        self.assertEqual(
            [message["id"] for message in graph.branch("branch-b")],
            ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "b8", "b9"],
        )

        row = graph.summary_row("main 1-5", "main", 5)
        self.assertEqual(
            [
                ref["id"]
                for ref in self.filter._parse_message_refs_json(
                    row.covered_message_refs_json
                )
            ],
            ["m1", "m2", "m3", "m4", "m5"],
        )
        self.assertIn("m8", graph.live_refs_by_id())
        self.assertIn("b8", graph.live_refs_by_id())

    def test_generated_inlet_rejects_non_aligned_sibling_summary(self):
        self.filter.valves.keep_last = 0
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("main", [f"m{i}" for i in range(1, 11)])
        graph.add_branch("branch-b", ["b8", "b9"], "main", "m7")
        store = _FakeBranchSummaryStore(self.filter, graph)
        store.add(graph.summary_row("main 1-5", "main", 5, sequence=1))
        store.add(graph.summary_row("main 1-10", "main", 10, sequence=2))

        async def noop(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = store.load
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-branch",
                    "model": "test-model",
                    "messages": graph.branch("branch-b"),
                }
            )
        )
        final_messages = result["messages"]

        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("main 1-5", final_messages[0]["content"])
        self.assertNotIn("main 1-10", final_messages[0]["content"])
        self.assertEqual(
            [message["id"] for message in final_messages[1:]],
            ["m6", "m7", "b8", "b9"],
        )
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m1", "m2", "m3", "m4", "m5"],
        )

    def test_generated_alternating_branches_use_branch_newest_summary(self):
        self.filter.valves.keep_last = 0
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("main", [f"m{i}" for i in range(1, 13)])
        graph.add_branch("branch-b", ["b8", "b9", "b10"], "main", "m7")
        store = _FakeBranchSummaryStore(self.filter, graph)
        store.add(graph.summary_row("main 1-5", "main", 5, sequence=1))
        store.add(graph.summary_row("main 1-10", "main", 10, sequence=2))
        store.add(graph.summary_row("branch-b 1-9", "branch-b", 9, sequence=3))

        async def noop(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = store.load
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        main_result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-branch",
                    "model": "test-model",
                    "messages": graph.branch("main"),
                }
            )
        )
        branch_result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-branch",
                    "model": "test-model",
                    "messages": graph.branch("branch-b"),
                }
            )
        )

        main_summary = main_result["messages"][0]
        branch_summary = branch_result["messages"][0]
        self.assertIn("main 1-10", main_summary["content"])
        self.assertNotIn("branch-b 1-9", main_summary["content"])
        self.assertEqual(
            [message["id"] for message in main_result["messages"][1:]],
            ["m11", "m12"],
        )
        self.assertIn("branch-b 1-9", branch_summary["content"])
        self.assertNotIn("main 1-10", branch_summary["content"])
        self.assertEqual(
            [message["id"] for message in branch_result["messages"][1:]],
            ["b10"],
        )

    def test_generated_derivation_uses_nearest_ancestor_and_live_tail(self):
        self.filter.valves.keep_last = 0
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 10000
        self.filter.valves.max_summary_tokens = 100
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("main", [f"m{i}" for i in range(1, 11)])
        graph.add_branch("branch-b", ["b8", "b9"], "main", "m7")
        store = _FakeBranchSummaryStore(self.filter, graph)
        store.add(graph.summary_row("main 1-5", "main", 5, sequence=1))
        store.add(graph.summary_row("main 1-10", "main", 10, sequence=2))
        captured = {}

        async def noop(*args, **kwargs):
            return None

        async def fake_summary_llm(
            conversation_text,
            body,
            user_data,
            event_call=None,
            request=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = conversation_text
            captured["previous_summary"] = previous_summary
            return "branch-b derived 1-9"

        self.filter._log = noop
        self.filter._load_applicable_summary_snapshot = store.load
        self.filter._save_summary = store.save
        self.filter._call_summary_llm = fake_summary_llm

        asyncio.run(
            self.filter._generate_summary_async(
                messages=graph.branch("branch-b"),
                chat_id="chat-branch",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=9,
            )
        )

        self.assertEqual(captured["previous_summary"], "main 1-5")
        self.assertIn("message m6", captured["conversation_text"])
        self.assertIn("message m7", captured["conversation_text"])
        self.assertIn("message b8", captured["conversation_text"])
        self.assertIn("message b9", captured["conversation_text"])
        self.assertNotIn("message m1", captured["conversation_text"])
        self.assertNotIn("message m8", captured["conversation_text"])
        self.assertEqual(store.saved_calls[-1]["summary"], "branch-b derived 1-9")
        self.assertEqual(store.saved_calls[-1]["compressed_count"], 9)
        self.assertEqual(
            [ref["id"] for ref in store.saved_calls[-1]["covered_message_refs"]],
            ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "b8", "b9"],
        )

        selected_after_save = self.filter._select_applicable_summary_snapshot(
            store.rows,
            graph.branch("branch-b"),
            live_message_refs_by_id=graph.live_refs_by_id(),
        )
        self.assertEqual(selected_after_save.summary, "branch-b derived 1-9")

    def test_generated_forced_compression_tracks_branch_switches_and_deletes(self):
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("main", [f"m{i}" for i in range(1, 13)])
        graph.add_branch("branch-b", ["b8", "b9", "b10"], "main", "m7")
        graph.add_branch("after-delete", ["m1", "m2", "m4", "m5", "d6"])
        store = _FakeBranchSummaryStore(self.filter, graph)

        main_1_5, saved = _run_forced_branch_compression(
            self.filter,
            graph,
            store,
            "main",
            5,
            "main 1-5",
        )
        self.assertIsNone(main_1_5["previous_summary"])
        self.assertEqual(saved["compressed_count"], 5)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["m1", "m2", "m3", "m4", "m5"],
        )

        main_1_10, saved = _run_forced_branch_compression(
            self.filter,
            graph,
            store,
            "main",
            10,
            "main 1-10",
        )
        self.assertEqual(main_1_10["previous_summary"], "main 1-5")
        self.assertIn("message m6", main_1_10["conversation_text"])
        self.assertIn("message m10", main_1_10["conversation_text"])
        self.assertNotIn("[ID: m1]", main_1_10["conversation_text"])
        self.assertEqual(saved["compressed_count"], 10)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            [f"m{i}" for i in range(1, 11)],
        )

        branch_1_9, saved = _run_forced_branch_compression(
            self.filter,
            graph,
            store,
            "branch-b",
            9,
            "branch-b 1-9",
        )
        self.assertEqual(branch_1_9["previous_summary"], "main 1-5")
        self.assertIn("message m6", branch_1_9["conversation_text"])
        self.assertIn("message m7", branch_1_9["conversation_text"])
        self.assertIn("message b8", branch_1_9["conversation_text"])
        self.assertIn("message b9", branch_1_9["conversation_text"])
        self.assertNotIn("message m8", branch_1_9["conversation_text"])
        self.assertEqual(saved["compressed_count"], 9)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "b8", "b9"],
        )

        main_1_12, saved = _run_forced_branch_compression(
            self.filter,
            graph,
            store,
            "main",
            12,
            "main 1-12",
        )
        self.assertEqual(main_1_12["previous_summary"], "main 1-10")
        self.assertIn("message m11", main_1_12["conversation_text"])
        self.assertIn("message m12", main_1_12["conversation_text"])
        self.assertNotIn("message b8", main_1_12["conversation_text"])
        self.assertEqual(saved["compressed_count"], 12)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            [f"m{i}" for i in range(1, 13)],
        )

        branch_1_10, saved = _run_forced_branch_compression(
            self.filter,
            graph,
            store,
            "branch-b",
            10,
            "branch-b 1-10",
        )
        self.assertEqual(branch_1_10["previous_summary"], "branch-b 1-9")
        self.assertIn("message b10", branch_1_10["conversation_text"])
        self.assertNotIn("message m11", branch_1_10["conversation_text"])
        self.assertEqual(saved["compressed_count"], 10)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "b8", "b9", "b10"],
        )

        graph.delete_message("m3")
        deleted_branch, saved = _run_forced_branch_compression(
            self.filter,
            graph,
            store,
            "after-delete",
            5,
            "after-delete 1-5",
        )
        self.assertEqual(deleted_branch["previous_summary"], "main 1-5")
        self.assertIn("message d6", deleted_branch["conversation_text"])
        self.assertNotIn("message m6", deleted_branch["conversation_text"])
        self.assertEqual(saved["compressed_count"], 5)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["m1", "m2", "m4", "m5", "d6"],
        )
        self.assertEqual(len(store.saved_calls), 6)

    def test_generated_deleted_ref_is_allowed_but_live_sibling_is_rejected(self):
        self.filter.valves.keep_last = 0
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("original", ["m1", "m2", "m3", "m4", "m5"])
        graph.add_branch("after-delete", ["m1", "m2", "m4", "m5"])
        row = graph.summary_row("summary with m3", "original", 5)

        deleted_selected = self.filter._select_applicable_summary_snapshot(
            [row],
            graph.branch("after-delete"),
            live_message_refs_by_id=graph.delete_message("m3").live_refs_by_id(),
        )
        self.assertIsNotNone(deleted_selected)

        live_sibling_graph = _GeneratedBranchGraph(self.filter)
        live_sibling_graph.add_branch("original", ["m1", "m2", "m3", "m4", "m5"])
        live_sibling_graph.add_branch("sibling", ["m1", "m2", "m4", "m5"])
        live_sibling_row = live_sibling_graph.summary_row(
            "summary with live sibling m3", "original", 5
        )
        live_sibling_selected = self.filter._select_applicable_summary_snapshot(
            [live_sibling_row],
            live_sibling_graph.branch("sibling"),
            live_message_refs_by_id=live_sibling_graph.live_refs_by_id(),
        )
        self.assertIsNone(live_sibling_selected)

    def test_generated_same_id_payload_edit_rejects_stale_summary(self):
        self.filter.valves.keep_last = 0
        graph = _GeneratedBranchGraph(self.filter)
        graph.add_branch("original", ["m1", "m2", "m3", "m4"])
        graph.add_branch("edited", ["m1", "m2", "m3", "m4"])
        graph.edit_message("edited", "m2", content="edited payload")
        stale_row = graph.summary_row("stale original summary", "original", 4)

        selected = self.filter._select_applicable_summary_snapshot(
            [stale_row],
            graph.branch("edited"),
            live_message_refs_by_id=graph.live_refs_by_id(),
        )

        self.assertIsNone(selected)

    def test_inlet_allows_deleted_refs_in_snapshot_and_keeps_new_tail(self):
        self.filter.valves.keep_last = 0
        snapshot_messages = _messages_with_ids(["m0", "m1", "deleted_m2", "m3", "m4"])
        current_messages = _messages_with_ids(["m0", "m1", "m3", "m4", "new_m5"])
        snapshot_refs = self.filter._message_refs_for_prefix(snapshot_messages, 5)
        snapshots = [_snapshot("summary with deleted message", snapshot_refs)]

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
        ):
            return self.filter._select_applicable_summary_snapshot(
                snapshots,
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(
                    self.filter, current_messages
                ),
            )

        async def noop(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        body = {
            "chat_id": "chat-1",
            "model": "test-model",
            "messages": current_messages,
        }

        result = asyncio.run(self.filter.inlet(body))
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 2)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("summary with deleted message", final_messages[0]["content"])
        self.assertEqual(final_messages[1]["id"], "new_m5")
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1", "m3", "m4"],
        )

    def test_inlet_reuses_prefix_snapshot_when_later_tool_tail_lacks_ids(self):
        self.filter.valves.keep_last = 0
        stable_prefix = _messages_with_ids(["m0", "m1", "m2", "m3"])
        current_messages = stable_prefix + [
            {
                "role": "assistant",
                "content": "calling tool",
                "tool_calls": [{"id": "call_1", "type": "function"}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "tool result"},
            {"role": "user", "content": "new question"},
        ]
        prefix_refs = self.filter._message_refs_for_prefix(stable_prefix, 4)
        snapshots = [_snapshot("summary before idless tool tail", prefix_refs)]

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
        ):
            return self.filter._select_applicable_summary_snapshot(
                snapshots,
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, stable_prefix),
            )

        async def noop(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        body = {
            "chat_id": "chat-1",
            "model": "test-model",
            "messages": current_messages,
        }

        result = asyncio.run(self.filter.inlet(body))
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 4)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("summary before idless tool tail", final_messages[0]["content"])
        self.assertEqual(final_messages[1]["content"], "calling tool")
        self.assertEqual(final_messages[2]["role"], "tool")
        self.assertEqual(final_messages[3]["content"], "new question")
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1", "m2", "m3"],
        )

    def test_snapshot_selection_rejects_snapshot_reaching_idless_tool_tail(self):
        self.filter.valves.keep_last = 0
        stable_prefix = _messages_with_ids(["m0", "m1", "m2", "m3"])
        current_messages = stable_prefix + [
            {
                "role": "assistant",
                "content": "calling tool",
                "tool_calls": [{"id": "call_1", "type": "function"}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "tool result"},
        ]
        unsafe_refs = self.filter._message_refs_for_prefix(
            stable_prefix
            + [
                {
                    "id": "tool-call",
                    "role": "assistant",
                    "content": "calling tool",
                    "tool_calls": [{"id": "call_1", "type": "function"}],
                }
            ],
            5,
        )

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("unsafe tool summary", unsafe_refs)],
            current_messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, stable_prefix),
        )

        self.assertIsNone(selected)

    def test_inlet_reuses_db_branch_snapshot_when_body_has_no_message_ids(self):
        self.filter.valves.keep_last = 0
        db_messages = _messages_with_ids([f"m{i}" for i in range(7)])
        body_messages = [
            {
                key: deepcopy(value)
                for key, value in message.items()
                if key != "id"
            }
            for message in db_messages
        ]
        snapshots = [
            _snapshot(
                "db-backed summary",
                self.filter._message_refs_for_prefix(db_messages, 4),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 4)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("db-backed summary", final_messages[0]["content"])
        self.assertEqual(
            [message["content"] for message in final_messages[1:]],
            ["message m4", "message m5", "message m6"],
        )
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1", "m2", "m3"],
        )

    def test_inlet_reuses_db_snapshot_when_current_tip_is_assistant_placeholder(self):
        self.filter.valves.keep_last = 0
        db_messages = _messages_with_ids([f"m{i}" for i in range(6)])
        self.assertEqual(db_messages[-2]["role"], "user")
        self.assertEqual(db_messages[-1]["role"], "assistant")
        body_messages = [
            {
                key: deepcopy(value)
                for key, value in message.items()
                if key != "id"
            }
            for message in db_messages[:-1]
        ]
        snapshots = [
            _snapshot(
                "user-tip db summary",
                self.filter._message_refs_for_prefix(db_messages, 4),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 2)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("user-tip db summary", final_messages[0]["content"])
        self.assertEqual(final_messages[1]["content"], "message m4")
        self.assertNotIn("message m5", [message["content"] for message in final_messages])
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1", "m2", "m3"],
        )

    def test_snapshot_selection_debug_handles_idless_tail_with_multiple_snapshots(self):
        self.filter.valves.keep_last = 0
        self.filter.valves.debug_mode = True
        messages = _messages_with_ids([f"m{i}" for i in range(5)]) + [
            {"role": "assistant", "content": "idless visible tail"}
        ]
        larger_snapshot = _snapshot(
            "larger summary",
            self.filter._message_refs_for_prefix(messages, 4),
        )
        smaller_snapshot = _snapshot(
            "smaller summary",
            self.filter._message_refs_for_prefix(messages, 3),
        )

        selected = self.filter._select_applicable_summary_snapshot(
            [larger_snapshot, smaller_snapshot],
            messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, messages[:5]),
        )

        self.assertIs(selected, larger_snapshot)

    def test_db_branch_snapshot_fallback_rejects_mismatched_idless_body(self):
        self.filter.valves.keep_last = 0
        db_messages = _messages_with_ids([f"m{i}" for i in range(5)])
        body_messages = [
            {
                key: deepcopy(value)
                for key, value in message.items()
                if key != "id"
            }
            for message in db_messages
        ]
        body_messages[2]["content"] = "edited body payload"
        snapshots = [
            _snapshot(
                "unsafe db summary",
                self.filter._message_refs_for_prefix(db_messages, 3),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )

        self.assertFalse(
            any(
                self.filter._is_summary_message(message)
                for message in result["messages"]
            )
        )
        self.assertEqual(result["messages"], body_messages)

    def test_inlet_reuses_same_length_idless_body_that_omits_db_output(self):
        self.filter.valves.keep_last = 0
        db_messages = [
            {"id": "m0", "role": "user", "content": "message m0"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "visible answer",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"},
                    }
                ],
                "output": [{"role": "assistant", "content": "hidden folded output"}],
            },
            {"id": "m2", "role": "user", "content": "message m2"},
        ]
        body_messages = [
            {"role": "user", "content": "message m0"},
            {
                "role": "assistant",
                "content": "visible answer",
                "tool_calls": deepcopy(db_messages[1]["tool_calls"]),
            },
            {"role": "user", "content": "message m2"},
        ]
        snapshots = [
            _snapshot(
                "same length output omitted summary",
                self.filter._message_refs_for_prefix(db_messages, 2),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )
        final_messages = result["messages"]

        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("same length output omitted summary", final_messages[0]["content"])
        self.assertEqual(final_messages[1]["content"], "message m2")

        mismatched_body = deepcopy(body_messages)
        mismatched_body[1]["tool_calls"][0]["function"]["name"] = "other"
        self.assertIsNone(
            self.filter._body_to_db_coverage_map_for_ref_fallback(
                mismatched_body,
                db_messages,
            )
        )

    def test_inlet_applies_summary_for_reasoning_model_via_position_fallback(self):
        """Issue #98: reasoning models rebuild assistant content from output,
        so body content (no reasoning) ≠ DB content (folded reasoning).  The
        position-based fallback must accept the snapshot so the summary is
        actually injected on the inlet."""
        self.filter.valves.keep_last = 0
        db_messages = [
            {"id": "m0", "role": "user", "content": "message m0"},
            {
                "id": "m1",
                "role": "assistant",
                "content": '<details type="reasoning">hidden reasoning chain</details>\nvisible answer',
                "output": [
                    {"type": "reasoning", "summary": [{"type": "output_text", "text": "hidden reasoning chain"}]},
                    {"type": "message", "content": [{"type": "output_text", "text": "visible answer"}]},
                ],
            },
            {"id": "m2", "role": "user", "content": "message m2"},
        ]
        # Body content is what process_messages_with_output produces:
        # reasoning stripped (reasoning_format=None), only "visible answer".
        body_messages = [
            {"role": "user", "content": "message m0"},
            {"role": "assistant", "content": "visible answer"},
            {"role": "user", "content": "message m2"},
        ]
        snapshots = [
            _snapshot(
                "reasoning model summary",
                self.filter._message_refs_for_prefix(db_messages, 2),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )
        final_messages = result["messages"]

        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("reasoning model summary", final_messages[0]["content"])
        self.assertEqual(final_messages[1]["content"], "message m2")

    def test_position_fallback_rejects_edited_content_when_db_has_no_output(self):
        """Position fallback must still reject when DB has no output array
        and the body content was edited (not rebuilt by OWUI)."""
        self.filter.valves.keep_last = 0
        db_messages = _messages_with_ids([f"m{i}" for i in range(3)])
        body_messages = [
            {"role": "user", "content": "message m0"},
            {"role": "assistant", "content": "EDITED, not the original"},
            {"role": "user", "content": "message m2"},
        ]

        result = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages,
            db_messages,
        )
        self.assertIsNone(result)

    def test_position_fallback_accepts_reasoning_content_mismatch(self):
        """Position fallback accepts content differences ONLY for DB messages
        that carry an output array (i.e. content was rebuilt by OWUI)."""
        db_messages = [
            {"id": "m0", "role": "user", "content": "message m0"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "<details type=\"reasoning\">reasoning</details>\nanswer",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "answer"}]}],
            },
            {"id": "m2", "role": "user", "content": "message m2"},
        ]
        body_messages = [
            {"role": "user", "content": "message m0"},
            {"role": "assistant", "content": "answer"},  # rebuilt, reasoning stripped
            {"role": "user", "content": "message m2"},
        ]

        result = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages,
            db_messages,
        )
        self.assertEqual(result, [0, 1, 2, 3])

    def test_unfold_db_branch_fallback_rejects_conversion_errors(self):
        misc_module = _ensure_module("open_webui.utils.misc")

        def convert_output_to_messages(output, raw=False):
            raise RuntimeError("bad folded output")

        misc_module.convert_output_to_messages = convert_output_to_messages

        db_messages = [
            {"id": "m0", "role": "user", "content": "message m0"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "folded",
                "output": [{"type": "message", "content": []}],
            },
        ]
        body_messages = [
            {"role": "user", "content": "message m0"},
            {"role": "assistant", "content": "converted output"},
        ]

        self.assertIsNone(
            self.filter._body_to_db_coverage_map_for_ref_fallback(
                body_messages,
                db_messages,
            )
        )

    def test_inlet_maps_folded_db_snapshot_to_unfolded_tool_body_tail(self):
        self.filter.valves.keep_last = 0
        folded_tool_message = {
            "id": "m1",
            "role": "assistant",
            "content": '<details type="tool_calls">folded result</details>',
            "output": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_1",
                    "content": "large tool result",
                },
                {"role": "assistant", "content": "tool follow-up"},
            ],
        }
        db_messages = [
            {"id": "m0", "role": "user", "content": "message m0"},
            folded_tool_message,
            {"id": "m2", "role": "user", "content": "message m2"},
            {"id": "m3", "role": "assistant", "content": "message m3"},
        ]
        body_messages = [
            {"role": "user", "content": "message m0"},
            deepcopy(folded_tool_message["output"][0]),
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "[content collapsed]",
                "metadata": {
                    "is_trimmed": True,
                    "trimmed_by": "async_context_compression",
                },
            },
            deepcopy(folded_tool_message["output"][2]),
            {"role": "user", "content": "message m2"},
            {"role": "assistant", "content": "message m3"},
        ]
        snapshots = [
            _snapshot(
                "folded tool summary",
                self.filter._message_refs_for_prefix(db_messages, 2),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 3)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("folded tool summary", final_messages[0]["content"])
        self.assertEqual(
            final_messages[0]["metadata"]["covered_until"],
            4,
        )
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1"],
        )
        self.assertEqual(
            [message["content"] for message in final_messages[1:]],
            ["message m2", "message m3"],
        )

    def test_unfolded_db_message_allows_trimmed_assistant_only_with_metadata(self):
        unfolded_db_message = {
            "role": "assistant",
            "content": "full assistant answer with embedded tool details",
        }
        trimmed_body_message = {
            "role": "assistant",
            "content": "collapsed assistant answer",
            "metadata": {"tool_outputs_trimmed": True},
        }
        unmarked_body_message = {
            "role": "assistant",
            "content": "collapsed assistant answer",
        }

        self.assertTrue(
            self.filter._body_message_matches_unfolded_db_message(
                trimmed_body_message,
                unfolded_db_message,
            )
        )
        self.assertFalse(
            self.filter._body_message_matches_unfolded_db_message(
                unmarked_body_message,
                unfolded_db_message,
            )
        )

    def test_inlet_maps_reasoning_output_body_to_folded_db_snapshot(self):
        self.filter.valves.keep_last = 0
        misc_module = _ensure_module("open_webui.utils.misc")

        def convert_output_to_messages(output, raw=False):
            messages = []
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                text = "".join(
                    part.get("text", "")
                    for part in item.get("content", [])
                    if isinstance(part, dict) and part.get("type") == "output_text"
                )
                if text:
                    messages.append({"role": "assistant", "content": text})
            return messages

        misc_module.convert_output_to_messages = convert_output_to_messages

        folded_reasoning_message = {
            "id": "m1",
            "role": "assistant",
            "content": (
                '<details type="reasoning">hidden chain</details>\n'
                "visible answer"
            ),
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "output_text", "text": "hidden chain"}],
                },
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "visible answer"}
                    ],
                },
            ],
        }
        db_messages = [
            {"id": "m0", "role": "user", "content": "message m0"},
            folded_reasoning_message,
            {"id": "m2", "role": "user", "content": "message m2"},
            {"id": "m3", "role": "assistant", "content": "message m3"},
        ]
        body_messages = [
            {"role": "user", "content": "message m0"},
            {"role": "assistant", "content": "visible answer"},
            {"role": "user", "content": "message m2"},
            {"role": "assistant", "content": "message m3"},
        ]
        snapshots = [
            _snapshot(
                "folded reasoning summary",
                self.filter._message_refs_for_prefix(db_messages, 2),
            )
        ]

        async def fake_load_snapshots(chat_id):
            return snapshots

        async def fake_load_live_refs(chat_id):
            return _live_refs_by_id(self.filter, db_messages)

        async def fake_load_full_chat_messages(chat_id):
            return db_messages

        async def noop(*args, **kwargs):
            return None

        self.filter._load_summary_snapshots = fake_load_snapshots
        self.filter._load_chat_history_live_refs = fake_load_live_refs
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._log = noop
        self.filter._emit_debug_log = noop
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 0
        }

        result = asyncio.run(
            self.filter.inlet(
                {
                    "chat_id": "chat-1",
                    "model": "test-model",
                    "messages": body_messages,
                }
            )
        )
        final_messages = result["messages"]

        self.assertEqual(len(final_messages), 3)
        self.assertTrue(self.filter._is_summary_message(final_messages[0]))
        self.assertIn("folded reasoning summary", final_messages[0]["content"])
        self.assertEqual(
            final_messages[0]["metadata"]["covered_until"],
            2,
        )
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[0]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1"],
        )
        self.assertEqual(
            [message["content"] for message in final_messages[1:]],
            ["message m2", "message m3"],
        )

    def test_outlet_does_not_reinject_live_sibling_snapshot(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(["m0", "m1", "new_m2", "new_m3"])
        old_branch_messages = _messages_with_ids(["m0", "m1", "old_m2", "old_m3"])
        old_refs = self.filter._message_refs_for_prefix(old_branch_messages, 4)
        snapshots = [_snapshot("old branch summary", old_refs)]
        live_messages = current_messages + old_branch_messages[2:]
        captured = {}
        scheduled = []

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
        ):
            return self.filter._select_applicable_summary_snapshot(
                snapshots,
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, live_messages),
            )

        async def fake_user_context(__user__, __event_call__):
            return {"user_language": "en-US"}

        async def fake_locked_summary_task(
            lock,
            chat_id,
            model,
            body,
            user_data,
            target_compressed_count,
            lang,
            __event_emitter__,
            __event_call__,
            __request__=None,
        ):
            captured["messages"] = body["messages"]

        async def noop(*args, **kwargs):
            return None

        def fake_create_task(coro):
            scheduled.append(coro)
            return None

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._get_user_context = fake_user_context
        self.filter._get_chat_context = lambda body, metadata=None: {
            "chat_id": "chat-1",
            "message_id": "msg-1",
        }
        self.filter._should_skip_compression = lambda body, model: False
        self.filter._locked_summary_task = fake_locked_summary_task
        self.filter._log = noop

        original_create_task = asyncio.create_task
        asyncio.create_task = fake_create_task
        try:
            asyncio.run(
                self.filter.outlet(
                    {"model": "test-model", "messages": current_messages},
                    __event_call__=None,
                )
            )
        finally:
            asyncio.create_task = original_create_task

        self.assertEqual(len(scheduled), 1)
        asyncio.run(scheduled[0])

        self.assertFalse(
            any(self.filter._is_summary_message(message) for message in captured["messages"])
        )
        self.assertEqual(
            [message["id"] for message in captured["messages"]],
            ["m0", "m1", "new_m2", "new_m3"],
        )

    def test_outlet_reinjects_matching_branch_snapshot_with_metadata(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(["m0", "m1", "m2", "m3", "m4"])
        prefix_refs = self.filter._message_refs_for_prefix(current_messages, 3)
        snapshots = [_snapshot("shared prefix summary", prefix_refs)]
        captured = {}
        scheduled = []

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
        ):
            return self.filter._select_applicable_summary_snapshot(
                snapshots,
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, current_messages),
            )

        async def fake_user_context(__user__, __event_call__):
            return {"user_language": "en-US"}

        async def fake_locked_summary_task(
            lock,
            chat_id,
            model,
            body,
            user_data,
            target_compressed_count,
            lang,
            __event_emitter__,
            __event_call__,
            __request__=None,
        ):
            captured["messages"] = body["messages"]

        async def noop(*args, **kwargs):
            return None

        def fake_create_task(coro):
            scheduled.append(coro)
            return None

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._get_user_context = fake_user_context
        self.filter._get_chat_context = lambda body, metadata=None: {
            "chat_id": "chat-1",
            "message_id": "msg-1",
        }
        self.filter._should_skip_compression = lambda body, model: False
        self.filter._locked_summary_task = fake_locked_summary_task
        self.filter._log = noop

        original_create_task = asyncio.create_task
        asyncio.create_task = fake_create_task
        try:
            asyncio.run(
                self.filter.outlet(
                    {"model": "test-model", "messages": current_messages},
                    __event_call__=None,
                )
            )
        finally:
            asyncio.create_task = original_create_task

        self.assertEqual(len(scheduled), 1)
        asyncio.run(scheduled[0])
        final_messages = captured["messages"]

        self.assertEqual(len(final_messages), 6)
        self.assertTrue(self.filter._is_summary_message(final_messages[3]))
        self.assertEqual(
            [
                ref["id"]
                for ref in final_messages[3]["metadata"]["covered_message_refs"]
            ],
            ["m0", "m1", "m2"],
        )
        self.assertEqual(final_messages[4]["id"], "m3")
        self.assertEqual(final_messages[5]["id"], "m4")

    def test_snapshot_selection_rejects_same_content_different_ids(self):
        self.filter.valves.keep_last = 0
        current_messages = [
            {"id": "new-1", "role": "user", "content": "same"},
            {"id": "new-2", "role": "assistant", "content": "same"},
        ]
        old_messages = [
            {"id": "old-1", "role": "user", "content": "same"},
            {"id": "old-2", "role": "assistant", "content": "same"},
        ]
        old_refs = self.filter._message_refs_for_prefix(old_messages, 2)

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("old same content", old_refs)],
            current_messages,
            live_message_refs_by_id=_live_refs_by_id(
                self.filter, current_messages + old_messages
            ),
        )

        self.assertIsNone(selected)

    def test_snapshot_selection_rejects_same_id_changed_payload(self):
        self.filter.valves.keep_last = 0
        original_messages = [
            {"id": "m1", "role": "user", "content": "original question"},
            {"id": "m2", "role": "assistant", "content": "original answer"},
        ]
        edited_messages = [
            {"id": "m1", "role": "user", "content": "edited question"},
            {"id": "m2", "role": "assistant", "content": "original answer"},
        ]
        original_refs = self.filter._message_refs_for_prefix(original_messages, 2)

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("old edited content", original_refs)],
            edited_messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, edited_messages),
        )

        self.assertIsNone(selected)

    def test_snapshot_selection_uses_nearest_available_ancestor_summary(self):
        self.filter.valves.keep_last = 0
        current_messages = _messages_with_ids(
            ["m0", "m1", "m2", "m3", "m4", "m5", "branch-user", "branch-assistant"]
        )
        older_refs = self.filter._message_refs_for_prefix(current_messages, 3)
        nearest_refs = self.filter._message_refs_for_prefix(current_messages, 6)
        unrelated_branch_refs = self.filter._message_refs_for_prefix(
            current_messages[:4]
            + [
                {"id": "other-user", "role": "user", "content": "other branch"},
                {
                    "id": "other-assistant",
                    "role": "assistant",
                    "content": "other answer",
                },
            ],
            6,
        )
        snapshots = [
            _snapshot("older common ancestor", older_refs),
            _snapshot("nearest common ancestor", nearest_refs),
            _snapshot("unrelated branch", unrelated_branch_refs),
        ]

        selected = self.filter._select_applicable_summary_snapshot(
            snapshots,
            current_messages,
            live_message_refs_by_id={
                **_live_refs_by_id(self.filter, current_messages),
                **{
                    ref["id"]: ref
                    for ref in unrelated_branch_refs
                    if ref["id"].startswith("other-")
                },
            },
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.summary, "nearest common ancestor")
        self.assertEqual(
            self.filter._summary_snapshot_current_coverage_count(selected),
            6,
        )

    def test_snapshot_selection_rejects_image_only_edit(self):
        # A message edited to swap only its attached image keeps identical text;
        # the fingerprint must still change so the stale summary is rejected (R5).
        self.filter.valves.keep_last = 0
        old_messages = [
            {"id": "m0", "role": "user", "content": "describe this", "images": ["old"]},
            {"id": "m1", "role": "assistant", "content": "an old picture"},
            {"id": "m2", "role": "user", "content": "and again"},
            {"id": "m3", "role": "assistant", "content": "sure"},
        ]
        current_messages = [
            {"id": "m0", "role": "user", "content": "describe this", "images": ["new"]},
            {"id": "m1", "role": "assistant", "content": "an old picture"},
            {"id": "m2", "role": "user", "content": "and again"},
            {"id": "m3", "role": "assistant", "content": "sure"},
        ]
        old_refs = self.filter._message_refs_for_prefix(old_messages, 4)

        selected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("stale image summary", old_refs)],
            current_messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, current_messages),
        )

        self.assertIsNone(selected)

    def test_snapshot_selection_discriminates_deleted_vs_sibling(self):
        # A covered ref missing from the current branch may be skipped only when
        # it is gone from the full graph (deleted). If it still exists off-chain
        # (live sibling), the snapshot must be rejected (R4 second discrimination).
        self.filter.valves.keep_last = 0
        snapshot_source = _messages_with_ids(["m0", "m1", "m2", "m3", "m4"])
        current_messages = _messages_with_ids(["m0", "m1", "m3", "m4"])
        snapshot_refs = self.filter._message_refs_for_prefix(snapshot_source, 5)
        snapshots = [_snapshot("summary covering m2", snapshot_refs)]

        deleted_selected = self.filter._select_applicable_summary_snapshot(
            list(snapshots),
            current_messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, current_messages),
        )
        self.assertIsNotNone(deleted_selected)

        sibling_graph = _live_refs_by_id(
            self.filter, current_messages + snapshot_source[2:3]
        )
        sibling_selected = self.filter._select_applicable_summary_snapshot(
            list(snapshots),
            current_messages,
            live_message_refs_by_id=sibling_graph,
        )
        self.assertIsNone(sibling_selected)

    def test_save_summary_dedup_hash_differs_for_protected_head_count(self):
        # Same covered refs saved with a different protected_head_count must land
        # in distinct rows; the dedup hash has to fold in the head count.
        refs = self.filter._message_refs_for_prefix(
            _messages_with_ids(["m0", "m1", "m2", "m3"]),
            4,
        )
        added_objects = []

        class FakeChatSummary:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        class FakeQuery:
            def __init__(self, model):
                self.model = model

            def filter_by(self, **kwargs):
                return self

            def first(self):
                return None

            def all(self):
                return []

        class FakeSession:
            def query(self, model):
                return FakeQuery(model)

            def add(self, obj):
                added_objects.append(obj)

            def delete(self, obj):
                pass

            def commit(self):
                pass

        class FakeAsyncContext:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        original_summary = module.ChatSummary
        module.ChatSummary = FakeChatSummary
        self.filter._async_db_session = lambda: FakeAsyncContext()

        try:
            saved_head_0 = asyncio.run(
                self.filter._save_summary(
                    "chat-1", "summary head 0", 4, refs, protected_head_count=0
                )
            )
            saved_head_2 = asyncio.run(
                self.filter._save_summary(
                    "chat-1", "summary head 2", 4, refs, protected_head_count=2
                )
            )
        finally:
            module.ChatSummary = original_summary

        self.assertTrue(saved_head_0)
        self.assertTrue(saved_head_2)
        snapshot_rows = [
            obj for obj in added_objects if isinstance(obj, FakeChatSummary)
        ]
        self.assertEqual(len(snapshot_rows), 2)
        self.assertNotEqual(
            snapshot_rows[0].covered_refs_hash,
            snapshot_rows[1].covered_refs_hash,
        )

    def test_snapshot_selection_rejects_coverage_that_splits_tool_group(self):
        # Coverage may not end inside a native [assistant(tool_calls), tool,
        # assistant] block; selection must reject a mid-group boundary and accept
        # one that aligns to the group edge (R7).
        self.filter.valves.keep_first = 0
        self.filter.valves.keep_last = 0
        messages = [
            {"id": "m0", "role": "user", "content": "ask"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_1", "type": "function"}],
            },
            {"id": "m2", "role": "tool", "tool_call_id": "call_1", "content": "result"},
            {"id": "m3", "role": "assistant", "content": "final"},
            {"id": "m4", "role": "user", "content": "next"},
        ]
        live = _live_refs_by_id(self.filter, messages)
        mid_group_refs = self.filter._message_refs_for_prefix(messages, 2)
        boundary_refs = self.filter._message_refs_for_prefix(messages, 4)

        rejected = self.filter._select_applicable_summary_snapshot(
            [_snapshot("cuts tool group", mid_group_refs)],
            messages,
            live_message_refs_by_id=live,
        )
        self.assertIsNone(rejected)

        accepted = self.filter._select_applicable_summary_snapshot(
            [_snapshot("aligned to boundary", boundary_refs)],
            messages,
            live_message_refs_by_id=live,
        )
        self.assertIsNotNone(accepted)
        self.assertEqual(accepted.summary, "aligned to boundary")

    def test_snapshot_selection_round_trips_between_branches(self):
        # Each branch keeps its own snapshot; switching back must select the
        # snapshot that matches the active branch and reject the sibling's (R9).
        self.filter.valves.keep_first = 0
        self.filter.valves.keep_last = 0
        branch_a = _messages_with_ids(["m0", "m1", "m2", "m3", "a4", "a5"])
        branch_b = _messages_with_ids(["m0", "m1", "m2", "m3", "b4", "b5"])
        snap_a = _snapshot(
            "branch A summary", self.filter._message_refs_for_prefix(branch_a, 6)
        )
        snap_b = _snapshot(
            "branch B summary", self.filter._message_refs_for_prefix(branch_b, 6)
        )
        live = _live_refs_by_id(self.filter, branch_a + branch_b[4:])

        selected_a = self.filter._select_applicable_summary_snapshot(
            [snap_a, snap_b], branch_a, live_message_refs_by_id=live
        )
        self.assertIsNotNone(selected_a)
        self.assertEqual(selected_a.summary, "branch A summary")

        selected_b = self.filter._select_applicable_summary_snapshot(
            [snap_a, snap_b], branch_b, live_message_refs_by_id=live
        )
        self.assertIsNotNone(selected_b)
        self.assertEqual(selected_b.summary, "branch B summary")

    def test_snapshot_selection_skips_corrupted_refs_json(self):
        # A snapshot row with unparsable refs JSON must be ignored as invalid
        # coverage without breaking the chat.
        self.filter.valves.keep_last = 0
        messages = _messages_with_ids(["m0", "m1", "m2"])
        bad_snapshot = types.SimpleNamespace(
            summary="corrupted",
            compressed_message_count=3,
            covered_message_refs_json="{not valid json",
            covered_refs_hash="hash",
            branch_tip_id="m2",
            updated_at=None,
            created_at=None,
        )

        selected = self.filter._select_applicable_summary_snapshot(
            [bad_snapshot],
            messages,
            live_message_refs_by_id=_live_refs_by_id(self.filter, messages),
        )

        self.assertIsNone(selected)

    def test_message_refs_for_prefix_includes_payload_fingerprints(self):
        # Covered refs must carry a fingerprint (not just an id) so in-place edits
        # invalidate the snapshot; a blank fingerprint would silently break reuse.
        messages = _messages_with_ids(["m0", "m1", "m2"])
        refs = self.filter._message_refs_for_prefix(messages, 3)

        self.assertEqual(len(refs), 3)
        for message, ref in zip(messages, refs):
            self.assertEqual(ref["id"], message["id"])
            self.assertTrue(ref["fingerprint"])
            self.assertEqual(
                ref["fingerprint"], self.filter._message_fingerprint(message)
            )

    def test_message_refs_for_prefix_skips_external_reference_messages(self):
        messages = [
            {"id": "m0", "role": "user", "content": "current chat"},
            {
                "role": "assistant",
                "content": "<external_references>ref</external_references>",
                "metadata": {
                    "is_summary": True,
                    "is_external_references": True,
                    "source": "external_references",
                },
            },
            {"id": "m1", "role": "assistant", "content": "answer"},
        ]

        refs = self.filter._message_refs_for_prefix(messages, 2)

        self.assertEqual([ref["id"] for ref in refs], ["m0", "m1"])
        self.assertEqual(self.filter._get_original_history_count(messages), 2)

    def test_save_summary_updates_existing_branch_row_by_hash(self):
        refs = self.filter._message_refs_for_prefix(
            _messages_with_ids(["m1", "m2"]),
            2,
        )
        existing_row = types.SimpleNamespace(
            summary="old branch summary",
            compressed_message_count=1,
            covered_message_refs_json=None,
            covered_refs_hash=None,
            branch_tip_id=None,
            source_current_id=None,
            updated_at=None,
        )
        added_objects = []
        commits = []

        class FakeChatSummary:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        class FakeQuery:
            def __init__(self, model):
                self.model = model

            def filter_by(self, **kwargs):
                return self

            def first(self):
                return existing_row

            def all(self):
                return []

        class FakeSession:
            def query(self, model):
                return FakeQuery(model)

            def add(self, obj):
                added_objects.append(obj)

            def delete(self, obj):
                raise AssertionError("No snapshots should be pruned in this test")

            def commit(self):
                commits.append(True)

        class FakeAsyncContext:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        original_summary = module.ChatSummary
        module.ChatSummary = FakeChatSummary
        self.filter._async_db_session = lambda: FakeAsyncContext()

        try:
            saved = asyncio.run(
                self.filter._save_summary(
                    "chat-1",
                    "short branch summary",
                    2,
                    refs,
                    source_current_id="m2",
                )
            )
        finally:
            module.ChatSummary = original_summary

        self.assertTrue(saved)
        self.assertEqual(added_objects, [])
        self.assertEqual(existing_row.summary, "short branch summary")
        self.assertEqual(existing_row.compressed_message_count, 2)
        self.assertEqual(existing_row.branch_tip_id, "m2")
        self.assertEqual(existing_row.source_current_id, "m2")
        self.assertEqual(
            [ref["id"] for ref in json.loads(existing_row.covered_message_refs_json)],
            ["m1", "m2"],
        )
        self.assertEqual(commits, [True])

    def test_save_summary_skips_without_message_refs(self):
        def fail_session():
            raise AssertionError("DB session should not open without branch refs")

        self.filter._async_db_session = fail_session

        saved = asyncio.run(
            self.filter._save_summary(
                "chat-1",
                "unverifiable summary",
                2,
                covered_message_refs=None,
            )
        )
        self.assertFalse(saved)

    def test_save_summary_skips_when_database_unavailable(self):
        def fail_session():
            raise AssertionError("DB session should not open when DB init failed")

        self.filter._summary_db_available = False
        self.filter._async_db_session = fail_session

        saved = asyncio.run(
            self.filter._save_summary(
                "chat-1",
                "summary",
                2,
                covered_message_refs=[{"id": "m1", "fingerprint": "fp"}],
            )
        )
        self.assertFalse(saved)

    def test_chat_summary_schema_detection_rejects_legacy_count_only_table(self):
        test_case = self

        class FakeInspector:
            def get_columns(self, table_name):
                test_case.assertEqual(table_name, "chat_summary")
                return [
                    {"name": "id"},
                    {"name": "chat_id"},
                    {"name": "summary"},
                    {"name": "compressed_message_count"},
                    {"name": "created_at"},
                    {"name": "updated_at"},
                ]

        self.assertFalse(self.filter._chat_summary_table_is_branch_aware(FakeInspector()))

    def test_chat_summary_schema_detection_does_not_rebuild_on_inspection_error(self):
        class FakeInspector:
            def get_columns(self, table_name):
                raise RuntimeError("temporary reflection failure")

        self.assertIsNone(
            self.filter._chat_summary_table_is_branch_aware(FakeInspector())
        )

    def test_chat_summary_schema_detection_rejects_unique_chat_id_constraint(self):
        test_case = self

        class FakeInspector:
            def get_columns(self, table_name):
                test_case.assertEqual(table_name, "chat_summary")
                return [
                    {"name": column_name}
                    for column_name in module.BRANCH_SUMMARY_REQUIRED_COLUMNS
                ]

            def get_unique_constraints(self, table_name, schema=None):
                test_case.assertEqual(table_name, "chat_summary")
                return [{"column_names": ["chat_id"]}]

            def get_indexes(self, table_name, schema=None):
                return []

        self.assertFalse(self.filter._chat_summary_table_is_branch_aware(FakeInspector()))

    def test_chat_summary_schema_detection_accepts_branch_aware_table(self):
        test_case = self

        class FakeInspector:
            def get_columns(self, table_name):
                test_case.assertEqual(table_name, "chat_summary")
                return [
                    {"name": column_name}
                    for column_name in module.BRANCH_SUMMARY_REQUIRED_COLUMNS
                ]

            def get_unique_constraints(self, table_name, schema=None):
                test_case.assertEqual(table_name, "chat_summary")
                return []

            def get_indexes(self, table_name, schema=None):
                test_case.assertEqual(table_name, "chat_summary")
                return [
                    {
                        "unique": True,
                        "column_names": ["chat_id", "covered_refs_hash"],
                    }
                ]

        self.assertTrue(self.filter._chat_summary_table_is_branch_aware(FakeInspector()))

    def test_init_database_migrates_legacy_snapshot_table_with_real_sqlite(self):
        real_module, sqlalchemy, restore_sqlalchemy_stubs = _load_module_with_real_sqlalchemy(
            "async_context_compression_real_sqlalchemy_under_test"
        )
        try:
            engine = sqlalchemy.create_engine("sqlite:///:memory:")
            metadata = sqlalchemy.MetaData()

            legacy_summary = sqlalchemy.Table(
                "chat_summary",
                metadata,
                sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
                sqlalchemy.Column("chat_id", sqlalchemy.String(255), unique=True),
                sqlalchemy.Column("summary", sqlalchemy.Text),
                sqlalchemy.Column("compressed_message_count", sqlalchemy.Integer),
                sqlalchemy.Column("created_at", sqlalchemy.DateTime),
                sqlalchemy.Column("updated_at", sqlalchemy.DateTime),
            )
            legacy_snapshot = sqlalchemy.Table(
                "chat_summary_snapshot",
                metadata,
                sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
                sqlalchemy.Column("chat_id", sqlalchemy.String(255), nullable=False),
                sqlalchemy.Column("summary", sqlalchemy.Text, nullable=False),
                sqlalchemy.Column("compressed_message_count", sqlalchemy.Integer),
                sqlalchemy.Column(
                    "covered_message_refs_json", sqlalchemy.Text, nullable=False
                ),
            )
            metadata.create_all(engine)

            refs = [
                {"id": "m1", "fingerprint": "fp1"},
                {"id": "m2", "fingerprint": "fp2"},
            ]
            with engine.begin() as connection:
                connection.execute(
                    legacy_summary.insert().values(
                        chat_id="chat-1",
                        summary="legacy count-only summary",
                        compressed_message_count=99,
                    )
                )
                connection.execute(
                    legacy_snapshot.insert(),
                    [
                        {
                            "chat_id": "chat-1",
                            "summary": "snapshot without protected head",
                            "compressed_message_count": 2,
                            "covered_message_refs_json": json.dumps(refs),
                        },
                        {
                            "chat_id": "chat-1",
                            "summary": "snapshot with protected head",
                            "compressed_message_count": 2,
                            "covered_message_refs_json": json.dumps(
                                {"refs": refs, "protected_head_count": 1}
                            ),
                        },
                    ],
                )

            filter_obj = real_module.Filter.__new__(real_module.Filter)
            filter_obj._db_engine = engine
            filter_obj._summary_db_available = True

            filter_obj._init_database()

            inspector = sqlalchemy.inspect(engine)
            self.assertTrue(inspector.has_table("chat_summary"))
            self.assertFalse(inspector.has_table("chat_summary_snapshot"))
            self.assertTrue(filter_obj._summary_db_available)
            self.assertFalse(
                filter_obj._table_has_unique_columns(
                    inspector, "chat_summary", ["chat_id"]
                )
            )
            self.assertTrue(
                filter_obj._table_has_unique_columns(
                    inspector, "chat_summary", ["chat_id", "covered_refs_hash"]
                )
            )

            with engine.connect() as connection:
                rows = list(
                    connection.execute(real_module.ChatSummary.__table__.select())
                    .mappings()
                    .all()
                )

            self.assertEqual(len(rows), 2)
            self.assertEqual(
                {row["summary"] for row in rows},
                {
                    "snapshot without protected head",
                    "snapshot with protected head",
                },
            )
            self.assertNotIn(
                "legacy count-only summary", {row["summary"] for row in rows}
            )
            self.assertEqual(len({row["covered_refs_hash"] for row in rows}), 2)
            self.assertEqual({row["branch_tip_id"] for row in rows}, {"m2"})
        finally:
            restore_sqlalchemy_stubs()

    def test_load_full_chat_messages_rebuilds_active_history_branch(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    chat={
                        "messages": [
                            {
                                "id": "stale-direct",
                                "role": "user",
                                "content": "Stale direct fallback",
                            }
                        ],
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
            messages = asyncio.run(self.filter._load_full_chat_messages("chat-1"))
        finally:
            module.Chats = original_chats

        self.assertEqual([message["id"] for message in messages], ["m1", "m2", "m3"])
        self.assertEqual(messages[2]["role"], "tool")

    def test_load_full_chat_messages_filters_failed_assistant_from_history_branch(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    chat={
                        "history": {
                            "currentId": "m4",
                            "messages": {
                                "m1": {
                                    "id": "m1",
                                    "role": "user",
                                    "content": "Question",
                                },
                                "m2": {
                                    "id": "m2",
                                    "role": "assistant",
                                    "content": "",
                                    "error": {"message": "provider failed"},
                                    "parentId": "m1",
                                },
                                "m3": {
                                    "id": "m3",
                                    "role": "user",
                                    "content": "Retry",
                                    "parentId": "m2",
                                },
                                "m4": {
                                    "id": "m4",
                                    "role": "assistant",
                                    "content": "OK",
                                    "parentId": "m3",
                                },
                            },
                        }
                    }
                )

        original_chats = module.Chats
        module.Chats = FakeChats
        try:
            messages = asyncio.run(self.filter._load_full_chat_messages("chat-1"))
        finally:
            module.Chats = original_chats

        self.assertEqual([message["id"] for message in messages], ["m1", "m3", "m4"])
        self.assertFalse(any("error" in message for message in messages))

    def test_load_full_chat_messages_filters_failed_assistant_from_direct_messages(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    chat={
                        "messages": [
                            {"id": "m1", "role": "user", "content": "Question"},
                            {
                                "id": "m2",
                                "role": "assistant",
                                "content": "",
                                "error": {"message": "provider failed"},
                            },
                            {"id": "m3", "role": "user", "content": "Retry"},
                            {"id": "m4", "role": "assistant", "content": "OK"},
                        ]
                    }
                )

        original_chats = module.Chats
        module.Chats = FakeChats
        try:
            messages = asyncio.run(self.filter._load_full_chat_messages("chat-1"))
        finally:
            module.Chats = original_chats

        self.assertEqual([message["id"] for message in messages], ["m1", "m3", "m4"])
        self.assertFalse(any("error" in message for message in messages))

    def test_load_authorized_chat_messages_uses_owner_helper(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                self.assertEqual(chat_id, "chat-1")
                self.assertEqual(user_id, "user-1")
                return types.SimpleNamespace(
                    user_id="user-1",
                    chat={
                        "history": {
                            "currentId": "m2",
                            "messages": {
                                "m1": {
                                    "role": "user",
                                    "content": "Owner question",
                                },
                                "m2": {
                                    "role": "assistant",
                                    "content": "Owner answer",
                                    "parentId": "m1",
                                },
                            },
                        }
                    },
                )

            @staticmethod
            def get_chat_by_id(chat_id):
                raise AssertionError("owner helper should satisfy authorization")

        original_chats = module.Chats
        module.Chats = FakeChats
        try:
            messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages(
                    "chat-1", {"id": "user-1"}
                )
            )
        finally:
            module.Chats = original_chats

        self.assertEqual([message["id"] for message in messages], ["m1", "m2"])

    def test_load_authorized_chat_messages_allows_shared_read_grant(self):
        captured = {}

        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                return None

            @staticmethod
            def get_chat_by_id_for_user(chat_id, user_id):
                return None

            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    user_id="owner-1",
                    organization_id="org-1",
                    chat={
                        "messages": [
                            {
                                "id": "shared-1",
                                "role": "user",
                                "content": "Shared question",
                            }
                        ]
                    },
                )

        class FakeAccessGrants:
            @staticmethod
            def has_access(
                user_id,
                resource_type,
                resource_id,
                permission="read",
                user_group_ids=None,
                organization_id=None,
                db=None,
            ):
                captured["organization_id"] = organization_id
                return (
                    user_id == "user-2"
                    and resource_type == "shared_chat"
                    and resource_id == "chat-1"
                    and permission == "read"
                    and organization_id == "org-1"
                )

        original_chats = module.Chats
        original_access_grants = module.AccessGrants
        module.Chats = FakeChats
        module.AccessGrants = FakeAccessGrants
        try:
            messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages(
                    "chat-1",
                    {
                        "id": "user-2",
                        "organization_id": "org-1",
                    },
                )
            )
        finally:
            module.Chats = original_chats
            module.AccessGrants = original_access_grants

        self.assertEqual(captured["organization_id"], "org-1")
        self.assertEqual([message["id"] for message in messages], ["shared-1"])

    def test_load_authorized_chat_messages_allows_direct_chat_grant(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                return None

            @staticmethod
            def get_chat_by_id_for_user(chat_id, user_id):
                self.assertEqual(chat_id, "chat-1")
                self.assertEqual(user_id, "user-2")
                return types.SimpleNamespace(
                    user_id="owner-1",
                    organization_id="org-2",
                    chat={
                        "messages": [
                            {
                                "id": "direct-grant-1",
                                "role": "user",
                                "content": "Direct grant question",
                            }
                        ]
                    },
                )

            @staticmethod
            def get_chat_by_id(chat_id):
                raise AssertionError("direct grant helper should satisfy access")

        original_chats = module.Chats
        module.Chats = FakeChats
        try:
            messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages(
                    "chat-1",
                    {
                        "id": "user-2",
                        "organization_id": "org-1",
                    },
                )
            )
        finally:
            module.Chats = original_chats

        self.assertEqual([message["id"] for message in messages], ["direct-grant-1"])

    def test_load_authorized_chat_messages_allows_admin_home_organization(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                return None

            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    user_id="owner-1",
                    organization_id="org-1",
                    chat={
                        "messages": [
                            {
                                "id": "admin-home-1",
                                "role": "user",
                                "content": "Admin home org question",
                            }
                        ]
                    },
                )

            @staticmethod
            def get_chat_by_id_for_user(chat_id, user_id):
                raise AssertionError("admin home organization should satisfy access")

        original_chats = module.Chats
        original_admin_access = module.ENABLE_ADMIN_CHAT_ACCESS
        module.Chats = FakeChats
        module.ENABLE_ADMIN_CHAT_ACCESS = True
        try:
            messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages(
                    "chat-1",
                    {
                        "id": "admin-1",
                        "role": "admin",
                        "organization_id": "org-1",
                    },
                )
            )
        finally:
            module.Chats = original_chats
            module.ENABLE_ADMIN_CHAT_ACCESS = original_admin_access

        self.assertEqual([message["id"] for message in messages], ["admin-home-1"])

    def test_load_authorized_chat_messages_denies_cross_org_admin_without_grant(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                return None

            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    user_id="owner-1",
                    organization_id="org-2",
                    chat={
                        "messages": [
                            {
                                "id": "cross-org-1",
                                "role": "user",
                                "content": "Cross org question",
                            }
                        ]
                    },
                )

            @staticmethod
            def get_chat_by_id_for_user(chat_id, user_id):
                return None

        class FakeAccessGrants:
            @staticmethod
            def has_access(*args, **kwargs):
                raise AssertionError("admin fallback should not use shared_chat grants")

        original_chats = module.Chats
        original_access_grants = module.AccessGrants
        original_admin_access = module.ENABLE_ADMIN_CHAT_ACCESS
        module.Chats = FakeChats
        module.AccessGrants = FakeAccessGrants
        module.ENABLE_ADMIN_CHAT_ACCESS = True
        try:
            messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages(
                    "chat-1",
                    {
                        "id": "admin-1",
                        "role": "admin",
                        "organization_id": "org-1",
                    },
                )
            )
        finally:
            module.Chats = original_chats
            module.AccessGrants = original_access_grants
            module.ENABLE_ADMIN_CHAT_ACCESS = original_admin_access

        self.assertEqual(messages, [])

    def test_load_authorized_chat_messages_fails_closed_without_access(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                return None

            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    user_id="owner-1",
                    chat={
                        "messages": [
                            {
                                "id": "private-1",
                                "role": "user",
                                "content": "Private question",
                            }
                        ]
                    },
                )

        class FakeAccessGrants:
            @staticmethod
            def has_access(*args, **kwargs):
                return False

        original_chats = module.Chats
        original_access_grants = module.AccessGrants
        module.Chats = FakeChats
        module.AccessGrants = FakeAccessGrants
        try:
            no_user_messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages("chat-1", None)
            )
            denied_messages = asyncio.run(
                self.filter._load_authorized_full_chat_messages(
                    "chat-1", {"id": "user-2"}
                )
            )
        finally:
            module.Chats = original_chats
            module.AccessGrants = original_access_grants

        self.assertEqual(no_user_messages, [])
        self.assertEqual(denied_messages, [])

    def test_load_chat_history_live_refs_reads_sibling_nodes_from_full_graph(self):
        class FakeChats:
            @staticmethod
            def get_chat_by_id(chat_id):
                return types.SimpleNamespace(
                    chat={
                        "history": {
                            "currentId": "new_m4",
                            "messages": {
                                "m1": {
                                    "role": "user",
                                    "content": "Question",
                                },
                                "m2": {
                                    "role": "assistant",
                                    "content": "Answer",
                                    "parentId": "m1",
                                },
                                "old_m3": {
                                    "role": "user",
                                    "content": "Old branch",
                                    "parentId": "m2",
                                },
                                "new_m3": {
                                    "role": "user",
                                    "content": "New branch",
                                    "parentId": "m2",
                                },
                                "new_m4": {
                                    "role": "assistant",
                                    "content": "New answer",
                                    "parentId": "new_m3",
                                },
                            },
                        }
                    }
                )

        original_chats = module.Chats
        module.Chats = FakeChats
        try:
            refs_by_id = asyncio.run(
                self.filter._load_chat_history_live_refs("chat-1")
            )
        finally:
            module.Chats = original_chats

        self.assertIn("old_m3", refs_by_id)
        self.assertIn("new_m4", refs_by_id)
        self.assertEqual(refs_by_id["old_m3"]["id"], "old_m3")

    def test_reconstruct_active_history_branch_uses_map_key_when_id_is_missing(self):
        messages = self.filter._reconstruct_active_history_branch(
            {
                "m1": {"role": "user", "content": "Question"},
                "m2": {
                    "role": "assistant",
                    "content": "Answer",
                    "parentId": "m1",
                },
            },
            "m2",
        )

        self.assertEqual([message["id"] for message in messages], ["m1", "m2"])

    def test_reconstruct_history_fallback_uses_map_key_when_id_is_missing(self):
        messages = self.filter._reconstruct_active_history_branch(
            {
                "m2": {"role": "assistant", "content": "Answer", "timestamp": 2},
                "m1": {"role": "user", "content": "Question", "timestamp": 1},
            },
            None,
        )

        self.assertEqual([message["id"] for message in messages], ["m1", "m2"])

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

    def test_outlet_keeps_native_output_messages_folded_for_summary_refs(self):
        messages = [
            {"id": "m0", "role": "user", "content": "search notes"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "I searched.",
                "output": [
                    {
                        "type": "function_call_output",
                        "call_id": "call-1",
                        "output": "folded tool result",
                    }
                ],
            },
        ]
        captured = {}

        async def fake_user_context(__user__, __event_call__):
            return {"user_language": "en-US"}

        async def noop_log(*args, **kwargs):
            return None

        async def fake_load_full_chat_messages(chat_id):
            return []

        def fake_locked_summary_task(
            lock,
            chat_id,
            model,
            body,
            user_data,
            target_compressed_count,
            lang,
            __event_emitter__,
            __event_call__,
            __request__=None,
        ):
            captured["messages"] = body["messages"]
            captured["target_compressed_count"] = target_compressed_count

            async def noop_task():
                return None

            return noop_task()

        def fake_create_task(coro):
            coro.close()
            return None

        self.filter._get_user_context = fake_user_context
        self.filter._get_chat_context = lambda body, metadata=None: {
            "chat_id": "chat-1",
            "message_id": "m1",
        }
        self.filter._should_skip_compression = lambda body, model: False
        self.filter._log = noop_log
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
        self.filter._locked_summary_task = fake_locked_summary_task
        self.filter.valves.keep_last = 0

        original_create_task = asyncio.create_task
        asyncio.create_task = fake_create_task
        try:
            asyncio.run(
                self.filter.outlet(
                    {
                        "model": "test-model",
                        "messages": messages,
                        "params": {"function_calling": "native"},
                    },
                    __event_call__=None,
                )
            )
        finally:
            asyncio.create_task = original_create_task

        self.assertEqual(captured["messages"], messages)
        self.assertIn("output", captured["messages"][1])
        captured_refs = self.filter._message_refs_for_prefix(
            captured["messages"],
            2,
        )
        self.assertEqual(
            [ref["id"] for ref in captured_refs],
            ["m0", "m1"],
        )
        self.assertEqual(captured["target_compressed_count"], 2)

    def test_select_native_summary_messages_uses_db_only_when_body_overlap_matches(self):
        body_messages = _messages_with_ids(["m0", "m1"])
        db_messages = body_messages + [
            {"id": "m2", "role": "user", "content": "persisted next turn"}
        ]

        selected, source = self.filter._select_native_summary_messages(
            body_messages, db_messages
        )

        self.assertIs(selected, db_messages)
        self.assertEqual(source, "outlet-db-native-folded")

        mismatched_db_messages = [
            {"id": "m0", "role": "user", "content": "search notes"},
            {"id": "m1", "role": "assistant", "content": "different answer"},
            {"id": "m2", "role": "user", "content": "persisted next turn"},
        ]

        selected, source = self.filter._select_native_summary_messages(
            body_messages, mismatched_db_messages
        )

        self.assertIs(selected, body_messages)
        self.assertEqual(source, "outlet-body-native-folded")

    def test_select_native_summary_messages_rejects_unprovable_body_overlap(self):
        body_messages = [
            {"role": "user", "content": "id-less outlet body"},
            {"role": "assistant", "content": "no stable id"},
        ]
        db_messages = _messages_with_ids(["m0", "m1", "m2"])

        selected, source = self.filter._select_native_summary_messages(
            body_messages, db_messages
        )

        self.assertIs(selected, body_messages)
        self.assertEqual(source, "outlet-body-native-folded")

    def test_select_native_summary_messages_accepts_db_hidden_output_superset(self):
        body_messages = [
            {"id": "m0", "role": "user", "content": "search notes"},
            {"id": "m1", "role": "assistant", "content": "I searched."},
        ]
        db_messages = [
            {"id": "m0", "role": "user", "content": "search notes"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "I searched.",
                "output": [
                    {
                        "type": "function_call_output",
                        "call_id": "call-1",
                        "output": "complete DB tool result",
                    }
                ],
            },
            {"id": "m2", "role": "user", "content": "persisted next turn"},
        ]

        selected, source = self.filter._select_native_summary_messages(
            body_messages, db_messages
        )

        self.assertIs(selected, db_messages)
        self.assertEqual(source, "outlet-db-native-folded")

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

    def test_format_messages_for_summary_includes_folded_native_output(self):
        messages = [
            {
                "id": "assistant-1",
                "role": "assistant",
                "content": "I searched the notes.",
                "output": [
                    {
                        "type": "function_call",
                        "name": "search_notes",
                        "arguments": {"query": "branch refs"},
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call-1",
                        "output": "Found canonical folded refs.",
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Use folded ids for snapshots.",
                            }
                        ],
                    },
                ],
            }
        ]

        formatted = self.filter._format_messages_for_summary(messages)

        self.assertIn("I searched the notes.", formatted)
        self.assertIn("function_call", formatted)
        self.assertIn("search_notes", formatted)
        self.assertIn("Found canonical folded refs.", formatted)
        self.assertIn("Use folded ids for snapshots.", formatted)

    def test_generate_summary_async_native_output_saves_folded_refs(self):
        misc_module = _ensure_module("open_webui.utils.misc")
        misc_module.convert_output_to_messages = lambda output, raw=True: [
            {
                "role": "assistant",
                "tool_calls": [{"id": "call-1", "function": {"name": "search"}}],
                "content": "",
            },
            {
                "role": "tool",
                "tool_call_id": "call-1",
                "content": "tool result from id-less unfolded child",
            },
            {
                "role": "assistant",
                "content": "final answer from id-less unfolded child",
            },
        ]

        self.filter.valves.keep_first = 0
        self.filter.valves.keep_last = 0
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 0
        captured = {}

        messages = [
            {"id": "m0", "role": "user", "content": "search notes"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "I searched.",
                "output": [
                    {
                        "type": "function_call_output",
                        "call_id": "call-1",
                        "output": "tool result from folded output",
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "final answer from folded output",
                            }
                        ],
                    },
                ],
            },
            {"id": "m2", "role": "user", "content": "next question"},
        ]

        self.assertIsNone(
            self.filter._message_refs_for_prefix(
                self.filter._unfold_messages(messages),
                2,
            )
        )

        async def mock_summary_llm(
            conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = conversation_text
            captured["previous_summary"] = previous_summary
            return "new native summary"

        async def mock_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            captured["chat_id"] = chat_id
            captured["summary"] = summary
            captured["compressed_count"] = compressed_count
            captured["covered_message_refs"] = covered_message_refs
            captured["source_current_id"] = source_current_id
            captured["protected_head_count"] = protected_head_count
            return True

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = mock_summary_llm
        self.filter._save_summary = mock_save_summary

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

        self.assertEqual(captured["chat_id"], "chat-1")
        self.assertEqual(captured["summary"], "new native summary")
        self.assertEqual(captured["compressed_count"], 2)
        self.assertEqual(
            [ref["id"] for ref in captured["covered_message_refs"]],
            ["m0", "m1"],
        )
        self.assertTrue(
            all(ref["fingerprint"] for ref in captured["covered_message_refs"])
        )
        self.assertEqual(captured["source_current_id"], "m2")
        self.assertIn("tool result from folded output", captured["conversation_text"])
        self.assertIn("final answer from folded output", captured["conversation_text"])
        self.assertNotIn("id-less unfolded child", captured["conversation_text"])

    def test_summary_save_progress_matches_final_prompt_shrink(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500

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

        async def mock_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            captured["chat_id"] = chat_id
            captured["summary"] = summary
            captured["compressed_count"] = compressed_count
            captured["covered_message_refs"] = covered_message_refs
            captured["source_current_id"] = source_current_id
            captured["protected_head_count"] = protected_head_count

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
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 100},
            {"id": "m2", "role": "assistant", "content": "A" * 100},
            {"id": "m3", "role": "user", "content": "B" * 100},
            {"id": "m4", "role": "assistant", "content": "C" * 100},
            {"id": "m5", "role": "user", "content": "Question 3"},
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
        self.assertEqual(captured["compressed_count"], 4)
        self.assertEqual(
            [ref["id"] for ref in captured["covered_message_refs"]],
            ["m0", "m1", "m2", "m3"],
        )
        self.assertEqual(captured["source_current_id"], "m5")
        self.assertEqual(captured["protected_head_count"], 2)
        self.assertEqual(captured["conversation_text"], f"{'A' * 100}\n{'B' * 100}")
        self.assertTrue(any(event["type"] == "status" for event in events))

    def test_generate_summary_async_saves_refs_after_reinjected_summary_marker(self):
        self.filter.valves.keep_first = 0
        self.filter.valves.keep_last = 0
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 0

        raw_messages = _messages_with_ids(["m0", "m1", "m2", "m3", "m4", "m5"])
        covered_refs = self.filter._message_refs_for_prefix(raw_messages, 4)
        summary_message = self.filter._build_summary_message(
            "older summary",
            "en-US",
            4,
            covered_refs,
        )
        reinjected_messages = raw_messages[:4] + [summary_message] + raw_messages[4:]
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

        async def mock_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            captured["chat_id"] = chat_id
            captured["summary"] = summary
            captured["compressed_count"] = compressed_count
            captured["covered_message_refs"] = covered_message_refs
            captured["source_current_id"] = source_current_id
            captured["protected_head_count"] = protected_head_count

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = mock_summary_llm
        self.filter._save_summary = mock_save_summary
        self.filter._format_messages_for_summary = lambda messages: "\n".join(
            msg["content"] for msg in messages
        )
        self.filter._build_summary_prompt = (
            lambda conversation_text, previous_summary=None: conversation_text
        )

        asyncio.run(
            self.filter._generate_summary_async(
                messages=reinjected_messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=6,
                lang="en-US",
                __event_emitter__=None,
                __event_call__=None,
            )
        )

        self.assertEqual(captured["chat_id"], "chat-1")
        self.assertEqual(captured["summary"], "new summary")
        self.assertEqual(captured["compressed_count"], 6)
        self.assertEqual(
            [ref["id"] for ref in captured["covered_message_refs"]],
            ["m0", "m1", "m2", "m3", "m4", "m5"],
        )
        self.assertEqual(captured["source_current_id"], "m5")
        self.assertEqual(captured["protected_head_count"], 0)
        self.assertIn("older summary", captured["conversation_text"])
        self.assertIsNone(captured["previous_summary"])

    def test_generate_summary_async_keeps_marker_and_one_new_message_when_oversized(self):
        # The embedded summary marker is the semantic root of the next summary.
        # Budget fitting may trim newer atomic groups, but it must not trim the
        # marker and must keep at least one new message for progress.
        self.filter.valves.keep_first = 0
        self.filter.valves.keep_last = 0
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 100

        base_messages = _messages_with_ids(["m0", "m1"])
        marker_refs = self.filter._message_refs_for_prefix(base_messages, 2)
        marker = self.filter._build_summary_message(
            "old summary " + "S" * 40, "en-US", 2, marker_refs
        )
        messages = [marker] + [
            {"id": "m2", "role": "user", "content": "aaa"},
            {"id": "m3", "role": "assistant", "content": "bbb"},
            {"id": "m4", "role": "user", "content": "ccc"},
        ]
        captured = {}

        async def mock_summary_llm(
            text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = text
            captured["previous_summary"] = previous_summary
            return "new summary"

        async def mock_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            captured["covered_message_refs"] = covered_message_refs
            captured["compressed_count"] = compressed_count

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = mock_summary_llm
        self.filter._save_summary = mock_save_summary
        self.filter._format_messages_for_summary = lambda msgs: "".join(
            m.get("content", "") for m in msgs
        )
        self.filter._build_summary_prompt = (
            lambda text, previous_summary=None: text
        )
        self.filter._count_tokens = len
        self.filter._get_summary_model_context_limit = lambda model_id: 1000
        self.filter._compute_summary_request_limits = lambda max_ctx, model_id=None: {
            "max_input_tokens": 20,
            "max_output_tokens": 100,
            "safety_margin_tokens": 10,
        }

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=5,
                lang="en-US",
                __event_emitter__=None,
                __event_call__=None,
            )
        )

        self.assertIn("covered_message_refs", captured)
        self.assertEqual(captured["compressed_count"], 3)
        self.assertEqual(
            [ref["id"] for ref in captured["covered_message_refs"]],
            ["m0", "m1", "m2"],
        )
        self.assertIn("old summary", captured["conversation_text"])
        self.assertIn("aaa", captured["conversation_text"])
        self.assertNotIn("bbb", captured["conversation_text"])
        self.assertNotIn("ccc", captured["conversation_text"])
        self.assertIsNone(captured["previous_summary"])

    def test_generate_summary_async_keeps_previous_summary_when_prompt_still_oversized(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500

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
        async def noop_save_summary(*args, **kwargs):
            return None

        self.filter._save_summary = noop_save_summary
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
        async def fake_load_applicable_summary_snapshot(chat_id, messages):
            return types.SimpleNamespace(summary="P" * 300)

        self.filter._load_applicable_summary_snapshot = (
            fake_load_applicable_summary_snapshot
        )

        messages = [
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 60},
            {"id": "m2", "role": "assistant", "content": "Answer 1"},
            {"id": "m3", "role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=3,
                lang="en-US",
                __event_emitter__=None,
                __event_call__=None,
            )
        )

        self.assertEqual(captured["conversation_text"], "Answer 1")
        self.assertEqual(captured["previous_summary"], "P" * 300)

    def test_generate_summary_async_db_previous_summary_starts_after_previous_coverage(self):
        self.filter.valves.keep_first = 0
        self.filter.valves.keep_last = 0
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 100

        messages = [
            {"id": "m0", "role": "user", "content": "old user 0"},
            {"id": "m1", "role": "assistant", "content": "old answer 1"},
            {"id": "m2", "role": "user", "content": "old user 2"},
            {"id": "m3", "role": "assistant", "content": "old answer 3"},
            {"id": "m4", "role": "user", "content": "new user 4"},
            {"id": "m5", "role": "assistant", "content": "new answer 5"},
        ]
        previous_refs = self.filter._message_refs_for_prefix(messages, 4)
        previous_snapshot = _snapshot("previous branch summary", previous_refs)
        captured = {}

        async def fake_load_applicable_summary_snapshot(chat_id, loaded_messages):
            self.assertEqual(loaded_messages, messages)
            return previous_snapshot

        async def mock_summary_llm(
            conversation_text,
            body,
            user_data,
            __event_call__=None,
            __request__=None,
            previous_summary=None,
        ):
            captured["conversation_text"] = conversation_text
            captured["previous_summary"] = previous_summary
            return "new summary"

        async def mock_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            captured["compressed_count"] = compressed_count
            captured["covered_message_refs"] = covered_message_refs
            captured["source_current_id"] = source_current_id
            captured["protected_head_count"] = protected_head_count

        async def noop_log(*args, **kwargs):
            return None

        self.filter._load_applicable_summary_snapshot = (
            fake_load_applicable_summary_snapshot
        )
        self.filter._log = noop_log
        self.filter._call_summary_llm = mock_summary_llm
        self.filter._save_summary = mock_save_summary
        self.filter._format_messages_for_summary = lambda msgs: "\n".join(
            msg["content"] for msg in msgs
        )
        self.filter._build_summary_prompt = (
            lambda text, previous_summary=None: (previous_summary or "") + "\n" + text
        )
        self.filter._count_tokens = len
        self.filter._get_summary_model_context_limit = lambda model_id: 1000
        self.filter._compute_summary_request_limits = lambda max_ctx, model_id=None: {
            "max_input_tokens": 45,
            "max_output_tokens": 100,
            "safety_margin_tokens": 10,
        }

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=6,
                lang="en-US",
                __event_emitter__=None,
                __event_call__=None,
            )
        )

        self.assertEqual(captured["previous_summary"], "previous branch summary")
        self.assertEqual(captured["conversation_text"], "new user 4")
        self.assertNotIn("old user", captured["conversation_text"])
        self.assertNotIn("new answer 5", captured["conversation_text"])
        self.assertEqual(captured["compressed_count"], 5)
        self.assertEqual(
            [ref["id"] for ref in captured["covered_message_refs"]],
            ["m0", "m1", "m2", "m3", "m4"],
        )
        self.assertEqual(captured["source_current_id"], "m5")
        self.assertEqual(captured["protected_head_count"], 0)

    def test_summary_budget_validation_requires_20_percent_new_message_space(self):
        self.filter.valves.max_summary_tokens = 800

        with self.assertRaisesRegex(ValueError, "80%"):
            self.filter._validate_summary_budget_configuration(
                "fake-summary-model",
                1000,
            )

        self.filter.valves.max_summary_tokens = 799
        self.filter._validate_summary_budget_configuration(
            "fake-summary-model",
            1000,
        )

    def test_valves_reject_summary_budget_without_new_message_space(self):
        with self.assertRaisesRegex(ValueError, "80%"):
            module.Filter.Valves(max_context_tokens=1000, max_summary_tokens=800)

        valves = module.Filter.Valves(max_context_tokens=1000, max_summary_tokens=799)
        self.assertEqual(valves.max_summary_tokens, 799)

        with self.assertRaisesRegex(ValueError, "80%"):
            module.Filter.Valves(
                summary_model="summary-model",
                summary_model_max_context=1000,
                max_context_tokens=10000,
                max_summary_tokens=800,
            )

        valves = module.Filter.Valves(
            summary_model="summary-model",
            summary_model_max_context=1000,
            max_context_tokens=10000,
            max_summary_tokens=799,
        )
        self.assertEqual(valves.max_summary_tokens, 799)

        with self.assertRaisesRegex(ValueError, "80%"):
            module.Filter.Valves(
                summary_model="summary-model",
                model_thresholds="other:100:10000, summary-model:100:1000",
                max_context_tokens=10000,
                max_summary_tokens=800,
            )

        valves = module.Filter.Valves(
            summary_model="summary-model",
            model_thresholds="other:100:10000, summary-model:100:1000",
            max_context_tokens=10000,
            max_summary_tokens=799,
        )
        self.assertEqual(valves.max_summary_tokens, 799)

    def test_call_summary_llm_silently_handles_provider_error_dict_by_default(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 1024
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
        self.filter.valves.max_summary_tokens = 1024
        self.filter.valves.show_debug_log = False
        self.filter.valves.summary_fail_mode = "raise"

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

    def test_call_summary_llm_times_out_provider_request(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 1024
        self.filter.valves.show_debug_log = False
        self.filter.valves.summary_fail_mode = "raise"
        self.filter.valves.summary_llm_timeout_seconds = 0.01

        async def fake_generate_chat_completion(request, payload, user):
            await asyncio.sleep(10)
            return {"choices": [{"message": {"content": "too late"}}]}

        async def noop_log(*args, **kwargs):
            return None

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
                    )
                )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        self.assertIn("timed out after 0.01 seconds", str(exc_info.exception))

    def test_call_summary_llm_timeout_zero_allows_slow_provider_success(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 1024
        self.filter.valves.show_debug_log = False
        self.filter.valves.summary_llm_timeout_seconds = 0

        async def fake_generate_chat_completion(request, payload, user):
            await asyncio.sleep(0.01)
            return {"choices": [{"message": {"content": "eventual summary"}}]}

        async def noop_log(*args, **kwargs):
            return None

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
                )
            )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        self.assertEqual(summary, "eventual summary")

    def test_extract_summary_text_supports_alternate_response_shapes(self):
        self.assertEqual(
            self.filter._extract_summary_text_from_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "<working_memory>",
                                    },
                                    {
                                        "type": "output_text",
                                        "text": "<current_goal>test</current_goal></working_memory>",
                                    },
                                ]
                            }
                        }
                    ]
                }
            ),
            "<working_memory><current_goal>test</current_goal></working_memory>",
        )
        self.assertEqual(
            self.filter._extract_summary_text_from_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "reasoning_content": "<working_memory><current_goal>reasoning must be ignored</current_goal></working_memory>",
                            }
                        }
                    ]
                }
            ),
            "",
        )
        self.assertEqual(
            self.filter._extract_summary_text_from_response(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "<working_memory><current_goal>responses api</current_goal></working_memory>",
                                }
                            ],
                        }
                    ]
                }
            ),
            "<working_memory><current_goal>responses api</current_goal></working_memory>",
        )
        self.assertEqual(
            self.filter._extract_summary_text_from_response(
                {
                    "output": [
                        {
                            "type": "reasoning",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "<working_memory><current_goal>reasoning output ignored</current_goal></working_memory>",
                                }
                            ],
                        },
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "<working_memory><current_goal>final answer only</current_goal></working_memory>",
                                }
                            ],
                        },
                    ]
                }
            ),
            "<working_memory><current_goal>final answer only</current_goal></working_memory>",
        )

    def test_call_summary_llm_accepts_output_only_response(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 1024
        self.filter.valves.show_debug_log = False

        async def fake_generate_chat_completion(request, payload, user):
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "<working_memory><current_goal>responses api</current_goal></working_memory>",
                            }
                        ],
                    }
                ]
            }

        async def noop_log(*args, **kwargs):
            return None

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
                )
            )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        self.assertEqual(
            summary,
            "<working_memory><current_goal>responses api</current_goal></working_memory>",
        )

    def test_call_summary_llm_rejects_empty_message_content(self):
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.max_summary_tokens = 1024
        self.filter.valves.show_debug_log = False
        self.filter.valves.summary_fail_mode = "raise"

        async def fake_generate_chat_completion(request, payload, user):
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                        },
                        "finish_reason": "stop",
                    }
                ]
            }

        async def noop_log(*args, **kwargs):
            return None

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
                    )
                )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        self.assertIn(
            "LLM response did not contain summary text", str(exc_info.exception)
        )

    def test_generate_summary_async_status_guides_user_to_browser_console(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500
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
                target_compressed_count=3,
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

    def test_generate_summary_async_empty_summary_settles_generating_status(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500
        self.filter.valves.show_debug_log = False

        events = []
        save_called = False

        async def empty_summary_llm(*args, **kwargs):
            return ""

        async def fake_save_summary(*args, **kwargs):
            nonlocal save_called
            save_called = True
            return True

        async def fake_emitter(event):
            events.append(event)

        async def no_snapshot(*args, **kwargs):
            return None

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = empty_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._load_applicable_summary_snapshot = no_snapshot
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
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 40},
            {"id": "m2", "role": "assistant", "content": "A" * 40},
            {"id": "m3", "role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=3,
                lang="en-US",
                __event_emitter__=fake_emitter,
                __event_call__=None,
            )
        )

        statuses = [
            event["data"] for event in events if event.get("type") == "status"
        ]
        self.assertGreaterEqual(len(statuses), 2)
        self.assertEqual(
            statuses[-2]["description"], "Generating context summary in background..."
        )
        self.assertFalse(statuses[-2]["done"])
        self.assertTrue(statuses[-1]["done"])
        self.assertIn("Summary Error", statuses[-1]["description"])
        self.assertIn("empty", statuses[-1]["description"])
        self.assertFalse(save_called)

    def test_generate_summary_async_save_failure_settles_generating_status(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500
        self.filter.valves.show_debug_log = False

        events = []
        save_called = False

        async def fake_summary_llm(*args, **kwargs):
            return "new summary"

        async def fail_save_summary(*args, **kwargs):
            nonlocal save_called
            save_called = True
            return False

        async def fake_emitter(event):
            events.append(event)

        async def no_snapshot(*args, **kwargs):
            return None

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fail_save_summary
        self.filter._load_applicable_summary_snapshot = no_snapshot
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
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 40},
            {"id": "m2", "role": "assistant", "content": "A" * 40},
            {"id": "m3", "role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=3,
                lang="en-US",
                __event_emitter__=fake_emitter,
                __event_call__=None,
            )
        )

        statuses = [
            event["data"] for event in events if event.get("type") == "status"
        ]
        self.assertGreaterEqual(len(statuses), 2)
        self.assertEqual(
            statuses[-2]["description"], "Generating context summary in background..."
        )
        self.assertFalse(statuses[-2]["done"])
        self.assertTrue(statuses[-1]["done"])
        self.assertIn("Summary Error", statuses[-1]["description"])
        self.assertIn("persisted", statuses[-1]["description"])
        self.assertTrue(save_called)
        self.assertFalse(
            any("Loaded historical summary" in status["description"] for status in statuses)
        )

    def test_generate_summary_async_terminal_status_emitter_failure_is_best_effort(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500
        self.filter.valves.show_debug_log = False

        events = []
        save_called = False

        async def empty_summary_llm(*args, **kwargs):
            return ""

        async def fake_save_summary(*args, **kwargs):
            nonlocal save_called
            save_called = True
            return True

        async def flaky_emitter(event):
            if events:
                raise RuntimeError("frontend disconnected")
            events.append(event)

        async def no_snapshot(*args, **kwargs):
            return None

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = empty_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._load_applicable_summary_snapshot = no_snapshot
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
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 40},
            {"id": "m2", "role": "assistant", "content": "A" * 40},
            {"id": "m3", "role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=3,
                lang="en-US",
                __event_emitter__=flaky_emitter,
                __event_call__=None,
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["data"]["description"],
            "Generating context summary in background...",
        )
        self.assertFalse(events[0]["data"]["done"])
        self.assertFalse(save_called)

    def test_generate_summary_async_error_status_emitter_failure_is_best_effort(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500
        self.filter.valves.show_debug_log = False

        events = []

        async def fail_summary_llm(*args, **kwargs):
            raise Exception("summary backend failed")

        async def flaky_emitter(event):
            if events:
                raise RuntimeError("frontend disconnected")
            events.append(event)

        async def no_snapshot(*args, **kwargs):
            return None

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._call_summary_llm = fail_summary_llm
        self.filter._load_applicable_summary_snapshot = no_snapshot
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
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 40},
            {"id": "m2", "role": "assistant", "content": "A" * 40},
            {"id": "m3", "role": "user", "content": "Question 2"},
        ]

        asyncio.run(
            self.filter._generate_summary_async(
                messages=messages,
                chat_id="chat-1",
                body={"model": "fake-summary-model"},
                user_data={"id": "user-1"},
                target_compressed_count=3,
                lang="en-US",
                __event_emitter__=flaky_emitter,
                __event_call__=None,
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["data"]["description"],
            "Generating context summary in background...",
        )
        self.assertFalse(events[0]["data"]["done"])

    def test_generate_summary_async_timeout_silent_settles_generating_status(self):
        self.filter.valves.keep_first = 1
        self.filter.valves.keep_last = 1
        self.filter.valves.summary_model = "fake-summary-model"
        self.filter.valves.summary_model_max_context = 1200
        self.filter.valves.max_summary_tokens = 500
        self.filter.valves.show_debug_log = False
        self.filter.valves.summary_llm_timeout_seconds = 0.01

        events = []
        save_called = False

        async def slow_generate_chat_completion(request, payload, user):
            await asyncio.sleep(10)
            return {"choices": [{"message": {"content": "too late"}}]}

        async def fake_save_summary(*args, **kwargs):
            nonlocal save_called
            save_called = True
            return True

        async def fake_emitter(event):
            events.append(event)

        async def no_snapshot(*args, **kwargs):
            return None

        async def noop_log(*args, **kwargs):
            return None

        original_generate = module.generate_chat_completion
        original_get_user = getattr(module.Users, "get_user_by_id", None)

        module.generate_chat_completion = slow_generate_chat_completion
        module.Users.get_user_by_id = staticmethod(
            lambda user_id: types.SimpleNamespace(email="user@example.com")
        )
        self.filter._log = noop_log
        self.filter._save_summary = fake_save_summary
        self.filter._load_applicable_summary_snapshot = no_snapshot
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
            {"id": "m0", "role": "system", "content": "System prompt"},
            {"id": "m1", "role": "user", "content": "Q" * 40},
            {"id": "m2", "role": "assistant", "content": "A" * 40},
            {"id": "m3", "role": "user", "content": "Question 2"},
        ]

        try:
            asyncio.run(
                self.filter._generate_summary_async(
                    messages=messages,
                    chat_id="chat-1",
                    body={"model": "fake-summary-model"},
                    user_data={"id": "user-1"},
                    target_compressed_count=3,
                    lang="en-US",
                    __event_emitter__=fake_emitter,
                    __event_call__=None,
                )
            )
        finally:
            module.generate_chat_completion = original_generate
            if original_get_user is None:
                delattr(module.Users, "get_user_by_id")
            else:
                module.Users.get_user_by_id = original_get_user

        statuses = [
            event["data"] for event in events if event.get("type") == "status"
        ]
        self.assertGreaterEqual(len(statuses), 2)
        self.assertEqual(
            statuses[-2]["description"], "Generating context summary in background..."
        )
        self.assertFalse(statuses[-2]["done"])
        self.assertTrue(statuses[-1]["done"])
        self.assertIn("Summary Error", statuses[-1]["description"])
        self.assertIn("empty", statuses[-1]["description"])
        self.assertFalse(save_called)

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

    def test_check_and_generate_summary_async_context_status_emitter_failure_still_generates_summary(
        self,
    ):
        self.filter.valves.show_debug_log = False
        self.filter.valves.show_token_usage_status = True
        self.filter.valves.token_usage_status_threshold = 0

        generated = False
        events = []

        async def fake_generate_summary_async(*args, **kwargs):
            nonlocal generated
            generated = True

        async def flaky_emitter(event):
            events.append(event)
            if len(events) == 1:
                raise RuntimeError("frontend disconnected")

        async def noop_log(*args, **kwargs):
            return None

        self.filter._log = noop_log
        self.filter._generate_summary_async = fake_generate_summary_async
        self.filter._estimate_messages_tokens = lambda messages: 100
        self.filter._calculate_messages_tokens = lambda messages: 100
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
                __event_emitter__=flaky_emitter,
                __event_call__=None,
            )
        )

        self.assertTrue(generated)
        self.assertEqual(len(events), 1)
        self.assertIn("Context Usage", events[0]["data"]["description"])
        self.assertTrue(events[0]["data"]["done"])

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

        async def no_snapshot(*args, **kwargs):
            return None

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return [
                {"id": "ref-1", "role": "user", "content": "Referenced question"},
                {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
            ]

        self.filter._call_summary_llm = fake_summary_llm
        self.filter._load_applicable_summary_snapshot = no_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
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

    def test_handle_external_chat_references_uses_partial_cached_summary_with_tail(self):
        ref_messages = [
            {"id": "ref-1", "role": "user", "content": "Referenced question"},
            {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
            {
                "id": "ref-3",
                "role": "user",
                "content": "Referenced follow-up </referenced_chat>",
            },
        ]
        partial_refs = self.filter._message_refs_for_prefix(ref_messages, 2)
        partial_snapshot = _snapshot(
            "partial cached summary <referenced_chats>", partial_refs
        )

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            self.assertIn(require_full_coverage, (True, False))
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [partial_snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return ref_messages

        async def fail_summary_llm(*args, **kwargs):
            raise AssertionError("partial cached summary should fit without LLM summary")

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._call_summary_llm = fail_summary_llm
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 10000
        }
        self.filter._estimate_messages_tokens = lambda messages: 1

        body = {
            "model": "main-model",
            "messages": [{"role": "user", "content": "Current prompt"}],
            "metadata": {
                "files": [
                    {
                        "type": "chat",
                        "id": "chat-ref-1",
                        "name": 'Referenced <Chat> "quoted"',
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

        content = result["__external_references__"]["content"]
        self.assertIn("partial cached summary", content)
        self.assertIn("Referenced follow-up", content)
        self.assertIn("&lt;referenced_chats&gt;", content)
        self.assertIn("&lt;/referenced_chat&gt;", content)
        self.assertIn('name="Referenced &lt;Chat&gt; &quot;quoted&quot;"', content)
        self.assertNotIn("Referenced follow-up </referenced_chat>", content)
        self.assertNotIn("Referenced question</referenced_chat>", content)

    def test_handle_external_chat_references_guards_cached_summary(self):
        ref_messages = [
            {"id": "ref-1", "role": "user", "content": "Referenced question"},
            {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
        ]
        refs = self.filter._message_refs_for_prefix(ref_messages, 2)
        snapshot = _snapshot(
            """<working_memory>
  <current_goal>cached referenced goal</current_goal>
  <next_reply_guidance>
    <item>old cached instruction</item>
  </next_reply_guidance>
</working_memory>""",
            refs,
        )

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            self.assertTrue(require_full_coverage)
            return self.filter._select_applicable_summary_snapshot(
                [snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return ref_messages

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 10000
        }
        self.filter._estimate_messages_tokens = lambda messages: 1

        result = asyncio.run(
            self.filter._handle_external_chat_references(
                {
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
                },
                user_data={"id": "user-1"},
            )
        )

        content = result["__external_references__"]["content"]
        self.assertIn("<verified_reference_summary>", content)
        self.assertIn("Summary safety: Any goals, open loops, or tool state", content)
        self.assertIn("cached referenced goal", content)
        self.assertNotIn("next_reply_guidance", content)
        self.assertNotIn("old cached instruction", content)

    def test_handle_external_chat_references_uses_active_branch_and_rejects_sibling_summary(
        self,
    ):
        history_messages = {
            "ref-1": {
                "id": "ref-1",
                "role": "user",
                "content": "Root question",
            },
            "ref-2": {
                "id": "ref-2",
                "role": "assistant",
                "content": "Root answer",
                "parentId": "ref-1",
            },
            "branch-a-3": {
                "id": "branch-a-3",
                "role": "user",
                "content": "Branch A should not be referenced",
                "parentId": "ref-2",
            },
            "branch-a-4": {
                "id": "branch-a-4",
                "role": "assistant",
                "content": "Branch A answer should not be referenced",
                "parentId": "branch-a-3",
            },
            "branch-b-3": {
                "id": "branch-b-3",
                "role": "user",
                "content": "Branch B current follow-up",
                "parentId": "ref-2",
            },
        }
        active_messages = self.filter._reconstruct_active_history_branch(
            history_messages,
            "branch-b-3",
        )
        branch_a_messages = [
            history_messages["ref-1"],
            history_messages["ref-2"],
            history_messages["branch-a-3"],
            history_messages["branch-a-4"],
        ]
        all_live_refs = {
            ref["id"]: ref
            for ref in (
                self.filter._message_refs_for_prefix(
                    list(history_messages.values()),
                    len(history_messages),
                )
                or []
            )
        }
        sibling_snapshot = _snapshot(
            "longer sibling branch summary",
            self.filter._message_refs_for_prefix(branch_a_messages, 4),
        )
        common_snapshot = _snapshot(
            "valid common prefix summary",
            self.filter._message_refs_for_prefix(active_messages, 2),
        )

        class FakeChats:
            @staticmethod
            def get_chat_by_id_and_user_id(chat_id, user_id):
                return types.SimpleNamespace(
                    user_id=user_id,
                    chat={
                        "history": {
                            "currentId": "branch-b-3",
                            "messages": history_messages,
                        }
                    },
                )

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            self.assertEqual(
                [message["id"] for message in messages],
                ["ref-1", "ref-2", "branch-b-3"],
            )
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [sibling_snapshot, common_snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=all_live_refs,
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fail_summary_llm(*args, **kwargs):
            raise AssertionError("active-branch partial summary should fit directly")

        original_chats = module.Chats
        module.Chats = FakeChats
        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._call_summary_llm = fail_summary_llm
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 10000
        }
        self.filter._estimate_messages_tokens = lambda messages: 1
        try:
            result = asyncio.run(
                self.filter._handle_external_chat_references(
                    {
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
                    },
                    user_data={"id": "user-1"},
                )
            )
        finally:
            module.Chats = original_chats

        content = result["__external_references__"]["content"]
        self.assertIn("valid common prefix summary", content)
        self.assertIn("Branch B current follow-up", content)
        self.assertNotIn("longer sibling branch summary", content)
        self.assertNotIn("Branch A should not be referenced", content)

    def test_handle_external_chat_references_preserves_protected_head_with_partial_summary(
        self,
    ):
        ref_messages = [
            {"id": "ref-1", "role": "system", "content": "Pinned instruction"},
            {"id": "ref-2", "role": "user", "content": "Referenced question"},
            {"id": "ref-3", "role": "assistant", "content": "Referenced answer"},
        ]
        partial_snapshot = _snapshot(
            "partial summary after protected head",
            self.filter._message_refs_for_prefix(ref_messages, 2),
            protected_head_count=1,
        )

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [partial_snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return ref_messages

        async def fail_summary_llm(*args, **kwargs):
            raise AssertionError("protected-head mixed block should fit directly")

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._call_summary_llm = fail_summary_llm
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 10000
        }
        self.filter._estimate_messages_tokens = lambda messages: 1

        result = asyncio.run(
            self.filter._handle_external_chat_references(
                {
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
                },
                user_data={"id": "user-1"},
            )
        )

        content = result["__external_references__"]["content"]
        self.assertIn("<protected_head_original_messages>", content)
        self.assertIn("Pinned instruction", content)
        self.assertIn("partial summary after protected head", content)
        self.assertIn("Referenced answer", content)

    def test_handle_external_chat_references_saves_generated_continuation_summary(self):
        ref_messages = [
            {"id": "ref-1", "role": "user", "content": "Referenced question"},
            {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
            {"id": "ref-3", "role": "user", "content": "Referenced follow-up"},
            {"id": "ref-4", "role": "assistant", "content": "Referenced final"},
        ]
        partial_refs = self.filter._message_refs_for_prefix(ref_messages, 2)
        partial_snapshot = _snapshot("partial cached summary", partial_refs)
        captured_llm = {}
        saved = {}

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            if saved and require_full_coverage:
                saved_snapshot = _snapshot(
                    saved["summary"], saved["covered_message_refs"]
                )
                return self.filter._select_applicable_summary_snapshot(
                    [saved_snapshot],
                    messages,
                    require_full_coverage=require_full_coverage,
                    live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                    max_coverage_count=max_coverage_count,
                    enforce_keep_first=enforce_keep_first,
                )
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [partial_snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return ref_messages

        async def fake_summary_llm(
            new_conversation_text,
            body,
            user_data,
            event_call=None,
            request=None,
            previous_summary=None,
        ):
            captured_llm["calls"] = captured_llm.get("calls", 0) + 1
            captured_llm["new_conversation_text"] = new_conversation_text
            captured_llm["previous_summary"] = previous_summary
            return "updated continuation summary"

        async def fake_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            saved.update(
                {
                    "chat_id": chat_id,
                    "summary": summary,
                    "compressed_count": compressed_count,
                    "covered_message_refs": covered_message_refs,
                    "protected_head_count": protected_head_count,
                }
            )
            return True

        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 100
        }
        self.filter._get_summary_model_context_limit = lambda model_id: 10000
        self.filter._estimate_messages_tokens = lambda messages: 20
        self.filter.valves.max_summary_tokens = 4096

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

        content = result["__external_references__"]["content"]
        self.assertIn("updated continuation summary", content)
        self.assertEqual(captured_llm["previous_summary"], "partial cached summary")
        self.assertIn("Referenced follow-up", captured_llm["new_conversation_text"])
        self.assertEqual(saved["chat_id"], "chat-ref-1")
        self.assertEqual(saved["summary"], "updated continuation summary")
        self.assertEqual(saved["compressed_count"], 4)
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["ref-1", "ref-2", "ref-3", "ref-4"],
        )
        self.assertEqual(captured_llm["calls"], 1)

        second_result = asyncio.run(
            self.filter._handle_external_chat_references(
                deepcopy(body),
                user_data={"id": "user-1"},
            )
        )

        self.assertIn(
            "updated continuation summary",
            second_result["__external_references__"]["content"],
        )
        self.assertEqual(captured_llm["calls"], 1)

    def test_handle_external_chat_references_keeps_unsummarized_tail_after_fitted_continuation(
        self,
    ):
        ref_messages = [
            {"id": "ref-1", "role": "user", "content": "Referenced question"},
            {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
            {"id": "ref-3", "role": "user", "content": "First fitted tail"},
            {"id": "ref-4", "role": "assistant", "content": "Unsummarized remainder"},
            {"id": "ref-5", "role": "user", "content": "Latest unsummarized tail"},
        ]
        partial_refs = self.filter._message_refs_for_prefix(ref_messages, 2)
        partial_snapshot = _snapshot("partial cached summary", partial_refs)
        captured_llm = {}
        saved = {}
        logs = []

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [partial_snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return ref_messages

        async def fake_summary_llm(
            new_conversation_text,
            body,
            user_data,
            event_call=None,
            request=None,
            previous_summary=None,
        ):
            captured_llm["body"] = body
            captured_llm["new_conversation_text"] = new_conversation_text
            captured_llm["previous_summary"] = previous_summary
            return "generated prefix continuation summary"

        async def fake_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            saved.update(
                {
                    "chat_id": chat_id,
                    "summary": summary,
                    "compressed_count": compressed_count,
                    "covered_message_refs": covered_message_refs,
                    "source_current_id": source_current_id,
                }
            )
            return True

        async def fake_log(message, *args, **kwargs):
            logs.append(message)

        self.filter.valves.summary_model = "configured-summary-model"
        self.filter.valves.max_summary_tokens = 4096
        self.filter._log = fake_log
        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 100
        }
        self.filter._get_summary_model_context_limit = lambda model_id: 1
        self.filter._estimate_messages_tokens = lambda messages: 80
        self.filter._format_prefix_messages_for_summary_with_count = (
            lambda messages, max_tokens: (
                self.filter._format_messages_for_summary(messages[:1]),
                1,
            )
        )

        original_estimator = module._estimate_text_tokens

        def fake_estimate_text_tokens(text):
            text = str(text)
            if "partial cached summary" in text and "Unsummarized" in text:
                return 1000
            if "Return only the XML working memory" in text and "Unsummarized" in text:
                return 1000
            return 1

        module._estimate_text_tokens = fake_estimate_text_tokens

        try:
            result = asyncio.run(
                self.filter._handle_external_chat_references(
                    {
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
                    },
                    user_data={"id": "user-1"},
                    __event_call__=object(),
                )
            )
        finally:
            module._estimate_text_tokens = original_estimator

        content = result["__external_references__"]["content"]
        self.assertIn("generated prefix continuation summary", content)
        self.assertIn("Unsummarized remainder", content)
        self.assertIn("Latest unsummarized tail", content)
        self.assertIn("<generated_reference_summary>", content)
        self.assertIn("<recent_original_messages>", content)
        self.assertEqual(captured_llm["body"]["model"], "configured-summary-model")
        self.assertEqual(captured_llm["previous_summary"], "partial cached summary")
        self.assertIn("First fitted tail", captured_llm["new_conversation_text"])
        self.assertNotIn("Unsummarized remainder", captured_llm["new_conversation_text"])
        self.assertEqual(saved["compressed_count"], 3)
        self.assertEqual(saved["source_current_id"], "ref-3")
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["ref-1", "ref-2", "ref-3"],
        )
        log_text = "\n".join(logs)
        self.assertIn("summarizing 1 contiguous tail message(s)", log_text)
        self.assertIn("Added 2 unsummarized tail message(s)", log_text)
        self.assertNotIn("Unsummarized remainder", log_text)
        self.assertNotIn("generated prefix continuation summary", log_text)

    def test_handle_external_chat_references_fits_generated_summary_to_keep_latest_tail(
        self,
    ):
        older_remainder = "Older unsummarized remainder " + ("old-detail " * 80)
        latest_remainder = "Latest unsummarized tail " + ("latest-detail " * 20)
        ref_messages = [
            {"id": "ref-1", "role": "user", "content": "Referenced question"},
            {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
            {"id": "ref-3", "role": "user", "content": "First fitted tail"},
            {"id": "ref-4", "role": "assistant", "content": older_remainder},
            {"id": "ref-5", "role": "user", "content": latest_remainder},
        ]
        partial_refs = self.filter._message_refs_for_prefix(ref_messages, 2)
        partial_snapshot = _snapshot("partial cached summary", partial_refs)
        logs = []
        saved = {}

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [partial_snapshot],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, ref_messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return ref_messages

        async def fake_summary_llm(*args, **kwargs):
            return "generated continuation summary " + ("summary-detail " * 140)

        async def fake_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            saved.update(
                {
                    "compressed_count": compressed_count,
                    "covered_message_refs": covered_message_refs,
                    "source_current_id": source_current_id,
                }
            )
            return True

        async def fake_log(message, *args, **kwargs):
            logs.append(message)

        original_estimator = module._estimate_text_tokens

        def fake_estimate_text_tokens(text):
            return max(1, len(str(text)) // 20)

        self.filter.valves.summary_model = "configured-summary-model"
        self.filter.valves.max_summary_tokens = 400
        self.filter._log = fake_log
        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 60
        }
        self.filter._get_summary_model_context_limit = lambda model_id: 1000
        self.filter._estimate_messages_tokens = lambda messages: 20
        module._estimate_text_tokens = fake_estimate_text_tokens
        try:
            result = asyncio.run(
                self.filter._handle_external_chat_references(
                    {
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
                    },
                    user_data={"id": "user-1"},
                    __event_call__=object(),
                )
            )
        finally:
            module._estimate_text_tokens = original_estimator

        content = result["__external_references__"]["content"]
        self.assertIn("<generated_reference_summary>", content)
        self.assertIn("<recent_original_messages>", content)
        self.assertIn("Latest unsummarized tail", content)
        self.assertNotIn("Older unsummarized remainder", content)
        self.assertEqual(saved["compressed_count"], 3)
        self.assertEqual(saved["source_current_id"], "ref-3")
        self.assertEqual(
            [ref["id"] for ref in saved["covered_message_refs"]],
            ["ref-1", "ref-2", "ref-3"],
        )

        log_text = "\n".join(logs)
        self.assertIn("Fitted generated referenced context", log_text)
        self.assertIn("omitted 1 older unsummarized tail message(s)", log_text)
        self.assertNotIn("Latest unsummarized tail", log_text)
        self.assertNotIn("Older unsummarized remainder", log_text)

    def test_handle_external_chat_references_processes_multiple_references_in_attachment_order(
        self,
    ):
        ref_one_messages = [
            {"id": "one-1", "role": "user", "content": "Chat One question"},
            {"id": "one-2", "role": "assistant", "content": "Chat One answer"},
            {"id": "one-3", "role": "user", "content": "Chat One tail"},
        ]
        ref_two_messages = [
            {"id": "two-1", "role": "user", "content": "Chat Two question"},
            {"id": "two-2", "role": "assistant", "content": "Chat Two answer"},
            {"id": "two-3", "role": "user", "content": "Chat Two tail"},
        ]
        messages_by_chat = {
            "chat-one": ref_one_messages,
            "chat-two": ref_two_messages,
        }
        snapshots_by_chat = {
            "chat-one": _snapshot(
                "chat one partial summary",
                self.filter._message_refs_for_prefix(ref_one_messages, 2),
            ),
            "chat-two": _snapshot(
                "chat two partial summary",
                self.filter._message_refs_for_prefix(ref_two_messages, 2),
            ),
        }
        summary_calls = []

        async def fake_load_snapshot(
            chat_id,
            messages,
            require_full_coverage=False,
            max_coverage_count=None,
            enforce_keep_first=True,
        ):
            if require_full_coverage:
                return None
            return self.filter._select_applicable_summary_snapshot(
                [snapshots_by_chat[chat_id]],
                messages,
                require_full_coverage=require_full_coverage,
                live_message_refs_by_id=_live_refs_by_id(self.filter, messages),
                max_coverage_count=max_coverage_count,
                enforce_keep_first=enforce_keep_first,
            )

        async def fake_load_authorized_full_chat_messages(chat_id, user_data=None):
            return messages_by_chat[chat_id]

        async def fake_summary_llm(
            new_conversation_text,
            body,
            user_data,
            event_call=None,
            request=None,
            previous_summary=None,
        ):
            summary_calls.append(
                {
                    "body": body,
                    "previous_summary": previous_summary,
                    "input": new_conversation_text,
                }
            )
            return "generated chat two summary"

        async def fake_save_summary(*args, **kwargs):
            return True

        original_estimator = module._estimate_text_tokens

        def fake_estimate_text_tokens(text):
            text = str(text)
            if "generated chat two summary" in text:
                return 1
            if "Chat One tail" in text or "Chat Two tail" in text:
                return 2
            return 1

        self.filter.valves.summary_model = "configured-summary-model"
        self.filter.valves.max_summary_tokens = 4096
        self.filter._load_applicable_summary_snapshot = fake_load_snapshot
        self.filter._load_authorized_full_chat_messages = (
            fake_load_authorized_full_chat_messages
        )
        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._get_model_thresholds = lambda model_id: {
            "max_context_tokens": 4
        }
        self.filter._get_summary_model_context_limit = lambda model_id: 1000
        self.filter._estimate_messages_tokens = lambda messages: 1
        module._estimate_text_tokens = fake_estimate_text_tokens
        try:
            result = asyncio.run(
                self.filter._handle_external_chat_references(
                    {
                        "model": "main-model",
                        "messages": [{"role": "user", "content": "Current prompt"}],
                        "metadata": {
                            "files": [
                                {
                                    "type": "chat",
                                    "id": "chat-one",
                                    "name": "Chat One",
                                },
                                {
                                    "type": "chat",
                                    "id": "chat-two",
                                    "name": "Chat Two",
                                },
                            ]
                        },
                    },
                    user_data={"id": "user-1"},
                )
            )
        finally:
            module._estimate_text_tokens = original_estimator

        content = result["__external_references__"]["content"]
        self.assertIn("chat one partial summary", content)
        self.assertIn("Chat One tail", content)
        self.assertIn("generated chat two summary", content)
        self.assertNotIn("Chat Two tail", content)
        self.assertEqual(len(summary_calls), 1)
        self.assertEqual(
            summary_calls[0]["previous_summary"],
            "chat two partial summary",
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
        async def noop_save_summary(*args, **kwargs):
            return None

        async def fake_load_full_chat_messages(chat_id):
            return [{"id": "ref-1", "role": "user", "content": "msg 1"}]

        self.filter._save_summary = noop_save_summary
        self.filter._load_full_chat_messages = fake_load_full_chat_messages
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

        async def fake_save_summary(
            chat_id,
            summary,
            compressed_count,
            covered_message_refs=None,
            source_current_id=None,
            protected_head_count=0,
        ):
            captured["saved"] = (
                chat_id,
                summary,
                compressed_count,
                covered_message_refs,
                source_current_id,
                protected_head_count,
            )

        async def noop_log(*args, **kwargs):
            return None

        self.filter._call_summary_llm = fake_summary_llm
        self.filter._save_summary = fake_save_summary
        self.filter._log = noop_log

        async def fake_load_full_chat_messages(chat_id):
            return [
                {"id": "ref-1", "role": "user", "content": "Referenced question"},
                {"id": "ref-2", "role": "assistant", "content": "Referenced answer"},
                {"id": "ref-3", "role": "user", "content": "Referenced follow-up"},
            ]

        self.filter._load_full_chat_messages = fake_load_full_chat_messages

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
        (
            saved_chat_id,
            saved_summary,
            saved_count,
            saved_refs,
            saved_source_id,
            saved_protected_head_count,
        ) = captured["saved"]
        self.assertEqual(saved_chat_id, "chat-ref-1")
        self.assertEqual(saved_summary, "cached reference summary")
        self.assertEqual(saved_count, 3)
        self.assertEqual([ref["id"] for ref in saved_refs], ["ref-1", "ref-2", "ref-3"])
        self.assertIsNone(saved_source_id)
        self.assertEqual(saved_protected_head_count, 0)

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
        async def fake_save_summary(*args, **kwargs):
            saved_calls.append(args)

        self.filter._save_summary = fake_save_summary
        self.filter._log = noop_log
        async def fake_load_full_chat_messages(chat_id):
            return [
            {"role": "user", "content": "msg 1"},
            {"role": "assistant", "content": "msg 2"},
            ]

        self.filter._load_full_chat_messages = fake_load_full_chat_messages
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
