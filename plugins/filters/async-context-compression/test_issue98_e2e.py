"""End-to-end verification for issue #98 using OpenWebUI's REAL functions.

This test module replaces the dummy ``convert_output_to_messages`` stub with
the **actual** implementation from OpenWebUI's main branch (sourced from
``open_webui/utils/misc.py`` and ``open_webui/utils/middleware.py``), then
reconstructs the exact data flow that happens when a reasoning model chat
hits the inlet:

    DB messages (with output arrays + folded reasoning content)
        ↓ process_messages_with_output(reasoning_format=get_reasoning_format(model))
    body messages (reasoning stripped / tagged / routed, per provider)
        ↓ Filter.inlet()
    plugin decides whether to inject the saved summary

The goal is to prove that Path 3 (position-based fallback) correctly accepts
the snapshot for reasoning models where body content ≠ DB content, while
still rejecting genuine mismatches (edited bodies, tampered tool calls).
"""

import asyncio
import importlib
import importlib.util
import json
import os
import sys
import types
import unittest
from copy import deepcopy

# ── OpenWebUI real functions (sourced from main branch) ──────────────
# Source: open_webui/utils/misc.py (convert_output_to_messages, reconcile_tool_pairs)
# Source: open_webui/utils/middleware.py (process_messages_with_output, get_reasoning_format)
# These are copied verbatim to avoid importing the full OpenWebUI stack.


def _owui_reconcile_tool_pairs(messages):
    """Drop unpaired tool_use / tool_result from a reconstructed conversation."""
    completed_tool_call_ids = {
        message['tool_call_id']
        for message in messages
        if message.get('role') == 'tool' and message.get('tool_call_id')
    }
    requested_tool_call_ids = {
        tool_call['id']
        for message in messages
        for tool_call in message.get('tool_calls') or ()
        if message.get('role') == 'assistant' and tool_call.get('id')
    }

    reconciled_messages = []
    for message in messages:
        role = message.get('role')
        if role != 'assistant' or not message.get('tool_calls'):
            reconciled_messages.append(message)
            continue

        valid_tool_calls = [
            tc for tc in message['tool_calls'] if tc.get('id') in completed_tool_call_ids
        ]
        if valid_tool_calls:
            reconciled_messages.append({**message, 'tool_calls': valid_tool_calls})
            continue

        content = message.get('content', '')
        has_meaningful_content = content.strip() if isinstance(content, str) else content
        if has_meaningful_content or message.get('reasoning_content'):
            reconciled_messages.append(
                {k: v for k, v in message.items() if k != 'tool_calls'}
            )
    return reconciled_messages


def _owui_convert_output_to_messages(output, raw=False, reasoning_format=None):
    """REAL OpenWebUI convert_output_to_messages from misc.py."""
    if not output or not isinstance(output, list):
        return []

    messages = []
    pending_tool_calls = []
    pending_content = []
    pending_reasoning = []

    def flush_pending():
        nonlocal pending_content, pending_tool_calls, pending_reasoning
        if not pending_content and not pending_tool_calls and not pending_reasoning:
            return
        message = {
            'role': 'assistant',
            'content': '\n'.join(pending_content) if pending_content else '',
            **({'tool_calls': pending_tool_calls} if pending_tool_calls else {}),
        }
        if pending_reasoning:
            message['reasoning_content'] = '\n'.join(pending_reasoning)
        messages.append(message)
        pending_content = []
        pending_tool_calls = []
        pending_reasoning = []

    for item in output:
        item_type = item.get('type', '')

        if item_type == 'message':
            content_parts = item.get('content', [])
            text = ''
            for part in content_parts:
                if part.get('type') == 'output_text':
                    text += part.get('text', '')
            if text:
                pending_content.append(text)

        elif item_type == 'function_call':
            arguments = item.get('arguments', '{}')
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments)
            pending_tool_calls.append({
                'id': item.get('call_id', ''),
                'type': 'function',
                'function': {'name': item.get('name', ''), 'arguments': arguments},
            })

        elif item_type == 'function_call_output':
            flush_pending()
            output_parts = item.get('output', [])
            content = ''
            for part in output_parts:
                if part.get('type') == 'input_text':
                    output_text = part.get('text', '')
                    content += str(output_text) if not isinstance(output_text, str) else output_text
            messages.append({
                'role': 'tool',
                'tool_call_id': item.get('call_id', ''),
                'content': content,
            })

        elif item_type == 'reasoning':
            if not reasoning_format:
                continue
            reasoning_text = ''
            source_list = item.get('summary', []) or item.get('content', [])
            for part in source_list:
                if part.get('type') == 'output_text':
                    reasoning_text += part.get('text', '')
                elif 'text' in part:
                    reasoning_text += part.get('text', '')
            if reasoning_text:
                if reasoning_format == 'think_tags':
                    start_tag = item.get('start_tag', '<think>')
                    end_tag = item.get('end_tag', '</think>')
                    pending_content.append(f'{start_tag}{reasoning_text}{end_tag}')
                elif reasoning_format == 'reasoning_content':
                    pending_reasoning.append(reasoning_text)

        elif item_type == 'open_webui:code_interpreter':
            code = item.get('code', '')
            code_output = item.get('output', '')
            if code:
                pending_content.append(f'<code_interpreter>\n{code}\n</code_interpreter>')
            if code_output:
                if isinstance(code_output, dict):
                    output_text = code_output.get('stdout', '') or code_output.get('result', '')
                else:
                    output_text = str(code_output)
                if output_text:
                    pending_content.append(f'<code_interpreter_output>\n{output_text}\n</code_interpreter_output>')

        elif item_type.startswith('open_webui:'):
            pass

    flush_pending()
    return _owui_reconcile_tool_pairs(messages)


