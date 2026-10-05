import json

import pytest

from conftest import fake_command, fake_uv, tree

import install


@pytest.fixture
def full_repo(repo):
    repo.skill("task", requires=["chreos"])
    repo.skill("context", requires=["idion"])
    repo.agent(
        "verification",
        model={"default": "anthropic", "anthropic": "claude-sonnet-5-5", "openai": "gpt-6.1-sol"},
        tools=["read", "search", "shell"],
        requires=["chreos"],
    )
    repo.tool("chreos")
    repo.tool("idion")
    return repo


def run(repo, *args):
    return install.main(list(args), repo=repo.root)


def test_skills_and_agents_for_every_assistant(home, full_repo, capsys):
    code = run(full_repo, "-a", "claude,codex,opencode", "-o", "skills,agents")

    assert code == 0
    assert sorted(tree(home)) == [
        ".agents/skills/context/SKILL.md",
        ".agents/skills/task/SKILL.md",
        ".claude/agents/verification.md",
        ".claude/skills/context/SKILL.md",
        ".claude/skills/task/SKILL.md",
        ".codex/agents/verification.toml",
        ".config/opencode/agents/verification.md",
        ".scepsis/installed.json",
    ]
    out = capsys.readouterr().out
    # OpenCode already reads ~/.claude/skills and ~/.agents/skills.
    assert "skip (shared)" in out and ".config/opencode/skills/task" in out


def test_opencode_alone_gets_its_own_skills(home, full_repo):
    assert run(full_repo, "-a", "opencode", "-o", "skills") == 0
    assert sorted(tree(home)) == [
        ".config/opencode/skills/context/SKILL.md",
        ".config/opencode/skills/task/SKILL.md",
        ".scepsis/installed.json",
    ]


def test_opencode_skips_skill_already_in_a_shared_dir(home, full_repo):
    (home / ".claude/skills/task").mkdir(parents=True)
    run(full_repo, "-a", "opencode", "-o", "skills")
    assert (home / ".config/opencode/skills/context/SKILL.md").exists()
    assert not (home / ".config/opencode/skills/task").exists()


def test_default_assistants_are_the_detected_ones(home, full_repo):
    (home / ".claude").mkdir()
    run(full_repo, "-o", "skills")
    assert sorted(tree(home)) == [
        ".claude/skills/context/SKILL.md",
        ".claude/skills/task/SKILL.md",
        ".scepsis/installed.json",
    ]


def test_no_assistant_detected_explains_how_to_target_one(home, full_repo, capsys):
    assert run(full_repo, "-o", "skills,agents") == 0
    assert "no AI assistant detected" in capsys.readouterr().err
    assert sorted(tree(home)) == []


def test_name_filters(home, full_repo):
    run(full_repo, "-a", "claude", "-s", "task", "-g", "verification", "-o", "skills,agents")
    assert sorted(tree(home / ".claude")) == ["agents/verification.md", "skills/task/SKILL.md"]


def test_repeated_flags_accumulate(home, full_repo):
    run(full_repo, "-a", "claude", "-a", "codex", "-o", "skills")
    assert (home / ".claude/skills/task/SKILL.md").exists()
    assert (home / ".agents/skills/task/SKILL.md").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["-a", "cursor"],
        ["-o", "templates"],
        ["-s", "nope"],
        ["-g", "nope"],
        ["-t", "nope"],
        ["-c", "claude"],
        ["-c", "cursor=/tmp"],
        ["-S", "galaxy"],
    ],
)
def test_usage_errors(home, full_repo, args):
    with pytest.raises(SystemExit) as exc:
        run(full_repo, *args)
    assert exc.value.code == 2


def test_never_touches_existing_user_files(home, full_repo, capsys):
    mine = home / ".claude/skills/task/SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("my own task skill")

    assert run(full_repo, "-a", "claude", "-o", "skills") == 0

    assert mine.read_text() == "my own task skill"
    assert "skip (exists)" in capsys.readouterr().out


def test_rerun_is_idempotent_then_updates_own_files(home, full_repo, capsys):
    run(full_repo, "-a", "claude", "-o", "skills")
    capsys.readouterr()

    run(full_repo, "-a", "claude", "-o", "skills")
    assert "unchanged" in capsys.readouterr().out

    (full_repo.root / "skills/task/SKILL.md").write_text("# Task v2\n")
    run(full_repo, "-a", "claude", "-o", "skills")
    assert "update" in capsys.readouterr().out
    assert (home / ".claude/skills/task/SKILL.md").read_text().endswith("# Task v2\n")


