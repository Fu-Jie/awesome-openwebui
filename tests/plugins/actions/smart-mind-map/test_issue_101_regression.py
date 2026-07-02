"""Regression test for issue #101: Smart Mind Map crashes OWUI v0.10+ frontend.

Issue: On OpenWebUI v0.10+, clicking the Smart Mind Map action produces
``Cannot read properties of undefined (reading 'content')`` at
``Chat.svelte`` (inside ``chatActionHandler``).

Two layers of the bug are covered here:

1. **Frontend crash** — the action's early-return paths appended a *new*
   message dict without an ``id`` field to ``body["messages"]``:

       body["messages"].append({"role": "assistant", "content": "❌ ..."})

   The OWUI v0.10+ frontend iterates the returned ``messages`` and does
   ``history.messages[message.id].content`` for each entry. When
   ``message.id`` is ``undefined``, ``history.messages[undefined]`` is
   ``undefined`` and accessing ``.content`` throws. Fixed by updating the
   existing last message (which carries a valid id) in place.

2. **Empty content on v0.10** — OWUI v0.10+ stores assistant replies in a
   structured ``output`` field and leaves the flat ``content`` empty, so the
   plugin's ``_extract_text_content`` returned nothing and the action hit the
   early-return path even when the assistant reply was perfectly valid. Fixed
   by ``_recover_message_content``: rebuild text from ``msg.output`` (inline)
   or via ``ChatMessages.get_message_by_id`` DB lookup using OWUI's own
   ``convert_output_to_messages``.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Mock the ``open_webui`` packages that smart_mind_map.py imports at load
# time, so the module can be imported in a standalone test environment.
# ---------------------------------------------------------------------------
# Mutable registries so individual tests can swap implementations.
_FAKE_DB_RECORDS: dict = {}
_FAKE_CONVERT_OUTPUT = None


def _fake_convert_output_to_messages(output):
    """Test-only stand-in for OWUI's convert_output_to_messages.

    Recognises a simple ``[{"type": "text", "content": "..."}]`` shape and
    returns ``[{"role": "assistant", "content": "..."}]`` so the plugin's
    recovery path can rebuild text. Tests that need to simulate a specific
    structured-output schema can override ``_FAKE_CONVERT_OUTPUT``.
    """
    if _FAKE_CONVERT_OUTPUT is not None:
        return _FAKE_CONVERT_OUTPUT(output)
    if not isinstance(output, list):
        return []
    out = []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "text":
            out.append({"role": "assistant", "content": item.get("content", "")})
    return out


class _FakeChatMessages:
    """Test-only stand-in for OWUI's ChatMessages model."""

    @staticmethod
    async def get_message_by_id(message_id):
        return _FAKE_DB_RECORDS.get(message_id)


_MOCK_MODULES = {
    "open_webui": types.ModuleType("open_webui"),
    "open_webui.utils": types.ModuleType("open_webui.utils"),
    "open_webui.utils.chat": types.ModuleType("open_webui.utils.chat"),
    "open_webui.utils.misc": types.ModuleType("open_webui.utils.misc"),
    "open_webui.models": types.ModuleType("open_webui.models"),
    "open_webui.models.users": types.ModuleType("open_webui.models.users"),
    "open_webui.models.chat_messages": types.ModuleType("open_webui.models.chat_messages"),
    "open_webui.env": types.ModuleType("open_webui.env"),
}
_MOCK_MODULES["open_webui.utils.chat"].generate_chat_completion = lambda *a, **kw: None
_MOCK_MODULES["open_webui.utils.misc"].convert_output_to_messages = (
    _fake_convert_output_to_messages
)
_MOCK_MODULES["open_webui.models.users"].Users = types.SimpleNamespace(
    get_user_by_id=lambda *a, **kw: None
)
_MOCK_MODULES["open_webui.models.chat_messages"].ChatMessages = _FakeChatMessages
_MOCK_MODULES["open_webui.env"].VERSION = "0.10.2"
for _name, _mod in _MOCK_MODULES.items():
    sys.modules.setdefault(_name, _mod)

MODULE_PATH = (
    Path(__file__).resolve().parents[4]
    / "plugins"
    / "actions"
    / "smart-mind-map"
    / "smart_mind_map.py"
)
SPEC = importlib.util.spec_from_file_location("smart_mind_map_under_test", MODULE_PATH)
smart_mind_map = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = smart_mind_map
SPEC.loader.exec_module(smart_mind_map)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_action():
    return smart_mind_map.Action()