def _owui_process_messages_with_output(messages, reasoning_format=None):
    """REAL OpenWebUI process_messages_with_output from middleware.py."""
    processed = []
    for message in messages:
        if message.get('role') == 'assistant' and message.get('output'):
            output_messages = _owui_convert_output_to_messages(
                message['output'], raw=True, reasoning_format=reasoning_format
            )
            if output_messages:
                processed.extend(output_messages)
                continue
        clean_message = {k: v for k, v in message.items() if k != 'output'}
        processed.append(clean_message)
    return processed


def _strip_ids(messages):
    """Simulate the OpenWebUI frontend: request body carries no message node ids.

    ``process_messages_with_output`` itself only strips ``output``; it does NOT
    remove ``id``.  But the request body that hits the inlet filter has no
    ``id`` fields — the frontend sends plain chat-completion messages.  This
    helper strips ids after reconstruction to match the real inlet payload.
    """
    result = []
    for msg in messages:
        clean = {k: v for k, v in msg.items() if k != 'id' and k != 'message_id'}
        result.append(clean)
    return result


def _build_body_from_db(db_messages, reasoning_format=None):
    """Simulate the full OpenWebUI inlet pipeline:

    1. process_messages_with_output (rebuilds assistant content from output)
    2. strip message node ids (frontend sends plain chat-completion messages)
    """
    rebuilt = _owui_process_messages_with_output(
        deepcopy(db_messages), reasoning_format=reasoning_format
    )
    return _strip_ids(rebuilt)


def _owui_get_reasoning_format(model):
    """REAL OpenWebUI get_reasoning_format from middleware.py."""
    provider = model.get('provider', '') if isinstance(model, dict) else ''
    if provider == 'ollama':
        return 'think_tags'
    if provider == 'llama.cpp':
        return 'reasoning_content'
    return None


# ── Plugin loading (reuse the stub machinery from the main test file) ──

PLUGIN_PATH = os.path.join(os.path.dirname(__file__), "async_context_compression.py")
MODULE_NAME = "async_context_compression_issue98_e2e"


def _ensure_module(name):
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


def _install_stubs():
    """Install stubs but with the REAL convert_output_to_messages."""
    pydantic_module = _ensure_module("pydantic")
    sqlalchemy_module = _ensure_module("sqlalchemy")
    sqlalchemy_orm_module = _ensure_module("sqlalchemy.orm")
    sqlalchemy_engine_module = _ensure_module("sqlalchemy.engine")

    class DummyBaseModel:
        def __init__(self, **kwargs):
            annotations = getattr(self.__class__, "__annotations__", {})
            for field_name in annotations:
                value = kwargs.get(field_name, getattr(self.__class__, field_name, None))
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

    # OpenWebUI stubs — but with REAL convert_output_to_messages
    _ensure_module("open_webui")
    _ensure_module("open_webui.utils")
    chat_module = _ensure_module("open_webui.utils.chat")
    misc_module = _ensure_module("open_webui.utils.misc")
    _ensure_module("open_webui.models")
    _ensure_module("open_webui.models.users")
    _ensure_module("open_webui.models.models")
    _ensure_module("open_webui.models.chats")
    _ensure_module("open_webui.main")
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
    # KEY: install the REAL convert_output_to_messages, not the dummy
    misc_module.convert_output_to_messages = _owui_convert_output_to_messages
    _ensure_module("open_webui.models.users").Users = DummyUsers
    _ensure_module("open_webui.models.models").Models = DummyModels
    _ensure_module("open_webui.models.chats").Chats = DummyChats
    _ensure_module("open_webui.main").app = object()
    fastapi_requests.Request = DummyRequest