def test_user_edits_to_installed_files_are_kept(home, full_repo, capsys):
    run(full_repo, "-a", "claude", "-o", "skills")
    installed = home / ".claude/skills/task/SKILL.md"
    installed.write_text("edited")
    (full_repo.root / "skills/task/SKILL.md").write_text("# Task v2\n")

    run(full_repo, "-a", "claude", "-o", "skills")
    assert installed.read_text() == "edited"
    assert "skip (modified)" in capsys.readouterr().out

    run(full_repo, "-a", "claude", "-o", "skills", "-f")
    assert installed.read_text().endswith("# Task v2\n")


def test_dry_run_writes_nothing(home, full_repo, capsys):
    log = home / "uv.log"
    fake_uv(home.bin, log)
    assert run(full_repo, "-a", "claude,codex,opencode", "-n") == 0
    assert sorted(tree(home)) == []
    out = capsys.readouterr().out
    assert "install" in out and "chreos" in out


def test_project_scope(home, full_repo, tmp_path):
    proj = tmp_path / "proj"
    run(full_repo, "-a", "claude,opencode", "-o", "skills,agents", "-p", str(proj))
    assert sorted(tree(proj)) == [
        ".claude/agents/verification.md",
        ".claude/skills/context/SKILL.md",
        ".claude/skills/task/SKILL.md",
        ".opencode/agents/verification.md",
    ]
    # The manifest stays in the user's home.
    assert (home / ".scepsis/installed.json").exists()


def test_project_scope_defaults_to_current_dir(home, full_repo, tmp_path, monkeypatch):
    proj = tmp_path / "cwd"
    proj.mkdir()
    monkeypatch.chdir(proj)
    run(full_repo, "-a", "claude", "-o", "skills", "-S", "project")
    assert (proj / ".claude/skills/task/SKILL.md").exists()


def test_config_dir_override(home, full_repo, tmp_path):
    run(full_repo, "-a", "claude", "-o", "agents", "-c", f"claude={tmp_path / 'alt'}")
    assert (tmp_path / "alt/agents/verification.md").exists()
    assert not (home / ".claude").exists()


def test_tools_are_installed_with_uv(home, full_repo):
    log = home / "uv.log"
    fake_uv(home.bin, log)
    assert run(full_repo, "-o", "tools") == 0
    assert log.read_text().splitlines() == [
        f"tool install {full_repo.root / 'tools/chreos'}",
        f"tool install {full_repo.root / 'tools/idion'}",
    ]


def test_tools_on_path_are_skipped_unless_forced(home, full_repo, capsys):
    log = home / "uv.log"
    fake_uv(home.bin, log)
    fake_command(home.bin, "chreos")

    run(full_repo, "-o", "tools", "-t", "chreos")
    assert not log.exists()
    assert "skip (on PATH)" in capsys.readouterr().out

    run(full_repo, "-o", "tools", "-t", "chreos", "-f")
    assert log.read_text().splitlines() == [
        f"tool install --force --reinstall {full_repo.root / 'tools/chreos'}"
    ]


def test_tools_without_uv_fail_but_the_rest_installs(home, full_repo, capsys):
    code = run(full_repo, "-a", "claude", "-o", "tools,skills")
    assert code == 1
    assert "uv" in capsys.readouterr().err
    assert (home / ".claude/skills/task/SKILL.md").exists()


def test_failing_uv_is_an_error(home, full_repo, capsys):
    fake_command(home.bin, "uv", "echo boom >&2; exit 3")
    assert run(full_repo, "-o", "tools", "-t", "idion") == 1
    assert "idion" in capsys.readouterr().err


def test_missing_required_commands_are_warned(home, full_repo, capsys):
    run(full_repo, "-a", "claude", "-o", "skills", "-s", "task")
    assert "requires 'chreos'" in capsys.readouterr().err


def test_required_commands_installed_in_the_same_run_are_fine(home, full_repo, capsys):
    fake_uv(home.bin, home / "uv.log")
    run(full_repo, "-a", "claude", "-o", "tools,skills")
    assert "requires" not in capsys.readouterr().err


def test_invalid_definition_is_an_error_but_others_install(home, full_repo, capsys):
    (full_repo.root / "skills/task/frontmatter.json").write_text("{}")
    assert run(full_repo, "-a", "claude", "-o", "skills") == 1
    assert "task" in capsys.readouterr().err
    assert (home / ".claude/skills/context/SKILL.md").exists()


def test_list(home, full_repo, capsys):
    (home / ".claude").mkdir()
    assert run(full_repo, "-l") == 0
    out = capsys.readouterr().out
    for word in ("claude", "detected", "codex", "chreos", "idion", "task", "context", "verification"):
        assert word in out
    assert sorted(tree(home)) == []


def test_manifest_records_installed_files(home, full_repo):
    run(full_repo, "-a", "claude", "-o", "skills", "-s", "task")
    data = json.loads((home / ".scepsis/installed.json").read_text())
    assert list(data["files"]) == [str(home / ".claude/skills/task/SKILL.md")]
