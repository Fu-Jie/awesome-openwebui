"""Regression test for issue #101: Smart Mind Map crashes OWUI v0.10+ frontend.

Issue: On OpenWebUI v0.10+, clicking the Smart Mind Map action produces
``Cannot read properties of undefined (reading 'content')`` at
``Chat.svelte`` (inside ``chatActionHandler``).

Root cause: The action's early-return paths (no messages / no extractable
content / text too short) appended a *new* message dict without an ``id``
field to ``body["messages"]``:

    body["messages"].append({"role": "assistant", "content": "❌ ..."})

The OWUI v0.10+ frontend iterates the returned ``messages`` and does
``history.messages[message.id].content`` for each entry. When ``message.id``
is ``undefined`` (the appended message has no id), ``history.messages[undefined]``
is ``undefined`` and accessing ``.content`` throws.

Fix: Update the *existing* last message's content (it already carries a valid
``id``) instead of appending a new id-less message. The frontend preserves the
original content as ``originalContent`` before applying the update.
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
_MOCK_MODULES = {
    "open_webui": types.ModuleType("open_webui"),
    "open_webui.utils": types.ModuleType("open_webui.utils"),
    "open_webui.utils.chat": types.ModuleType("open_webui.utils.chat"),
    "open_webui.models": types.ModuleType("open_webui.models"),
    "open_webui.models.users": types.ModuleType("open_webui.models.users"),
    "open_webui.env": types.ModuleType("open_webui.env"),
}
_MOCK_MODULES["open_webui.utils.chat"].generate_chat_completion = lambda *a, **kw: None
_MOCK_MODULES["open_webui.models.users"].Users = types.SimpleNamespace(
    get_user_by_id=lambda *a, **kw: None
)
_MOCK_MODULES["open_webui.env"].VERSION = "0.0.0"
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