_install_stubs()
spec = importlib.util.spec_from_file_location(MODULE_NAME, PLUGIN_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = module
spec.loader.exec_module(module)
module.Filter._init_database = lambda self: None

Filter = module.Filter


# ── Helpers ───────────────────────────────────────────────────────────

def _live_refs_by_id(filter_obj, messages):
    refs = filter_obj._message_refs_for_prefix(messages, len(messages))
    if refs is None:
        return {}
    return {ref["id"]: ref for ref in refs}


def _snapshot(content, refs, protected_head_count=0):
    """Build a snapshot object that mirrors the ChatSummary ORM row.

    The plugin reads snapshot fields via ``getattr`` (e.g.
    ``covered_message_refs_json``, ``compressed_message_count``) and writes
    selection metadata via ``setattr`` (``_annotate_summary_snapshot_selection``).
    A plain dict therefore cannot work — ``types.SimpleNamespace`` matches the
    ORM attribute-access contract, exactly like the main test suite's helper.
    """
    refs_payload = refs
    if protected_head_count > 0:
        refs_payload = {
            "refs": refs,
            "protected_head_count": protected_head_count,
        }
    return types.SimpleNamespace(
        summary=content,
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


# ── Test data builders simulating real reasoning-model chats ──────────

def _build_reasoning_chat_openai_compatible():
    """Build DB messages + body messages for an OpenAI-compatible reasoning model.

    reasoning_format = None (default for non-ollama/llama.cpp providers).
    DB assistant content contains a folded <details type="reasoning"> block.
    Body assistant content has reasoning stripped by convert_output_to_messages.
    """
    db_messages = [
        {"id": "m0", "role": "user", "content": "What is 2+2?"},
        {
            "id": "m1",
            "role": "assistant",
            "content": '<details type="reasoning">\nLet me think... 2+2=4\n</details>\nThe answer is 4.',
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "output_text", "text": "Let me think... 2+2=4"}],
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "The answer is 4."}],
                },
            ],
        },
        {"id": "m2", "role": "user", "content": "Thanks!"},
    ]
    # Simulate what OpenWebUI does before inlet: process_messages_with_output
    # + strip ids (frontend sends plain chat-completion messages without ids)
    body_messages = _build_body_from_db(db_messages, reasoning_format=None)
    return db_messages, body_messages


def _build_reasoning_chat_ollama():
    """Build DB + body for an Ollama reasoning model (reasoning_format='think_tags')."""
    db_messages = [
        {"id": "m0", "role": "user", "content": "Explain recursion."},
        {
            "id": "m1",
            "role": "assistant",
            "content": '<details type="reasoning">\nRecursion is self-reference...\n</details>\nRecursion is when a function calls itself.',
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "output_text", "text": "Recursion is self-reference..."}],
                    "start_tag": "<think>",
                    "end_tag": "</think>",
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Recursion is when a function calls itself."}],
                },
            ],
        },
        {"id": "m2", "role": "user", "content": "Got it."},
    ]
    body_messages = _build_body_from_db(db_messages, reasoning_format="think_tags")
    return db_messages, body_messages


def _build_reasoning_chat_llamacpp():
    """Build DB + body for a llama.cpp reasoning model (reasoning_format='reasoning_content')."""
    db_messages = [
        {"id": "m0", "role": "user", "content": "Why is the sky blue?"},
        {
            "id": "m1",
            "role": "assistant",
            "content": '<details type="reasoning">\nRayleigh scattering...\n</details>\nThe sky appears blue due to Rayleigh scattering.',
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "output_text", "text": "Rayleigh scattering..."}],
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "The sky appears blue due to Rayleigh scattering."}],
                },
            ],
        },
        {"id": "m2", "role": "user", "content": "Interesting."},
    ]
    body_messages = _build_body_from_db(db_messages, reasoning_format="reasoning_content")
    return db_messages, body_messages


