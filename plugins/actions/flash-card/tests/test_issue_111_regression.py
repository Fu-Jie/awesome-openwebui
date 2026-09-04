"""Regression tests for issue #111.

OpenWebUI 0.11+ only emits Action-generated HTML as a Rich UI embed when the
Action returns an inline ``HTMLResponse``. Returning a mutated message body
silently completes the Action without rendering the generated card.
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _FakeHTMLResponse:
    def __init__(self, content, headers=None, status_code=200):
        self.body = content.encode("utf-8")
        self.headers = {"content-type": "text/html; charset=utf-8", **(headers or {})}
        self.status_code = status_code


def _install_import_stubs(monkeypatch):
    fastapi = types.ModuleType("fastapi")
    fastapi_responses = types.ModuleType("fastapi.responses")
    fastapi_responses.HTMLResponse = _FakeHTMLResponse
    fastapi.responses = fastapi_responses

    open_webui = types.ModuleType("open_webui")
    open_webui_utils = types.ModuleType("open_webui.utils")
    open_webui_chat = types.ModuleType("open_webui.utils.chat")
    open_webui_users = types.ModuleType("open_webui.models.users")
    open_webui_models = types.ModuleType("open_webui.models")
    open_webui_chat.generate_chat_completion = None
    open_webui_users.Users = types.SimpleNamespace(get_user_by_id=None)
    open_webui.utils = open_webui_utils
    open_webui.models = open_webui_models
    open_webui_utils.chat = open_webui_chat
    open_webui_models.users = open_webui_users

    for name, module in {
        "fastapi": fastapi,
        "fastapi.responses": fastapi_responses,
        "open_webui": open_webui,
        "open_webui.utils": open_webui_utils,
        "open_webui.utils.chat": open_webui_chat,
        "open_webui.models": open_webui_models,
        "open_webui.models.users": open_webui_users,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_action(filename, module_name):
    path = REPO_ROOT / "plugins" / "actions" / "flash-card" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("filename", "module_name"),
    [
        ("flash_card.py", "flash_card_issue_111_en"),
        ("flash_card_cn.py", "flash_card_issue_111_cn"),
    ],
)
def test_action_returns_inline_html_response_for_openwebui_011(
    filename, module_name, monkeypatch
):
    _install_import_stubs(monkeypatch)
    module = _load_action(filename, module_name)

    async def fake_get_user_by_id(user_id):
        return {"id": user_id, "email": "test@example.com"}

    async def fake_generate_chat_completion(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"title":"Test Card","summary":"A test summary.","key_points":["Point one"],"tags":["test"],"category":"Fact"}'
                    }
                }
            ]
        }

    monkeypatch.setattr(
        module.Users,
        "get_user_by_id",
        fake_get_user_by_id,
    )
    monkeypatch.setattr(module, "generate_chat_completion", fake_generate_chat_completion)

    async def noop_emitter(event):
        return None

    original_content = "A sufficiently long message for generating a flash card. " * 3
    body = {
        "model": "test-model",
        "messages": [{"role": "assistant", "content": original_content}],
    }

    result = asyncio.run(
        module.Action().action(
            body,
            __user__={"id": "user-1", "language": "en-US"},
            __event_emitter__=noop_emitter,
        )
    )

    assert isinstance(result, _FakeHTMLResponse)
    assert result.status_code == 200
    assert result.headers["Content-Disposition"] == "inline"
    rendered = result.body.decode("utf-8")
    assert "<!-- OPENWEBUI_PLUGIN_OUTPUT -->" in rendered
    assert "Test Card" in rendered
    # The current Action pipeline consumes the response as an embed; it does
    # not depend on mutating the original message with a fenced HTML block.
    assert body["messages"][-1]["content"] == original_content