def _body_with_assistant(content: str, msg_id: str = "msg-asst-1"):
    """Build a minimal action body that mirrors what OWUI v0.10 frontend sends.

    Each message carries an ``id`` — this is what the frontend later uses to
    look the message up in ``history.messages``.
    """
    return {
        "model": "test-model",
        "messages": [
            {"id": "msg-user-1", "role": "user", "content": "Please summarize."},
            {"id": msg_id, "role": "assistant", "content": content},
        ],
        "chat_id": "chat-1",
        "session_id": "sess-1",
        "id": msg_id,
    }


async def _noop_emitter(*args, **kwargs):
    return None


# ---------------------------------------------------------------------------
# Unit tests for the _set_last_message_content helper
# ---------------------------------------------------------------------------
class TestSetLastMessageContent:
    def test_updates_last_message_content_in_place(self):
        action = _make_action()
        body = {
            "messages": [
                {"id": "a", "role": "user", "content": "hi"},
                {"id": "b", "role": "assistant", "content": "hello"},
            ]
        }
        action._set_last_message_content(body, "❌ error")
        assert body["messages"][-1]["content"] == "❌ error"
        # The id must be preserved — OWUI frontend needs it.
        assert body["messages"][-1]["id"] == "b"
        # No new message appended.
        assert len(body["messages"]) == 2

    def test_preserves_other_fields_of_last_message(self):
        action = _make_action()
        body = {
            "messages": [
                {
                    "id": "x",
                    "role": "assistant",
                    "content": "old",
                    "timestamp": 123,
                    "sources": ["s1"],
                }
            ]
        }
        action._set_last_message_content(body, "new content")
        last = body["messages"][-1]
        assert last["content"] == "new content"
        assert last["id"] == "x"
        assert last["timestamp"] == 123
        assert last["sources"] == ["s1"]

    def test_noop_when_messages_missing(self):
        action = _make_action()
        body = {}
        action._set_last_message_content(body, "err")
        assert body == {}

    def test_noop_when_messages_empty(self):
        action = _make_action()
        body = {"messages": []}
        action._set_last_message_content(body, "err")
        assert body["messages"] == []

    def test_noop_when_body_is_none(self):
        action = _make_action()
        # Should not raise.
        action._set_last_message_content(None, "err")

    def test_handles_non_dict_last_message(self):
        action = _make_action()
        body = {"messages": ["not-a-dict"]}
        action._set_last_message_content(body, "recovered")
        assert body["messages"][-1]["content"] == "recovered"


# ---------------------------------------------------------------------------
# Integration tests for the action() early-return paths (issue #101 core)
# ---------------------------------------------------------------------------
class TestActionEarlyReturnNoIdlessMessages:
    """Every message in the returned body MUST carry an ``id``.

    This is the invariant the OWUI v0.10+ frontend relies on. Before the fix,
    the early-return paths appended ``{"role": "assistant", "content": ...}``
    (no id), which crashed the frontend.
    """

    @pytest.mark.asyncio
    async def test_path_no_messages_does_not_append_idless_message(self):
        action = _make_action()
        body = {"model": "test-model", "messages": "not-a-list"}
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        # No new message appended.
        assert result["messages"] == "not-a-list"

    @pytest.mark.asyncio
    async def test_path_empty_content_updates_last_message_no_append(self):
        action = _make_action()
        body = _body_with_assistant(content="")
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        msgs = result["messages"]
        # No new message appended — still 2 messages.
        assert len(msgs) == 2
        # Every message still has an id.
        assert all("id" in m for m in msgs), [m for m in msgs if "id" not in m]
        # Last message content was updated with the error.
        assert "❌" in msgs[-1]["content"]
        assert msgs[-1]["id"] == "msg-asst-1"

    @pytest.mark.asyncio
    async def test_path_short_text_updates_last_message_no_append(self):
        action = _make_action()
        body = _body_with_assistant(content="hi")  # shorter than MIN_TEXT_LENGTH (100)
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        msgs = result["messages"]
        assert len(msgs) == 2
        assert all("id" in m for m in msgs)
        # Last message contains the original short text + the warning.
        assert "hi" in msgs[-1]["content"]
        assert "⚠️" in msgs[-1]["content"]
        assert msgs[-1]["id"] == "msg-asst-1"

    @pytest.mark.asyncio
    async def test_all_returned_messages_have_id(self):
        """Critical invariant for OWUI v0.10+ frontend: no id-less messages."""
        action = _make_action()
        body = _body_with_assistant(content="")
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        for m in result["messages"]:
            assert "id" in m, f"Message without id would crash OWUI v0.10 frontend: {m}"
            assert m["id"] is not None

    @pytest.mark.asyncio
    async def test_multimodal_empty_content_list_triggers_safe_path(self):
        """Content as an empty list (multimodal with no text part) must not
        crash the frontend either."""
        action = _make_action()
        body = _body_with_assistant(content=[])
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        msgs = result["messages"]
        assert all("id" in m for m in msgs)
        assert len(msgs) == 2  # no append