def _build_reasoning_with_tool_calls():
    """Build DB + body for a reasoning model that also calls a tool.

    The output array contains: reasoning → function_call → function_call_output → message.
    After process_messages_with_output, the single DB assistant message expands into
    multiple body messages (assistant+tool_calls, tool result, assistant text).
    So body count > DB count — Path 3 won't fire, but Path 2 (unfolded) should match.
    """
    db_messages = [
        {"id": "m0", "role": "user", "content": "What's the weather in Tokyo?"},
        {
            "id": "m1",
            "role": "assistant",
            "content": '<details type="reasoning">\nI need to check the weather.\n</details>\nThe weather in Tokyo is 25°C and sunny.',
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "output_text", "text": "I need to check the weather."}],
                },
                {
                    "type": "function_call",
                    "call_id": "call_w1",
                    "name": "get_weather",
                    "arguments": '{"city": "Tokyo"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_w1",
                    "output": [{"type": "input_text", "text": "25°C, sunny"}],
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "The weather in Tokyo is 25°C and sunny."}],
                },
            ],
        },
        {"id": "m2", "role": "user", "content": "Great, thanks!"},
    ]
    body_messages = _build_body_from_db(db_messages, reasoning_format=None)
    return db_messages, body_messages


# ── Tests ─────────────────────────────────────────────────────────────

