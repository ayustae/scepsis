import json
import tomllib

import pytest

import install

VERIFICATION = {
    "name": "verification",
    "description": 'Checks "done" tasks — against reality.',
    "model": {
        "default": "anthropic",
        "anthropic": "claude-sonnet-5-5",
        "openai": "gpt-6.1-sol",
        "deepseek": "deepseek-v4-pro",
    },
    "tools": ["read", "search", "shell"],
    "requires": ["chreos"],
}
BODY = "# Verification\n\nRun `chreos task show`.\n"


def item(kind, meta, body=BODY):
    return install.Item(kind, meta["name"], meta, body)


def frontmatter(text):
    """Split rendered markdown into (frontmatter lines, body)."""
    assert text.startswith("---\n")
    head, body = text[4:].split("\n---\n\n", 1)
    return head.split("\n"), body


@pytest.mark.parametrize("assistant", install.ASSISTANTS)
def test_skill_has_name_description_and_body(assistant):
    meta = {"name": "task", "description": 'Use for "tasks": a\\b — ok', "requires": ["chreos"]}
    lines, body = frontmatter(install.render_skill(assistant, item("skills", meta)))
    assert lines == ["name: task", f"description: {json.dumps(meta['description'], ensure_ascii=False)}"]
    assert body == BODY


def test_skill_not_user_invocable_only_maps_for_claude():
    meta = {"name": "task", "description": "d", "user_invocable": False}
    lines, _ = frontmatter(install.render_skill("claude", item("skills", meta)))
    assert "user-invocable: false" in lines
    for other in ("codex", "opencode"):
        lines, _ = frontmatter(install.render_skill(other, item("skills", meta)))
        assert not any("invocable" in line for line in lines)


def test_claude_agent():
    text = install.render_agent("claude", item("agents", VERIFICATION))
    lines, body = frontmatter(text)
    assert lines == [
        "name: verification",
        'description: "Checks \\"done\\" tasks — against reality."',
        "model: claude-sonnet-5-5",
        "tools: Read, Grep, Glob, Bash",
    ]
    assert body == BODY


def test_claude_agent_without_model_or_tools():
    meta = {"name": "v", "description": "d"}
    lines, _ = frontmatter(install.render_agent("claude", item("agents", meta)))
    assert lines == ["name: v", 'description: "d"']


def test_opencode_agent():
    lines, body = frontmatter(install.render_agent("opencode", item("agents", VERIFICATION)))
    assert lines == [
        'description: "Checks \\"done\\" tasks — against reality."',
        "mode: subagent",
        "model: anthropic/claude-sonnet-5-5",
        "permission:",
        "  edit: deny",
        "  webfetch: deny",
        "  websearch: deny",
    ]
    assert body == BODY


def test_opencode_agent_model_needs_default_provider_entry():
    meta = dict(VERIFICATION, model={"default": "openai", "anthropic": "claude-sonnet-5-5"})
    lines, _ = frontmatter(install.render_agent("opencode", item("agents", meta)))
    assert not any(line.startswith("model:") for line in lines)


def test_opencode_agent_without_tools_has_no_permission_block():
    meta = {"name": "v", "description": "d"}
    lines, _ = frontmatter(install.render_agent("opencode", item("agents", meta)))
    assert lines == ['description: "d"', "mode: subagent"]


def test_codex_agent_is_valid_toml():
    data = tomllib.loads(install.render_agent("codex", item("agents", VERIFICATION)))
    assert data == {
        "name": "verification",
        "description": VERIFICATION["description"],
        "model": "gpt-6.1-sol",
        "sandbox_mode": "read-only",
        "developer_instructions": BODY,
    }


def test_codex_agent_with_edit_can_write_the_workspace():
    meta = dict(VERIFICATION, tools=["read", "edit"])
    data = tomllib.loads(install.render_agent("codex", item("agents", meta)))
    assert data["sandbox_mode"] == "workspace-write"


def test_codex_agent_without_model_or_tools():
    meta = {"name": "v", "description": "d"}
    data = tomllib.loads(install.render_agent("codex", item("agents", meta)))
    assert data == {"name": "v", "description": "d", "developer_instructions": BODY}


@pytest.mark.parametrize(
    "body",
    [
        "Quotes ''' inside\n",
        'Triple """ and \\ backslash\n',
        "Ends with a quote'",
        "Control \x01 char\n",
        "Tab\tand\r\nCRLF\n",
    ],
)
def test_codex_instructions_survive_any_body(body):
    data = tomllib.loads(install.render_agent("codex", item("agents", VERIFICATION, body)))
    assert data["developer_instructions"] == body


def test_codex_instructions_use_readable_literal_string_when_possible():
    text = install.render_agent("codex", item("agents", VERIFICATION))
    assert "developer_instructions = '''\n# Verification" in text


def test_agent_filenames():
    assert install.agent_filename("claude", "v") == "v.md"
    assert install.agent_filename("opencode", "v") == "v.md"
    assert install.agent_filename("codex", "v") == "v.toml"