# ---------------------------------------------------------------------------
# OWUI v0.10+ structured-output recovery (the *second* layer of issue #101)
# ---------------------------------------------------------------------------
class TestRecoverContentFromOutput:
    """OWUI v0.10+ stores assistant replies in a structured ``output`` field
    and leaves ``content`` empty. The plugin must rebuild the text instead of
    reporting "no content found to export".
    """

    def test_extract_text_from_output_rebuilds_assistant_text(self):
        action = _make_action()
        output = [{"type": "text", "content": "Hello world"}]
        assert action._extract_text_from_output(output) == "Hello world"

    def test_extract_text_from_output_empty_when_no_text_part(self):
        action = _make_action()
        assert action._extract_text_from_output([]) == ""
        assert action._extract_text_from_output(None) == ""
        assert action._extract_text_from_output([{"type": "image_url"}]) == ""

    def test_extract_text_from_output_skips_reasoning_role(self):
        """Reasoning is carried in a separate ``reasoning`` field by OWUI's
        ``convert_output_to_messages``; only ``content`` is joined."""
        action = _make_action()
        output = [{"type": "text", "content": "final answer"}]
        global _FAKE_CONVERT_OUTPUT
        _FAKE_CONVERT_OUTPUT = lambda out: [
            {"role": "assistant", "content": "final answer", "reasoning": "thinking..."},
        ]
        try:
            assert action._extract_text_from_output(output) == "final answer"
        finally:
            _FAKE_CONVERT_OUTPUT = None

    @pytest.mark.asyncio
    async def test_recover_uses_inline_output_when_content_empty(self):
        """When ``msg.content`` is empty but ``msg.output`` carries the text,
        recovery should populate ``msg.content`` from ``output``."""
        action = _make_action()
        body = {
            "chat_id": "chat-1",
            "id": "msg-asst-1",
            "messages": [
                {
                    "id": "msg-asst-1",
                    "role": "assistant",
                    "content": "",
                    "output": [{"type": "text", "content": "Recovered inline text"}],
                }
            ],
        }
        msg = body["messages"][0]
        recovered = await action._recover_message_content(body, msg)
        assert recovered == "Recovered inline text"
        # Backfilled onto the message for downstream code.
        assert msg["content"] == "Recovered inline text"

    @pytest.mark.asyncio
    async def test_recover_uses_db_lookup_when_content_and_output_empty(self):
        """When both ``content`` and ``output`` are absent, recovery should
        fall back to ``ChatMessages.get_message_by_id``."""
        action = _make_action()
        _FAKE_DB_RECORDS.clear()
        _FAKE_DB_RECORDS["chat-1-msg-asst-1"] = types.SimpleNamespace(
            output=[{"type": "text", "content": "Recovered from DB"}]
        )
        try:
            body = {
                "chat_id": "chat-1",
                "id": "msg-asst-1",
                "messages": [
                    {"id": "msg-asst-1", "role": "assistant", "content": ""},
                ],
            }
            msg = body["messages"][0]
            recovered = await action._recover_message_content(body, msg)
            assert recovered == "Recovered from DB"
            assert msg["content"] == "Recovered from DB"
        finally:
            _FAKE_DB_RECORDS.clear()

    @pytest.mark.asyncio
    async def test_recover_returns_empty_when_db_record_missing(self):
        action = _make_action()
        _FAKE_DB_RECORDS.clear()
        body = {
            "chat_id": "chat-1",
            "id": "msg-asst-1",
            "messages": [{"id": "msg-asst-1", "role": "assistant", "content": ""}],
        }
        msg = body["messages"][0]
        assert await action._recover_message_content(body, msg) == ""

    @pytest.mark.asyncio
    async def test_recover_prefers_existing_nonempty_content(self):
        """If ``content`` is already populated (pre-v0.10 or OWUI backfilled
        it), recovery must return it as-is and not touch ``output``/DB."""
        action = _make_action()
        body = {
            "chat_id": "chat-1",
            "id": "msg-asst-1",
            "messages": [
                {
                    "id": "msg-asst-1",
                    "role": "assistant",
                    "content": "original content",
                    "output": [{"type": "text", "content": "should not be used"}],
                }
            ],
        }
        msg = body["messages"][0]
        recovered = await action._recover_message_content(body, msg)
        assert recovered == "original content"

    @pytest.mark.asyncio
    async def test_recover_returns_empty_when_no_chat_id(self):
        """Without chat_id/message_id the DB lookup can't run — return empty
        rather than crashing."""
        action = _make_action()
        body = {"messages": [{"id": "", "role": "assistant", "content": ""}]}
        msg = body["messages"][0]
        assert await action._recover_message_content(body, msg) == ""


