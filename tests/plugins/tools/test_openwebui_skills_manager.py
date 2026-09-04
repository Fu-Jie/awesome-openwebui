import asyncio
import importlib.util
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "tools"
    / "openwebui-skills-manager"
    / "openwebui_skills_manager.py"
)
SPEC = importlib.util.spec_from_file_location("openwebui_skills_manager", MODULE_PATH)
openwebui_skills_manager = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = openwebui_skills_manager
SPEC.loader.exec_module(openwebui_skills_manager)


def test_user_skills_supports_legacy_user_scoped_api(monkeypatch):
    calls = []

    class LegacySkills:
        async def get_skills_by_user_id(self, user_id, access):
            calls.append((user_id, access))
            return ["legacy-skill"]

    monkeypatch.setattr(openwebui_skills_manager, "Skills", LegacySkills())

    result = asyncio.run(openwebui_skills_manager._user_skills("user-1", "read"))

    assert result == ["legacy-skill"]
    assert calls == [("user-1", "read")]


def test_user_skills_supports_get_skills_user_filter(monkeypatch):
    calls = []

    class CurrentSkills:
        async def get_skills(self, *, user_id=None):
            calls.append(user_id)
            return ["current-skill"]

    monkeypatch.setattr(openwebui_skills_manager, "Skills", CurrentSkills())

    result = asyncio.run(openwebui_skills_manager._user_skills("user-2", "read"))

    assert result == ["current-skill"]
    assert calls == ["user-2"]


def test_user_skills_does_not_use_unscoped_current_api(monkeypatch):
    class CurrentSkills:
        async def get_skills(self, *, user_id=None):
            assert user_id is not None
            return []

    monkeypatch.setattr(openwebui_skills_manager, "Skills", CurrentSkills())

    with_error = None
    try:
        asyncio.run(openwebui_skills_manager._user_skills("user-3", "write"))
    except RuntimeError as exc:
        with_error = exc

    assert str(with_error) == "unsupported_skills_access: write"


def test_parse_skill_md_meta_supports_folded_multiline_description():
    content = (
        "---\r\n"
        "name: persona-selector\r\n"
        "description: >\r\n"
        "  Two-step persona picker. Step 1: numbered category list.\r\n"
        "  Step 2: numbered persona list. 160 personas + Custom.\r\n"
        "---\r\n\r\n"
        "# Persona Selector\r\n\r\n"
        "Body content.\r\n"
    )

    name, description, body = openwebui_skills_manager._parse_skill_md_meta(
        content, "fallback-skill"
    )

    assert name == "persona-selector"
    assert description == (
        "Two-step persona picker. Step 1: numbered category list. "
        "Step 2: numbered persona list. 160 personas + Custom."
    )
    assert body == "# Persona Selector\n\nBody content."


def test_parse_skill_md_meta_supports_literal_multiline_description_and_title_fallback():
    content = (
        "---\n"
        'title: "Data Storyteller"\n'
        "description: |\n"
        "  First line.\n"
        "  Second line.\n"
        "\n"
        "  Third paragraph.\n"
        "---\n\n"
        "Explain how to turn analysis into a narrative.\n"
    )

    name, description, body = openwebui_skills_manager._parse_skill_md_meta(
        content, "fallback-skill"
    )

    assert name == "Data Storyteller"
    assert description == "First line.\nSecond line.\n\nThird paragraph."
    assert body == "Explain how to turn analysis into a narrative."