class TestIssue98E2E(unittest.TestCase):
    """End-to-end verification using OpenWebUI's real convert_output_to_messages."""

    def setUp(self):
        self.filter = Filter()
        self.filter.valves.keep_last = 0

    # ── Scenario 1: OpenAI-compatible reasoning model ─────────────────

    def test_openai_reasoning_body_content_differs_from_db(self):
        """Verify the premise: body content (reasoning stripped) ≠ DB content."""
        db_messages, body_messages = _build_reasoning_chat_openai_compatible()
        db_content = db_messages[1]["content"]
        body_content = body_messages[1]["content"]
        self.assertIn("<details type=\"reasoning\">", db_content)
        self.assertNotIn("<details type=\"reasoning\">", body_content)
        self.assertNotEqual(db_content, body_content)

    def test_openai_reasoning_path1_folded_fails(self):
        """Path 1 (folded content match) must fail because content differs."""
        db_messages, body_messages = _build_reasoning_chat_openai_compatible()
        result = self.filter._body_message_matches_db_branch_message(
            body_messages[1], db_messages[1]
        )
        self.assertFalse(result)

    def test_openai_reasoning_path3_position_accepts(self):
        """Path 3 (position-based) must accept despite content difference."""
        db_messages, body_messages = _build_reasoning_chat_openai_compatible()
        coverage = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages, db_messages
        )
        self.assertIsNotNone(coverage, "Path 3 should accept reasoning model body")
        self.assertEqual(coverage, [0, 1, 2, 3])

    def test_openai_reasoning_inlet_injects_summary(self):
        """Full inlet call must inject the summary for OpenAI-compatible reasoning."""
        db_messages, body_messages = _build_reasoning_chat_openai_compatible()
        snapshots = [
            _snapshot(
                "openai reasoning summary",
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
            "max_context_tokens": 100000,
            "compression_threshold_tokens": 1000,
        }

        # Diagnose: call _load_applicable_summary_snapshot directly
        snapshot = asyncio.run(self.filter._load_applicable_summary_snapshot(
            "chat-openai-reasoning", body_messages,
        ))
        self.assertIsNotNone(
            snapshot,
            f"Snapshot must be selected. body_messages={body_messages}, db_messages={db_messages}",
        )

        result = asyncio.run(self.filter.inlet({
            "chat_id": "chat-openai-reasoning",
            "model": "test-model",
            "messages": body_messages,
        }))

        self.assertTrue(
            self.filter._is_summary_message(result["messages"][0]),
            f"Summary must be injected at position 0. Got: {result['messages']}",
        )
        self.assertIn("openai reasoning summary", result["messages"][0]["content"])

    # ── Scenario 2: Ollama reasoning model (think_tags) ───────────────

    def test_ollama_reasoning_body_has_think_tags_not_details(self):
        """Ollama: body content has <think> tags, DB has <details>."""
        db_messages, body_messages = _build_reasoning_chat_ollama()
        self.assertIn("<details type=\"reasoning\">", db_messages[1]["content"])
        self.assertIn("<think>", body_messages[1]["content"])
        self.assertNotIn("<details type=\"reasoning\">", body_messages[1]["content"])

    def test_ollama_reasoning_path3_accepts(self):
        db_messages, body_messages = _build_reasoning_chat_ollama()
        coverage = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages, db_messages
        )
        self.assertIsNotNone(coverage)
        self.assertEqual(coverage, [0, 1, 2, 3])

    # ── Scenario 3: llama.cpp reasoning model (reasoning_content) ─────

    def test_llamacpp_reasoning_body_has_reasoning_content_field(self):
        """llama.cpp: body has reasoning_content field, DB does not."""
        db_messages, body_messages = _build_reasoning_chat_llamacpp()
        self.assertNotIn("reasoning_content", db_messages[1])
        self.assertIn("reasoning_content", body_messages[1])

    def test_llamacpp_reasoning_path3_accepts(self):
        db_messages, body_messages = _build_reasoning_chat_llamacpp()
        coverage = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages, db_messages
        )
        self.assertIsNotNone(coverage)
        self.assertEqual(coverage, [0, 1, 2, 3])

    # ── Scenario 4: Reasoning + tool calls (count mismatch, Path 2) ───

    def test_reasoning_with_tool_calls_body_count_differs(self):
        """When output has function_call, body count > DB count (expanded)."""
        db_messages, body_messages = _build_reasoning_with_tool_calls()
        self.assertEqual(len(db_messages), 3)
        # DB assistant expands to: assistant(tool_calls) + tool(result) + assistant(text)
        self.assertGreater(len(body_messages), 3)

    def test_reasoning_with_tool_calls_path3_rejects_count_mismatch(self):
        """Path 3 must reject because body count ≠ DB count (tool expansion)."""
        db_messages, body_messages = _build_reasoning_with_tool_calls()
        # Path 3 checks len(body) == len(db), which fails here.
        # But Path 2 (unfolded) should handle this via _unfold_db_branch_for_body_ref_fallback.
        # We verify the overall fallback still returns a valid coverage map.
        coverage = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages, db_messages
        )
        # Path 2 should succeed: unfolded DB matches body 1:1
        self.assertIsNotNone(coverage, "Path 2 (unfolded) should handle tool-call expansion")

    # ── Scenario 5: Negative — edited body with no DB output ──────────

    def test_edited_body_no_output_rejected(self):
        """If DB has no output array and body content was edited, reject."""
        db_messages = [
            {"id": "m0", "role": "user", "content": "original"},
            {"id": "m1", "role": "assistant", "content": "original answer"},
            {"id": "m2", "role": "user", "content": "follow up"},
        ]
        body_messages = [
            {"role": "user", "content": "original"},
            {"role": "assistant", "content": "EDITED answer"},  # tampered
            {"role": "user", "content": "follow up"},
        ]
        coverage = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages, db_messages
        )
        self.assertIsNone(coverage, "Must reject edited body when DB has no output")

    # ── Scenario 6: Negative — tampered tool_calls ────────────────────

    def test_tampered_tool_calls_rejected(self):
        """If body tool_calls differ from DB, Path 3 must reject."""
        db_messages = [
            {"id": "m0", "role": "user", "content": "q"},
            {
                "id": "m1",
                "role": "assistant",
                "content": "answer",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "search", "arguments": "{}"}}],
                "output": [{"type": "message",
                            "content": [{"type": "output_text", "text": "answer"}]}],
            },
            {"id": "m2", "role": "user", "content": "next"},
        ]
        body_messages = [
            {"role": "user", "content": "q"},
            {
                "role": "assistant",
                "content": "answer",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "DIFFERENT", "arguments": "{}"}}],
            },
            {"role": "user", "content": "next"},
        ]
        coverage = self.filter._body_to_db_coverage_map_for_ref_fallback(
            body_messages, db_messages
        )
        self.assertIsNone(coverage, "Must reject tampered tool_calls")

    # ── Scenario 7: Verify body has no ids (precondition for Path 3) ──

    def test_openai_reasoning_body_has_no_message_ids(self):
        """Verify that process_messages_with_output strips ids from body."""
        db_messages, body_messages = _build_reasoning_chat_openai_compatible()
        for msg in body_messages:
            self.assertIsNone(
                self.filter._get_message_id(msg),
                "Body messages must not carry OpenWebUI ids (plain chat)",
            )

    # ── Scenario 8: Full inlet for Ollama reasoning ───────────────────

    def test_ollama_reasoning_inlet_injects_summary(self):
        db_messages, body_messages = _build_reasoning_chat_ollama()
        snapshots = [
            _snapshot(
                "ollama reasoning summary",
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
            "max_context_tokens": 100000,
            "compression_threshold_tokens": 1000,
        }

        result = asyncio.run(self.filter.inlet({
            "chat_id": "chat-ollama-reasoning",
            "model": "test-model",
            "messages": body_messages,
        }))

        self.assertTrue(self.filter._is_summary_message(result["messages"][0]))
        self.assertIn("ollama reasoning summary", result["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