class TestActionUsesOutputRecovery:
    """End-to-end: when the v0.10 payload has empty ``content`` but valid
    ``output``, the action must not crash and every returned message must
    keep its ``id``. (Recovery correctness is covered by the unit tests above;
    these tests focus on the frontend-safety invariant under the full action
    flow, including when downstream steps like user-lookup / LLM call fail in
    the test environment.)
    """

    @pytest.mark.asyncio
    async def test_action_recovers_from_inline_output_no_crash(self):
        action = _make_action()
        long_text = "x" * 200
        body = {
            "model": "test-model",
            "chat_id": "chat-1",
            "id": "msg-asst-1",
            "session_id": "sess-1",
            "messages": [
                {"id": "msg-user-1", "role": "user", "content": "summarize"},
                {
                    "id": "msg-asst-1",
                    "role": "assistant",
                    "content": "",
                    "output": [{"type": "text", "content": long_text}],
                },
            ],
        }
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        msgs = result["messages"]
        assert all("id" in m for m in msgs), "id-less message would crash OWUI v0.10"
        assert len(msgs) == 2  # no append

    @pytest.mark.asyncio
    async def test_action_recovers_from_db_lookup_no_crash(self):
        action = _make_action()
        long_text = "y" * 200
        _FAKE_DB_RECORDS.clear()
        _FAKE_DB_RECORDS["chat-1-msg-asst-1"] = types.SimpleNamespace(
            output=[{"type": "text", "content": long_text}]
        )
        try:
            body = {
                "model": "test-model",
                "chat_id": "chat-1",
                "id": "msg-asst-1",
                "session_id": "sess-1",
                "messages": [
                    {"id": "msg-user-1", "role": "user", "content": "summarize"},
                    {"id": "msg-asst-1", "role": "assistant", "content": ""},
                ],
            }
            result = await action.action(
                body,
                __user__={"id": "u1", "name": "Test", "language": "en-US"},
                __event_emitter__=_noop_emitter,
            )
            msgs = result["messages"]
            assert all("id" in m for m in msgs), "id-less message would crash OWUI v0.10"
            assert len(msgs) == 2  # no append
        finally:
            _FAKE_DB_RECORDS.clear()

    @pytest.mark.asyncio
    async def test_action_empty_content_and_no_output_still_safe(self):
        """When content is empty AND no output can be recovered, the action
        must still not crash the frontend (id invariant holds, error
        notification sent)."""
        action = _make_action()
        _FAKE_DB_RECORDS.clear()
        body = {
            "model": "test-model",
            "chat_id": "chat-1",
            "id": "msg-asst-1",
            "session_id": "sess-1",
            "messages": [
                {"id": "msg-user-1", "role": "user", "content": "summarize"},
                {"id": "msg-asst-1", "role": "assistant", "content": ""},
            ],
        }
        result = await action.action(
            body,
            __user__={"id": "u1", "name": "Test", "language": "en-US"},
            __event_emitter__=_noop_emitter,
        )
        msgs = result["messages"]
        assert all("id" in m for m in msgs)
        assert len(msgs) == 2  # no append
        assert "❌" in msgs[-1]["content"]
